import SwiftUI
import UIKit

struct FinancialsScreen: View {
    let accessToken: String?

    @State private var response: FinancialsResponse?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        ownerScreen {
            FieldLGXMobileHeader(
                eyebrow: "Financials",
                title: "Money flow",
                subtitle: "Revenue, expenses, receipts, payroll, and invoice exposure from the field."
            )

            if isLoading && response == nil {
                loadingPanel
            } else if let response {
                financialSummary(response.summary)
                recentReceipts(response.receipts)
            } else if let errorMessage {
                errorPanel(errorMessage)
            }
        }
        .refreshable { await load() }
        .task { await load() }
    }

    private func financialSummary(_ summary: FinancialsSummary) -> some View {
        LazyVGrid(
            columns: [
                GridItem(.flexible(), spacing: 8),
                GridItem(.flexible(), spacing: 8),
                GridItem(.flexible(), spacing: 8)
            ],
            spacing: 8
        ) {
            financialMetric("Revenue", "$\(summary.monthRevenue)", "paid")
            financialMetric("Open", "$\(summary.openInvoiceTotal)", "draft + sent")
            financialMetric("Expenses", "$\(summary.expenseTotal)", "receipts")
            financialMetric("Payroll", "$\(summary.payrollTotal)", "paid")
            financialMetric("Net", "$\(summary.netMonth)", "pulse")
        }
    }

    private func financialMetric(_ label: String, _ value: String, _ detail: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label.uppercased())
                .font(.system(size: 8, weight: .black))
                .tracking(1.1)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
                .lineLimit(1)
            Text(value)
                .font(.system(size: 20, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(1)
                .minimumScaleFactor(0.5)
            Text(detail)
                .font(.system(size: 10, weight: .bold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
                .lineLimit(1)
                .minimumScaleFactor(0.62)
        }
        .frame(maxWidth: .infinity, minHeight: 78, alignment: .leading)
        .fieldPanel(padding: 12)
    }

    private func recentReceipts(_ receipts: [MobileReceipt]) -> some View {
        ownerCard(title: "Receipts", count: receipts.count) {
            if receipts.isEmpty {
                ownerEmpty("No receipts captured this month.")
            } else {
                ForEach(receipts) { receipt in
                    ownerListRow(
                        title: receipt.vendor.isEmpty ? receipt.description : receipt.vendor,
                        subtitle: "\(receipt.receiptDate) · \(receipt.category)",
                        trailing: "$\(receipt.amount)",
                        icon: "receipt"
                    )
                }
            }
        }
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        #if DEBUG
        if accessToken == "preview-token" {
            response = .preview
            isLoading = false
            return
        }
        #endif
        do {
            response = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).financials()
        } catch {
            errorMessage = ownerAPIMessage(error, screen: "Financials")
        }
        isLoading = false
    }
}

struct EmployeesScreen: View {
    let accessToken: String?

    @State private var response: TeamResponse?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        ownerScreen {
            FieldLGXMobileHeader(
                eyebrow: "Employee command",
                title: "Team",
                subtitle: "Clocked-in crews, employee profiles, schedules, and time needing review."
            )

            if isLoading && response == nil {
                loadingPanel
            } else if let response {
                teamSummary(response.summary)
                clockedInSection(response.todayEntries)
                employeeSection(response.employees)
            } else if let errorMessage {
                errorPanel(errorMessage)
            }
        }
        .refreshable { await load() }
        .task { await load() }
    }

    private func teamSummary(_ summary: TeamSummary) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
            ownerMetric("Employees", "\(summary.employees)", "on team")
            ownerMetric("Clocked in", "\(summary.clockedIn)", "active now")
            ownerMetric("Time review", "\(summary.pendingTime)", "pending")
            ownerMetric("Time off", "\(summary.pendingTimeOff)", "requests")
        }
    }

    private func clockedInSection(_ entries: [TeamTimeEntry]) -> some View {
        ownerCard(title: "Today time", count: entries.count) {
            if entries.isEmpty {
                ownerEmpty("No team time entries today.")
            } else {
                ForEach(entries) { entry in
                    ownerListRow(
                        title: entry.employee,
                        subtitle: "\(displayDateTime(entry.clockIn)) · \(entry.status.replacingOccurrences(of: "_", with: " "))",
                        trailing: entry.durationMinutes.map { "\($0 / 60)h \($0 % 60)m" } ?? "Live",
                        icon: entry.clockOut == nil ? "location.fill" : "clock"
                    )
                }
            }
        }
    }

    private func employeeSection(_ employees: [TeamEmployee]) -> some View {
        ownerCard(title: "Employees", count: employees.count) {
            ForEach(employees) { employee in
                VStack(alignment: .leading, spacing: 10) {
                    HStack(spacing: 12) {
                        Circle()
                            .fill(employee.isClockedIn ? FieldLGXTheme.lime : FieldLGXTheme.tertiaryText)
                            .frame(width: 10, height: 10)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(employee.name)
                                .font(.system(size: 16, weight: .black))
                                .foregroundStyle(FieldLGXTheme.text)
                            Text(employee.role.capitalized)
                                .font(.system(size: 12, weight: .bold))
                                .foregroundStyle(FieldLGXTheme.secondaryText)
                        }
                        Spacer()
                        Text(employee.isClockedIn ? "Live" : "Off")
                            .font(.system(size: 12, weight: .black))
                            .foregroundStyle(employee.isClockedIn ? FieldLGXTheme.lime : FieldLGXTheme.secondaryText)
                    }
                    if !employee.phone.isEmpty || !employee.email.isEmpty {
                        Text([employee.phone, employee.email].filter { !$0.isEmpty }.joined(separator: " · "))
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(FieldLGXTheme.secondaryText)
                    }
                }
                .padding(14)
                .fieldInsetSurface()
            }
        }
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        #if DEBUG
        if accessToken == "preview-token" {
            response = .preview
            isLoading = false
            return
        }
        #endif
        do {
            response = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).team()
        } catch {
            errorMessage = ownerAPIMessage(error, screen: "Employee command")
        }
        isLoading = false
    }
}

private func ownerAPIMessage(_ error: Error, screen: String) -> String {
    if let apiError = error as? APIError, apiError.statusCode == 404 {
        return "\(screen) is waiting on the latest FIELDLGX server update. The app is connected, but this mobile endpoint is not live on the server yet."
    }
    return error.localizedDescription
}

struct AgreementsScreen: View {
    let accessToken: String?

    @State private var response: AgreementsResponse?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        ownerScreen {
            FieldLGXMobileHeader(
                eyebrow: "Agreements",
                title: "Service plans",
                subtitle: "Maintenance agreements, included visits, prepaid work, and covered services."
            )

            if isLoading && response == nil {
                loadingPanel
            } else if let response {
                agreementSummary(response.summary)
                agreementList(response.agreements)
            } else if let errorMessage {
                errorPanel(errorMessage)
            }
        }
        .refreshable { await load() }
        .task { await load() }
    }

    private func agreementSummary(_ summary: AgreementsSummary) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
            ownerMetric("Active", "\(summary.active)", "running")
            ownerMetric("Drafts", "\(summary.draft)", "building")
            ownerMetric("Expired", "\(summary.expired)", "review")
            ownerMetric("Visits", "\(summary.scheduledVisits)", "scheduled")
        }
    }

    private func agreementList(_ agreements: [MobileAgreement]) -> some View {
        ownerCard(title: "Plans", count: agreements.count) {
            if agreements.isEmpty {
                ownerEmpty("No service agreements yet.")
            } else {
                ForEach(agreements) { agreement in
                    VStack(alignment: .leading, spacing: 12) {
                        ownerListRow(
                            title: agreement.name,
                            subtitle: "\(agreement.customer.name) · \(agreement.billingFrequency)",
                            trailing: "$\(agreement.price)",
                            icon: agreement.prepaid ? "checkmark.seal.fill" : "doc.text"
                        )
                        HStack(spacing: 8) {
                            agreementPill(agreement.status.capitalized)
                            agreementPill("\(agreement.visitsRemaining) visits left")
                            if agreement.autoRenew {
                                agreementPill("Auto renew")
                            }
                        }
                        if let first = agreement.lineItems.first {
                            Text(first.serviceName)
                                .font(.system(size: 13, weight: .semibold))
                                .foregroundStyle(FieldLGXTheme.secondaryText)
                                .lineLimit(2)
                        }
                    }
                    .padding(14)
                    .fieldInsetSurface()
                }
            }
        }
    }

    private func agreementPill(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11, weight: .black))
            .foregroundStyle(FieldLGXTheme.text)
            .padding(.horizontal, 10)
            .frame(height: 28)
            .background(FieldLGXTheme.elevatedBackground.opacity(0.78))
            .clipShape(Capsule())
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        #if DEBUG
        if accessToken == "preview-token" {
            response = .preview
            isLoading = false
            return
        }
        #endif
        do {
            response = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).agreements()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

struct OwnerSettingsScreen: View {
    let accessToken: String?
    let signOut: () -> Void

    @AppStorage(FieldLGXAppearanceChoice.storageKey) private var appearanceRawValue = FieldLGXAppearanceChoice.system.rawValue
    @State private var response: OwnerSettingsResponse?
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var iconMessage: String?

    var body: some View {
        ownerScreen {
            FieldLGXMobileHeader(
                eyebrow: "System",
                title: "Settings",
                subtitle: "Business identity, payment defaults, notifications, and mobile readiness."
            )

            if isLoading && response == nil {
                loadingPanel
            } else if let response {
                contactSection(response)
                billingSection(response.billing)
                notificationSection(response.notifications)
                appearanceSection
            } else if let errorMessage {
                errorPanel(errorMessage)
            }

            Button(action: signOut) {
                Label("Sign out", systemImage: "rectangle.portrait.and.arrow.right")
            }
            .buttonStyle(FieldLGXPrimaryButtonStyle())
        }
        .refreshable { await load() }
        .task { await load() }
    }

    private func contactSection(_ response: OwnerSettingsResponse) -> some View {
        ownerCard(title: "Business", count: nil) {
            ownerListRow(title: response.business.name, subtitle: response.contact.shopAddress.isEmpty ? "Workspace profile" : response.contact.shopAddress, trailing: "", icon: "building.2")
            ownerListRow(title: response.contact.contactEmail.isEmpty ? "No contact email" : response.contact.contactEmail, subtitle: response.contact.contactPhone, trailing: "", icon: "envelope")
            ownerListRow(title: response.contact.websiteURL.isEmpty ? "No website set" : response.contact.websiteURL, subtitle: "Client-facing documents", trailing: "", icon: "globe")
        }
    }

    private func billingSection(_ billing: OwnerBillingSettings) -> some View {
        ownerCard(title: "Billing defaults", count: nil) {
            ownerToggleRow("Card payments", billing.clientCardPaymentsEnabled, "Client checkout")
            ownerToggleRow("Invoice card default", billing.defaultInvoiceCardPaymentsEnabled, "New invoices")
            ownerToggleRow("Saved cards", billing.clientSavedCardsEnabled, "Customer based")
            ownerToggleRow("Stripe ready", billing.stripeConnected, "Connected account")
            ownerListRow(title: "Due date", subtitle: billing.defaultInvoiceDueDays.map { "\($0) days after issue" } ?? "No default", trailing: "", icon: "calendar.badge.clock")
        }
    }

    private func notificationSection(_ notifications: OwnerNotificationSettings) -> some View {
        ownerCard(title: "Notifications", count: nil) {
            ownerToggleRow("Job scheduled", notifications.jobScheduled, "Client update")
            ownerToggleRow("Crew en route", notifications.crewEnRoute, "Client update")
            ownerToggleRow("Job complete", notifications.jobCompleted, "Client update")
            ownerToggleRow("Invoice reminders", notifications.invoiceReminders, "Payment follow-up")
            ownerListRow(title: "Estimate follow-up", subtitle: "\(notifications.estimateFollowUpDays) days", trailing: "", icon: "paperplane")
        }
    }

    private var appearanceSection: some View {
        ownerCard(title: "Appearance", count: nil) {
            VStack(alignment: .leading, spacing: 12) {
                Text("Theme")
                    .font(.system(size: 13, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)

                HStack(spacing: 8) {
                    ForEach(FieldLGXAppearanceChoice.allCases) { choice in
                        appearanceButton(choice)
                    }
                }

                Text("App icon")
                    .font(.system(size: 13, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                    .padding(.top, 4)

                VStack(spacing: 8) {
                    ForEach(FieldLGXAppIconChoice.allCases) { choice in
                        Button {
                            changeAppIcon(to: choice)
                        } label: {
                            HStack(spacing: 12) {
                                RoundedRectangle(cornerRadius: 10, style: .continuous)
                                    .fill(iconSwatch(for: choice))
                                    .frame(width: 38, height: 38)
                                    .overlay(
                                        Image("FieldLGXMonogram")
                                            .resizable()
                                            .scaledToFit()
                                            .padding(6)
                                    )

                                VStack(alignment: .leading, spacing: 3) {
                                    Text(choice.title)
                                        .font(.system(size: 14, weight: .black))
                                        .foregroundStyle(FieldLGXTheme.text)
                                    Text(choice.subtitle)
                                        .font(.system(size: 12, weight: .semibold))
                                        .foregroundStyle(FieldLGXTheme.secondaryText)
                                }
                                Spacer()
                                if UIApplication.shared.alternateIconName == choice.alternateIconName {
                                    Image(systemName: "checkmark.circle.fill")
                                        .foregroundStyle(FieldLGXTheme.lime)
                                }
                            }
                            .padding(12)
                            .fieldInsetSurface()
                        }
                        .buttonStyle(.plain)
                    }
                }

                if let iconMessage {
                    Text(iconMessage)
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                }
            }
        }
    }

    private func appearanceButton(_ choice: FieldLGXAppearanceChoice) -> some View {
        let selected = appearanceRawValue == choice.rawValue
        return Button {
            appearanceRawValue = choice.rawValue
        } label: {
            VStack(spacing: 7) {
                Image(systemName: choice.systemImage)
                    .font(.system(size: 15, weight: .black))
                Text(choice.title)
                    .font(.system(size: 12, weight: .black))
                    .lineLimit(1)
                    .minimumScaleFactor(0.72)
            }
            .foregroundStyle(selected ? .black : FieldLGXTheme.text)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(selected ? FieldLGXTheme.lime : FieldLGXTheme.elevatedBackground)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .stroke(selected ? FieldLGXTheme.lime : FieldLGXTheme.panelStroke, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(choice.title) theme")
    }

    private func iconSwatch(for choice: FieldLGXAppIconChoice) -> AnyShapeStyle {
        switch choice {
        case .primary, .dark:
            AnyShapeStyle(Color.black)
        case .light:
            AnyShapeStyle(Color(red: 0.97, green: 0.99, blue: 0.94))
        }
    }

    private func changeAppIcon(to choice: FieldLGXAppIconChoice) {
        guard UIApplication.shared.supportsAlternateIcons else {
            iconMessage = "This device does not support alternate app icons."
            return
        }
        guard UIApplication.shared.alternateIconName != choice.alternateIconName else {
            iconMessage = "\(choice.title) icon is already active."
            return
        }
        UIApplication.shared.setAlternateIconName(choice.alternateIconName) { error in
            if let error {
                iconMessage = "Could not change icon: \(error.localizedDescription)"
            } else {
                iconMessage = "\(choice.title) icon selected."
            }
        }
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        #if DEBUG
        if accessToken == "preview-token" {
            response = .preview
            isLoading = false
            return
        }
        #endif
        do {
            response = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).ownerSettings()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

private func ownerScreen<Content: View>(@ViewBuilder content: @escaping () -> Content) -> some View {
    ZStack {
        FieldLGXScreenBackground()
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                content()
            }
            .padding(.horizontal, 16)
            .padding(.top, FieldLGXTheme.ownerTopOffset)
            .padding(.bottom, 92)
        }
    }
    .toolbar(.hidden, for: .navigationBar)
    .navigationBarBackButtonHidden(true)
}

private var loadingPanel: some View {
    ProgressView()
        .tint(FieldLGXTheme.lime)
        .frame(maxWidth: .infinity, minHeight: 220)
        .fieldPanel()
}

private func errorPanel(_ message: String) -> some View {
    Text(message)
        .font(.system(size: 15, weight: .semibold))
        .foregroundStyle(FieldLGXTheme.secondaryText)
        .frame(maxWidth: .infinity, alignment: .leading)
        .fieldPanel()
}

private func ownerMetric(_ label: String, _ value: String, _ detail: String) -> some View {
    VStack(alignment: .leading, spacing: 5) {
        Text(label.uppercased())
            .font(.system(size: 8, weight: .black))
            .tracking(1.15)
            .foregroundStyle(FieldLGXTheme.tertiaryText)
            .lineLimit(1)
        Text(value)
            .font(.system(size: 21, weight: .black, design: .rounded))
            .foregroundStyle(FieldLGXTheme.text)
            .lineLimit(1)
            .minimumScaleFactor(0.55)
        Text(detail)
            .font(.system(size: 10, weight: .bold))
            .foregroundStyle(FieldLGXTheme.secondaryText)
            .lineLimit(1)
            .minimumScaleFactor(0.62)
    }
    .frame(maxWidth: .infinity, minHeight: 82, alignment: .leading)
    .fieldPanel(padding: 12)
}

private func ownerCard<Content: View>(title: String, count: Int?, @ViewBuilder content: () -> Content) -> some View {
    VStack(alignment: .leading, spacing: 12) {
        HStack {
            Text(title.uppercased())
                .font(.system(size: 11, weight: .black))
                .tracking(2.1)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            Spacer()
            if let count {
                Text("\(count)")
                    .font(.system(size: 12, weight: .black))
                    .foregroundStyle(.black)
                    .frame(minWidth: 30, minHeight: 30)
                    .background(FieldLGXTheme.lime)
                    .clipShape(Capsule())
            }
        }
        content()
    }
    .fieldPanel()
}

private func ownerListRow(title: String, subtitle: String, trailing: String, icon: String) -> some View {
    HStack(spacing: 12) {
        Image(systemName: icon)
            .font(.system(size: 15, weight: .black))
            .foregroundStyle(FieldLGXTheme.lime)
            .frame(width: 24)
        VStack(alignment: .leading, spacing: 3) {
            Text(title)
                .font(.system(size: 15, weight: .black))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(2)
            if !subtitle.isEmpty {
                Text(subtitle)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .lineLimit(2)
            }
        }
        Spacer()
        if !trailing.isEmpty {
            Text(trailing)
                .font(.system(size: 14, weight: .black))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(1)
        }
    }
    .padding(14)
    .fieldInsetSurface()
}

private func ownerToggleRow(_ title: String, _ isOn: Bool, _ detail: String) -> some View {
    HStack(spacing: 12) {
        Image(systemName: isOn ? "checkmark.circle.fill" : "circle")
            .font(.system(size: 18, weight: .black))
            .foregroundStyle(isOn ? FieldLGXTheme.lime : FieldLGXTheme.tertiaryText)
        VStack(alignment: .leading, spacing: 3) {
            Text(title)
                .font(.system(size: 15, weight: .black))
                .foregroundStyle(FieldLGXTheme.text)
            Text(detail)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
        }
        Spacer()
        Text(isOn ? "On" : "Off")
            .font(.system(size: 12, weight: .black))
            .foregroundStyle(isOn ? FieldLGXTheme.lime : FieldLGXTheme.secondaryText)
    }
    .padding(14)
    .fieldInsetSurface()
}

private func ownerEmpty(_ text: String) -> some View {
    Text(text)
        .font(.system(size: 14, weight: .semibold))
        .foregroundStyle(FieldLGXTheme.secondaryText)
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .fieldInsetSurface()
}

private func displayDateTime(_ value: String) -> String {
    String(value.prefix(16)).replacingOccurrences(of: "T", with: " ")
}

#if DEBUG
private extension FinancialsResponse {
    static let preview = FinancialsResponse(
        summary: FinancialsSummary(
            monthRevenue: "8420.00",
            openInvoiceTotal: "3185.00",
            expenseTotal: "740.26",
            payrollTotal: "2210.00",
            netMonth: "5469.74"
        ),
        receipts: [
            MobileReceipt(id: 1, vendor: "SiteOne", description: "Mulch and edging", category: "materials", amount: "312.40", receiptDate: "2026-05-10", jobID: 44, fileURL: "", createdAt: "2026-05-10T09:00:00"),
            MobileReceipt(id: 2, vendor: "Fuel stop", description: "Crew truck fuel", category: "fuel", amount: "86.12", receiptDate: "2026-05-09", jobID: nil, fileURL: "", createdAt: "2026-05-09T16:30:00")
        ],
        serverTime: "2026-05-10T12:00:00"
    )
}

private extension TeamResponse {
    static let preview = TeamResponse(
        summary: TeamSummary(employees: 6, clockedIn: 4, pendingTime: 2, pendingTimeOff: 1),
        employees: [
            TeamEmployee(id: 1, name: "Alex Buckley", email: "alex@example.com", phone: "555-0100", role: "crew", hourlyRate: "22.00", color: "#9FE84C", isActive: true, isClockedIn: true, schedule: []),
            TeamEmployee(id: 2, name: "Jordan Crew", email: "jordan@example.com", phone: "555-0110", role: "manager", hourlyRate: "28.00", color: "#6EA8FF", isActive: true, isClockedIn: false, schedule: [])
        ],
        todayEntries: [
            TeamTimeEntry(id: 11, employee: "Alex Buckley", clockIn: "2026-05-10T07:42:00", clockOut: nil, durationMinutes: nil, status: "pending_approval"),
            TeamTimeEntry(id: 12, employee: "Mia Field", clockIn: "2026-05-10T08:04:00", clockOut: "2026-05-10T11:48:00", durationMinutes: 224, status: "approved")
        ],
        serverTime: "2026-05-10T12:00:00"
    )
}

private extension AgreementsResponse {
    static let preview = AgreementsResponse(
        summary: AgreementsSummary(active: 12, draft: 2, expired: 1, scheduledVisits: 9),
        agreements: [
            MobileAgreement(
                id: 1,
                name: "Estate maintenance",
                customer: MoneyCustomer(id: 1, name: "Maple Ridge HOA"),
                status: "active",
                agreementType: "Maintenance Plan",
                billingFrequency: "Monthly",
                startDate: "2026-04-01",
                endDate: "2027-03-31",
                price: "1200.00",
                visitsIncluded: 36,
                visitsUsed: 8,
                visitsRemaining: 28,
                autoRenew: true,
                prepaid: false,
                lineItems: [
                    AgreementLineItemMobile(id: 1, serviceName: "Weekly mowing", description: "Common areas and entrances", frequency: "Per Visit", quantity: "1", unit: "visit", unitPrice: "220.00", lineTotal: "220.00", progress: "8/36")
                ]
            )
        ],
        serverTime: "2026-05-10T12:00:00"
    )
}

private extension OwnerSettingsResponse {
    static let preview = OwnerSettingsResponse(
        business: MobileBusiness.preview,
        contact: OwnerContactSettings(fromEmail: "office@fieldlgx.com", contactEmail: "office@fieldlgx.com", contactPhone: "555-0199", websiteURL: "fieldlgx.com", shopAddress: "9302 North Bayland Drive", logoURL: ""),
        billing: OwnerBillingSettings(defaultInvoiceAutomationMode: "monthly", autoInvoiceSendBehavior: "draft", defaultMonthlyInvoiceSendDay: 28, defaultInvoiceDueDays: 14, defaultEstimateValidDays: 30, clientCardPaymentsEnabled: true, defaultInvoiceCardPaymentsEnabled: true, clientSavedCardsEnabled: true, stripeConnected: true),
        notifications: OwnerNotificationSettings(jobScheduled: true, crewEnRoute: true, jobCompleted: true, completionPhotos: true, invoiceReminders: true, estimateFollowUpDays: 3, googleReviewRequests: false),
        serverTime: "2026-05-10T12:00:00"
    )
}

private extension MobileBusiness {
    static let preview = MobileBusiness(
        id: 1,
        name: "FIELDLGX Demo",
        timezone: "America/Indiana/Indianapolis",
        clientCardPaymentsEnabled: true,
        defaultInvoiceCardPaymentsEnabled: true,
        clientSavedCardsEnabled: true
    )
}
#endif
