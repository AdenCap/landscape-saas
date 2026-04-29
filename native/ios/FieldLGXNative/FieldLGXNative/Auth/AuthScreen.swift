import AuthenticationServices
import SwiftUI

struct AuthScreen: View {
    @Bindable var session: AuthSession
    @State private var identifier = ""
    @State private var password = ""

    var body: some View {
        ZStack {
            heroBackdrop

            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    logo
                        .padding(.top, 22)

                    Spacer(minLength: 18)

                    heroCopy

                    signInPanel

                    Spacer(minLength: 18)
                }
                .padding(.horizontal, 22)
                .padding(.bottom, 24)
                .frame(maxWidth: .infinity, alignment: .leading)
                .frame(minHeight: UIScreen.main.bounds.height)
            }
            .scrollIndicators(.hidden)
        }
    }

    private var heroBackdrop: some View {
        ZStack {
            FieldLGXTheme.background.ignoresSafeArea()

            Image("MarketingSkid")
                .resizable()
                .scaledToFill()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .scaleEffect(1.08)
                .offset(x: 78, y: -18)
                .opacity(0.72)
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

    private var logo: some View {
        HStack(spacing: 12) {
            Image("FieldLGXMonogram")
                .resizable()
                .scaledToFit()
                .frame(width: 30, height: 30)

            Image("FieldLGXWordmark")
                .resizable()
                .scaledToFit()
                .frame(width: 156, height: 38)
                .accessibilityLabel("FIELDLGX")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color.black.opacity(0.44))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private var heroCopy: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Run the day.")
                .font(.system(size: 52, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(1)
                .minimumScaleFactor(0.72)

            Text("Own the season.")
                .font(.system(size: 52, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.lime)
                .lineLimit(1)
                .minimumScaleFactor(0.72)
        }
        .shadow(color: .black.opacity(0.48), radius: 18, x: 0, y: 10)
    }

    private var signInPanel: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("SIGN IN")
                        .font(.system(size: 11, weight: .black))
                        .tracking(2.3)
                        .foregroundStyle(FieldLGXTheme.lime)

                    Text("Enter your workspace")
                        .font(.system(size: 20, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                }
                Spacer()
            }

            VStack(spacing: 12) {
                TextField("Email or username", text: $identifier)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled(true)
                    .keyboardType(.emailAddress)
                    .textContentType(.username)
                    .fieldLGXInput(icon: "person.crop.circle")
                    .accessibilityLabel("Email or username")
                    .accessibilityIdentifier("auth.email")

                SecureField("Password", text: $password)
                    .textContentType(.password)
                    .fieldLGXInput(icon: "lock")
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
                .padding(.horizontal, 18)
                .frame(height: 56)
                .background(FieldLGXTheme.lime)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                .shadow(color: FieldLGXTheme.lime.opacity(0.22), radius: 18, x: 0, y: 12)
            }
            .disabled(session.isLoading || identifier.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || password.isEmpty)
            .accessibilityLabel("Sign in")
            .accessibilityIdentifier("auth.signIn")

            DividerLabel()

            HStack(spacing: 10) {
                SignInWithAppleButton(.signIn) { request in
                    request.requestedScopes = [.fullName, .email]
                } onCompletion: { result in
                    handleAppleResult(result)
                }
                .signInWithAppleButtonStyle(.white)
                .frame(height: 50)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                .accessibilityIdentifier("auth.apple")

                Button {
                    session.showGoogleConfigurationMessage()
                } label: {
                    Text("G")
                        .font(.system(size: 20, weight: .black))
                        .foregroundStyle(.black)
                        .frame(width: 56, height: 50)
                        .background(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                }
                .accessibilityLabel("Sign in with Google")
                .accessibilityIdentifier("auth.google")
            }

            if let errorMessage = session.errorMessage {
                Text(errorMessage)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(.red.opacity(0.94))
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(18)
        .background(.ultraThinMaterial.opacity(0.58), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .background(FieldLGXTheme.panel.opacity(0.84), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
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
    func fieldLGXInput(icon: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 17, weight: .bold))
                .foregroundStyle(FieldLGXTheme.tertiaryText)
                .frame(width: 22)
            self
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.text)
        }
        .padding(16)
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
