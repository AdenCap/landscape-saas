import SwiftUI
import PhotosUI

struct JobDetailScreen: View {
    let jobID: Int
    let accessToken: String?
    let previewJob: TodayJob?

    @Environment(\.dismiss) private var dismiss
    @State private var detail: JobDetailResponse?
    @State private var isLoading = false
    @State private var actionInFlight: JobAction?
    @State private var errorMessage: String?
    @State private var isShowingSkipSheet = false
    @State private var skipReason = ""
    @State private var completionPhotoItem: PhotosPickerItem?

    private enum JobAction {
        case start
        case complete
        case skip
        case uploadPhoto
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            FieldLGXTheme.background.ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    topBar

                    if isLoading && detail == nil {
                        ProgressView()
                            .tint(FieldLGXTheme.lime)
                            .frame(maxWidth: .infinity, minHeight: 260)
                    } else if let detail {
                        hero(detail.job)
                        actionPanel(detail)
                        contextSections(detail)
                    } else if let errorMessage {
                        errorState(errorMessage)
                    }
                }
                .padding(24)
                .padding(.bottom, 24)
            }
            .refreshable {
                await loadDetail()
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .task {
            await loadDetail()
        }
        .sheet(isPresented: $isShowingSkipSheet) {
            skipSheet
                .presentationDetents([.medium])
                .presentationDragIndicator(.visible)
        }
        .onChange(of: completionPhotoItem) { _, newItem in
            guard let newItem else { return }
            Task {
                await uploadCompletionPhoto(newItem)
            }
        }
    }

    private var topBar: some View {
        HStack {
            Button {
                dismiss()
            } label: {
                Label("Route", systemImage: "chevron.left")
                    .font(.system(size: 15, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 11)
                    .background(FieldLGXTheme.elevatedBackground)
                    .clipShape(Capsule())
            }
            .accessibilityLabel("Back to route")

            Spacer()
        }
    }

    private func hero(_ job: TodayJob) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 7) {
                Text(statusText(job.status))
                    .font(.system(size: 12, weight: .black))
                    .tracking(2.2)
                    .foregroundStyle(FieldLGXTheme.lime)

                Text(job.customer.name)
                    .font(.system(size: 42, weight: .black, design: .rounded))
                    .foregroundStyle(FieldLGXTheme.text)
                    .lineLimit(3)
                    .minimumScaleFactor(0.75)

                Text(job.property.address)
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
            }

            HStack(spacing: 10) {
                infoPill("TIME", job.scheduledTime ?? "Anytime")
                infoPill("CREW", job.assigned.crew ?? job.assigned.employee ?? "Unassigned")
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func actionPanel(_ detail: JobDetailResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("FIELD ACTIONS")
                .font(.system(size: 12, weight: .black))
                .tracking(2.2)
                .foregroundStyle(FieldLGXTheme.tertiaryText)

            HStack(spacing: 10) {
                actionButton(
                    title: "Start",
                    systemImage: "play.fill",
                    action: .start,
                    isEnabled: detail.actions.canStart
                ) {
                    await perform(.start)
                }

                actionButton(
                    title: "Complete",
                    systemImage: "checkmark",
                    action: .complete,
                    isEnabled: detail.actions.canComplete
                ) {
                    await perform(.complete)
                }
            }

            Button {
                isShowingSkipSheet = true
            } label: {
                Label("Skip job", systemImage: "forward.end.fill")
                    .font(.system(size: 16, weight: .black))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 15)
            }
            .disabled(!detail.actions.canSkip || actionInFlight != nil)
            .foregroundStyle(detail.actions.canSkip ? FieldLGXTheme.text : FieldLGXTheme.tertiaryText)
            .background(FieldLGXTheme.elevatedBackground)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))

            if detail.actions.requiresCompletionPhoto && !detail.actions.hasCompletionPhoto {
                VStack(alignment: .leading, spacing: 10) {
                    Label("Completion photo required before this can be marked done.", systemImage: "camera.fill")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(FieldLGXTheme.lime)

                    completionPhotoPicker(title: "Add completion photo", isPrimary: true)
                }
                .padding(.top, 2)
            } else {
                completionPhotoPicker(title: detail.actions.hasCompletionPhoto ? "Add another photo" : "Add photo proof", isPrimary: false)
            }

            if let errorMessage {
                Text(errorMessage)
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(Color.red.opacity(0.85))
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(16)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func completionPhotoPicker(title: String, isPrimary: Bool) -> some View {
        PhotosPicker(selection: $completionPhotoItem, matching: .images) {
            HStack(spacing: 9) {
                if actionInFlight == .uploadPhoto {
                    ProgressView()
                        .tint(isPrimary ? .black : FieldLGXTheme.lime)
                } else {
                    Image(systemName: "camera.fill")
                }
                Text(title)
            }
            .font(.system(size: 16, weight: .black))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .foregroundStyle(isPrimary ? .black : FieldLGXTheme.text)
            .background(isPrimary ? FieldLGXTheme.lime : FieldLGXTheme.elevatedBackground)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .disabled(actionInFlight != nil)
    }

    @ViewBuilder
    private func contextSections(_ detail: JobDetailResponse) -> some View {
        if !detail.job.alerts.isEmpty {
            detailSection(title: "Need to know") {
                ForEach(detail.job.alerts) { alert in
                    row(title: alert.label, value: alert.text, systemImage: "exclamationmark.circle")
                }
            }
        }

        if !detail.job.serviceItems.isEmpty {
            detailSection(title: "Work items") {
                ForEach(detail.job.serviceItems) { item in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(item.name)
                            .font(.system(size: 18, weight: .black, design: .rounded))
                            .foregroundStyle(FieldLGXTheme.text)
                        if !item.detailDescription.isEmpty {
                            Text(item.detailDescription)
                                .font(.system(size: 15, weight: .medium))
                                .foregroundStyle(FieldLGXTheme.secondaryText)
                        }
                        Text("\(item.quantity) \(item.unit)")
                            .font(.system(size: 13, weight: .bold))
                            .foregroundStyle(FieldLGXTheme.tertiaryText)
                    }
                    .padding(.vertical, 6)
                }
            }
        }

        detailSection(title: "Job notes") {
            if detail.job.notes.isEmpty && detail.jobNotes.isEmpty {
                Text("No notes on this job.")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
            } else {
                if !detail.job.notes.isEmpty {
                    row(title: "Job note", value: detail.job.notes, systemImage: "note.text")
                }
                ForEach(detail.jobNotes) { note in
                    row(title: note.author.isEmpty ? "Note" : note.author, value: note.text, systemImage: "text.bubble")
                }
            }
        }
    }

    private func detailSection<Content: View>(
        title: String,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title.uppercased())
                .font(.system(size: 12, weight: .black))
                .tracking(2.2)
                .foregroundStyle(FieldLGXTheme.tertiaryText)

            content()
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func row(title: String, value: String, systemImage: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: systemImage)
                .font(.system(size: 17, weight: .bold))
                .foregroundStyle(FieldLGXTheme.lime)
                .frame(width: 26)

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.system(size: 15, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                Text(value)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.vertical, 4)
    }

    private func infoPill(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.system(size: 10, weight: .black))
                .tracking(1.8)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            Text(value)
                .font(.system(size: 15, weight: .black))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(1)
                .minimumScaleFactor(0.75)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(FieldLGXTheme.elevatedBackground)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private func actionButton(
        title: String,
        systemImage: String,
        action: JobAction,
        isEnabled: Bool,
        run: @escaping () async -> Void
    ) -> some View {
        Button {
            Task { await run() }
        } label: {
            HStack(spacing: 8) {
                if actionInFlight == action {
                    ProgressView()
                        .tint(.black)
                } else {
                    Image(systemName: systemImage)
                }
                Text(title)
            }
            .font(.system(size: 16, weight: .black))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 15)
        }
        .disabled(!isEnabled || actionInFlight != nil)
        .foregroundStyle(.black)
        .background(isEnabled ? FieldLGXTheme.lime : FieldLGXTheme.tertiaryText)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private var skipSheet: some View {
        NavigationStack {
            ZStack {
                FieldLGXTheme.background.ignoresSafeArea()
                VStack(alignment: .leading, spacing: 16) {
                    Text("Why is this job being skipped?")
                        .font(.system(size: 24, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)

                    TextField("Customer requested next week", text: $skipReason, axis: .vertical)
                        .font(.system(size: 17, weight: .semibold))
                        .lineLimit(3...5)
                        .padding(16)
                        .foregroundStyle(FieldLGXTheme.text)
                        .background(FieldLGXTheme.elevatedBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))

                    Button {
                        Task { await performSkip() }
                    } label: {
                        Text("Skip job")
                            .font(.system(size: 17, weight: .black))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 16)
                    }
                    .disabled(skipReason.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || actionInFlight != nil)
                    .foregroundStyle(.black)
                    .background(FieldLGXTheme.lime)
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))

                    Spacer()
                }
                .padding(24)
            }
        }
    }

    private func errorState(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Could not load job")
                .font(.system(size: 22, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
            Text(message)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(FieldLGXTheme.secondaryText)
            Button("Try again") {
                Task { await loadDetail() }
            }
            .buttonStyle(.borderedProminent)
            .tint(FieldLGXTheme.lime)
            .foregroundStyle(.black)
        }
        .padding(18)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private func loadDetail() async {
        guard let accessToken else {
            detail = .preview
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            detail = try await client(accessToken: accessToken).jobDetail(id: jobID)
        } catch {
            detail = detail ?? previewJob.map { job in
                JobDetailResponse(
                    job: job,
                    actions: JobActions(
                        canStart: job.status == "scheduled",
                        canComplete: job.status == "in_progress",
                        canSkip: job.status == "scheduled" || job.status == "in_progress",
                        requiresCompletionPhoto: false,
                        hasCompletionPhoto: false
                    ),
                    jobNotes: [],
                    serverTime: ""
                )
            }
            errorMessage = error.localizedDescription
        }
    }

    private func perform(_ action: JobAction) async {
        guard let accessToken else { return }
        actionInFlight = action
        errorMessage = nil
        defer { actionInFlight = nil }

        do {
            let api = client(accessToken: accessToken)
            switch action {
            case .start:
                detail = try await api.startJob(id: jobID)
            case .complete:
                detail = try await api.completeJob(id: jobID)
            case .skip, .uploadPhoto:
                break
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func performSkip() async {
        guard let accessToken else { return }
        let reason = skipReason.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !reason.isEmpty else { return }
        actionInFlight = .skip
        errorMessage = nil
        defer { actionInFlight = nil }

        do {
            detail = try await client(accessToken: accessToken).skipJob(id: jobID, reason: reason)
            isShowingSkipSheet = false
            skipReason = ""
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func uploadCompletionPhoto(_ item: PhotosPickerItem) async {
        guard let accessToken else { return }
        actionInFlight = .uploadPhoto
        errorMessage = nil
        defer {
            actionInFlight = nil
            completionPhotoItem = nil
        }

        do {
            guard let data = try await item.loadTransferable(type: Data.self) else {
                errorMessage = "Could not read that photo."
                return
            }
            detail = try await client(accessToken: accessToken).uploadCompletionPhoto(id: jobID, imageData: data)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func client(accessToken: String) -> APIClient {
        APIClient(baseURL: URL(string: "http://127.0.0.1:8004")!, accessToken: accessToken)
    }

    private func statusText(_ status: String) -> String {
        switch status {
        case "in_progress":
            "IN PROGRESS"
        case "completed":
            "COMPLETED"
        case "skipped":
            "SKIPPED"
        default:
            "SCHEDULED"
        }
    }
}

#Preview {
    JobDetailScreen(jobID: 1, accessToken: nil, previewJob: TodayResponse.preview.jobs[0])
        .preferredColorScheme(.dark)
}
