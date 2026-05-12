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
    let refreshToken: String?
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
    let defaultInvoiceCardPaymentsEnabled: Bool
    let clientSavedCardsEnabled: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case timezone
        case clientCardPaymentsEnabled = "client_card_payments_enabled"
        case defaultInvoiceCardPaymentsEnabled = "default_invoice_card_payments_enabled"
        case clientSavedCardsEnabled = "client_saved_cards_enabled"
    }

    init(
        id: Int,
        name: String,
        timezone: String,
        clientCardPaymentsEnabled: Bool,
        defaultInvoiceCardPaymentsEnabled: Bool,
        clientSavedCardsEnabled: Bool
    ) {
        self.id = id
        self.name = name
        self.timezone = timezone
        self.clientCardPaymentsEnabled = clientCardPaymentsEnabled
        self.defaultInvoiceCardPaymentsEnabled = defaultInvoiceCardPaymentsEnabled
        self.clientSavedCardsEnabled = clientSavedCardsEnabled
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(Int.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        timezone = try container.decodeIfPresent(String.self, forKey: .timezone) ?? "America/New_York"
        clientCardPaymentsEnabled = try container.decodeIfPresent(Bool.self, forKey: .clientCardPaymentsEnabled) ?? false
        defaultInvoiceCardPaymentsEnabled = try container.decodeIfPresent(Bool.self, forKey: .defaultInvoiceCardPaymentsEnabled) ?? true
        clientSavedCardsEnabled = try container.decodeIfPresent(Bool.self, forKey: .clientSavedCardsEnabled) ?? false
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

struct CommandResponse: Codable, Equatable {
    let date: String
    let summary: CommandSummary
    let attention: [CommandAttention]
    let nextJobs: [TodayJob]
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case date
        case summary
        case attention
        case nextJobs = "next_jobs"
        case serverTime = "server_time"
    }

    init(
        date: String,
        summary: CommandSummary,
        attention: [CommandAttention],
        nextJobs: [TodayJob],
        serverTime: String
    ) {
        self.date = date
        self.summary = summary
        self.attention = attention
        self.nextJobs = nextJobs
        self.serverTime = serverTime
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        date = try container.decodeIfPresent(String.self, forKey: .date) ?? ""
        summary = try container.decodeIfPresent(CommandSummary.self, forKey: .summary) ?? .empty
        attention = try container.decodeIfPresent([CommandAttention].self, forKey: .attention) ?? []
        nextJobs = try container.decodeIfPresent([TodayJob].self, forKey: .nextJobs) ?? []
        serverTime = try container.decodeIfPresent(String.self, forKey: .serverTime) ?? ""
    }
}

struct CommandSummary: Codable, Equatable {
    let todayJobs: Int
    let activeRoutes: Int
    let unassignedJobs: Int
    let needsScheduled: Int
    let readyToBill: Int
    let readyToBillTotal: String
    let scheduledValue: String
    let outstandingTotal: String
    let openEstimates: Int
    let customers: Int

    enum CodingKeys: String, CodingKey {
        case todayJobs = "today_jobs"
        case activeRoutes = "active_routes"
        case unassignedJobs = "unassigned_jobs"
        case needsScheduled = "needs_scheduled"
        case readyToBill = "ready_to_bill"
        case readyToBillTotal = "ready_to_bill_total"
        case scheduledValue = "scheduled_value"
        case outstandingTotal = "outstanding_total"
        case openEstimates = "open_estimates"
        case customers
    }

    init(
        todayJobs: Int,
        activeRoutes: Int,
        unassignedJobs: Int,
        needsScheduled: Int,
        readyToBill: Int,
        readyToBillTotal: String,
        scheduledValue: String,
        outstandingTotal: String,
        openEstimates: Int,
        customers: Int
    ) {
        self.todayJobs = todayJobs
        self.activeRoutes = activeRoutes
        self.unassignedJobs = unassignedJobs
        self.needsScheduled = needsScheduled
        self.readyToBill = readyToBill
        self.readyToBillTotal = readyToBillTotal
        self.scheduledValue = scheduledValue
        self.outstandingTotal = outstandingTotal
        self.openEstimates = openEstimates
        self.customers = customers
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        todayJobs = try container.decodeIfPresent(Int.self, forKey: .todayJobs) ?? 0
        activeRoutes = try container.decodeIfPresent(Int.self, forKey: .activeRoutes) ?? 0
        unassignedJobs = try container.decodeIfPresent(Int.self, forKey: .unassignedJobs) ?? 0
        needsScheduled = try container.decodeIfPresent(Int.self, forKey: .needsScheduled) ?? 0
        readyToBill = try container.decodeIfPresent(Int.self, forKey: .readyToBill) ?? 0
        readyToBillTotal = try container.decodeIfPresent(String.self, forKey: .readyToBillTotal) ?? "0.00"
        scheduledValue = try container.decodeIfPresent(String.self, forKey: .scheduledValue) ?? "0.00"
        outstandingTotal = try container.decodeIfPresent(String.self, forKey: .outstandingTotal) ?? "0.00"
        openEstimates = try container.decodeIfPresent(Int.self, forKey: .openEstimates) ?? 0
        customers = try container.decodeIfPresent(Int.self, forKey: .customers) ?? 0
    }

    static let empty = CommandSummary(
        todayJobs: 0,
        activeRoutes: 0,
        unassignedJobs: 0,
        needsScheduled: 0,
        readyToBill: 0,
        readyToBillTotal: "0.00",
        scheduledValue: "0.00",
        outstandingTotal: "0.00",
        openEstimates: 0,
        customers: 0
    )
}

struct CommandAttention: Codable, Equatable, Identifiable {
    var id: String { "\(kind)-\(title)" }

    let kind: String
    let title: String
    let detail: String
    let count: Int

    enum CodingKeys: String, CodingKey {
        case kind
        case title
        case detail
        case count
    }

    init(kind: String, title: String, detail: String, count: Int) {
        self.kind = kind
        self.title = title
        self.detail = detail
        self.count = count
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        kind = try container.decodeIfPresent(String.self, forKey: .kind) ?? "stable"
        title = try container.decodeIfPresent(String.self, forKey: .title) ?? "Day looks stable"
        detail = try container.decodeIfPresent(String.self, forKey: .detail) ?? ""
        count = try container.decodeIfPresent(Int.self, forKey: .count) ?? 0
    }
}

struct WorkResponse: Codable, Equatable {
    let date: String
    let summary: WorkSummary
    let serviceFilters: [WorkServiceFilter]
    let sections: WorkSections
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case date
        case summary
        case serviceFilters = "service_filters"
        case sections
        case serverTime = "server_time"
    }
}

struct WorkSummary: Codable, Equatable {
    let upcoming: Int
    let needsScheduled: Int
    let finished: Int
    let needsBilling: Int

    enum CodingKeys: String, CodingKey {
        case upcoming
        case needsScheduled = "needs_scheduled"
        case finished
        case needsBilling = "needs_billing"
    }
}

struct WorkServiceFilter: Codable, Equatable, Identifiable {
    var id: String { key }

    let key: String
    let label: String
}

struct WorkSections: Codable, Equatable {
    let upcoming: [TodayJob]
    let needsScheduled: [TodayJob]
    let finished: [TodayJob]
    let needsBilling: [TodayJob]

    enum CodingKeys: String, CodingKey {
        case upcoming
        case needsScheduled = "needs_scheduled"
        case finished
        case needsBilling = "needs_billing"
    }
}

struct CalendarResponse: Codable, Equatable {
    let view: String
    let date: String
    let range: CalendarRange
    let summary: CalendarSummary
    let jobs: [TodayJob]
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case view
        case date
        case range
        case summary
        case jobs
        case serverTime = "server_time"
    }
}

struct CalendarRange: Codable, Equatable {
    let start: String
    let end: String
}

struct CalendarSummary: Codable, Equatable {
    let total: Int
    let unassigned: Int
    let completed: Int
}

struct MoneyResponse: Codable, Equatable {
    let summary: MoneySummary
    let invoices: [MobileInvoice]
    let estimates: [MobileEstimate]
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case summary
        case invoices
        case estimates
        case serverTime = "server_time"
    }
}

struct MoneySummary: Codable, Equatable {
    let outstanding: String
    let overdue: String
    let drafts: Int
    let paidMonth: String
    let openEstimates: Int
    var buildingInvoices: Int? = nil
    var buildingTotal: String? = nil

    enum CodingKeys: String, CodingKey {
        case outstanding
        case overdue
        case drafts
        case paidMonth = "paid_month"
        case openEstimates = "open_estimates"
        case buildingInvoices = "building_invoices"
        case buildingTotal = "building_total"
    }
}

struct FinancialsResponse: Codable, Equatable {
    let summary: FinancialsSummary
    let receipts: [MobileReceipt]
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case summary
        case receipts
        case serverTime = "server_time"
    }
}

struct FinancialsSummary: Codable, Equatable {
    let monthRevenue: String
    let openInvoiceTotal: String
    let expenseTotal: String
    let payrollTotal: String
    let netMonth: String

    enum CodingKeys: String, CodingKey {
        case monthRevenue = "month_revenue"
        case openInvoiceTotal = "open_invoice_total"
        case expenseTotal = "expense_total"
        case payrollTotal = "payroll_total"
        case netMonth = "net_month"
    }
}

struct TeamResponse: Codable, Equatable {
    let summary: TeamSummary
    let employees: [TeamEmployee]
    let todayEntries: [TeamTimeEntry]
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case summary
        case employees
        case todayEntries = "today_entries"
        case serverTime = "server_time"
    }
}

struct TeamSummary: Codable, Equatable {
    let employees: Int
    let clockedIn: Int
    let pendingTime: Int
    let pendingTimeOff: Int

    enum CodingKeys: String, CodingKey {
        case employees
        case clockedIn = "clocked_in"
        case pendingTime = "pending_time"
        case pendingTimeOff = "pending_time_off"
    }
}

struct TeamEmployee: Codable, Equatable, Identifiable {
    let id: Int
    let name: String
    let email: String
    let phone: String
    let role: String
    let hourlyRate: String
    let color: String
    let isActive: Bool
    let isClockedIn: Bool
    let schedule: [TeamScheduleSlot]

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case email
        case phone
        case role
        case hourlyRate = "hourly_rate"
        case color
        case isActive = "is_active"
        case isClockedIn = "is_clocked_in"
        case schedule
    }
}

struct TeamScheduleSlot: Codable, Equatable, Identifiable {
    var id: String { "\(day)-\(start)-\(end)" }

    let day: String
    let start: String
    let end: String
}

struct TeamTimeEntry: Codable, Equatable, Identifiable {
    let id: Int
    let employee: String
    let clockIn: String
    let clockOut: String?
    let durationMinutes: Int?
    let status: String

    enum CodingKeys: String, CodingKey {
        case id
        case employee
        case clockIn = "clock_in"
        case clockOut = "clock_out"
        case durationMinutes = "duration_minutes"
        case status
    }
}

struct AgreementsResponse: Codable, Equatable {
    let summary: AgreementsSummary
    let agreements: [MobileAgreement]
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case summary
        case agreements
        case serverTime = "server_time"
    }
}

struct AgreementsSummary: Codable, Equatable {
    let active: Int
    let draft: Int
    let expired: Int
    let scheduledVisits: Int

    enum CodingKeys: String, CodingKey {
        case active
        case draft
        case expired
        case scheduledVisits = "scheduled_visits"
    }
}

struct MobileAgreement: Codable, Equatable, Identifiable {
    let id: Int
    let name: String
    let customer: MoneyCustomer
    let status: String
    let agreementType: String
    let billingFrequency: String
    let startDate: String?
    let endDate: String?
    let price: String
    let visitsIncluded: Int
    let visitsUsed: Int
    let visitsRemaining: Int
    let autoRenew: Bool
    let prepaid: Bool
    let lineItems: [AgreementLineItemMobile]

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case customer
        case status
        case agreementType = "agreement_type"
        case billingFrequency = "billing_frequency"
        case startDate = "start_date"
        case endDate = "end_date"
        case price
        case visitsIncluded = "visits_included"
        case visitsUsed = "visits_used"
        case visitsRemaining = "visits_remaining"
        case autoRenew = "auto_renew"
        case prepaid
        case lineItems = "line_items"
    }
}

struct AgreementLineItemMobile: Codable, Equatable, Identifiable {
    let id: Int
    let serviceName: String
    let description: String
    let frequency: String
    let quantity: String
    let unit: String
    let unitPrice: String
    let lineTotal: String
    let progress: String

    enum CodingKeys: String, CodingKey {
        case id
        case serviceName = "service_name"
        case description
        case frequency
        case quantity
        case unit
        case unitPrice = "unit_price"
        case lineTotal = "line_total"
        case progress
    }
}

struct OwnerSettingsResponse: Codable, Equatable {
    let business: MobileBusiness
    let contact: OwnerContactSettings
    let billing: OwnerBillingSettings
    let notifications: OwnerNotificationSettings
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case business
        case contact
        case billing
        case notifications
        case serverTime = "server_time"
    }
}

struct OwnerContactSettings: Codable, Equatable {
    let fromEmail: String
    let contactEmail: String
    let contactPhone: String
    let websiteURL: String
    let shopAddress: String
    let logoURL: String

    enum CodingKeys: String, CodingKey {
        case fromEmail = "from_email"
        case contactEmail = "contact_email"
        case contactPhone = "contact_phone"
        case websiteURL = "website_url"
        case shopAddress = "shop_address"
        case logoURL = "logo_url"
    }
}

struct OwnerBillingSettings: Codable, Equatable {
    let defaultInvoiceAutomationMode: String
    let autoInvoiceSendBehavior: String
    let defaultMonthlyInvoiceSendDay: Int?
    let defaultInvoiceDueDays: Int?
    let defaultEstimateValidDays: Int
    let clientCardPaymentsEnabled: Bool
    let defaultInvoiceCardPaymentsEnabled: Bool
    let clientSavedCardsEnabled: Bool
    let stripeConnected: Bool

    enum CodingKeys: String, CodingKey {
        case defaultInvoiceAutomationMode = "default_invoice_automation_mode"
        case autoInvoiceSendBehavior = "auto_invoice_send_behavior"
        case defaultMonthlyInvoiceSendDay = "default_monthly_invoice_send_day"
        case defaultInvoiceDueDays = "default_invoice_due_days"
        case defaultEstimateValidDays = "default_estimate_valid_days"
        case clientCardPaymentsEnabled = "client_card_payments_enabled"
        case defaultInvoiceCardPaymentsEnabled = "default_invoice_card_payments_enabled"
        case clientSavedCardsEnabled = "client_saved_cards_enabled"
        case stripeConnected = "stripe_connected"
    }
}

struct OwnerNotificationSettings: Codable, Equatable {
    let jobScheduled: Bool
    let crewEnRoute: Bool
    let jobCompleted: Bool
    let completionPhotos: Bool
    let invoiceReminders: Bool
    let estimateFollowUpDays: Int
    let googleReviewRequests: Bool

    enum CodingKeys: String, CodingKey {
        case jobScheduled = "job_scheduled"
        case crewEnRoute = "crew_en_route"
        case jobCompleted = "job_completed"
        case completionPhotos = "completion_photos"
        case invoiceReminders = "invoice_reminders"
        case estimateFollowUpDays = "estimate_follow_up_days"
        case googleReviewRequests = "google_review_requests"
    }
}

struct MobileInvoice: Codable, Equatable, Identifiable {
    let id: Int
    let number: String
    let customer: MoneyCustomer
    let status: String
    let issueDate: String?
    let dueDate: String?
    let total: String
    let enableCardPayment: Bool
    var isMonthly: Bool? = nil
    var periodStart: String? = nil
    var periodEnd: String? = nil
    var sendOn: String? = nil

    enum CodingKeys: String, CodingKey {
        case id
        case number
        case customer
        case status
        case issueDate = "issue_date"
        case dueDate = "due_date"
        case total
        case enableCardPayment = "enable_card_payment"
        case isMonthly = "is_monthly"
        case periodStart = "period_start"
        case periodEnd = "period_end"
        case sendOn = "send_on"
    }
}

struct MonthlyInvoiceQueueResponse: Codable, Equatable {
    let summary: MonthlyInvoiceSummary
    let invoices: [MobileInvoice]
    let serverTime: String
    let result: MonthlyInvoiceBatchResult?

    enum CodingKeys: String, CodingKey {
        case summary
        case invoices
        case serverTime = "server_time"
        case result
    }
}

struct MonthlyInvoiceSummary: Codable, Equatable {
    let draftCount: Int
    let sentCount: Int
    let paidCount: Int
    let draftTotal: String
    let sentTotal: String
    let paidTotal: String

    enum CodingKeys: String, CodingKey {
        case draftCount = "draft_count"
        case sentCount = "sent_count"
        case paidCount = "paid_count"
        case draftTotal = "draft_total"
        case sentTotal = "sent_total"
        case paidTotal = "paid_total"
    }
}

struct MonthlyInvoiceBatchResult: Codable, Equatable {
    let sent: Int
    let emailed: Int
    let charged: Int
    let emailFailed: Int
    let message: String

    enum CodingKeys: String, CodingKey {
        case sent
        case emailed
        case charged
        case emailFailed = "email_failed"
        case message
    }
}

struct MobileEstimate: Codable, Equatable, Identifiable {
    let id: Int
    let title: String
    let customer: MoneyCustomer
    let status: String
    let validUntil: String?
    let total: String
    let depositRequired: Bool
    var photoCount: Int? = nil

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case customer
        case status
        case validUntil = "valid_until"
        case total
        case depositRequired = "deposit_required"
        case photoCount = "photo_count"
    }
}

struct MoneyCustomer: Codable, Equatable {
    let id: Int
    let name: String
}

struct InvoiceDetailResponse: Codable, Equatable {
    let invoice: MobileInvoice
    let summary: InvoiceSummary
    let lineItems: [MoneyLineItem]
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case invoice
        case summary
        case lineItems = "line_items"
        case serverTime = "server_time"
    }
}

struct EstimateDetailResponse: Codable, Equatable {
    let estimate: MobileEstimate
    let summary: EstimateSummary
    let deposit: EstimateDeposit
    let lineItems: [MoneyLineItem]
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case estimate
        case summary
        case deposit
        case lineItems = "line_items"
        case serverTime = "server_time"
    }
}

struct InvoiceActionResponse: Codable, Equatable {
    let result: InvoiceActionResult
    let invoice: MobileInvoice
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case result
        case invoice
        case serverTime = "server_time"
    }
}

struct InvoiceActionResult: Codable, Equatable {
    let sent: Bool?
    let charged: Bool?
    let email: String?
    let message: String?
    let chargeMessage: String?

    enum CodingKeys: String, CodingKey {
        case sent
        case charged
        case email
        case message
        case chargeMessage = "charge_message"
    }
}

struct EstimateActionResponse: Codable, Equatable {
    let estimate: MobileEstimate
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case estimate
        case serverTime = "server_time"
    }
}

struct EstimatePhotoUploadResponse: Codable, Equatable {
    let estimate: MobileEstimate
    let photoCount: Int
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case estimate
        case photoCount = "photo_count"
        case serverTime = "server_time"
    }
}

struct ReceiptUploadResponse: Codable, Equatable {
    let receipt: MobileReceipt
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case receipt
        case serverTime = "server_time"
    }
}

struct MobileReceipt: Codable, Equatable, Identifiable {
    let id: Int
    let vendor: String
    let description: String
    let category: String
    let amount: String
    let receiptDate: String
    let jobID: Int?
    let fileURL: String
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case vendor
        case description
        case category
        case amount
        case receiptDate = "receipt_date"
        case jobID = "job_id"
        case fileURL = "file_url"
        case createdAt = "created_at"
    }
}

struct InvoiceSummary: Codable, Equatable {
    let subtotal: String
    let tax: String
    let total: String
    let paidItems: Int
    let lineItems: Int

    enum CodingKeys: String, CodingKey {
        case subtotal
        case tax
        case total
        case paidItems = "paid_items"
        case lineItems = "line_items"
    }
}

struct EstimateSummary: Codable, Equatable {
    let baseTotal: String
    let addonsTotal: String
    let total: String
    let lineItems: Int

    enum CodingKeys: String, CodingKey {
        case baseTotal = "base_total"
        case addonsTotal = "addons_total"
        case total
        case lineItems = "line_items"
    }
}

struct EstimateDeposit: Codable, Equatable {
    let required: Bool
    let type: String
    let amount: String
    let amountDue: String
    let paid: Bool

    enum CodingKeys: String, CodingKey {
        case required
        case type
        case amount
        case amountDue = "amount_due"
        case paid
    }
}

struct MoneyLineItem: Codable, Equatable, Identifiable {
    let id: Int
    let description: String
    let detailDescription: String
    let quantity: String
    let unit: String
    let unitPrice: String
    let lineTotal: String
    let isPaid: Bool
    let isOptional: Bool
    let isDiscount: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case description
        case detailDescription = "detail_description"
        case quantity
        case unit
        case unitPrice = "unit_price"
        case lineTotal = "line_total"
        case isPaid = "is_paid"
        case isOptional = "is_optional"
        case isDiscount = "is_discount"
    }
}

struct SyncPushResponse: Codable, Equatable {
    let accepted: [SyncAcceptedMutation]
    let rejected: [SyncRejectedMutation]
    let conflicts: [String]
    let cursor: String
}

struct SyncAcceptedMutation: Codable, Equatable, Identifiable {
    var id: String { localID }

    let index: Int
    let localID: String
    let entityType: String
    let operation: String
    let serverID: Int

    enum CodingKeys: String, CodingKey {
        case index
        case localID = "local_id"
        case entityType = "entity_type"
        case operation
        case serverID = "server_id"
    }
}

struct SyncRejectedMutation: Codable, Equatable, Identifiable {
    var id: String { "\(index)-\(localID)" }

    let index: Int
    let localID: String
    let entityType: String
    let reason: String

    enum CodingKeys: String, CodingKey {
        case index
        case localID = "local_id"
        case entityType = "entity_type"
        case reason
    }
}

struct JobOptionsResponse: Codable, Equatable {
    let properties: [JobOptionProperty]
    let services: [JobOptionService]
    let crews: [JobOptionCrew]
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case properties
        case services
        case crews
        case serverTime = "server_time"
    }
}

struct JobOptionProperty: Codable, Equatable, Identifiable {
    let id: Int
    let customerID: Int
    let customerName: String
    let address: String

    enum CodingKeys: String, CodingKey {
        case id
        case customerID = "customer_id"
        case customerName = "customer_name"
        case address
    }
}

struct JobOptionService: Codable, Equatable, Identifiable {
    let id: Int
    let name: String
    let unit: String
    let unitPrice: String

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case unit
        case unitPrice = "unit_price"
    }
}

struct JobOptionCrew: Codable, Equatable, Identifiable {
    let id: Int
    let name: String
}

struct JobCreateServiceItem: Equatable {
    let serviceID: Int
    let description: String
    let detailDescription: String
    let quantity: String
    let unit: String
    let unitPrice: String

    var dictionary: [String: Any] {
        [
            "service_id": serviceID,
            "description": description,
            "detail_description": detailDescription,
            "quantity": quantity,
            "unit": unit,
            "unit_price": unitPrice,
        ]
    }
}

struct TodayResponse: Codable, Equatable {
    let date: String
    let summary: TodaySummary
    let jobs: [TodayJob]
}

struct ClientsResponse: Codable, Equatable {
    let summary: ClientsSummary
    let clients: [MobileClient]
    let serverTime: String

    enum CodingKeys: String, CodingKey {
        case summary
        case clients
        case serverTime = "server_time"
    }
}

struct ClientsSummary: Codable, Equatable {
    let total: Int
    let shown: Int
}

struct ClientDetailResponse: Codable, Equatable {
    let client: MobileClient
    let serverTime: String?

    enum CodingKeys: String, CodingKey {
        case client
        case serverTime = "server_time"
    }
}

struct MobileClient: Codable, Equatable, Identifiable {
    let id: Int
    let name: String
    let email: String
    let phone: String
    let primaryAddress: String
    let mailingAddress: String
    let notes: String
    let billing: ClientBilling
    let stats: ClientStats
    let properties: [MobileClientProperty]
    let updatedAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case email
        case phone
        case primaryAddress = "primary_address"
        case mailingAddress = "mailing_address"
        case notes
        case billing
        case stats
        case properties
        case updatedAt = "updated_at"
    }
}

struct ClientBilling: Codable, Equatable {
    let invoiceFrequency: String
    let monthlyInvoiceSendDay: Int?
    let invoiceDueDays: Int?
    let hasCardOnFile: Bool
    let cardLast4: String
    let cardBrand: String
    let autoCharge: Bool
    let autoChargeCompletedJobs: Bool
    let autoChargeMonthlyInvoices: Bool

    enum CodingKeys: String, CodingKey {
        case invoiceFrequency = "invoice_frequency"
        case monthlyInvoiceSendDay = "monthly_invoice_send_day"
        case invoiceDueDays = "invoice_due_days"
        case hasCardOnFile = "has_card_on_file"
        case cardLast4 = "card_last4"
        case cardBrand = "card_brand"
        case autoCharge = "auto_charge"
        case autoChargeCompletedJobs = "auto_charge_completed_jobs"
        case autoChargeMonthlyInvoices = "auto_charge_monthly_invoices"
    }
}

struct ClientStats: Codable, Equatable {
    let jobs: Int
    let invoices: Int
    let estimates: Int
}

struct MobileClientProperty: Codable, Equatable, Identifiable {
    let id: Int
    let address: String
    let latitude: String?
    let longitude: String?
    let notes: String
    let gateCode: String
    let hasDog: Bool
    let yardSqft: Int?

    enum CodingKeys: String, CodingKey {
        case id
        case address
        case latitude
        case longitude
        case notes
        case gateCode = "gate_code"
        case hasDog = "has_dog"
        case yardSqft = "yard_sqft"
    }
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

struct TimeClockLocationResponse: Codable, Equatable {
    let ok: Bool
    let location: TimeClockLocationPing
    let timeClock: TimeClockResponse

    enum CodingKeys: String, CodingKey {
        case ok
        case location
        case timeClock = "time_clock"
    }
}

struct TimeClockLocationPing: Codable, Equatable, Identifiable {
    let id: Int
    let latitude: String
    let longitude: String
    let accuracyMeters: String?
    let recordedAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case latitude
        case longitude
        case accuracyMeters = "accuracy_meters"
        case recordedAt = "recorded_at"
    }
}

struct TodayJob: Codable, Equatable, Identifiable {
    let id: Int
    let status: String
    var color: String? = nil
    var statusColor: String? = nil
    var assigneeColor: String? = nil
    var crewColor: String? = nil
    var jobColorOverride: String? = nil
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
        case color
        case statusColor = "status_color"
        case assigneeColor = "assignee_color"
        case crewColor = "crew_color"
        case jobColorOverride = "job_color_override"
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

    static let previewClockedIn = TimeClockResponse(
        isClockedIn: true,
        activeEntry: TimeClockEntry(
            id: 1,
            clockIn: "2026-05-04T08:00:00Z",
            clockOut: nil,
            durationMinutes: nil,
            status: "open",
            clockInLatitude: nil,
            clockInLongitude: nil,
            clockOutLatitude: nil,
            clockOutLongitude: nil
        ),
        todayMinutes: 125,
        todayDisplay: "2h 5m",
        serverTime: "2026-05-04T10:05:00Z"
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
