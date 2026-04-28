import SwiftUI

struct AppShell: View {
    @Bindable var session: AuthSession

    var body: some View {
        if let user = session.currentUser {
            TabView {
                ForEach(AppTab.tabs(for: user.role)) { tab in
                    NavigationStack {
                        PlaceholderScreen(tab: tab, user: user, signOut: session.signOut)
                    }
                    .tabItem {
                        Label(tab.title, systemImage: tab.systemImage)
                    }
                }
            }
            .tint(FieldLGXTheme.lime)
        } else {
            AuthScreen(session: session)
        }
    }
}

private struct PlaceholderScreen: View {
    let tab: AppTab
    let user: MobileUser
    let signOut: () -> Void

    var body: some View {
        ZStack {
            FieldLGXTheme.background.ignoresSafeArea()

            VStack(alignment: .leading, spacing: 20) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(user.businessName.uppercased())
                            .font(.system(size: 12, weight: .bold))
                            .tracking(2.5)
                            .foregroundStyle(FieldLGXTheme.lime)

                        Text(tab.title)
                            .font(.system(size: 42, weight: .black, design: .rounded))
                            .foregroundStyle(FieldLGXTheme.text)
                    }

                    Spacer()

                    Button(action: signOut) {
                        Image(systemName: "rectangle.portrait.and.arrow.right")
                            .font(.system(size: 17, weight: .bold))
                            .foregroundStyle(FieldLGXTheme.text)
                            .frame(width: 40, height: 40)
                            .background(FieldLGXTheme.elevatedBackground)
                            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                    }
                    .accessibilityLabel("Sign out")
                }

                VStack(alignment: .leading, spacing: 12) {
                    Label(user.role.title, systemImage: "person.crop.circle.badge.checkmark")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(FieldLGXTheme.lime)

                    Text(tab.placeholderCopy)
                        .font(.system(size: 17, weight: .medium))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(18)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(FieldLGXTheme.panel)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
                )

                Spacer()
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .toolbar(.hidden, for: .navigationBar)
    }
}

#Preview("Owner") {
    AppShell(session: AuthSession(currentUser: .previewOwner))
}

#Preview("Signed Out") {
    AppShell(session: AuthSession())
}
