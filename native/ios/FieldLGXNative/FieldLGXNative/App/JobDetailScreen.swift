import SwiftUI
import PhotosUI
import SwiftData

struct JobDetailScreen: View {
    let jobID: Int
    let accessToken: String?
    let previewJob: TodayJob?

    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @State private var detail: JobDetailResponse?
    @State private var isLoading = false
    @State private var actionInFlight: JobAction?
    @State private var errorMessage: String?
    @State private var offlineMessage: String?
    @State private var pendingOfflineCount = 0
    @State private var isShowingSkipSheet = false
    @State private var isShowingNoteSheet = false
    @State private var isShowingIssueSheet = false
    @State private var skipReason = ""
    @State private var noteText = ""
    @State private var issueDescription = ""
    @State private var selectedIssueType = "access"
    @State private var completionPhotoItem: PhotosPickerItem?
    @State private var sitePhotoItem: PhotosPickerItem?
    @State private var selectedSitePhotoCategory = "general"

    private enum JobAction {
        case start
        case complete
        case skip
        case uploadPhoto
        case uploadSitePhoto
        case addNote
        case reportIssue
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
            refreshPendingCount()
        }
        .sheet(isPresented: $isShowingSkipSheet) {
            skipSheet
                .presentationDetents([.medium])
                .presentationDragIndicator(.visible)
        }
        .sheet(isPresented: $isShowingNoteSheet) {
            noteSheet
                .presentationDetents([.medium])
                .presentationDragIndicator(.visible)
        }
        .sheet(isPresented: $isShowingIssueSheet) {
            issueSheet
                .presentationDetents([.medium])
                .presentationDragIndicator(.visible)
        }
        .onChange(of: completionPhotoItem) { _, newItem in
            guard let newItem else { return }
            Task {
                await uploadCompletionPhoto(newItem)
            }
        }
        .onChange(of: sitePhotoItem) { _, newItem in
            guard let newItem else { return }
            Task {
                await uploadSitePhoto(newItem)
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

            Button {
                isShowingNoteSheet = true
            } label: {
                Label("Add field note", systemImage: "text.bubble.fill")
                    .font(.system(size: 16, weight: .black))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 15)
            }
            .disabled(actionInFlight != nil)
            .foregroundStyle(FieldLGXTheme.text)
            .background(FieldLGXTheme.elevatedBackground)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))

            Button {
                isShowingIssueSheet = true
            } label: {
                Label("Report issue", systemImage: "exclamationmark.triangle.fill")
                    .font(.system(size: 16, weight: .black))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 15)
            }
            .disabled(actionInFlight != nil)
            .foregroundStyle(FieldLGXTheme.text)
            .background(FieldLGXTheme.elevatedBackground)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))

            sitePhotoPicker

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

            if pendingOfflineCount > 0 {
                VStack(alignment: .leading, spacing: 8) {
                    Label("\(pendingOfflineCount) offline action\(pendingOfflineCount == 1 ? "" : "s") waiting to sync.", systemImage: "arrow.triangle.2.circlepath")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(FieldLGXTheme.lime)

                    Button {
                        Task { await flushOfflineActions() }
                    } label: {
                        Text("Sync now")
                            .font(.system(size: 15, weight: .black))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                    }
                    .disabled(actionInFlight != nil)
                    .foregroundStyle(.black)
                    .background(FieldLGXTheme.lime)
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                }
            }

            if let offlineMessage {
                Text(offlineMessage)
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(FieldLGXTheme.lime)
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

    private var sitePhotoPicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            Menu {
                ForEach(sitePhotoCategories, id: \.value) { category in
                    Button(category.label) {
                        selectedSitePhotoCategory = category.value
                    }
                }
            } label: {
                HStack {
                    Text("Photo type")
                    Spacer()
                    Text(selectedSitePhotoCategoryLabel)
                        .foregroundStyle(FieldLGXTheme.lime)
                    Image(systemName: "chevron.up.chevron.down")
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                }
                .font(.system(size: 14, weight: .black))
                .foregroundStyle(FieldLGXTheme.text)
                .padding(14)
                .background(FieldLGXTheme.elevatedBackground)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            }

            PhotosPicker(selection: $sitePhotoItem, matching: .images) {
                HStack(spacing: 9) {
                    if actionInFlight == .uploadSitePhoto {
                        ProgressView()
                            .tint(FieldLGXTheme.lime)
                    } else {
                        Image(systemName: "photo.fill")
                    }
                    Text("Add site photo")
                    Spacer()
                    Text("\(detail?.job.photoCount ?? 0)")
                        .font(.system(size: 13, weight: .black))
                        .foregroundStyle(FieldLGXTheme.lime)
                }
                .font(.system(size: 16, weight: .black))
                .padding(.vertical, 14)
                .padding(.horizontal, 16)
                .foregroundStyle(FieldLGXTheme.text)
                .background(FieldLGXTheme.elevatedBackground)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
            .disabled(actionInFlight != nil)
        }
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

        if !detail.jobIssues.isEmpty {
            detailSection(title: "Open issues") {
                ForEach(detail.jobIssues) { issue in
                    row(
                        title: "\(issue.issueTypeDisplay) · \(issue.status.capitalized)",
                        value: issue.description,
                        systemImage: "exclamationmark.triangle"
                    )
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

    private var noteSheet: some View {
        NavigationStack {
            ZStack {
                FieldLGXTheme.background.ignoresSafeArea()
                VStack(alignment: .leading, spacing: 16) {
                    Text("Add a field note")
                        .font(.system(size: 24, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)

                    Text("Visible to the crew and attached to this job.")
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)

                    TextField("Gate locked, customer request, or field detail", text: $noteText, axis: .vertical)
                        .font(.system(size: 17, weight: .semibold))
                        .lineLimit(4...7)
                        .padding(16)
                        .foregroundStyle(FieldLGXTheme.text)
                        .background(FieldLGXTheme.elevatedBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))

                    Button {
                        Task { await addFieldNote() }
                    } label: {
                        HStack {
                            if actionInFlight == .addNote {
                                ProgressView()
                                    .tint(.black)
                            }
                            Text("Save note")
                        }
                        .font(.system(size: 17, weight: .black))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                    }
                    .disabled(noteText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || actionInFlight != nil)
                    .foregroundStyle(.black)
                    .background(FieldLGXTheme.lime)
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))

                    Spacer()
                }
                .padding(24)
            }
        }
    }

    private var issueSheet: some View {
        NavigationStack {
            ZStack {
                FieldLGXTheme.background.ignoresSafeArea()
                VStack(alignment: .leading, spacing: 16) {
                    Text("Report an issue")
                        .font(.system(size: 24, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)

                    Text("Use this for access problems, damage, customer concerns, or anything the office needs to review.")
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)

                    Menu {
                        ForEach(issueTypes, id: \.value) { issueType in
                            Button(issueType.label) {
                                selectedIssueType = issueType.value
                            }
                        }
                    } label: {
                        HStack {
                            Text(selectedIssueLabel)
                            Spacer()
                            Image(systemName: "chevron.up.chevron.down")
                        }
                        .font(.system(size: 17, weight: .black))
                        .foregroundStyle(FieldLGXTheme.text)
                        .padding(16)
                        .background(FieldLGXTheme.elevatedBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                    }

                    TextField("Describe what happened", text: $issueDescription, axis: .vertical)
                        .font(.system(size: 17, weight: .semibold))
                        .lineLimit(4...7)
                        .padding(16)
                        .foregroundStyle(FieldLGXTheme.text)
                        .background(FieldLGXTheme.elevatedBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))

                    Button {
                        Task { await reportIssue() }
                    } label: {
                        HStack {
                            if actionInFlight == .reportIssue {
                                ProgressView()
                                    .tint(.black)
                            }
                            Text("Report issue")
                        }
                        .font(.system(size: 17, weight: .black))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                    }
                    .disabled(issueDescription.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || actionInFlight != nil)
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
                    jobIssues: [],
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
            case .skip, .uploadPhoto, .uploadSitePhoto, .addNote, .reportIssue:
                break
            }
        } catch {
            if action == .start {
                queueOfflineAction(["action": "start"])
            } else if action == .complete {
                queueOfflineAction(["action": "complete"])
            } else {
                errorMessage = error.localizedDescription
            }
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
            queueOfflineAction(["action": "skip", "reason": reason])
            isShowingSkipSheet = false
            skipReason = ""
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

    private func uploadSitePhoto(_ item: PhotosPickerItem) async {
        guard let accessToken else { return }
        actionInFlight = .uploadSitePhoto
        errorMessage = nil
        defer {
            actionInFlight = nil
            sitePhotoItem = nil
        }

        do {
            guard let data = try await item.loadTransferable(type: Data.self) else {
                errorMessage = "Could not read that photo."
                return
            }
            detail = try await client(accessToken: accessToken).uploadJobPhoto(
                id: jobID,
                imageData: data,
                category: selectedSitePhotoCategory
            )
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func addFieldNote() async {
        guard let accessToken else { return }
        let text = noteText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        actionInFlight = .addNote
        errorMessage = nil
        defer { actionInFlight = nil }

        do {
            detail = try await client(accessToken: accessToken).addJobNote(id: jobID, text: text)
            noteText = ""
            isShowingNoteSheet = false
        } catch {
            queueOfflineAction(["action": "add_note", "text": text])
            noteText = ""
            isShowingNoteSheet = false
        }
    }

    private func reportIssue() async {
        guard let accessToken else { return }
        let description = issueDescription.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !description.isEmpty else { return }
        actionInFlight = .reportIssue
        errorMessage = nil
        defer { actionInFlight = nil }

        do {
            detail = try await client(accessToken: accessToken).reportJobIssue(
                id: jobID,
                issueType: selectedIssueType,
                description: description
            )
            issueDescription = ""
            selectedIssueType = "access"
            isShowingIssueSheet = false
        } catch {
            queueOfflineAction([
                "action": "report_issue",
                "issue_type": selectedIssueType,
                "description": description
            ])
            issueDescription = ""
            selectedIssueType = "access"
            isShowingIssueSheet = false
        }
    }

    private func queueOfflineAction(_ payload: [String: String]) {
        do {
            try SyncQueue(modelContext: modelContext).enqueue(
                entityType: "job_action",
                serverID: "\(jobID)",
                operation: .externalAction,
                payload: payload,
                baseRevision: nil
            )
            errorMessage = nil
            offlineMessage = "Saved offline. This will sync when the connection is back."
            refreshPendingCount()
        } catch {
            errorMessage = "Could not save this action offline."
        }
    }

    private func flushOfflineActions() async {
        guard let accessToken else { return }
        actionInFlight = .addNote
        errorMessage = nil
        defer { actionInFlight = nil }

        let completed = await SyncQueue(modelContext: modelContext).flush(apiClient: client(accessToken: accessToken))
        refreshPendingCount()
        if completed > 0 {
            offlineMessage = "Synced \(completed) offline action\(completed == 1 ? "" : "s")."
            await loadDetail()
        } else if pendingOfflineCount > 0 {
            errorMessage = "Offline actions are still waiting. Try again when the connection improves."
        }
    }

    private func refreshPendingCount() {
        pendingOfflineCount = (try? SyncQueue(modelContext: modelContext).pendingCount()) ?? 0
    }

    private func client(accessToken: String) -> APIClient {
        APIClient(baseURL: URL(string: "http://127.0.0.1:8004")!, accessToken: accessToken)
    }

    private var issueTypes: [(value: String, label: String)] {
        [
            ("access", "Access / gate / lock"),
            ("equipment", "Equipment"),
            ("customer_request", "Customer request"),
            ("damage", "Damage / concern"),
            ("other", "Other")
        ]
    }

    private var selectedIssueLabel: String {
        issueTypes.first { $0.value == selectedIssueType }?.label ?? "Other"
    }

    private var sitePhotoCategories: [(value: String, label: String)] {
        [
            ("general", "General"),
            ("before", "Before"),
            ("during", "During"),
            ("after", "After"),
            ("issue", "Issue")
        ]
    }

    private var selectedSitePhotoCategoryLabel: String {
        sitePhotoCategories.first { $0.value == selectedSitePhotoCategory }?.label ?? "General"
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
