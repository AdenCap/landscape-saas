import SwiftUI

struct InvoiceDetailScreen: View {
    let invoiceID: Int
    let accessToken: String?
    let previewInvoice: MobileInvoice?

    @Environment(\.dismiss) private var dismiss
    @State private var detail: InvoiceDetailResponse?
    @State private var isLoading = false
    @State private var isActing = false
    @State private var errorMessage: String?
    @State private var actionMessage: String?

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    topBar

                    if isLoading && detail == nil {
                        ProgressView()
                            .tint(FieldLGXTheme.lime)
                            .frame(maxWidth: .infinity, minHeight: 220)
                    } else if let detail {
                        hero(detail.invoice, summary: detail.summary)
                        actionPanel(detail.invoice)
                        lineItems(detail.lineItems)
                    } else if let errorMessage {
                        errorState(errorMessage)
                    }
                }
                .padding(.horizontal, 24)
                .padding(.top, 16)
                .padding(.bottom, 18)
            }
            .refreshable {
                await loadDetail()
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .task {
            await loadDetail()
        }
    }

    private var topBar: some View {
        HStack {
            Button {
                dismiss()
            } label: {
                Label("Money", systemImage: "chevron.left")
                    .font(.system(size: 15, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 11)
                    .background(FieldLGXTheme.elevatedBackground)
                    .clipShape(Capsule())
            }
            Spacer()
        }
    }

    private func hero(_ invoice: MobileInvoice, summary: InvoiceSummary) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("INVOICE")
                .font(.system(size: 12, weight: .black))
                .tracking(2.4)
                .foregroundStyle(FieldLGXTheme.lime)

            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(invoice.number)
                        .font(.system(size: 42, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                    Text(invoice.customer.name)
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                }
                Spacer()
                statusPill(invoice.status)
            }

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                metric("Total", "$\(summary.total)")
                metric("Subtotal", "$\(summary.subtotal)")
                metric("Due", invoice.dueDate ?? "No date")
                metric("Paid items", "\(summary.paidItems)/\(summary.lineItems)")
            }

            if invoice.enableCardPayment {
                Label("Card payment enabled", systemImage: "creditcard.fill")
                    .font(.system(size: 14, weight: .black))
                    .foregroundStyle(FieldLGXTheme.lime)
            }

            if let actionMessage {
                Text(actionMessage)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(20)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func actionPanel(_ invoice: MobileInvoice) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("NEXT ACTION")
                .font(.system(size: 12, weight: .black))
                .tracking(2.2)
                .foregroundStyle(FieldLGXTheme.tertiaryText)

            Button {
                Task { await runInvoiceAction(invoice.status.lowercased() == "draft" ? "send" : "reminder") }
            } label: {
                HStack {
                    if isActing {
                        ProgressView()
                            .tint(.black)
                    } else {
                        Image(systemName: invoice.status.lowercased() == "draft" ? "paperplane.fill" : "bell.badge.fill")
                    }
                    Text(invoice.status.lowercased() == "draft" ? "Send invoice" : "Send reminder")
                    Spacer()
                    Image(systemName: "arrow.right")
                }
                .font(.system(size: 17, weight: .black))
                .foregroundStyle(.black)
                .padding(.horizontal, 16)
                .frame(height: 56)
                .background(FieldLGXTheme.lime)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
            .disabled(isActing || invoice.status.lowercased() == "paid")
            .opacity(invoice.status.lowercased() == "paid" ? 0.45 : 1)
        }
        .padding(18)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func lineItems(_ items: [MoneyLineItem]) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("LINE ITEMS")
                .font(.system(size: 12, weight: .black))
                .tracking(2.2)
                .foregroundStyle(FieldLGXTheme.tertiaryText)

            if items.isEmpty {
                Text("No line items yet.")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(FieldLGXTheme.elevatedBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            } else {
                ForEach(items) { item in
                    MoneyLineItemRow(item: item) {
                        Task { await setLineItem(item, paid: !item.isPaid) }
                    }
                }
            }
        }
        .padding(18)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func metric(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label.uppercased())
                .font(.system(size: 10, weight: .black))
                .tracking(1.7)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            Text(value)
                .font(.system(size: 18, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .padding(13)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(FieldLGXTheme.elevatedBackground)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private func statusPill(_ status: String) -> some View {
        Text(status.capitalized)
            .font(.system(size: 12, weight: .black))
            .foregroundStyle(.black)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(FieldLGXTheme.lime)
            .clipShape(Capsule())
    }

    private func errorState(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Could not load invoice")
                .font(.system(size: 22, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
            Text(message)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(FieldLGXTheme.secondaryText)
        }
        .padding(18)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private func loadDetail() async {
        guard let accessToken, accessToken != "preview-token" else {
            if let previewInvoice {
                detail = .preview(invoice: previewInvoice)
            }
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            detail = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
                .invoiceDetail(id: invoiceID)
        } catch {
            errorMessage = "Check the connection and try again."
        }
    }

    private func runInvoiceAction(_ action: String) async {
        guard let accessToken, accessToken != "preview-token" else {
            actionMessage = action == "send" ? "Invoice marked ready to send." : "Reminder queued for this invoice."
            return
        }
        isActing = true
        actionMessage = nil
        defer { isActing = false }

        do {
            let response = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
                .invoiceAction(id: invoiceID, action: action)
            if let message = response.result.message {
                actionMessage = message
            } else if let email = response.result.email, action == "send" {
                actionMessage = "Invoice sent to \(email)."
            } else {
                actionMessage = action == "send" ? "Invoice sent." : "Reminder queued."
            }
            await loadDetail()
        } catch {
            actionMessage = action == "send" ? "Could not send invoice." : "Could not send reminder."
        }
    }

    private func setLineItem(_ item: MoneyLineItem, paid: Bool) async {
        guard let accessToken, accessToken != "preview-token" else {
            actionMessage = paid ? "Line item marked paid." : "Line item reopened."
            return
        }
        isActing = true
        actionMessage = nil
        defer { isActing = false }

        do {
            detail = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
                .setInvoiceLineItemPaid(invoiceID: invoiceID, itemID: item.id, paid: paid, paymentMethod: paid ? "card" : "")
            actionMessage = paid ? "Line item marked paid." : "Line item reopened."
        } catch {
            actionMessage = "Could not update line item payment."
        }
    }
}

struct MoneyLineItemRow: View {
    let item: MoneyLineItem
    var onTogglePaid: (() -> Void)?

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 5) {
                HStack(spacing: 8) {
                    Text(item.description)
                        .font(.system(size: 17, weight: .black))
                        .foregroundStyle(FieldLGXTheme.text)
                    if item.isOptional {
                        chip("Optional")
                    }
                    if item.isPaid {
                        chip("Paid")
                    }
                }
                if !item.detailDescription.isEmpty {
                    Text(item.detailDescription)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Text("\(item.quantity) \(item.unit)")
                    .font(.system(size: 12, weight: .black))
                    .foregroundStyle(FieldLGXTheme.tertiaryText)
            }

            Spacer()

            Text("$\(item.lineTotal)")
                .font(.system(size: 16, weight: .black))
                .foregroundStyle(FieldLGXTheme.text)
        }
        .padding(16)
        .background(FieldLGXTheme.elevatedBackground)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(alignment: .bottomTrailing) {
            if let onTogglePaid {
                Button(action: onTogglePaid) {
                    Text(item.isPaid ? "Mark unpaid" : "Mark paid")
                        .font(.system(size: 11, weight: .black))
                        .foregroundStyle(item.isPaid ? FieldLGXTheme.text : .black)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 7)
                        .background(item.isPaid ? FieldLGXTheme.panel : FieldLGXTheme.lime)
                        .clipShape(Capsule())
                }
                .padding(10)
            }
        }
    }

    private func chip(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 10, weight: .black))
            .foregroundStyle(FieldLGXTheme.lime)
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(FieldLGXTheme.lime.opacity(0.12))
            .clipShape(Capsule())
    }
}

private extension InvoiceDetailResponse {
    static func preview(invoice: MobileInvoice) -> InvoiceDetailResponse {
        InvoiceDetailResponse(
            invoice: invoice,
            summary: InvoiceSummary(subtotal: invoice.total, tax: "0.00", total: invoice.total, paidItems: 0, lineItems: 1),
            lineItems: [
                MoneyLineItem(
                    id: 1,
                    description: "Mowing service",
                    detailDescription: "Weekly maintenance visit",
                    quantity: "1",
                    unit: "visit",
                    unitPrice: invoice.total,
                    lineTotal: invoice.total,
                    isPaid: false,
                    isOptional: false,
                    isDiscount: false
                )
            ],
            serverTime: ""
        )
    }
}
