import Foundation

struct MobileUser: Codable, Equatable, Identifiable {
    let id: Int
    let name: String
    let email: String
    let role: AppRole
    let businessName: String
}

struct AuthTokens: Codable, Equatable {
    let accessToken: String
    let refreshToken: String
}

struct AuthBootstrap: Codable, Equatable {
    let user: MobileUser
    let tokens: AuthTokens
}

extension MobileUser {
    static let previewOwner = MobileUser(
        id: 1,
        name: "Aden Cappelletti",
        email: "owner@fieldlgx.local",
        role: .owner,
        businessName: "FIELDLGX Demo"
    )
}
