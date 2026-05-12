import AuthenticationServices
import SwiftUI

struct AuthScreen: View {
    @Bindable var session: AuthSession
    @State private var identifier = ""
    @State private var password = ""

    var body: some View {
        GeometryReader { proxy in
            let compact = proxy.size.height < 900
            let titleSize = min(proxy.size.width * (compact ? 0.086 : 0.098), compact ? 35 : 40)

            ZStack {
                heroBackdrop(size: proxy.size, compact: compact)

                VStack(alignment: .leading, spacing: 0) {
                    logo(compact: compact)

                    heroCopy(titleSize: titleSize)
                        .padding(.top, compact ? 42 : 58)

                    Spacer(minLength: compact ? 22 : 30)

                    signInPanel(compact: compact)
                        .padding(.bottom, compact ? 94 : 104)
                }
                .padding(.horizontal, compact ? 16 : 22)
                .padding(.top, proxy.safeAreaInsets.top + (compact ? 8 : 14))
                .padding(.bottom, proxy.safeAreaInsets.bottom + (compact ? 8 : 12))
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            }
        }
        .dynamicTypeSize(.medium ... .xLarge)
    }

    private func heroBackdrop(size: CGSize, compact: Bool) -> some View {
        ZStack {
            FieldLGXScreenBackground()

            Image("MarketingSkid")
                .resizable()
                .scaledToFill()
                .frame(width: size.width, height: size.height)
                .scaleEffect(compact ? 1.02 : 1.08)
                .offset(x: size.width * (compact ? 0.26 : 0.20), y: compact ? -8 : -18)
                .opacity(compact ? 0.58 : 0.68)
                .ignoresSafeArea()

            LinearGradient(
                colors: [
                    Color.black.opacity(0.96),
                    Color.black.opacity(0.72),
                    Color.black.opacity(0.20),
                    Color.black.opacity(0.80)
                ],
                startPoint: .leading,
                endPoint: .trailing
            )
            .ignoresSafeArea()

            LinearGradient(
                colors: [
                    Color.black.opacity(0.40),
                    Color.clear,
                    FieldLGXTheme.background.opacity(0.94)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            GridPattern()
                .stroke(Color.white.opacity(0.035), lineWidth: 1)
                .ignoresSafeArea()
        }
    }

    private func logo(compact: Bool) -> some View {
        HStack(spacing: compact ? 9 : 11) {
            Image("FieldLGXMonogram")
                .resizable()
                .scaledToFit()
                .frame(width: compact ? 30 : 34, height: compact ? 30 : 34)

            Text("FIELDLGX")
                .font(.system(size: compact ? 18 : 20, weight: .black))
                .tracking(1.8)
                .foregroundStyle(FieldLGXTheme.text)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("FIELDLGX")
        .padding(.horizontal, compact ? 12 : 14)
        .padding(.vertical, compact ? 10 : 11)
        .background(Color.black.opacity(0.44))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func heroCopy(titleSize: CGFloat) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Run the day.")
                .font(.system(size: titleSize, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(1)
                .minimumScaleFactor(0.68)

            Text("Own the season.")
                .font(.system(size: titleSize, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.lime)
                .lineLimit(1)
                .minimumScaleFactor(0.68)
        }
        .shadow(color: .black.opacity(0.48), radius: 18, x: 0, y: 10)
    }

    private func signInPanel(compact: Bool) -> some View {
        VStack(alignment: .leading, spacing: compact ? 8 : 11) {
            Text("SIGN IN")
                .font(.system(size: 11, weight: .black))
                .tracking(2.3)
                .foregroundStyle(FieldLGXTheme.lime)

            VStack(spacing: compact ? 8 : 10) {
                TextField("Email or username", text: $identifier)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled(true)
                    .keyboardType(.emailAddress)
                    .textContentType(.username)
                    .fieldLGXInput(icon: "person.crop.circle", compact: compact)
                    .accessibilityLabel("Email or username")
                    .accessibilityIdentifier("auth.email")

                SecureField("Password", text: $password)
                    .textContentType(.password)
                    .fieldLGXInput(icon: "lock", compact: compact)
                    .accessibilityLabel("Password")
                    .accessibilityIdentifier("auth.password")
            }

            Button {
                Task {
                    await session.signIn(email: identifier, password: password)
                }
            } label: {
                HStack(spacing: 10) {
                    Text(session.isLoading ? "Signing in" : "Sign in")
                    Spacer()
                    Image(systemName: "arrow.right")
                }
                .font(.system(size: 17, weight: .black))
                .foregroundStyle(Color.black)
                .padding(.horizontal, compact ? 14 : 18)
                .frame(height: compact ? 46 : 54)
                .background(FieldLGXTheme.lime)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                .shadow(color: FieldLGXTheme.lime.opacity(0.22), radius: 18, x: 0, y: 12)
            }
            .disabled(session.isLoading || identifier.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || password.isEmpty)
            .accessibilityLabel("Sign in")
            .accessibilityIdentifier("auth.signIn")

            DividerLabel()

            SignInWithAppleButton(.signIn) { request in
                request.requestedScopes = [.fullName, .email]
            } onCompletion: { result in
                handleAppleResult(result)
            }
            .signInWithAppleButtonStyle(.white)
            .frame(height: compact ? 42 : 48)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            .accessibilityIdentifier("auth.apple")

            if let errorMessage = session.errorMessage {
                Text(errorMessage)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(.red.opacity(0.94))
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(compact ? 12 : 16)
        .background(.ultraThinMaterial.opacity(0.42), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .background(FieldLGXTheme.panel.opacity(0.94), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func handleAppleResult(_ result: Result<ASAuthorization, Error>) {
        switch result {
        case let .success(authorization):
            guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
                  let tokenData = credential.identityToken,
                  let token = String(data: tokenData, encoding: .utf8)
            else {
                session.errorMessage = "Apple did not return a usable sign-in token."
                return
            }
            Task {
                await session.signInWithApple(identityToken: token)
            }
        case let .failure(error):
            session.errorMessage = "Apple Sign-In failed: \(error.localizedDescription)"
        }
    }
}

private extension View {
    func fieldLGXInput(icon: String, compact: Bool) -> some View {
        HStack(spacing: compact ? 10 : 12) {
            Image(systemName: icon)
                .font(.system(size: compact ? 14 : 17, weight: .bold))
                .foregroundStyle(FieldLGXTheme.tertiaryText)
                .frame(width: compact ? 20 : 22)
            self
                .font(.system(size: compact ? 14 : 17, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.text)
        }
        .padding(compact ? 10 : 16)
        .background(Color.black.opacity(0.48))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }
}

private struct GridPattern: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let spacing: CGFloat = 58
        var x: CGFloat = 0
        while x <= rect.maxX {
            path.move(to: CGPoint(x: x, y: rect.minY))
            path.addLine(to: CGPoint(x: x, y: rect.maxY))
            x += spacing
        }
        var y: CGFloat = 0
        while y <= rect.maxY {
            path.move(to: CGPoint(x: rect.minX, y: y))
            path.addLine(to: CGPoint(x: rect.maxX, y: y))
            y += spacing
        }
        return path
    }
}

private struct DividerLabel: View {
    var body: some View {
        HStack(spacing: 12) {
            Rectangle()
                .fill(FieldLGXTheme.panelStroke)
                .frame(height: 1)
            Text("OR")
                .font(.system(size: 11, weight: .black))
                .tracking(1.8)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            Rectangle()
                .fill(FieldLGXTheme.panelStroke)
                .frame(height: 1)
        }
    }
}

#Preview {
    AuthScreen(session: AuthSession())
}
