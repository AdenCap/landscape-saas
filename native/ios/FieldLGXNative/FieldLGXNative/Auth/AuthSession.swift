import Foundation
import Observation

@Observable
final class AuthSession {
    private(set) var currentUser: MobileUser?

    var isAuthenticated: Bool {
        currentUser != nil
    }

    init(currentUser: MobileUser? = nil) {
        self.currentUser = currentUser
    }

    func signInPreview(role: AppRole) {
        currentUser = MobileUser(
            id: role == .crew ? 3 : 1,
            name: role == .crew ? "Crew Preview" : "\(role.title) Preview",
            email: "\(role.rawValue)@fieldlgx.local",
            role: role,
            businessName: "FIELDLGX Demo"
        )
    }

    func signOut() {
        currentUser = nil
    }
}
