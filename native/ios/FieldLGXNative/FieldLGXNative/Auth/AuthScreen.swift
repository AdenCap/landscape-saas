import SwiftUI

struct AuthScreen: View {
    @Bindable var session: AuthSession
    @State private var selectedRole: AppRole = .owner

    var body: some View {
        ZStack {
            FieldLGXTheme.background.ignoresSafeArea()

            VStack(alignment: .leading, spacing: 28) {
                Spacer(minLength: 16)

                VStack(alignment: .leading, spacing: 10) {
                    Text("FIELDLGX")
                        .font(.system(size: 38, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)

                    Text("Native field operations foundation")
                        .font(.system(size: 17, weight: .medium))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                }

                VStack(alignment: .leading, spacing: 16) {
                    Text("Preview Role")
                        .font(.system(size: 13, weight: .bold))
                        .tracking(2)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)

                    Picker("Preview Role", selection: $selectedRole) {
                        ForEach(AppRole.allCases) { role in
                            Text(role.title).tag(role)
                        }
                    }
                    .pickerStyle(.segmented)

                    Button {
                        session.signInPreview(role: selectedRole)
                    } label: {
                        HStack {
                            Text("Enter \(selectedRole.title) Shell")
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

#Preview {
    AuthScreen(session: AuthSession())
}
