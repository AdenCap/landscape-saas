import SwiftUI
import SwiftData
import PhotosUI

private struct MoneyDraftLineItem: Identifiable, Equatable {
    let id = UUID()
    var description = ""
    var detailDescription = ""
    var quantity = "1"
    var unit = "visit"
    var unitPrice = ""
    var isOptional = false

    var isReady: Bool {
        !description.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        !unitPrice.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var payload: [String: Any] {
        [
            "description": description,
            "detail_description": detailDescription,
            "quantity": quantity,
            "unit": unit,
            "unit_price": unitPrice,
            "is_optional": isOptional
        ]
    }
}

struct MoneyScreen: View {
    let accessToken: String?
    var defaultCardPaymentEnabled = true

    @State private var money: MoneyResponse?
    @State private var monthlyQueue: MonthlyInvoiceQueueResponse?
    @State private var isLoading = false
    @State private var isBatchSending = false
    @State private var errorMessage: String?
    @State private var batchMessage: String?
    @State private var showingInvoiceCreate = false
    @State private var showingEstimateCreate = false
    @State private var showingReceiptCreate = false

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    header
                    actionBar

                    if isLoading && money == nil {
                        ProgressView()
                            .tint(FieldLGXTheme.lime)
                            .frame(maxWidth: .infinity, minHeight: 220)
                    } else if let money {
                        summaryGrid(money.summary)
                        monthlySection(monthlyQueue)
                        invoiceSection(money.invoices)
                        estimateSection(money.estimates)
                    } else if let errorMessage {
                        Text(errorMessage)
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundStyle(FieldLGXTheme.secondaryText)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, FieldLGXTheme.ownerTopOffset)
                .padding(.bottom, 18)
            }
            .refreshable {
                await loadMoney()
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .navigationBarBackButtonHidden(true)
        .sheet(isPresented: $showingInvoiceCreate) {
            CreateInvoiceSheet(
                accessToken: accessToken,
                defaultCardPaymentEnabled: defaultCardPaymentEnabled
            ) {
                await loadMoney()
            }
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
        .sheet(isPresented: $showingEstimateCreate) {
            CreateEstimateSheet(accessToken: accessToken) {
                await loadMoney()
            }
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
        .sheet(isPresented: $showingReceiptCreate) {
            CreateReceiptSheet(accessToken: accessToken)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
        .task {
            await loadMoney()
        }
    }

    private var header: some View {
        FieldLGXMobileHeader(
            eyebrow: "Money command",
            title: "Invoices",
            subtitle: "Drafts, estimates, monthly batches, reminders, and payments."
        )
    }

    private var actionBar: some View {
        HStack(spacing: 10) {
            Button {
                showingInvoiceCreate = true
            } label: {
                Label("Invoice", systemImage: "doc.badge.plus")
                    .font(.system(size: 15, weight: .black))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
            }
            .foregroundStyle(.black)
            .background(FieldLGXTheme.lime)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))

            Button {
                showingEstimateCreate = true
            } label: {
                Label("Estimate", systemImage: "doc.text")
                    .font(.system(size: 15, weight: .black))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
            }
            .foregroundStyle(FieldLGXTheme.text)
            .background(FieldLGXTheme.elevatedBackground)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
            )

            Button {
                showingReceiptCreate = true
            } label: {
                Image(systemName: "camera.fill")
                    .font(.system(size: 16, weight: .black))
                    .frame(width: 50, height: 50)
            }
            .foregroundStyle(FieldLGXTheme.text)
            .background(FieldLGXTheme.elevatedBackground)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
            )
        }
    }

    private func summaryGrid(_ summary: MoneySummary) -> some View {
        LazyVGrid(
            columns: [
                GridItem(.flexible(), spacing: 8),
                GridItem(.flexible(), spacing: 8),
                GridItem(.flexible(), spacing: 8)
            ],
            spacing: 8
        ) {
            metric("Outstanding", "$\(summary.outstanding)", "open invoices")
            metric("Overdue", "$\(summary.overdue)", "needs follow-up")
            metric("Ready", "\(summary.drafts)", "to send")
            metric("Building", "$\(summary.buildingTotal ?? "0.00")", "\(summary.buildingInvoices ?? 0) recurring")
            metric("Paid month", "$\(summary.paidMonth)", "collected")
            metric("Estimates", "\(summary.openEstimates)", "open quotes")
        }
    }

    private func metric(_ label: String, _ value: String, _ detail: String) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(label.uppercased())
                .font(.system(size: 8, weight: .black))
                .tracking(1.1)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
                .lineLimit(1)
            Text(value)
                .font(.system(size: 21, weight: .black, design: .rounded))
                .foregroundStyle(label == "Overdue" ? .red.opacity(0.95) : FieldLGXTheme.text)
                .lineLimit(1)
                .minimumScaleFactor(0.52)
            Text(detail)
                .font(.system(size: 10, weight: .bold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
                .lineLimit(1)
                .minimumScaleFactor(0.62)
        }
        .frame(maxWidth: .infinity, minHeight: 82, alignment: .leading)
        .fieldPanel(padding: 12)
    }

    private func invoiceSection(_ invoices: [MobileInvoice]) -> some View {
        card(title: "Invoices", count: invoices.count) {
            if invoices.isEmpty {
                empty("No invoices yet.")
            } else {
                ForEach(invoices) { invoice in
                    NavigationLink {
                        InvoiceDetailScreen(invoiceID: invoice.id, accessToken: accessToken, previewInvoice: invoice)
                    } label: {
                        moneyRow(title: invoice.number, subtitle: invoice.customer.name, status: invoice.status, total: invoice.total)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private func estimateSection(_ estimates: [MobileEstimate]) -> some View {
        card(title: "Estimates", count: estimates.count) {
            if estimates.isEmpty {
                empty("No estimates yet.")
            } else {
                ForEach(estimates) { estimate in
                    NavigationLink {
                        EstimateDetailScreen(estimateID: estimate.id, accessToken: accessToken, previewEstimate: estimate)
                    } label: {
                        moneyRow(title: estimate.title, subtitle: estimate.customer.name, status: estimate.status, total: estimate.total)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private func monthlySection(_ queue: MonthlyInvoiceQueueResponse?) -> some View {
        card(title: "Recurring batches", count: queue?.summary.draftCount ?? 0) {
            if let queue {
                VStack(alignment: .leading, spacing: 12) {
                    HStack(spacing: 10) {
                        monthlyMetric("Building", "$\(queue.summary.draftTotal)", "\(queue.summary.draftCount) waiting")
                        monthlyMetric("Sent", "$\(queue.summary.sentTotal)", "\(queue.summary.sentCount) out")
                        monthlyMetric("Paid", "$\(queue.summary.paidTotal)", "\(queue.summary.paidCount) collected")
                    }

                    if let batchMessage {
                        Text(batchMessage)
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(FieldLGXTheme.secondaryText)
                    }

                    Button {
                        Task { await sendMonthlyDrafts(queue.invoices.filter { $0.status.lowercased() == "draft" }.map(\.id)) }
                    } label: {
                        HStack {
                            if isBatchSending {
                                ProgressView()
                                    .tint(.black)
                            } else {
                                Image(systemName: "paperplane.fill")
                            }
                            Text(isBatchSending ? "Sending" : "Send all ready")
                            Spacer()
                            Text("\(queue.summary.draftCount)")
                        }
                        .font(.system(size: 16, weight: .black))
                        .foregroundStyle(.black)
                        .padding(.horizontal, 16)
                        .frame(height: 54)
                        .background(FieldLGXTheme.lime)
                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                    }
                    .disabled(isBatchSending || queue.summary.draftCount == 0)
                    .opacity(queue.summary.draftCount == 0 ? 0.5 : 1)

                    if queue.invoices.isEmpty {
                        empty("No recurring invoices yet.")
                    } else {
                        ForEach(queue.invoices) { invoice in
                            NavigationLink {
                                InvoiceDetailScreen(invoiceID: invoice.id, accessToken: accessToken, previewInvoice: invoice)
                            } label: {
                                moneyRow(
                                    title: "Batch \(invoice.number)",
                                    subtitle: monthlySubtitle(invoice),
                                    status: invoice.status,
                                    total: invoice.total,
                                    cardPayment: invoice.enableCardPayment
                                )
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            } else {
                empty("Recurring invoices will appear here while completed services are collected.")
            }
        }
    }

    private func card<Content: View>(title: String, count: Int, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text(title.uppercased())
                    .font(.system(size: 11, weight: .black))
                    .tracking(2.2)
                    .foregroundStyle(FieldLGXTheme.tertiaryText)
                Spacer()
                Text("\(count)")
                    .font(.system(size: 15, weight: .black))
                    .foregroundStyle(FieldLGXTheme.lime)
            }
            content()
        }
        .fieldPanel()
    }

    private func monthlyMetric(_ label: String, _ value: String, _ detail: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label.uppercased())
                .font(.system(size: 9, weight: .black))
                .tracking(1.5)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            Text(value)
                .font(.system(size: 17, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(1)
                .minimumScaleFactor(0.68)
            Text(detail)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
                .lineLimit(1)
                .minimumScaleFactor(0.72)
        }
        .frame(maxWidth: .infinity, minHeight: 74, alignment: .leading)
        .padding(12)
        .background(FieldLGXTheme.elevatedBackground)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func moneyRow(title: String, subtitle: String, status: String, total: String, cardPayment: Bool = false) -> some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 5) {
                Text(title)
                    .font(.system(size: 17, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                Text(subtitle)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .lineLimit(2)
                if cardPayment {
                    Label("Card payment on", systemImage: "creditcard.fill")
                        .font(.system(size: 11, weight: .black))
                        .foregroundStyle(FieldLGXTheme.lime)
                }
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 5) {
                Text("$\(total)")
                    .font(.system(size: 16, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                Text(status.capitalized)
                    .font(.system(size: 12, weight: .black))
                    .foregroundStyle(FieldLGXTheme.lime)
            }
        }
        .padding(16)
        .background(FieldLGXTheme.elevatedBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private func monthlySubtitle(_ invoice: MobileInvoice) -> String {
        var parts = [invoice.customer.name]
        if let periodStart = invoice.periodStart, let periodEnd = invoice.periodEnd {
            parts.append("\(periodStart) to \(periodEnd)")
        }
        if let sendOn = invoice.sendOn {
            parts.append("send \(sendOn)")
        }
        return parts.joined(separator: " - ")
    }

    private func empty(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 15, weight: .semibold))
            .foregroundStyle(FieldLGXTheme.secondaryText)
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
        .background(FieldLGXTheme.elevatedBackground)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func loadMoney() async {
        guard let accessToken, accessToken != "preview-token" else {
            money = .preview
            monthlyQueue = .preview
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            let client = APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
            money = try await client.money()
            monthlyQueue = try? await client.monthlyInvoices()
        } catch {
            errorMessage = "Could not load money command."
        }
    }

    private func sendMonthlyDrafts(_ ids: [Int]) async {
        guard !ids.isEmpty else { return }
        guard let accessToken, accessToken != "preview-token" else {
            batchMessage = "Recurring drafts sent."
            return
        }
        isBatchSending = true
        batchMessage = nil
        defer { isBatchSending = false }

        do {
            let response = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
                .sendMonthlyInvoices(invoiceIDs: ids)
            monthlyQueue = response
            batchMessage = response.result?.message ?? "Recurring drafts sent."
            await loadMoney()
        } catch {
            batchMessage = "Could not send recurring invoices."
        }
    }
}

private extension MoneyResponse {
    static let preview = MoneyResponse(
        summary: MoneySummary(
            outstanding: "180.00",
            overdue: "0.00",
            drafts: 1,
            paidMonth: "2400.00",
            openEstimates: 2,
            buildingInvoices: 1,
            buildingTotal: "240.00"
        ),
        invoices: [
            MobileInvoice(id: 1, number: "#1", customer: MoneyCustomer(id: 1, name: "Money Client"), status: "sent", issueDate: "2026-05-01", dueDate: "2026-05-15", total: "180.00", enableCardPayment: true)
        ],
        estimates: [
            MobileEstimate(id: 1, title: "Landscape Refresh", customer: MoneyCustomer(id: 1, name: "Money Client"), status: "sent", validUntil: nil, total: "950.00", depositRequired: true)
        ],
        serverTime: "2026-05-08T12:00:00Z"
    )
}

private extension MonthlyInvoiceQueueResponse {
    static let preview = MonthlyInvoiceQueueResponse(
        summary: MonthlyInvoiceSummary(draftCount: 1, sentCount: 2, paidCount: 0, draftTotal: "240.00", sentTotal: "520.00", paidTotal: "0.00"),
        invoices: [
            MobileInvoice(
                id: 2,
                number: "#2",
                customer: MoneyCustomer(id: 1, name: "Money Client"),
                status: "draft",
                issueDate: "2026-05-31",
                dueDate: "2026-06-15",
                total: "240.00",
                enableCardPayment: true,
                isMonthly: true,
                periodStart: "2026-05-01",
                periodEnd: "2026-05-31",
                sendOn: "2026-05-31"
            )
        ],
        serverTime: "2026-05-08T12:00:00Z",
        result: nil
    )
}

struct EstimatesScreen: View {
    let accessToken: String?

    @State private var money: MoneyResponse?
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingEstimateCreate = false

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    FieldLGXMobileHeader(
                        eyebrow: "Sales command",
                        title: "Estimates",
                        subtitle: "Create quotes, track follow-ups, attach photos, and move accepted work into the schedule."
                    ) {
                        Button {
                            showingEstimateCreate = true
                        } label: {
                            Image(systemName: "plus")
                                .font(.system(size: 21, weight: .black))
                                .foregroundStyle(.black)
                                .frame(width: 52, height: 52)
                                .background(FieldLGXTheme.lime)
                                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                        }
                        .accessibilityLabel("Create estimate")
                    }

                    if isLoading && money == nil {
                        ProgressView()
                            .tint(FieldLGXTheme.lime)
                            .frame(maxWidth: .infinity, minHeight: 220)
                    } else if let money {
                        estimateCommandPanel(money)
                        estimateList(money.estimates)
                    } else if let errorMessage {
                        Text(errorMessage)
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundStyle(FieldLGXTheme.secondaryText)
                            .fieldPanel()
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, FieldLGXTheme.ownerTopOffset)
                .padding(.bottom, 18)
            }
            .refreshable {
                await loadEstimates()
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .navigationBarBackButtonHidden(true)
        .sheet(isPresented: $showingEstimateCreate) {
            CreateEstimateSheet(accessToken: accessToken) {
                await loadEstimates()
            }
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
        .task {
            await loadEstimates()
        }
    }

    private func estimateCommandPanel(_ money: MoneyResponse) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("QUOTE QUEUE")
                        .font(.system(size: 11, weight: .black))
                        .tracking(2)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                    Text(primaryEstimateTitle(money.estimates))
                        .font(.system(size: 24, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 8)

                Text("\(money.estimates.count)")
                    .font(.system(size: 26, weight: .black, design: .rounded))
                    .foregroundStyle(.black)
                    .frame(width: 52, height: 52)
                    .background(FieldLGXTheme.lime)
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            }

            HStack(spacing: 8) {
                estimateMetric("Open", value: money.summary.openEstimates)
                estimateMetric("Drafts", value: money.estimates.filter { $0.status.lowercased() == "draft" }.count)
                estimateMetric("Sent", value: money.estimates.filter { $0.status.lowercased() == "sent" }.count)
            }

            Button {
                showingEstimateCreate = true
            } label: {
                Label("Create estimate", systemImage: "doc.badge.plus")
                    .font(.system(size: 16, weight: .black))
                    .foregroundStyle(.black)
                    .frame(maxWidth: .infinity)
                    .frame(height: 52)
                    .background(FieldLGXTheme.lime)
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
        }
        .fieldPanel(padding: 16)
    }

    private func estimateMetric(_ label: String, value: Int) -> some View {
        HStack(spacing: 6) {
            Text(label)
                .font(.system(size: 11, weight: .black))
            Text("\(value)")
                .font(.system(size: 12, weight: .black))
                .foregroundStyle(value == 0 ? FieldLGXTheme.secondaryText : FieldLGXTheme.lime)
        }
        .foregroundStyle(FieldLGXTheme.text)
        .padding(.horizontal, 10)
        .frame(maxWidth: .infinity)
        .frame(height: 36)
        .background(FieldLGXTheme.elevatedBackground)
        .clipShape(Capsule())
        .overlay(Capsule().stroke(FieldLGXTheme.panelStroke, lineWidth: 1))
    }

    private func primaryEstimateTitle(_ estimates: [MobileEstimate]) -> String {
        let draftCount = estimates.filter { $0.status.lowercased() == "draft" }.count
        let sentCount = estimates.filter { $0.status.lowercased() == "sent" }.count
        if draftCount > 0 {
            return "\(draftCount) draft \(draftCount == 1 ? "quote" : "quotes") to finish"
        }
        if sentCount > 0 {
            return "\(sentCount) sent \(sentCount == 1 ? "quote" : "quotes") to follow"
        }
        if estimates.isEmpty {
            return "No active estimates"
        }
        return "\(estimates.count) estimates in motion"
    }

    private func estimateList(_ estimates: [MobileEstimate]) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 5) {
                    Text("ESTIMATES")
                        .font(.system(size: 12, weight: .black))
                        .tracking(2.2)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                    Text("Quote pipeline")
                        .font(.system(size: 25, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                }
                Spacer()
                Text("\(estimates.count)")
                    .font(.system(size: 15, weight: .black))
                    .foregroundStyle(FieldLGXTheme.lime)
            }

            if estimates.isEmpty {
                Text("No estimates yet.")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(FieldLGXTheme.elevatedBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
            } else {
                ForEach(estimates) { estimate in
                    NavigationLink {
                        EstimateDetailScreen(estimateID: estimate.id, accessToken: accessToken, previewEstimate: estimate)
                    } label: {
                        estimateRow(estimate)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .fieldPanel()
    }

    private func estimateRow(_ estimate: MobileEstimate) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "doc.badge.plus")
                .font(.system(size: 17, weight: .black))
                .foregroundStyle(FieldLGXTheme.lime)
                .frame(width: 42, height: 42)
                .background(FieldLGXTheme.lime.opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: 15, style: .continuous))

            VStack(alignment: .leading, spacing: 4) {
                Text(estimate.title)
                    .font(.system(size: 16, weight: .black, design: .rounded))
                    .foregroundStyle(FieldLGXTheme.text)
                    .lineLimit(1)
                Text(estimate.customer.name)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .lineLimit(1)
            }

            Spacer(minLength: 0)

            VStack(alignment: .trailing, spacing: 4) {
                Text("$\(estimate.total)")
                    .font(.system(size: 15, weight: .black, design: .rounded))
                    .foregroundStyle(FieldLGXTheme.text)
                Text(estimate.status.capitalized)
                    .font(.system(size: 11, weight: .black))
                    .foregroundStyle(FieldLGXTheme.lime)
            }
        }
        .padding(14)
        .background(FieldLGXTheme.elevatedBackground)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func loadEstimates() async {
        guard let accessToken, accessToken != "preview-token" else {
            money = .preview
            return
        }

        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            money = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).money()
        } catch {
            errorMessage = "Could not load estimates."
        }
    }
}

struct CreateInvoiceSheet: View {
    let accessToken: String?
    let defaultCardPaymentEnabled: Bool
    let onCreated: () async -> Void

    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @State private var clients: [MobileClient] = []
    @State private var selectedClientID: Int?
    @State private var dueDate = Date()
    @State private var enableCardPayment: Bool
    @State private var lineItems = [MoneyDraftLineItem(unit: "visit")]
    @State private var isSaving = false
    @State private var errorMessage: String?
    @State private var statusMessage: String?
    @State private var showingCreateClient = false

    init(accessToken: String?, defaultCardPaymentEnabled: Bool, onCreated: @escaping () async -> Void) {
        self.accessToken = accessToken
        self.defaultCardPaymentEnabled = defaultCardPaymentEnabled
        self.onCreated = onCreated
        _enableCardPayment = State(initialValue: defaultCardPaymentEnabled)
    }

    var body: some View {
        MoneyCreateShell(title: "Create invoice", eyebrow: "NEW INVOICE", errorMessage: errorMessage, statusMessage: statusMessage) {
            clientPicker
            createClientButton
            DatePicker("Due date", selection: $dueDate, displayedComponents: .date)
                .font(.system(size: 16, weight: .bold))
                .foregroundStyle(FieldLGXTheme.text)
                .padding(16)
                .background(FieldLGXTheme.panel)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            Toggle("Card payment", isOn: $enableCardPayment)
                .font(.system(size: 16, weight: .bold))
                .foregroundStyle(FieldLGXTheme.text)
                .padding(16)
                .background(FieldLGXTheme.panel)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            invoiceLineItems
            saveButton("Create invoice") { await save() }
        }
        .task { await loadClients() }
        .sheet(isPresented: $showingCreateClient) {
            CreateClientSheet(accessToken: accessToken) { response in
                await loadClients(selecting: response.client.id)
            }
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
    }

    private var clientPicker: some View {
        VStack(alignment: .leading, spacing: 6) {
            moneyLabel("Client")
            Picker("Client", selection: $selectedClientID) {
                Text("Select").tag(Int?.none)
                ForEach(clients) { client in
                    Text(client.name).tag(Optional(client.id))
                }
            }
            .pickerStyle(.menu)
            .tint(FieldLGXTheme.text)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(FieldLGXTheme.panel)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
    }

    private var createClientButton: some View {
        Button {
            showingCreateClient = true
        } label: {
            Label("Create new client", systemImage: "person.badge.plus")
                .font(.system(size: 16, weight: .black))
                .foregroundStyle(FieldLGXTheme.text)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
            .background(FieldLGXTheme.elevatedBackground)
            .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        }
    }

    private func saveButton(_ title: String, action: @escaping () async -> Void) -> some View {
        Button {
            Task { await action() }
        } label: {
            HStack {
                if isSaving { ProgressView().tint(.black) }
                Text(isSaving ? "Saving" : title)
                Spacer()
                Image(systemName: "arrow.right")
            }
            .font(.system(size: 17, weight: .black))
            .foregroundStyle(.black)
            .padding(.horizontal, 16)
            .frame(height: 54)
            .background(FieldLGXTheme.lime)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .disabled(selectedClientID == nil || !hasValidLineItems || isSaving)
    }

    private var invoiceLineItems: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                moneyLabel("Line items")
                Spacer()
                Button {
                    lineItems.append(MoneyDraftLineItem(unit: "visit"))
                } label: {
                    Label("Add item", systemImage: "plus")
                        .font(.system(size: 13, weight: .black))
                        .foregroundStyle(.black)
                        .padding(.horizontal, 12)
                        .frame(height: 34)
                        .background(FieldLGXTheme.lime)
                        .clipShape(Capsule())
                }
            }

            ForEach($lineItems) { $item in
                lineItemEditor(item: $item, canRemove: lineItems.count > 1)
            }
        }
    }

    private func lineItemEditor(item: Binding<MoneyDraftLineItem>, canRemove: Bool) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Service item")
                    .font(.system(size: 13, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                Spacer()
                if canRemove {
                    Button {
                        lineItems.removeAll { $0.id == item.wrappedValue.id }
                    } label: {
                        Image(systemName: "minus")
                            .font(.system(size: 13, weight: .black))
                            .foregroundStyle(FieldLGXTheme.text)
                            .frame(width: 30, height: 30)
                            .background(FieldLGXTheme.elevatedBackground)
                            .clipShape(Circle())
                    }
                    .accessibilityLabel("Remove line item")
                }
            }
            moneyField("Line item", text: item.description)
            moneyField("Description", text: item.detailDescription, axis: .vertical)
            HStack(spacing: 10) {
                moneyField("Qty", text: item.quantity)
                moneyField("Price", text: item.unitPrice)
            }
        }
        .padding(14)
        .background(FieldLGXTheme.panelGradient)
        .clipShape(RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private var hasValidLineItems: Bool {
        lineItems.contains { $0.isReady }
    }

    private func loadClients(selecting preferredID: Int? = nil) async {
        guard let accessToken, accessToken != "preview-token" else {
            clients = [.preview]
            selectedClientID = clients.first?.id
            return
        }
        do {
            let response = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).clients()
            clients = response.clients
            selectedClientID = preferredID ?? clients.first?.id
        } catch {
            errorMessage = "Could not load clients."
        }
    }

    private func save() async {
        guard let clientID = selectedClientID else { return }
        guard let accessToken, accessToken != "preview-token" else {
            dismiss()
            return
        }
        isSaving = true
        errorMessage = nil
        statusMessage = nil
        defer { isSaving = false }
        let payload = invoicePayload(clientID: clientID)
        do {
            _ = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).createInvoice(payload: payload)
            await onCreated()
            dismiss()
        } catch {
            do {
                try SyncQueue(modelContext: modelContext).enqueue(
                    entityType: "invoice",
                    serverID: nil,
                    operation: .create,
                    payload: payload,
                    baseRevision: nil
                )
                statusMessage = "Saved offline. This invoice will sync when service is back."
                await onCreated()
                dismiss()
            } catch {
                errorMessage = "Could not create this invoice or save it offline."
            }
        }
    }

    private func invoicePayload(clientID: Int) -> [String: Any] {
        [
            "customer_id": clientID,
            "due_date": Self.dayFormatter.string(from: dueDate),
            "enable_card_payment": enableCardPayment,
            "line_items": lineItems.filter(\.isReady).map(\.payload)
        ]
    }

    private static let dayFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()
}

struct CreateEstimateSheet: View {
    let accessToken: String?
    let onCreated: () async -> Void

    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @State private var clients: [MobileClient] = []
    @State private var selectedClientID: Int?
    @State private var title = ""
    @State private var notes = ""
    @State private var validUntil = Date()
    @State private var depositRequired = false
    @State private var depositAmount = ""
    @State private var lineItems = [MoneyDraftLineItem(unit: "project")]
    @State private var isSaving = false
    @State private var errorMessage: String?
    @State private var statusMessage: String?
    @State private var showingCreateClient = false

    var body: some View {
        MoneyCreateShell(title: "Create estimate", eyebrow: "NEW ESTIMATE", errorMessage: errorMessage, statusMessage: statusMessage) {
            clientPicker
            createClientButton
            moneyField("Title", text: $title)
            moneyField("Notes", text: $notes, axis: .vertical)
            DatePicker("Valid until", selection: $validUntil, displayedComponents: .date)
                .font(.system(size: 16, weight: .bold))
                .foregroundStyle(FieldLGXTheme.text)
                .padding(16)
                .background(FieldLGXTheme.panel)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            Toggle("Require deposit", isOn: $depositRequired)
                .font(.system(size: 16, weight: .bold))
                .foregroundStyle(FieldLGXTheme.text)
                .padding(16)
                .background(FieldLGXTheme.panel)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            if depositRequired {
                moneyField("Deposit amount", text: $depositAmount)
            }
            estimateLineItems
            saveButton("Create estimate") { await save() }
        }
        .task { await loadClients() }
        .sheet(isPresented: $showingCreateClient) {
            CreateClientSheet(accessToken: accessToken) { response in
                await loadClients(selecting: response.client.id)
            }
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
    }

    private var clientPicker: some View {
        VStack(alignment: .leading, spacing: 6) {
            moneyLabel("Client")
            Picker("Client", selection: $selectedClientID) {
                Text("Select").tag(Int?.none)
                ForEach(clients) { client in
                    Text(client.name).tag(Optional(client.id))
                }
            }
            .pickerStyle(.menu)
            .tint(FieldLGXTheme.text)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(FieldLGXTheme.panel)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
    }

    private var createClientButton: some View {
        Button {
            showingCreateClient = true
        } label: {
            Label("Create new client", systemImage: "person.badge.plus")
                .font(.system(size: 16, weight: .black))
                .foregroundStyle(FieldLGXTheme.text)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(FieldLGXTheme.elevatedBackground)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
    }

    private func saveButton(_ title: String, action: @escaping () async -> Void) -> some View {
        Button {
            Task { await action() }
        } label: {
            HStack {
                if isSaving { ProgressView().tint(.black) }
                Text(isSaving ? "Saving" : title)
                Spacer()
                Image(systemName: "arrow.right")
            }
            .font(.system(size: 17, weight: .black))
            .foregroundStyle(.black)
            .padding(.horizontal, 16)
            .frame(height: 54)
            .background(FieldLGXTheme.lime)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .disabled(selectedClientID == nil || title.isEmpty || !hasValidLineItems || isSaving)
    }

    private var estimateLineItems: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                moneyLabel("Line items")
                Spacer()
                Button {
                    lineItems.append(MoneyDraftLineItem(unit: "project"))
                } label: {
                    Label("Add item", systemImage: "plus")
                        .font(.system(size: 13, weight: .black))
                        .foregroundStyle(.black)
                        .padding(.horizontal, 12)
                        .frame(height: 34)
                        .background(FieldLGXTheme.lime)
                        .clipShape(Capsule())
                }
            }

            ForEach($lineItems) { $item in
                estimateLineItemEditor(item: $item, canRemove: lineItems.count > 1)
            }
        }
    }

    private func estimateLineItemEditor(item: Binding<MoneyDraftLineItem>, canRemove: Bool) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Estimate item")
                    .font(.system(size: 13, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                Spacer()
                Toggle("Optional", isOn: item.isOptional)
                    .labelsHidden()
                    .tint(FieldLGXTheme.lime)
                if canRemove {
                    Button {
                        lineItems.removeAll { $0.id == item.wrappedValue.id }
                    } label: {
                        Image(systemName: "minus")
                            .font(.system(size: 13, weight: .black))
                            .foregroundStyle(FieldLGXTheme.text)
                            .frame(width: 30, height: 30)
                            .background(FieldLGXTheme.elevatedBackground)
                            .clipShape(Circle())
                    }
                    .accessibilityLabel("Remove line item")
                }
            }
            moneyField("Line item", text: item.description)
            moneyField("Description", text: item.detailDescription, axis: .vertical)
            HStack(spacing: 10) {
                moneyField("Qty", text: item.quantity)
                moneyField("Unit", text: item.unit)
                moneyField("Price", text: item.unitPrice)
            }
        }
        .padding(14)
        .background(FieldLGXTheme.panelGradient)
        .clipShape(RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private var hasValidLineItems: Bool {
        lineItems.contains { $0.isReady }
    }

    private func loadClients(selecting preferredID: Int? = nil) async {
        guard let accessToken, accessToken != "preview-token" else {
            clients = [.preview]
            selectedClientID = clients.first?.id
            return
        }
        do {
            let response = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).clients()
            clients = response.clients
            selectedClientID = preferredID ?? clients.first?.id
        } catch {
            errorMessage = "Could not load clients."
        }
    }

    private func save() async {
        guard let clientID = selectedClientID else { return }
        guard let accessToken, accessToken != "preview-token" else {
            dismiss()
            return
        }
        isSaving = true
        errorMessage = nil
        statusMessage = nil
        defer { isSaving = false }
        let payload = estimatePayload(clientID: clientID)
        do {
            _ = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).createEstimate(payload: payload)
            await onCreated()
            dismiss()
        } catch {
            do {
                try SyncQueue(modelContext: modelContext).enqueue(
                    entityType: "estimate",
                    serverID: nil,
                    operation: .create,
                    payload: payload,
                    baseRevision: nil
                )
                statusMessage = "Saved offline. This estimate will sync when service is back."
                await onCreated()
                dismiss()
            } catch {
                errorMessage = "Could not create this estimate or save it offline."
            }
        }
    }

    private func estimatePayload(clientID: Int) -> [String: Any] {
        [
            "customer_id": clientID,
            "title": title,
            "notes": notes,
            "valid_until": Self.dayFormatter.string(from: validUntil),
            "deposit_required": depositRequired,
            "deposit_type": "fixed",
            "deposit_amount": depositAmount,
            "line_items": lineItems.filter(\.isReady).map(\.payload)
        ]
    }

    private static let dayFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()
}

struct CreateReceiptSheet: View {
    let accessToken: String?

    @Environment(\.dismiss) private var dismiss
    @State private var photoItem: PhotosPickerItem?
    @State private var photoData: Data?
    @State private var vendor = ""
    @State private var amount = ""
    @State private var receiptDate = Self.defaultDate
    @State private var description = ""
    @State private var category = "materials"
    @State private var isSaving = false
    @State private var errorMessage: String?
    @State private var statusMessage: String?

    private static var defaultDate: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: Date())
    }

    var body: some View {
        MoneyCreateShell(title: "Add receipt", eyebrow: "FIELD COST", errorMessage: errorMessage, statusMessage: statusMessage) {
            PhotosPicker(selection: $photoItem, matching: .images) {
                HStack {
                    Image(systemName: photoData == nil ? "photo.badge.plus" : "checkmark.circle.fill")
                    Text(photoData == nil ? "Choose receipt photo" : "Receipt photo ready")
                    Spacer()
                    Image(systemName: "arrow.up.circle.fill")
                }
                .font(.system(size: 17, weight: .black))
                .foregroundStyle(.black)
                .padding(.horizontal, 16)
                .frame(height: 58)
                .background(FieldLGXTheme.lime)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
            .onChange(of: photoItem) { _, newItem in
                guard let newItem else { return }
                Task {
                    photoData = try? await newItem.loadTransferable(type: Data.self)
                }
            }

            receiptField("Vendor", text: $vendor, placeholder: "Landscape Supply")
            receiptField("Amount", text: $amount, placeholder: "42.18", keyboard: .decimalPad)
            receiptField("Receipt date", text: $receiptDate, placeholder: "2026-05-06")
            receiptField("Description", text: $description, placeholder: "Mulch, fuel, materials")
            categoryMenu
            saveButton
        }
    }

    private var categoryMenu: some View {
        Menu {
            ForEach(receiptCategories, id: \.value) { categoryOption in
                Button(categoryOption.label) {
                    category = categoryOption.value
                }
            }
        } label: {
            HStack {
                Text("Category")
                Spacer()
                Text(receiptCategories.first { $0.value == category }?.label ?? "Other")
                    .foregroundStyle(FieldLGXTheme.text)
                Image(systemName: "chevron.down")
            }
            .font(.system(size: 15, weight: .bold))
            .foregroundStyle(FieldLGXTheme.secondaryText)
            .padding(16)
            .background(FieldLGXTheme.elevatedBackground)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
    }

    private var receiptCategories: [(value: String, label: String)] {
        [
            ("materials", "Materials"),
            ("fuel", "Fuel"),
            ("equipment", "Equipment"),
            ("supplies", "Supplies"),
            ("labor", "Labor"),
            ("other", "Other")
        ]
    }

    private func receiptField(_ label: String, text: Binding<String>, placeholder: String, keyboard: UIKeyboardType = .default) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label.uppercased())
                .font(.system(size: 11, weight: .black))
                .tracking(1.8)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            TextField(placeholder, text: text)
                .keyboardType(keyboard)
                .textInputAutocapitalization(.words)
                .font(.system(size: 17, weight: .bold))
                .foregroundStyle(FieldLGXTheme.text)
                .padding(16)
                .background(FieldLGXTheme.elevatedBackground)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
    }

    private var saveButton: some View {
        Button {
            Task { await save() }
        } label: {
            HStack {
                if isSaving {
                    ProgressView()
                        .tint(.black)
                } else {
                    Image(systemName: "checkmark.circle.fill")
                }
                Text(isSaving ? "Saving" : "Save receipt")
                Spacer()
            }
            .font(.system(size: 17, weight: .black))
            .foregroundStyle(.black)
            .padding(.horizontal, 16)
            .frame(height: 58)
            .background(FieldLGXTheme.lime)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .disabled(isSaving)
        .opacity(isSaving ? 0.55 : 1)
    }

    private func save() async {
        errorMessage = nil
        statusMessage = nil
        guard let photoData else {
            errorMessage = "Choose a receipt photo first."
            return
        }
        guard let accessToken, accessToken != "preview-token" else {
            statusMessage = "Receipt saved."
            return
        }
        isSaving = true
        defer { isSaving = false }

        do {
            _ = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
                .uploadReceipt(
                    imageData: photoData,
                    receiptDate: receiptDate,
                    amount: amount,
                    vendor: vendor,
                    description: description,
                    category: category
                )
            statusMessage = "Receipt saved to financials."
            dismiss()
        } catch {
            errorMessage = "Could not save this receipt."
        }
    }
}

private struct MoneyCreateShell<Content: View>: View {
    let title: String
    let eyebrow: String
    let errorMessage: String?
    var statusMessage: String? = nil
    @ViewBuilder var content: () -> Content

    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ZStack {
                FieldLGXScreenBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        Text(eyebrow)
                            .font(.system(size: 12, weight: .black))
                            .tracking(2.4)
                            .foregroundStyle(FieldLGXTheme.lime)
                        Text(title)
                            .font(.system(size: 34, weight: .black, design: .rounded))
                            .foregroundStyle(FieldLGXTheme.text)
                        content()
                        if let errorMessage {
                            Text(errorMessage)
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(.red)
                        }
                        if let statusMessage {
                            Text(statusMessage)
                                .font(.system(size: 14, weight: .bold))
                                .foregroundStyle(FieldLGXTheme.lime)
                        }
                    }
                    .padding(24)
                }
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

private func moneyLabel(_ text: String) -> some View {
    Text(text.uppercased())
        .font(.system(size: 10, weight: .black))
        .tracking(1.8)
        .foregroundStyle(FieldLGXTheme.tertiaryText)
}

private func moneyField(_ label: String, text: Binding<String>, axis: Axis = .horizontal) -> some View {
    VStack(alignment: .leading, spacing: 6) {
        moneyLabel(label)
        TextField(label, text: text, axis: axis)
            .font(.system(size: 16, weight: .semibold))
            .foregroundStyle(FieldLGXTheme.text)
            .padding(14)
            .background(FieldLGXTheme.panel)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
            )
    }
}
