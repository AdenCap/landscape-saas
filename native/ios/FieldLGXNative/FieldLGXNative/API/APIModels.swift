import Foundation

struct MobileUser: Codable, Equatable, Identifiable {
    let id: Int
    let email: String
    let username: String
    let name: String
    let role: AppRole
    let businessID: Int?

    enum CodingKeys: String, CodingKey {
        case id
        case email
        case username
        case name
        case role
        case businessID = "business_id"
    }
}

struct LoginResponse: Codable, Equatable {
    let accessToken: String
    let refreshToken: String
    let user: MobileUser

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case user
    }
}

struct BootstrapResponse: Codable, Equatable {
    let user: MobileUser
    let business: MobileBusiness
    let modules: [String]
    let sync: BootstrapSync
}

struct MobileBusiness: Codable, Equatable, Identifiable {
    let id: Int
    let name: String
    let timezone: String
    let clientCardPaymentsEnabled: Bool
    let clientSavedCardsEnabled: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case timezone
        case clientCardPaymentsEnabled = "client_card_payments_enabled"
        case clientSavedCardsEnabled = "client_saved_cards_enabled"
    }
}

struct BootstrapSync: Codable, Equatable {
    let cursor: String?
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case cursor
        case serverTime = "server_time"
    }
}

extension MobileUser {
    static let previewOwner = MobileUser(
        id: 1,
        email: "owner@fieldlgx.local",
        username: "owner",
        name: "Aden Cappelletti",
        role: .owner,
        businessID: 1
    )
}
