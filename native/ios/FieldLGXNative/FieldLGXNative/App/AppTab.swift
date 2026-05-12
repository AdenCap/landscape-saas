import SwiftUI

enum AppRole: String, CaseIterable, Codable, Identifiable {
    case owner
    case manager
    case crew

    var id: String { rawValue }

    var title: String {
        switch self {
        case .owner: "Owner"
        case .manager: "Manager"
        case .crew: "Crew"
        }
    }
}

enum AppTab: String, CaseIterable, Identifiable {
    case command
    case calendar
    case work
    case clients
    case money
    case estimates
    case financials
    case employees
    case agreements
    case settings
    case mowing
    case fertilization
    case today
    case route
    case time
    case messages
    case more

    var id: String { rawValue }

    var title: String {
        switch self {
        case .command: "Dashboard"
        case .calendar: "Calendar"
        case .work: "Jobs"
        case .clients: "Clients"
        case .money: "Invoices"
        case .estimates: "Estimates"
        case .financials: "Financials"
        case .employees: "Employees"
        case .agreements: "Agreements"
        case .settings: "Settings"
        case .mowing: "Mowing"
        case .fertilization: "Fertilization"
        case .today: "Today"
        case .route: "Route"
        case .time: "Time"
        case .messages: "Messages"
        case .more: "More"
        }
    }

    var systemImage: String {
        switch self {
        case .command: "square.grid.2x2"
        case .calendar: "calendar"
        case .work: "checklist"
        case .clients: "person.2"
        case .money: "doc.text"
        case .estimates: "doc.badge.plus"
        case .financials: "chart.line.uptrend.xyaxis"
        case .employees: "person.3"
        case .agreements: "doc.plaintext"
        case .settings: "gearshape"
        case .mowing: "leaf"
        case .fertilization: "sprout"
        case .today: "sun.max"
        case .route: "map"
        case .time: "clock"
        case .messages: "bubble.left.and.bubble.right"
        case .more: "ellipsis.circle"
        }
    }

    static func tabs(for role: AppRole) -> [AppTab] {
        switch role {
        case .owner, .manager:
            [.command, .work, .calendar, .clients, .money, .estimates, .financials, .employees, .agreements, .mowing, .fertilization, .settings]
        case .crew:
            [.today, .route, .time, .more]
        }
    }
}
