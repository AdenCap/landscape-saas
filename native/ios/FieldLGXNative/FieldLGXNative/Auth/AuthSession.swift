import Foundation
import Observation

@Observable
final class AuthSession {
    private(set) var currentUser: MobileUser?
    private(set) var business: MobileBusiness?
    private(set) var accessToken: String?
    var isLoading = false
    var errorMessage: String?

    private let keychain = KeychainStore(service: "com.fieldlgx.native.auth")
    private let baseURL = URL(string: "http://127.0.0.1:8004")!

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

    func signInWithApple(identityToken: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            let response = try await APIClient(baseURL: baseURL).appleLogin(identityToken: identityToken)
            await completeSignIn(response)
        } catch {
            errorMessage = "Apple Sign-In is wired in the app, but token verification still needs the Apple developer keys on the server."
        }
    }

    func showGoogleConfigurationMessage() {
        errorMessage = "Google Sign-In needs the iOS Google client ID and SDK package configured before App Store release. Email/username login is ready locally."
    }

    func loadBootstrap() async {
        guard let accessToken else { return }
        do {
            let response = try await APIClient(baseURL: baseURL, accessToken: accessToken).bootstrap()
            currentUser = response.user
            business = response.business
        } catch {
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
        keychain.delete(account: "refresh_token")
        accessToken = nil
        currentUser = nil
        business = nil
        errorMessage = nil
    }

    private func completeSignIn(_ response: LoginResponse) async {
        do {
            try keychain.save(response.refreshToken, account: "refresh_token")
            accessToken = response.accessToken
            currentUser = response.user
            await loadBootstrap()
        } catch {
            errorMessage = "Signed in, but this device could not save the session."
        }
    }
}
