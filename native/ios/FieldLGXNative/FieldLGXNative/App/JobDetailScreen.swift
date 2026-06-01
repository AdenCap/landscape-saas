import SwiftUI
import PhotosUI
import SwiftData
import UIKit

struct JobDetailScreen: View {
    let jobID: Int
    let accessToken: String?
    let previewJob: TodayJob?

    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @Environment(\.openURL) private var openURL
    @Environment(\.fieldLGXUsesOwnerChrome) private var usesOwnerChrome
    @State private var detail: JobDetailResponse?
    @State private var isLoading = false
    @State private var actionInFlight: JobAction?
    @State private var errorMessage: String?
    @State private var offlineMessage: String?
    @State private var pendingOfflineCount = 0
    @State private var isShowingSkipSheet = false
    @State private var isShowingNoteSheet = false
    @State private var isShowingIssueSheet = false
    @State private var editingJob: TodayJob?
    @State private var skipReason = ""
    @State private var noteText = ""
    @State private var issueDescription = ""
    @State private var selectedIssueType = "access"
    @State private var completionPhotoItem: PhotosPickerItem?
    @State private var sitePhotoItem: PhotosPickerItem?
    @State private var selectedSitePhotoCategory = "general"
    @State private var cameraMode: CameraMode?

    private enum JobAction {
        case start
        case complete
        case skip
        case uploadPhoto
        case uploadSitePhoto
        case addNote
        case reportIssue
    }

    private enum CameraMode: String, Identifiable {
        case completion
        case site

        var id: String { rawValue }
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            FieldLGXScreenBackground()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    topBar

                    if isLoading && detail == nil {
                        ProgressView()
                            .tint(FieldLGXTheme.lime)
                            .frame(maxWidth: .infinity, minHeight: 260)
                    } else if let detail {
                        hero(detail.job)
                        mobileWorkshopPanel(detail)
                        actionPanel(detail)
                        contextSections(detail)
                    } else if let errorMessage {
                        errorState(errorMessage)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, usesOwnerChrome ? FieldLGXTheme.ownerTopOffset : 16)
                .padding(.bottom, 18)
            }
            .refreshable {
                await loadDetail()
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .navigationBarBackButtonHidden(true)
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
        .sheet(item: $editingJob) { job in
            EditJobSheet(accessToken: accessToken, job: job) { response in
                detail = response
            }
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
        .sheet(item: $cameraMode) { mode in
            CameraCaptureSheet { image in
                Task {
                    await uploadCameraImage(image, mode: mode)
                }
            }
            .ignoresSafeArea()
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
                Label("Back", systemImage: "chevron.left")
                    .font(.system(size: 15, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 11)
                    .background(FieldLGXTheme.elevatedBackground)
                    .clipShape(Capsule())
                    .overlay(Capsule().stroke(FieldLGXTheme.panelStroke, lineWidth: 1))
            }
            .accessibilityLabel("Back to route")

            Spacer()

            if let activeJob {
                Button {
                    editingJob = activeJob
                } label: {
                    Label("Edit", systemImage: "slider.horizontal.3")
                        .font(.system(size: 15, weight: .black))
                        .foregroundStyle(.black)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 11)
                        .background(FieldLGXTheme.lime)
                        .clipShape(Capsule())
                }
                .accessibilityLabel("Edit job")
            }
        }
    }

    private var activeJob: TodayJob? {
        detail?.job ?? previewJob
    }

    private func hero(_ job: TodayJob) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 7) {
                HStack(spacing: 8) {
                    Circle()
                        .fill(FieldLGXTheme.lime)
                        .frame(width: 8, height: 8)
                    Text(statusText(job.status))
                        .font(.system(size: 12, weight: .black))
                        .tracking(2.2)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                }

                Text(job.customer.name)
                    .font(.system(size: 40, weight: .black, design: .rounded))
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

            HStack(spacing: 8) {
                fieldSignalPill("Items", "\(job.serviceItems.count)")
                fieldSignalPill("Photos", "\(job.photoCount)")
                if job.scheduledEndDate != nil {
                    fieldSignalPill("Multi-day", "On")
                }
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(FieldLGXTheme.panelGradient)
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func actionPanel(_ detail: JobDetailResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("MORE FIELD ACTIONS")
                .font(.system(size: 12, weight: .black))
                .tracking(2.2)
                .foregroundStyle(FieldLGXTheme.tertiaryText)

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
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))

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
        .background(FieldLGXTheme.panelGradient)
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func mobileWorkshopPanel(_ detail: JobDetailResponse) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("FIELD ACTIONS")
                        .font(.system(size: 12, weight: .black))
                        .tracking(2.2)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                    Text("Update the job without leaving the field.")
                        .font(.system(size: 16, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                }
                Spacer()
                Text(detail.job.status.capitalized)
                    .font(.system(size: 12, weight: .black))
                    .foregroundStyle(.black)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(FieldLGXTheme.lime)
                    .clipShape(Capsule())
            }

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
                    title: "Done",
                    systemImage: "checkmark",
                    action: .complete,
                    isEnabled: detail.actions.canComplete
                ) {
                    await perform(.complete)
                }
            }

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                workshopTile("Schedule", "calendar.badge.clock") {
                    editingJob = detail.job
                }

                workshopTile("Note", "text.bubble.fill") {
                    isShowingNoteSheet = true
                }

                workshopTile("Issue", "exclamationmark.triangle.fill") {
                    isShowingIssueSheet = true
                }

                PhotosPicker(selection: $sitePhotoItem, matching: .images) {
                    workshopTileLabel("Photo", "camera.fill")
                }
                .disabled(actionInFlight != nil)

                workshopTile("Directions", "location.fill") {
                    openURL(directionsURL(for: detail.job))
                }

                workshopTile("Call", "phone.fill") {
                    if let url = phoneURL(for: detail.job) {
                        openURL(url)
                    }
                }
                .opacity(phoneURL(for: detail.job) == nil ? 0.45 : 1)
                .disabled(phoneURL(for: detail.job) == nil)
            }
        }
        .padding(18)
        .background(FieldLGXTheme.panelGradient)
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func workshopTile(_ title: String, _ systemImage: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            workshopTileLabel(title, systemImage)
        }
        .buttonStyle(.plain)
        .disabled(actionInFlight != nil)
    }

    private func fieldSignalPill(_ label: String, _ value: String) -> some View {
        HStack(spacing: 5) {
            Text(label.uppercased())
                .font(.system(size: 9, weight: .black))
                .tracking(1.4)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            Text(value)
                .font(.system(size: 12, weight: .black))
                .foregroundStyle(FieldLGXTheme.lime)
        }
        .padding(.horizontal, 10)
        .frame(height: 32)
        .background(FieldLGXTheme.elevatedBackground)
        .clipShape(Capsule())
        .overlay(Capsule().stroke(FieldLGXTheme.panelStroke, lineWidth: 1))
    }

    private func workshopTileLabel(_ title: String, _ systemImage: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: systemImage)
                .font(.system(size: 18, weight: .black))
                .foregroundStyle(FieldLGXTheme.lime)
            Text(title)
                .font(.system(size: 15, weight: .black))
                .foregroundStyle(FieldLGXTheme.text)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 13)
        .frame(maxWidth: .infinity, minHeight: 52)
        .background(FieldLGXTheme.elevatedBackground)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func directionsURL(for job: TodayJob) -> URL {
        if
            let latitude = job.property.latitude,
            let longitude = job.property.longitude,
            !latitude.isEmpty,
            !longitude.isEmpty,
            let url = URL(string: "http://maps.apple.com/?daddr=\(latitude),\(longitude)")
        {
            return url
        }

        let encodedAddress = job.property.address.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? job.property.address
        return URL(string: "http://maps.apple.com/?daddr=\(encodedAddress)") ?? URL(string: "http://maps.apple.com/")!
    }

    private func phoneURL(for job: TodayJob) -> URL? {
        let digits = job.customer.phone.filter(\.isNumber)
        guard !digits.isEmpty else { return nil }
        return URL(string: "tel://\(digits)")
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

            cameraButton(title: "Take site photo", mode: .site, isPrimary: false)
        }
    }

    private func completionPhotoPicker(title: String, isPrimary: Bool) -> some View {
        VStack(spacing: 10) {
            PhotosPicker(selection: $completionPhotoItem, matching: .images) {
                HStack(spacing: 9) {
                    if actionInFlight == .uploadPhoto {
                        ProgressView()
                            .tint(isPrimary ? .black : FieldLGXTheme.lime)
                    } else {
                        Image(systemName: "photo.fill")
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

            cameraButton(title: "Take completion photo", mode: .completion, isPrimary: isPrimary)
        }
    }

    private func cameraButton(title: String, mode: CameraMode, isPrimary: Bool) -> some View {
        Button {
            guard UIImagePickerController.isSourceTypeAvailable(.camera) else {
                errorMessage = "Camera is not available on this simulator."
                return
            }
            cameraMode = mode
        } label: {
            Label(title, systemImage: "camera.fill")
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
        .background(FieldLGXTheme.panelGradient)
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
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
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
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
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private var skipSheet: some View {
        NavigationStack {
            ZStack {
                FieldLGXScreenBackground()
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
                FieldLGXScreenBackground()
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
                FieldLGXScreenBackground()
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
            errorMessage = "Sign in again to load this job."
            return
        }
        if accessToken == "preview-token" {
            detail = .preview
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            detail = try await client(accessToken: accessToken).jobDetail(id: jobID)
        } catch {
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

    private func uploadCameraImage(_ image: UIImage, mode: CameraMode) async {
        guard let data = image.jpegData(compressionQuality: 0.82) else {
            errorMessage = "Could not prepare that photo."
            return
        }
        switch mode {
        case .completion:
            await uploadCompletionPhotoData(data)
        case .site:
            await uploadSitePhotoData(data)
        }
    }

    private func uploadCompletionPhotoData(_ data: Data) async {
        guard let accessToken else { return }
        actionInFlight = .uploadPhoto
        errorMessage = nil
        defer { actionInFlight = nil }

        do {
            detail = try await client(accessToken: accessToken).uploadCompletionPhoto(id: jobID, imageData: data)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func uploadSitePhotoData(_ data: Data) async {
        guard let accessToken else { return }
        actionInFlight = .uploadSitePhoto
        errorMessage = nil
        defer { actionInFlight = nil }

        do {
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
        APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
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

private struct EditJobSheet: View {
    let accessToken: String?
    let job: TodayJob
    let onSaved: (JobDetailResponse) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var scheduledDate: Date
    @State private var scheduledEndDate: Date
    @State private var scheduledTime: Date
    @State private var scheduledEndTime: Date
    @State private var spansMultipleDays: Bool
    @State private var status: String
    @State private var selectedColor: String
    @State private var notes: String
    @State private var options: JobOptionsResponse?
    @State private var selectedCrewID: Int?
    @State private var editableItems: [EditableJobItem]
    @State private var isSaving = false
    @State private var errorMessage: String?

    init(accessToken: String?, job: TodayJob, onSaved: @escaping (JobDetailResponse) -> Void) {
        self.accessToken = accessToken
        self.job = job
        self.onSaved = onSaved
        _scheduledDate = State(initialValue: Self.parseDay(job.scheduledDate))
        _scheduledEndDate = State(initialValue: Self.parseDay(job.scheduledEndDate ?? job.scheduledDate))
        _scheduledTime = State(initialValue: Self.parseTime(job.scheduledTime))
        _scheduledEndTime = State(initialValue: Self.parseTime(job.scheduledEndTime))
        _spansMultipleDays = State(initialValue: (job.scheduledEndDate ?? job.scheduledDate) != job.scheduledDate)
        _status = State(initialValue: job.status)
        _selectedColor = State(initialValue: job.jobColorOverride ?? job.statusColor ?? job.color ?? "#3b82f6")
        _notes = State(initialValue: job.notes)
        _editableItems = State(initialValue: job.serviceItems.map { EditableJobItem(from: $0) })
    }

    var body: some View {
        NavigationStack {
            ZStack {
                FieldLGXScreenBackground()

                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        header
                        scheduleCard
                        crewCard
                        statusCard
                        colorCard
                        serviceItemsCard
                        notesCard
                        photoShortcutCard

                        if let errorMessage {
                            Text(errorMessage)
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(.red)
                                .fixedSize(horizontal: false, vertical: true)
                        }

                        Button {
                            Task { await save() }
                        } label: {
                            HStack {
                                if isSaving {
                                    ProgressView()
                                        .tint(.black)
                                }
                                Text(isSaving ? "Saving" : "Save job")
                                Spacer()
                                Image(systemName: "checkmark")
                            }
                            .font(.system(size: 17, weight: .black))
                            .foregroundStyle(.black)
                            .padding(.horizontal, 16)
                            .frame(height: 54)
                            .background(FieldLGXTheme.lime)
                            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                        }
                        .disabled(isSaving)
                    }
                    .padding(24)
                }
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                        .font(.system(size: 15, weight: .bold))
                }
            }
        }
        .task {
            await loadOptions()
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("FULL JOB EDIT")
                .font(.system(size: 12, weight: .black))
                .tracking(2.4)
                .foregroundStyle(FieldLGXTheme.lime)

            Text(job.customer.name)
                .font(.system(size: 32, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(2)
                .minimumScaleFactor(0.8)

            Text(job.property.address)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
        }
    }

    private var scheduleCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            label("Schedule")
            DatePicker("Date", selection: $scheduledDate, displayedComponents: .date)
            DatePicker("Time", selection: $scheduledTime, displayedComponents: .hourAndMinute)
            Toggle("Multi-day job", isOn: $spansMultipleDays)
            if spansMultipleDays {
                DatePicker("End date", selection: $scheduledEndDate, in: scheduledDate..., displayedComponents: .date)
                DatePicker("End time", selection: $scheduledEndTime, displayedComponents: .hourAndMinute)
            }
        }
        .font(.system(size: 16, weight: .bold))
        .foregroundStyle(FieldLGXTheme.text)
        .padding(16)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    @ViewBuilder
    private var crewCard: some View {
        if let options, !options.crews.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                label("Crew")
                Picker("Crew", selection: $selectedCrewID) {
                    Text("Keep current").tag(Int?.none)
                    ForEach(options.crews) { crew in
                        Text(crew.name).tag(Optional(crew.id))
                    }
                }
                .pickerStyle(.menu)
                .tint(FieldLGXTheme.text)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(14)
                .background(FieldLGXTheme.panel)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
                )
            }
        }
    }

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            label("Status")
            Picker("Status", selection: $status) {
                Text("Scheduled").tag("scheduled")
                Text("In progress").tag("in_progress")
                Text("Completed").tag("completed")
                Text("Skipped").tag("skipped")
                Text("Cancelled").tag("cancelled")
            }
            .pickerStyle(.segmented)
        }
        .padding(16)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private var colorCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            label("Calendar color")
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 42), spacing: 10)], spacing: 10) {
                ForEach(Self.calendarColors, id: \.self) { hex in
                    Button {
                        selectedColor = hex
                    } label: {
                        ZStack {
                            RoundedRectangle(cornerRadius: 14, style: .continuous)
                                .fill(Color(hex: hex) ?? FieldLGXTheme.lime)
                                .frame(height: 42)
                            if selectedColor.lowercased() == hex.lowercased() {
                                Image(systemName: "checkmark")
                                    .font(.system(size: 14, weight: .black))
                                    .foregroundStyle(.black)
                            }
                        }
                        .overlay(
                            RoundedRectangle(cornerRadius: 14, style: .continuous)
                                .stroke(Color.white.opacity(selectedColor.lowercased() == hex.lowercased() ? 0.75 : 0.14), lineWidth: 2)
                        )
                    }
                    .buttonStyle(.plain)
                }
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

    @ViewBuilder
    private var serviceItemsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                label("Job items")
                Spacer()
                Button {
                    addServiceItem()
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

            if editableItems.isEmpty {
                Text("Add at least one line item so crews and invoices carry the right scope.")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .padding(14)
                    .fieldInsetSurface()
            }

            ForEach($editableItems) { $item in
                VStack(alignment: .leading, spacing: 10) {
                    if let options, !options.services.isEmpty {
                        Picker("Service", selection: $item.serviceID) {
                            ForEach(options.services) { service in
                                Text(service.name).tag(service.id)
                            }
                        }
                        .pickerStyle(.menu)
                        .tint(FieldLGXTheme.text)
                        .onChange(of: item.serviceID) { _, newValue in
                            if let service = options.services.first(where: { $0.id == newValue }) {
                                item.description = service.name
                                if item.unit.isEmpty { item.unit = service.unit }
                                if item.unitPrice.isEmpty || item.unitPrice == "0.00" { item.unitPrice = service.unitPrice }
                            }
                        }
                    }

                    TextField("Title shown to crew and invoice", text: $item.description)
                        .font(.system(size: 16, weight: .black))
                        .foregroundStyle(FieldLGXTheme.text)
                        .padding(12)
                        .fieldInsetSurface()

                    TextField("Description, scope, materials, client request", text: $item.detailDescription, axis: .vertical)
                        .font(.system(size: 15, weight: .semibold))
                        .lineLimit(2...5)
                        .foregroundStyle(FieldLGXTheme.text)
                        .padding(12)
                        .fieldInsetSurface()

                    HStack(spacing: 8) {
                        TextField("Qty", text: $item.quantity)
                            .keyboardType(.decimalPad)
                        TextField("Unit", text: $item.unit)
                        TextField("Price", text: $item.unitPrice)
                            .keyboardType(.decimalPad)
                    }
                    .font(.system(size: 15, weight: .bold))
                    .foregroundStyle(FieldLGXTheme.text)
                    .textFieldStyle(.plain)
                    .padding(12)
                    .fieldInsetSurface()

                    Button(role: .destructive) {
                        editableItems.removeAll { $0.id == item.id }
                    } label: {
                        Label("Remove item", systemImage: "trash")
                            .font(.system(size: 13, weight: .black))
                    }
                    .disabled(editableItems.count <= 1)
                    .foregroundStyle(editableItems.count <= 1 ? FieldLGXTheme.tertiaryText : .red.opacity(0.9))
                }
                .padding(12)
                .background(FieldLGXTheme.elevatedBackground.opacity(0.88))
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
                )
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

    private var notesCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            label("Job notes")
            TextField("Crew instructions, customer requests, access details", text: $notes, axis: .vertical)
                .font(.system(size: 17, weight: .semibold))
                .lineLimit(4...8)
                .foregroundStyle(FieldLGXTheme.text)
                .padding(16)
                .background(FieldLGXTheme.panel)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
                )
        }
    }

    private var photoShortcutCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            label("Photos, notes, and issues")
            Text("Use the job detail actions for completion photos, site photos, crew notes, and reported issues. They stay attached to this job record.")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(16)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func label(_ text: String) -> some View {
        Text(text.uppercased())
            .font(.system(size: 10, weight: .black))
            .tracking(1.8)
            .foregroundStyle(FieldLGXTheme.tertiaryText)
    }

    private func loadOptions() async {
        guard let accessToken, accessToken != "preview-token" else {
            let response = JobOptionsResponse(
                properties: [],
                services: [],
                crews: [JobOptionCrew(id: 1, name: job.assigned.crew ?? "Crew A")],
                serverTime: ""
            )
            options = response
            selectedCrewID = matchingCrewID(in: response)
            hydrateMissingServiceIDs(from: response)
            return
        }

        do {
            let response = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).jobOptions()
            options = response
            selectedCrewID = matchingCrewID(in: response)
            hydrateMissingServiceIDs(from: response)
        } catch {
            errorMessage = "Crew options are unavailable, but schedule and notes can still be edited."
        }
    }

    private func matchingCrewID(in options: JobOptionsResponse) -> Int? {
        guard let name = job.assigned.crew else { return nil }
        return options.crews.first { $0.name == name }?.id
    }

    private func save() async {
        guard let accessToken, accessToken != "preview-token" else {
            dismiss()
            return
        }

        isSaving = true
        errorMessage = nil
        defer { isSaving = false }

        do {
            let response = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).updateJob(
                id: job.id,
                scheduledDate: Self.dayFormatter.string(from: scheduledDate),
                scheduledTime: Self.timeFormatter.string(from: scheduledTime),
                scheduledEndDate: spansMultipleDays ? Self.dayFormatter.string(from: scheduledEndDate) : "",
                scheduledEndTime: spansMultipleDays ? Self.timeFormatter.string(from: scheduledEndTime) : "",
                notes: notes,
                status: status,
                crewID: selectedCrewID,
                color: selectedColor,
                serviceItems: editableItems.compactMap { item in
                    guard item.serviceID > 0, !item.description.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                        return nil
                    }
                    return JobCreateServiceItem(
                        serviceID: item.serviceID,
                        description: item.description,
                        detailDescription: item.detailDescription,
                        quantity: item.quantity.isEmpty ? "1" : item.quantity,
                        unit: item.unit.isEmpty ? "visit" : item.unit,
                        unitPrice: item.unitPrice.isEmpty ? "0" : item.unitPrice
                    )
                }
            )
            onSaved(response)
            dismiss()
        } catch {
            errorMessage = "Could not save this job. Check the connection and try again."
        }
    }

    private static func parseDay(_ value: String?) -> Date {
        guard let value, let date = dayFormatter.date(from: value) else {
            return Date()
        }
        return date
    }

    private static func parseTime(_ value: String?) -> Date {
        guard let value, let date = timeFormatter.date(from: value) else {
            return Date()
        }
        return date
    }

    private static let dayFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()

    private static let timeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "HH:mm"
        return formatter
    }()

    private static let calendarColors = [
        "#3b82f6", "#22c55e", "#f59e0b", "#ef4444",
        "#8b5cf6", "#ec4899", "#06b6d4", "#94a3b8"
    ]

    private func addServiceItem() {
        if let service = options?.services.first {
            editableItems.append(EditableJobItem(service: service))
        } else {
            editableItems.append(EditableJobItem())
        }
    }

    private func hydrateMissingServiceIDs(from options: JobOptionsResponse) {
        for index in editableItems.indices where editableItems[index].serviceID == 0 {
            let normalizedName = editableItems[index].description.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            if let service = options.services.first(where: { $0.name.lowercased() == normalizedName }) {
                editableItems[index].serviceID = service.id
                if editableItems[index].unit.isEmpty {
                    editableItems[index].unit = service.unit
                }
            }
        }
        if editableItems.isEmpty, let service = options.services.first {
            editableItems.append(EditableJobItem(service: service))
        }
    }
}

private struct EditableJobItem: Identifiable, Equatable {
    let id = UUID()
    var serviceID: Int
    var description: String
    var detailDescription: String
    var quantity: String
    var unit: String
    var unitPrice: String

    init() {
        serviceID = 0
        description = ""
        detailDescription = ""
        quantity = "1"
        unit = "visit"
        unitPrice = "0.00"
    }

    init(service: JobOptionService) {
        serviceID = service.id
        description = service.name
        detailDescription = ""
        quantity = "1"
        unit = service.unit.isEmpty ? "visit" : service.unit
        unitPrice = service.unitPrice
    }

    init(from item: TodayServiceItem) {
        serviceID = item.serviceID ?? 0
        description = item.name
        detailDescription = item.detailDescription
        quantity = item.quantity
        unit = item.unit
        unitPrice = item.unitPrice
    }
}

private struct CameraCaptureSheet: UIViewControllerRepresentable {
    let onCapture: (UIImage) -> Void
    @Environment(\.dismiss) private var dismiss

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.delegate = context.coordinator
        picker.allowsEditing = false
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(onCapture: onCapture, dismiss: dismiss)
    }

    final class Coordinator: NSObject, UINavigationControllerDelegate, UIImagePickerControllerDelegate {
        let onCapture: (UIImage) -> Void
        let dismiss: DismissAction

        init(onCapture: @escaping (UIImage) -> Void, dismiss: DismissAction) {
            self.onCapture = onCapture
            self.dismiss = dismiss
        }

        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            if let image = info[.originalImage] as? UIImage {
                onCapture(image)
            }
            dismiss()
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            dismiss()
        }
    }
}

#Preview {
    JobDetailScreen(jobID: 1, accessToken: nil, previewJob: TodayResponse.preview.jobs[0])
        .preferredColorScheme(.dark)
}
