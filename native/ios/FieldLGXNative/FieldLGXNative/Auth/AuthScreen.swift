import AuthenticationServices
import SwiftUI

struct AuthScreen: View {
    @Bindable var session: AuthSession
    @State private var identifier = ""
    @State private var password = ""

    var body: some View {
        ZStack {
            AuthBackdrop()

            ScrollView {
                VStack(alignment: .leading, spacing: 26) {
                    Spacer(minLength: 16)

                    brandHeader

                    VStack(alignment: .leading, spacing: 18) {
                        Text("SIGN IN")
                            .font(.system(size: 12, weight: .black))
                            .tracking(2.5)
                            .foregroundStyle(FieldLGXTheme.tertiaryText)

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
                                Image(systemName: "arrow.right.circle.fill")
                                Text(session.isLoading ? "Signing in" : "Sign in")
                                Spacer()
                                Text("FIELDLGX")
                                    .font(.system(size: 11, weight: .black))
                                    .tracking(1.8)
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

                        VStack(spacing: 10) {
                            SignInWithAppleButton(.continue) { request in
                                request.requestedScopes = [.fullName, .email]
                            } onCompletion: { result in
                                handleAppleResult(result)
                            }
                            .signInWithAppleButtonStyle(.white)
                            .frame(height: 52)
                            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                            .accessibilityIdentifier("auth.apple")

                            Button {
                                session.showGoogleConfigurationMessage()
                            } label: {
                                HStack(spacing: 12) {
                                    Text("G")
                                        .font(.system(size: 18, weight: .black))
                                        .foregroundStyle(.black)
                                        .frame(width: 26, height: 26)
                                        .background(.white)
                                        .clipShape(Circle())
                                    Text("Continue with Google")
                                    Spacer()
                                }
                                .font(.system(size: 16, weight: .bold))
                                .foregroundStyle(FieldLGXTheme.text)
                                .padding(.horizontal, 16)
                                .frame(height: 52)
                                .background(FieldLGXTheme.elevatedBackground)
                                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                                        .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
                                )
                            }
                            .accessibilityIdentifier("auth.google")
                        }

                        if let errorMessage = session.errorMessage {
                            Text(errorMessage)
                                .font(.system(size: 13, weight: .semibold))
                                .foregroundStyle(.red.opacity(0.92))
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .padding(18)
                    .background(FieldLGXTheme.panel.opacity(0.96))
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
                    )

                    trustRail

                    Spacer(minLength: 20)
                }
                .padding(24)
            }
        }
    }

    private var brandHeader: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 12) {
                Text("FL")
                    .font(.system(size: 22, weight: .black, design: .rounded))
                    .foregroundStyle(FieldLGXTheme.lime)
                    .frame(width: 48, height: 48)
                    .background(FieldLGXTheme.elevatedBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(FieldLGXTheme.lime.opacity(0.55), lineWidth: 1)
                    )

                VStack(alignment: .leading, spacing: 4) {
                    Text("FIELDLGX")
                        .font(.system(size: 28, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                    Text("LANDSCAPE OPERATIONS")
                        .font(.system(size: 10, weight: .black))
                        .tracking(2.4)
                        .foregroundStyle(FieldLGXTheme.lime)
                }
            }

            Text("Run the day. Own the season.")
                .font(.system(size: 42, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(3)
                .minimumScaleFactor(0.76)

            Text("Schedule crews, capture field notes, track time, and keep every job moving from one premium mobile command center.")
                .font(.system(size: 16, weight: .semibold))
                .lineSpacing(4)
                .foregroundStyle(FieldLGXTheme.secondaryText)
        }
    }

    private var trustRail: some View {
        HStack(spacing: 10) {
            AuthMetric(label: "Offline", value: "Ready")
            AuthMetric(label: "Time", value: "GPS")
            AuthMetric(label: "Photos", value: "Proof")
        }
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
        .background(FieldLGXTheme.elevatedBackground)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }
}

private struct AuthBackdrop: View {
    var body: some View {
        ZStack {
            FieldLGXTheme.background.ignoresSafeArea()

            LinearGradient(
                colors: [
                    FieldLGXTheme.lime.opacity(0.16),
                    Color.clear,
                    Color(red: 0.02, green: 0.03, blue: 0.025).opacity(0.9)
                ],
                startPoint: .topTrailing,
                endPoint: .bottomLeading
            )
            .ignoresSafeArea()

            GridPattern()
                .stroke(Color.white.opacity(0.035), lineWidth: 1)
                .ignoresSafeArea()
        }
    }
}

private struct GridPattern: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let spacing: CGFloat = 42
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

private struct AuthMetric: View {
    let label: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label.uppercased())
                .font(.system(size: 9, weight: .black))
                .tracking(1.6)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            Text(value)
                .font(.system(size: 15, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(FieldLGXTheme.panel.opacity(0.82))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }
}

#Preview {
    AuthScreen(session: AuthSession())
}
