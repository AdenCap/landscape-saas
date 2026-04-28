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

struct TodayResponse: Codable, Equatable {
    let date: String
    let summary: TodaySummary
    let jobs: [TodayJob]
}

struct TodaySummary: Codable, Equatable {
    let total: Int
    let completed: Int
    let remaining: Int
}

struct TimeClockResponse: Codable, Equatable {
    let isClockedIn: Bool
    let activeEntry: TimeClockEntry?
    let todayMinutes: Int
    let todayDisplay: String
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case isClockedIn = "is_clocked_in"
        case activeEntry = "active_entry"
        case todayMinutes = "today_minutes"
        case todayDisplay = "today_display"
        case serverTime = "server_time"
    }
}

struct TimeClockEntry: Codable, Equatable, Identifiable {
    let id: Int
    let clockIn: String
    let clockOut: String?
    let durationMinutes: Int?
    let status: String
    let clockInLatitude: String?
    let clockInLongitude: String?
    let clockOutLatitude: String?
    let clockOutLongitude: String?

    enum CodingKeys: String, CodingKey {
        case id
        case clockIn = "clock_in"
        case clockOut = "clock_out"
        case durationMinutes = "duration_minutes"
        case status
        case clockInLatitude = "clock_in_latitude"
        case clockInLongitude = "clock_in_longitude"
        case clockOutLatitude = "clock_out_latitude"
        case clockOutLongitude = "clock_out_longitude"
    }
}

struct TodayJob: Codable, Equatable, Identifiable {
    let id: Int
    let status: String
    let scheduledDate: String?
    let scheduledEndDate: String?
    let scheduledTime: String?
    let scheduledEndTime: String?
    let routeOrder: Int
    let customer: TodayCustomer
    let property: TodayProperty
    let assigned: TodayAssignment
    let notes: String
    let alerts: [TodayAlert]
    let serviceItems: [TodayServiceItem]
    let photoCount: Int

    enum CodingKeys: String, CodingKey {
        case id
        case status
        case scheduledDate = "scheduled_date"
        case scheduledEndDate = "scheduled_end_date"
        case scheduledTime = "scheduled_time"
        case scheduledEndTime = "scheduled_end_time"
        case routeOrder = "route_order"
        case customer
        case property
        case assigned
        case notes
        case alerts
        case serviceItems = "service_items"
        case photoCount = "photo_count"
    }
}

struct TodayCustomer: Codable, Equatable {
    let id: Int
    let name: String
    let phone: String
}

struct TodayProperty: Codable, Equatable {
    let id: Int
    let address: String
    let latitude: String?
    let longitude: String?
}

struct TodayAssignment: Codable, Equatable {
    let crew: String?
    let employee: String?
}

struct TodayAlert: Codable, Equatable, Identifiable {
    var id: String { "\(label)-\(text)" }

    let label: String
    let text: String
}

struct TodayServiceItem: Codable, Equatable, Identifiable {
    let id: Int
    let name: String
    let detailDescription: String
    let quantity: String
    let unit: String
    let unitPrice: String
    let scheduledDate: String?

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case detailDescription = "detail_description"
        case quantity
        case unit
        case unitPrice = "unit_price"
        case scheduledDate = "scheduled_date"
    }
}

struct JobDetailResponse: Codable, Equatable {
    let job: TodayJob
    let actions: JobActions
    let jobNotes: [JobNote]
    let jobIssues: [JobIssue]
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case job
        case actions
        case jobNotes = "job_notes"
        case jobIssues = "job_issues"
        case serverTime = "server_time"
    }
}

struct JobActions: Codable, Equatable {
    let canStart: Bool
    let canComplete: Bool
    let canSkip: Bool
    let requiresCompletionPhoto: Bool
    let hasCompletionPhoto: Bool

    enum CodingKeys: String, CodingKey {
        case canStart = "can_start"
        case canComplete = "can_complete"
        case canSkip = "can_skip"
        case requiresCompletionPhoto = "requires_completion_photo"
        case hasCompletionPhoto = "has_completion_photo"
    }
}

struct JobNote: Codable, Equatable, Identifiable {
    let id: Int
    let text: String
    let visibility: String
    let author: String
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case text
        case visibility
        case author
        case createdAt = "created_at"
    }
}

struct JobIssue: Codable, Equatable, Identifiable {
    let id: Int
    let issueType: String
    let issueTypeDisplay: String
    let description: String
    let status: String
    let reportedBy: String
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case issueType = "issue_type"
        case issueTypeDisplay = "issue_type_display"
        case description
        case status
        case reportedBy = "reported_by"
        case createdAt = "created_at"
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

extension TodayResponse {
    static let preview = TodayResponse(
        date: "2026-05-04",
        summary: TodaySummary(total: 2, completed: 0, remaining: 2),
        jobs: [
            TodayJob(
                id: 1,
                status: "scheduled",
                scheduledDate: "2026-05-04",
                scheduledEndDate: nil,
                scheduledTime: "08:30",
                scheduledEndTime: nil,
                routeOrder: 1,
                customer: TodayCustomer(id: 1, name: "Maple Ridge", phone: "555-0100"),
                property: TodayProperty(id: 1, address: "123 Test Lawn Ave", latitude: nil, longitude: nil),
                assigned: TodayAssignment(crew: "Crew A", employee: nil),
                notes: "Mow front and back.",
                alerts: [
                    TodayAlert(label: "Gate code", text: "2480"),
                    TodayAlert(label: "Permanent note", text: "Use side gate.")
                ],
                serviceItems: [
                    TodayServiceItem(
                        id: 1,
                        name: "Mowing",
                        detailDescription: "Trim fence line and blow clippings.",
                        quantity: "1.00",
                        unit: "visit",
                        unitPrice: "65.00",
                        scheduledDate: nil
                    )
                ],
                photoCount: 0
            )
        ]
    )
}

extension TimeClockResponse {
    static let preview = TimeClockResponse(
        isClockedIn: false,
        activeEntry: nil,
        todayMinutes: 0,
        todayDisplay: "0h 0m",
        serverTime: "2026-05-04T12:00:00Z"
    )
}

extension JobDetailResponse {
    static let preview = JobDetailResponse(
        job: TodayResponse.preview.jobs[0],
        actions: JobActions(
            canStart: true,
            canComplete: false,
            canSkip: true,
            requiresCompletionPhoto: false,
            hasCompletionPhoto: false
        ),
        jobNotes: [
            JobNote(
                id: 1,
                text: "Customer asked for a text before arrival.",
                visibility: "crew",
                author: "Aden Cappelletti",
                createdAt: "2026-05-04T08:00:00Z"
            )
        ],
        jobIssues: [
            JobIssue(
                id: 1,
                issueType: "access",
                issueTypeDisplay: "Access / gate / lock",
                description: "Back gate is locked.",
                status: "open",
                reportedBy: "Crew A",
                createdAt: "2026-05-04T09:00:00Z"
            )
        ],
        serverTime: "2026-05-04T12:00:00Z"
    )
}
