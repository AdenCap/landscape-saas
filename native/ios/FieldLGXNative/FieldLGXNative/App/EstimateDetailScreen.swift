import SwiftUI
import PhotosUI

struct EstimateDetailScreen: View {
    let estimateID: Int
    let accessToken: String?
    let previewEstimate: MobileEstimate?

    @Environment(\.dismiss) private var dismiss
    @State private var detail: EstimateDetailResponse?
    @State private var isLoading = false
    @State private var isActing = false
    @State private var errorMessage: String?
    @State private var actionMessage: String?
    @State private var estimatePhotoItem: PhotosPickerItem?
    @State private var isUploadingPhoto = false

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
                        hero(detail.estimate, summary: detail.summary, deposit: detail.deposit)
                        actionPanel(detail.estimate)
                        photoPanel(detail.estimate)
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
        .onChange(of: estimatePhotoItem) { _, newItem in
            guard let newItem else { return }
            Task {
                await uploadEstimatePhoto(newItem)
            }
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

    private func hero(_ estimate: MobileEstimate, summary: EstimateSummary, deposit: EstimateDeposit) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("ESTIMATE")
                .font(.system(size: 12, weight: .black))
                .tracking(2.4)
                .foregroundStyle(FieldLGXTheme.lime)

            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(estimate.title)
                        .font(.system(size: 34, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                        .lineLimit(3)
                        .minimumScaleFactor(0.75)
                    Text(estimate.customer.name)
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                }
                Spacer()
                statusPill(estimate.status)
            }

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                metric("Total", "$\(summary.total)")
                metric("Base", "$\(summary.baseTotal)")
                metric("Add-ons", "$\(summary.addonsTotal)")
                metric("Valid", estimate.validUntil ?? "No date")
            }

            if deposit.required {
                HStack {
                    Label("Deposit due", systemImage: "creditcard.fill")
                    Spacer()
                    Text("$\(deposit.amountDue)")
                }
                .font(.system(size: 15, weight: .black))
                .foregroundStyle(deposit.paid ? FieldLGXTheme.secondaryText : FieldLGXTheme.lime)
                .padding(14)
                .background(FieldLGXTheme.elevatedBackground)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
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

    private func actionPanel(_ estimate: MobileEstimate) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("NEXT ACTION")
                .font(.system(size: 12, weight: .black))
                .tracking(2.2)
                .foregroundStyle(FieldLGXTheme.tertiaryText)

            if estimate.status.lowercased() == "draft" {
                estimateButton(title: "Mark sent", systemImage: "paperplane.fill", action: "mark_sent", filled: true)
            }
            estimateButton(title: "Send follow-up", systemImage: "arrow.triangle.2.circlepath", action: "followup", filled: estimate.status.lowercased() != "draft")
                .disabled(estimate.status.lowercased() == "accepted" || isActing)
                .opacity(estimate.status.lowercased() == "accepted" ? 0.45 : 1)
        }
        .padding(18)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func estimateButton(title: String, systemImage: String, action: String, filled: Bool) -> some View {
        Button {
            Task { await runEstimateAction(action) }
        } label: {
            HStack {
                if isActing {
                    ProgressView()
                        .tint(filled ? .black : FieldLGXTheme.lime)
                } else {
                    Image(systemName: systemImage)
                }
                Text(title)
                Spacer()
                Image(systemName: "arrow.right")
            }
            .font(.system(size: 17, weight: .black))
            .foregroundStyle(filled ? .black : FieldLGXTheme.text)
            .padding(.horizontal, 16)
            .frame(height: 56)
            .background(filled ? FieldLGXTheme.lime : FieldLGXTheme.elevatedBackground)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .disabled(isActing)
    }

    private func photoPanel(_ estimate: MobileEstimate) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("PHOTOS")
                        .font(.system(size: 12, weight: .black))
                        .tracking(2.2)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                    Text("\(estimate.photoCount ?? 0) attached")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                }
                Spacer()
            }

            PhotosPicker(selection: $estimatePhotoItem, matching: .images) {
                HStack {
                    if isUploadingPhoto {
                        ProgressView()
                            .tint(.black)
                    } else {
                        Image(systemName: "photo.badge.plus")
                    }
                    Text("Add estimate photo")
                    Spacer()
                    Image(systemName: "arrow.up.circle.fill")
                }
                .font(.system(size: 17, weight: .black))
                .foregroundStyle(.black)
                .padding(.horizontal, 16)
                .frame(height: 56)
                .background(FieldLGXTheme.lime)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
            .disabled(isUploadingPhoto)

            Text("Attach property photos, site conditions, or visual notes before sending the quote.")
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(FieldLGXTheme.tertiaryText)
                .fixedSize(horizontal: false, vertical: true)
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
                Text("No estimate items yet.")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(FieldLGXTheme.elevatedBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            } else {
                ForEach(items) { item in
                    MoneyLineItemRow(item: item)
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
            Text("Could not load estimate")
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
            if let previewEstimate {
                detail = .preview(estimate: previewEstimate)
            }
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            detail = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
                .estimateDetail(id: estimateID)
        } catch {
            errorMessage = "Check the connection and try again."
        }
    }

    private func runEstimateAction(_ action: String) async {
        guard let accessToken, accessToken != "preview-token" else {
            actionMessage = action == "mark_sent" ? "Estimate marked sent." : "Follow-up queued for this estimate."
            return
        }
        isActing = true
        actionMessage = nil
        defer { isActing = false }

        do {
            _ = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
                .estimateAction(id: estimateID, action: action)
            actionMessage = action == "mark_sent" ? "Estimate marked sent." : "Follow-up queued."
            await loadDetail()
        } catch {
            actionMessage = action == "mark_sent" ? "Could not mark estimate sent." : "Could not send follow-up."
        }
    }

    private func uploadEstimatePhoto(_ item: PhotosPickerItem) async {
        isUploadingPhoto = true
        actionMessage = nil
        defer {
            isUploadingPhoto = false
            estimatePhotoItem = nil
        }

        guard let accessToken, accessToken != "preview-token" else {
            actionMessage = "Photo attached."
            return
        }
        do {
            guard let data = try await item.loadTransferable(type: Data.self) else {
                actionMessage = "Could not read that photo."
                return
            }
            _ = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
                .uploadEstimatePhoto(id: estimateID, imageData: data)
            actionMessage = "Photo attached to this estimate."
            await loadDetail()
        } catch {
            actionMessage = "Could not upload that photo."
        }
    }
}

private extension EstimateDetailResponse {
    static func preview(estimate: MobileEstimate) -> EstimateDetailResponse {
        EstimateDetailResponse(
            estimate: estimate,
            summary: EstimateSummary(baseTotal: estimate.total, addonsTotal: "0.00", total: estimate.total, lineItems: 1),
            deposit: EstimateDeposit(required: estimate.depositRequired, type: "fixed", amount: "150.00", amountDue: "150.00", paid: false),
            lineItems: [
                MoneyLineItem(
                    id: 1,
                    description: "Landscape refresh",
                    detailDescription: "Bed cleanup, edging, and mulch touch-up",
                    quantity: "1.00",
                    unit: "project",
                    unitPrice: estimate.total,
                    lineTotal: estimate.total,
                    isPaid: false,
                    isOptional: false,
                    isDiscount: false
                )
            ],
            serverTime: ""
        )
    }
}
