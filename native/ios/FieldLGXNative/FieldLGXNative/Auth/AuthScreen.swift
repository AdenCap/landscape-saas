import SwiftUI

struct AuthScreen: View {
    @Bindable var session: AuthSession
    @State private var email = ""
    @State private var password = ""

    var body: some View {
        ZStack {
            FieldLGXTheme.background.ignoresSafeArea()

            VStack(alignment: .leading, spacing: 22) {
                Spacer(minLength: 16)

                VStack(alignment: .leading, spacing: 10) {
                    Text("FIELDLGX")
                        .font(.system(size: 38, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)

                    Text("Run the day. Own the season.")
                        .font(.system(size: 17, weight: .medium))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                }

                VStack(alignment: .leading, spacing: 16) {
                    Text("SIGN IN")
                        .font(.system(size: 13, weight: .bold))
                        .tracking(2)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)

                    TextField("Email", text: $email)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.emailAddress)
                        .textContentType(.username)
                        .fieldLGXInput()

                    SecureField("Password", text: $password)
                        .textContentType(.password)
                        .fieldLGXInput()

                    Button {
                        Task {
                            await session.signIn(email: email, password: password)
                        }
                    } label: {
                        HStack {
                            Text(session.isLoading ? "Signing in..." : "Sign in")
                            Spacer()
                            Image(systemName: "arrow.right")
                        }
                        .font(.system(size: 17, weight: .bold))
                        .foregroundStyle(Color.black)
                        .padding(.horizontal, 18)
                        .frame(height: 54)
                        .background(FieldLGXTheme.lime)
                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                    }
                    .disabled(session.isLoading)

                    if let errorMessage = session.errorMessage {
                        Text(errorMessage)
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(.red)
                    }
                }
                .padding(18)
                .background(FieldLGXTheme.panel)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
                )

                Spacer(minLength: 20)
            }
            .padding(24)
        }
    }
}

private extension View {
    func fieldLGXInput() -> some View {
        self
            .font(.system(size: 17, weight: .semibold))
            .foregroundStyle(FieldLGXTheme.text)
            .padding(16)
            .background(FieldLGXTheme.elevatedBackground)
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
