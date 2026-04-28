import SwiftData
import SwiftUI

@main
struct FieldLGXNativeApp: App {
    @State private var session = AuthSession()

    var body: some Scene {
        WindowGroup {
            AppShell(session: session)
                .preferredColorScheme(.dark)
        }
        .modelContainer(for: [PendingMutation.self, CachedTodaySnapshot.self])
    }
}
