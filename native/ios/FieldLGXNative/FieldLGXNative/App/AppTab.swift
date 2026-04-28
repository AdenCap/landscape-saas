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
    case today
    case route
    case time
    case messages
    case more

    var id: String { rawValue }

    var title: String {
        switch self {
        case .command: "Command"
        case .calendar: "Calendar"
        case .work: "Work"
        case .clients: "Clients"
        case .money: "Money"
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
        case .money: "dollarsign.circle"
        case .today: "sun.max"
        case .route: "map"
        case .time: "clock"
        case .messages: "bubble.left.and.bubble.right"
        case .more: "ellipsis.circle"
        }
    }

    var placeholderCopy: String {
        switch self {
        case .command: "Today’s work, crew status, billing alerts, and anything needing your eye."
        case .calendar: "Daily schedules, recurring work, multi-day jobs, and crew assignments."
        case .work: "Jobs, service items, notes, photos, issues, and completion status."
        case .clients: "Customers, properties, permanent notes, billing preferences, and history."
        case .money: "Estimates, invoices, deposits, monthly batches, reminders, and payments."
        case .today: "Your assigned stops, job details, notes, photos, maps, and field actions."
        case .route: "Stop order, property context, directions, and status for the day."
        case .time: "Clock in, clock out, breaks, and location-backed timeline events."
        case .messages: "Owner updates, manager notes, and field communication."
        case .more: "Profile, offline queue, settings, permissions, and support."
        }
    }

    static func tabs(for role: AppRole) -> [AppTab] {
        switch role {
        case .owner, .manager:
            [.command, .calendar, .work, .clients, .money, .more]
        case .crew:
            [.today, .route, .time, .messages, .more]
        }
    }
}
