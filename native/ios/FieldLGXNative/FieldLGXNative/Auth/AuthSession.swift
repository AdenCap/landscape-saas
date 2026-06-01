import Foundation
import LocalAuthentication
import Observation

@Observable
final class AuthSession {
    private(set) var currentUser: MobileUser?
    private(set) var business: MobileBusiness?
    private(set) var accessToken: String?
    private var accessTokenExpiresAt: Date?
    private var refreshTask: Task<Void, Never>?
    var isLoading = false
    var isRestoring = false
    var isBiometricLocked = false
    private(set) var hasSavedSession = false
    var errorMessage: String?

    private let keychain = KeychainStore(service: "com.fieldlgx.app.auth")
    private let baseURL = FieldLGXConfig.apiBaseURL

    var isAuthenticated: Bool {
        currentUser != nil && accessToken != nil
    }

    init(currentUser: MobileUser? = nil) {
        self.currentUser = currentUser
    }

    func signIn(email: String, password: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            let response = try await APIClient(baseURL: baseURL).login(
                email: email.trimmingCharacters(in: .whitespacesAndNewlines),
                password: password
            )
            await completeSignIn(response)
        } catch {
            errorMessage = "Sign in failed: \(error.localizedDescription)"
        }
    }

    func restoreSessionIfPossible() async {
        guard currentUser == nil, accessToken == nil, !isRestoring else { return }
        isRestoring = true
        defer { isRestoring = false }

        do {
            guard let refreshToken = try keychain.read(account: "refresh_token") else {
                hasSavedSession = false
                return
            }
            hasSavedSession = true
            if canUseDeviceAuthentication {
                isBiometricLocked = true
                return
            }
            let response = try await APIClient(baseURL: baseURL).refresh(refreshToken: refreshToken)
            await completeSignIn(response)
        } catch {
            clearSavedSession(deleteRefreshToken: true)
        }
    }

    func refreshSessionIfNeeded() async {
        guard currentUser != nil, accessToken != "preview-token" else { return }
        guard shouldRefreshAccessToken else { return }
        await refreshAccessToken()
    }

    func signInWithApple(identityToken: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            let response = try await APIClient(baseURL: baseURL).appleLogin(identityToken: identityToken)
            await completeSignIn(response)
        } catch {
            errorMessage = "Apple Sign-In failed: \(error.localizedDescription)"
        }
    }

    func loadBootstrap() async {
        guard let accessToken else { return }
        do {
            let response = try await APIClient(baseURL: baseURL, accessToken: accessToken).bootstrap()
            currentUser = response.user
            business = response.business
        } catch {
            #if DEBUG
            print("FIELDLGX bootstrap load failed: \(error)")
            #endif
            errorMessage = "Signed in, but the workspace could not load."
        }
    }

    func signInPreview(role: AppRole) {
        currentUser = MobileUser(
            id: role == .crew ? 3 : 1,
            email: "\(role.rawValue)@fieldlgx.local",
            username: role.rawValue,
            name: role == .crew ? "Crew Preview" : "\(role.title) Preview",
            role: role,
            businessID: 1
        )
        accessToken = "preview-token"
    }

    func signOut() {
        refreshTask?.cancel()
        refreshTask = nil
        clearSavedSession(deleteRefreshToken: true)
    }

    private func clearSavedSession(deleteRefreshToken: Bool = false) {
        if deleteRefreshToken {
            keychain.delete(account: "refresh_token")
        }
        accessToken = nil
        accessTokenExpiresAt = nil
        currentUser = nil
        business = nil
        isBiometricLocked = false
        hasSavedSession = false
        errorMessage = nil
    }

    func lockForQuickUnlock() {
        guard isAuthenticated, canUseDeviceAuthentication else { return }
        isBiometricLocked = true
    }

    @MainActor
    func unlockWithDeviceAuthentication() async {
        guard isBiometricLocked else { return }
        let context = LAContext()
        context.localizedCancelTitle = "Use password"
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthentication, error: &error) else {
            isBiometricLocked = false
            return
        }

        do {
            let unlocked = try await context.evaluatePolicy(
                .deviceOwnerAuthentication,
                localizedReason: "Unlock FIELDLGX to view your business."
            )
            if unlocked {
                isBiometricLocked = false
                errorMessage = nil
                if currentUser == nil || accessToken == nil {
                    await restoreUnlockedSavedSession()
                } else {
                    await refreshSessionIfNeeded()
                }
            }
        } catch {
            errorMessage = "Could not unlock with Face ID. You can sign out and use your password."
        }
    }

    private func restoreUnlockedSavedSession() async {
        isRestoring = true
        defer { isRestoring = false }

        do {
            guard let refreshToken = try keychain.read(account: "refresh_token") else {
                clearSavedSession()
                return
            }
            let response = try await APIClient(baseURL: baseURL).refresh(refreshToken: refreshToken)
            await completeSignIn(response)
        } catch {
            clearSavedSession(deleteRefreshToken: true)
            errorMessage = "Your saved session expired. Please sign in again."
        }
    }

    private var canUseDeviceAuthentication: Bool {
        let context = LAContext()
        var error: NSError?
        return context.canEvaluatePolicy(.deviceOwnerAuthentication, error: &error)
    }

    private func completeSignIn(_ response: LoginResponse, lockBehindBiometrics: Bool = false) async {
        do {
            if let refreshToken = response.refreshToken {
                try keychain.save(refreshToken, account: "refresh_token")
                hasSavedSession = true
            }
            accessToken = response.accessToken
            accessTokenExpiresAt = Self.expirationDate(from: response.accessToken)
            currentUser = response.user
            scheduleAccessTokenRefresh()
            await loadBootstrap()
            if lockBehindBiometrics && canUseDeviceAuthentication {
                isBiometricLocked = true
            } else {
                isBiometricLocked = false
            }
        } catch {
            errorMessage = "Signed in, but this device could not save the session."
        }
    }

    private var shouldRefreshAccessToken: Bool {
        guard let accessTokenExpiresAt else { return true }
        return accessTokenExpiresAt.timeIntervalSinceNow < 90
    }

    private func refreshAccessToken() async {
        do {
            guard let refreshToken = try keychain.read(account: "refresh_token") else {
                signOut()
                return
            }
            let response = try await APIClient(baseURL: baseURL).refresh(refreshToken: refreshToken)
            await completeSignIn(response)
        } catch {
            signOut()
        }
    }

    private func scheduleAccessTokenRefresh() {
        refreshTask?.cancel()
        guard accessToken != "preview-token" else { return }

        let delay: TimeInterval
        if let accessTokenExpiresAt {
            delay = max(accessTokenExpiresAt.timeIntervalSinceNow - 60, 30)
        } else {
            delay = 8 * 60
        }

        refreshTask = Task { [weak self] in
            do {
                try await Task.sleep(for: .seconds(delay))
            } catch {
                return
            }
            guard !Task.isCancelled else { return }
            await self?.refreshAccessToken()
        }
    }

    private static func expirationDate(from token: String) -> Date? {
        let parts = token.split(separator: ".")
        guard parts.count > 1 else { return nil }
        let body = parts[1]
        var value = String(body)
        value += String(repeating: "=", count: (4 - value.count % 4) % 4)
        guard
            let data = Data(base64Encoded: value.replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")),
            let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let exp = object["exp"] as? TimeInterval
        else {
            return nil
        }
        return Date(timeIntervalSince1970: exp)
    }
}
