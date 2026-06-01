import SwiftUI

struct WorkScreen: View {
    let accessToken: String?
    let pageTitle: String
    let pageEyebrow: String
    let pageSubtitle: String
    let lockServiceFilter: Bool

    @State private var work: WorkResponse?
    @State private var selectedService: String
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingCreateJob = false

    init(
        accessToken: String?,
        initialService: String = "all",
        pageTitle: String = "Jobs",
        pageEyebrow: String = "Field work",
        pageSubtitle: String = "Schedule work, open job details, document the visit, and keep billing connected.",
        lockServiceFilter: Bool = false
    ) {
        self.accessToken = accessToken
        self.pageTitle = pageTitle
        self.pageEyebrow = pageEyebrow
        self.pageSubtitle = pageSubtitle
        self.lockServiceFilter = lockServiceFilter
        _selectedService = State(initialValue: initialService)
    }

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    header
                    webActionStack

                    if isLoading && work == nil {
                        ProgressView()
                            .tint(FieldLGXTheme.lime)
                            .frame(maxWidth: .infinity, minHeight: 220)
                    } else if let work {
                        fieldQueueStrip(work.summary)
                        if lockServiceFilter {
                            serviceCommandPanel(work.summary)
                            focusedServiceBadge
                        } else {
                            serviceFilters(work.serviceFilters)
                        }
                        section(
                            eyebrow: "SCHEDULE QUEUE",
                            title: "Needs scheduled",
                            count: work.summary.needsScheduled,
                            jobs: work.sections.needsScheduled,
                            empty: "Nothing needs scheduling."
                        )
                        section(
                            eyebrow: "SCHEDULED",
                            title: "Upcoming work",
                            count: work.summary.upcoming,
                            jobs: work.sections.upcoming,
                            empty: "No upcoming work in this filter."
                        )
                        section(
                            eyebrow: "COMPLETE",
                            title: "Finished jobs",
                            count: work.summary.finished,
                            jobs: work.sections.finished,
                            empty: "No completed jobs yet."
                        )
                        section(
                            eyebrow: "BILLING",
                            title: "Needs billing",
                            count: work.summary.needsBilling,
                            jobs: work.sections.needsBilling,
                            empty: "Nothing pending billing."
                        )
                    } else if let errorMessage {
                        errorState(errorMessage)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, FieldLGXTheme.ownerTopOffset)
                .padding(.bottom, 18)
            }
            .refreshable {
                await loadWork()
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .navigationBarBackButtonHidden(true)
        .task(id: selectedService) {
            await loadWork()
        }
        .sheet(isPresented: $showingCreateJob) {
            CreateJobSheet(accessToken: accessToken) {
                await loadWork()
            }
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
    }

    private var header: some View {
        FieldLGXPageTitle(
            eyebrow: pageEyebrow,
            title: pageTitle,
            subtitle: pageSubtitle
        )
    }

    private var focusedServiceBadge: some View {
        HStack(spacing: 10) {
            Image(systemName: selectedService == "mowing" ? "leaf.fill" : "sprout.fill")
                .font(.system(size: 17, weight: .black))
                .foregroundStyle(.black)
                .frame(width: 42, height: 42)
                .background(FieldLGXTheme.lime)
                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))

            VStack(alignment: .leading, spacing: 3) {
                Text(selectedService == "mowing" ? "Mowing work only" : "Fertilization work only")
                    .font(.system(size: 15, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                Text("Open Jobs from the menu to see every service together.")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
            }

            Spacer(minLength: 0)
        }
        .fieldPanel(padding: 14)
    }

    private func serviceCommandPanel(_ summary: WorkSummary) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 12) {
                Image(systemName: selectedService == "mowing" ? "leaf.fill" : "sprout.fill")
                    .font(.system(size: 24, weight: .black))
                    .foregroundStyle(.black)
                    .frame(width: 54, height: 54)
                    .background(FieldLGXTheme.lime)
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))

                VStack(alignment: .leading, spacing: 4) {
                    Text(selectedService == "mowing" ? "Mowing command" : "Fertilization command")
                        .font(.system(size: 22, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                    Text(selectedService == "mowing" ? "Routes, recurring lawns, skipped cuts, notes, and billing stay attached." : "Rounds, applications, property notes, photos, and billing stay attached.")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                serviceMetric("Upcoming", "\(summary.upcoming)", "scheduled")
                serviceMetric("Needs scheduled", "\(summary.needsScheduled)", "queue")
                serviceMetric("Finished", "\(summary.finished)", "recent")
                serviceMetric("Needs billing", "\(summary.needsBilling)", "ready")
            }
        }
        .fieldPanel(padding: 16)
    }

    private func serviceMetric(_ title: String, _ value: String, _ caption: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title.uppercased())
                .font(.system(size: 9, weight: .black))
                .tracking(1.5)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            Text(value)
                .font(.system(size: 25, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
            Text(caption)
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .fieldInsetSurface()
    }

    private var webActionStack: some View {
        VStack(spacing: 10) {
            NavigationLink {
                CalendarScreen(accessToken: accessToken)
            } label: {
                quickActionLabel("Schedule work", detail: "Open the calendar", icon: "calendar")
                    .foregroundStyle(.black)
                    .background(FieldLGXTheme.lime)
            }
            .buttonStyle(.plain)

            HStack(spacing: 10) {
                Button {
                    showingCreateJob = true
                } label: {
                    quickActionLabel("New job", detail: "Create field work", icon: "checkmark.circle.badge.plus")
                        .foregroundStyle(FieldLGXTheme.text)
                        .background(FieldLGXTheme.panelGradient)
                        .overlay(actionStroke)
                }

                NavigationLink {
                    RouteScreen(accessToken: accessToken)
                } label: {
                    quickActionLabel("Routes", detail: "Crew order", icon: "point.topleft.down.curvedto.point.bottomright.up")
                        .foregroundStyle(FieldLGXTheme.text)
                        .background(FieldLGXTheme.panelGradient)
                        .overlay(actionStroke)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func quickActionLabel(_ title: String, detail: String, icon: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 17, weight: .black))
                .frame(width: 24)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.system(size: 15, weight: .black))
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)
                Text(detail)
                    .font(.system(size: 11, weight: .bold))
                    .opacity(0.68)
                    .lineLimit(1)
                    .minimumScaleFactor(0.76)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 14)
        .frame(maxWidth: .infinity)
        .frame(height: 54)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private var actionStroke: some View {
        RoundedRectangle(cornerRadius: 18, style: .continuous)
            .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
    }

    private func fieldQueueStrip(_ summary: WorkSummary) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("FIELD QUEUE")
                        .font(.system(size: 11, weight: .black))
                        .tracking(2.0)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                    Text(primaryQueueTitle(summary))
                        .font(.system(size: 24, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 8)

                Text("\(summary.upcoming)")
                    .font(.system(size: 26, weight: .black, design: .rounded))
                    .foregroundStyle(.black)
                    .frame(width: 52, height: 52)
                    .background(FieldLGXTheme.lime)
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                    .accessibilityLabel("\(summary.upcoming) upcoming jobs")
            }

            HStack(spacing: 8) {
                queuePill("Schedule", value: summary.needsScheduled)
                queuePill("Finish", value: summary.finished)
                queuePill("Bill", value: summary.needsBilling)
            }
        }
        .fieldPanel(padding: 16)
    }

    private func primaryQueueTitle(_ summary: WorkSummary) -> String {
        if summary.needsScheduled > 0 {
            return "\(summary.needsScheduled) \(summary.needsScheduled == 1 ? "job needs" : "jobs need") scheduled"
        }
        if summary.upcoming > 0 {
            return "\(summary.upcoming) \(summary.upcoming == 1 ? "job" : "jobs") coming up"
        }
        if summary.needsBilling > 0 {
            return "\(summary.needsBilling) \(summary.needsBilling == 1 ? "job is" : "jobs are") ready to invoice"
        }
        return "No urgent job work"
    }

    private func queuePill(_ label: String, value: Int) -> some View {
        HStack(spacing: 6) {
            Text(label)
                .font(.system(size: 11, weight: .black))
                .lineLimit(1)
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

    private func summaryGrid(_ summary: WorkSummary) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
            metric("Upcoming", "\(summary.upcoming)", "next 14 days")
            metric("Needs scheduled", "\(summary.needsScheduled)", "queue")
            metric("Finished", "\(summary.finished)", "recent work")
            metric("Needs billing", "\(summary.needsBilling)", "ready")
        }
    }

    private func metric(_ label: String, _ value: String, _ detail: String) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(label.uppercased())
                .font(.system(size: 10, weight: .black))
                .tracking(1.8)
                .foregroundStyle(FieldLGXTheme.tertiaryText)

            Text(value)
                .font(.system(size: 28, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)

            Text(detail)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
        }
        .frame(maxWidth: .infinity, minHeight: 92, alignment: .leading)
        .fieldPanel(padding: 16)
    }

    private func serviceFilters(_ filters: [WorkServiceFilter]) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 10) {
                ForEach(filters) { filter in
                    Button {
                        selectedService = filter.key
                    } label: {
                        Text(filter.label)
                            .font(.system(size: 14, weight: .black))
                            .foregroundStyle(selectedService == filter.key ? .black : FieldLGXTheme.secondaryText)
                            .padding(.horizontal, 14)
                            .frame(height: 40)
                            .background(selectedService == filter.key ? FieldLGXTheme.lime : FieldLGXTheme.elevatedBackground)
                            .clipShape(Capsule())
                            .overlay(
                                Capsule()
                                    .stroke(selectedService == filter.key ? FieldLGXTheme.lime : FieldLGXTheme.panelStroke, lineWidth: 1)
                            )
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private func section(eyebrow: String, title: String, count: Int, jobs: [TodayJob], empty: String) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(eyebrow)
                        .font(.system(size: 11, weight: .black))
                        .tracking(2.2)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)

                    Text(title)
                        .font(.system(size: 26, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                }

                Spacer()

                Text("\(count)")
                    .font(.system(size: 15, weight: .black))
                    .foregroundStyle(count == 0 ? FieldLGXTheme.secondaryText : FieldLGXTheme.lime)
                    .frame(width: 36, height: 36)
                    .background(FieldLGXTheme.elevatedBackground)
                    .clipShape(Circle())
            }

            if jobs.isEmpty {
                Text(empty)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(FieldLGXTheme.elevatedBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            } else {
                ForEach(jobs) { job in
                    NavigationLink {
                        JobDetailScreen(jobID: job.id, accessToken: accessToken, previewJob: job)
                    } label: {
                        TodayJobCard(job: job)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .fieldPanel()
    }

    private func errorState(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Could not load work")
                .font(.system(size: 22, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
            Text(message)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(FieldLGXTheme.secondaryText)
            Button("Try again") {
                Task { await loadWork() }
            }
            .buttonStyle(.borderedProminent)
            .tint(FieldLGXTheme.lime)
            .foregroundStyle(.black)
        }
        .fieldPanel()
    }

    private func loadWork() async {
        guard let accessToken, accessToken != "preview-token" else {
            work = .preview
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            work = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
                .work(service: selectedService)
        } catch {
            errorMessage = "Check your connection and try again."
        }
    }
}

private extension WorkResponse {
    static let preview = WorkResponse(
        date: "2026-05-07",
        summary: WorkSummary(upcoming: 1, needsScheduled: 1, finished: 1, needsBilling: 1),
        serviceFilters: [
            WorkServiceFilter(key: "all", label: "All"),
            WorkServiceFilter(key: "mowing", label: "Mowing"),
            WorkServiceFilter(key: "fertilization", label: "Fertilization"),
        ],
        sections: WorkSections(
            upcoming: TodayResponse.preview.jobs,
            needsScheduled: TodayResponse.preview.jobs,
            finished: TodayResponse.preview.jobs,
            needsBilling: TodayResponse.preview.jobs
        ),
        serverTime: "2026-05-07T12:00:00Z"
    )
}
