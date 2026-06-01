import SwiftUI

struct CommandScreen: View {
    let accessToken: String?
    let businessName: String
    let signOut: () -> Void

    @State private var command: CommandResponse?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()

            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if isLoading && command == nil {
                        ProgressView()
                            .tint(FieldLGXTheme.lime)
                            .frame(maxWidth: .infinity, minHeight: 240)
                    } else if let command {
                        todayCommandStrip(command)
                        commandSearch
                        dispatchPanel(command)
                        morningBrief(command.attention)
                        statGrid(command.summary)
                        nextJobs(command.nextJobs)
                    } else if let errorMessage {
                        errorState(errorMessage)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 16)
                .padding(.bottom, 18)
            }
            .refreshable {
                await loadCommand()
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .navigationBarBackButtonHidden(true)
        .task {
            await loadCommand()
        }
    }

    private var commandHeader: some View {
        HStack(alignment: .center, spacing: 12) {
            Circle()
                .fill(FieldLGXTheme.lime)
                .frame(width: 10, height: 10)
                .shadow(color: FieldLGXTheme.lime.opacity(0.45), radius: 10, x: 0, y: 0)

            Text("FIELD COMMAND")
                .font(.system(size: 16, weight: .black))
                .tracking(3.0)
                .foregroundStyle(FieldLGXTheme.secondaryText)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func opsSummary(_ summary: CommandSummary) -> some View {
        HStack(spacing: 8) {
            opsMetric("Today", "\(summary.todayJobs)", "jobs")
            opsMetric("Crews", "\(summary.activeRoutes)", "routes")
            opsMetric("Open", "\(summary.unassignedJobs)", "need crew")
            opsMetric("Bill", "\(summary.readyToBill)", "ready")
        }
    }

    private func opsMetric(_ label: String, _ value: String, _ detail: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label.uppercased())
                .font(.system(size: 8, weight: .black))
                .tracking(1.1)
                .foregroundStyle(FieldLGXTheme.tertiaryText)

            Text(value)
                .font(.system(size: 20, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(1)
                .minimumScaleFactor(0.68)

            Text(detail)
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
                .lineLimit(1)
                .minimumScaleFactor(0.72)
        }
        .frame(maxWidth: .infinity, minHeight: 58, alignment: .leading)
        .padding(.horizontal, 10)
        .background(commandPanelGradient)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 16))
    }

    private var commandSearch: some View {
        HStack(spacing: 14) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 24, weight: .bold))
                .foregroundStyle(FieldLGXTheme.secondaryText)

            Text("Search clients, jobs, invoices, commands")
                .font(.system(size: 19, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
                .lineLimit(1)
                .minimumScaleFactor(0.74)
        }
        .frame(maxWidth: .infinity, minHeight: 64, alignment: .leading)
        .padding(.horizontal, 18)
        .background(commandInsetBackground)
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 28))
    }

    private func dispatchPanel(_ command: CommandResponse) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 7) {
                    sectionKicker("TODAY'S DISPATCH")
                    Text("Field Command")
                        .font(.system(size: 28, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                        .lineLimit(2)
                        .minimumScaleFactor(0.7)
                }

                Spacer()

                NavigationLink {
                    CalendarScreen(accessToken: accessToken)
                } label: {
                    Text("Open calendar")
                        .font(.system(size: 14, weight: .black))
                        .foregroundStyle(.black)
                        .padding(.horizontal, 15)
                        .frame(height: 42)
                        .background(FieldLGXTheme.lime)
                        .clipShape(Capsule())
                }
                .buttonStyle(.plain)
            }

            dispatchPrimary(job: command.nextJobs.first)
            dispatchCommandStack(command)
        }
        .padding(18)
        .background(commandGridPanel)
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 28))
        .shadow(color: Color.black.opacity(0.34), radius: 30, x: 0, y: 20)
    }

    @ViewBuilder
    private func dispatchPrimary(job: TodayJob?) -> some View {
        if let job {
            NavigationLink {
                JobDetailScreen(jobID: job.id, accessToken: accessToken, previewJob: job)
            } label: {
                VStack(alignment: .leading, spacing: 16) {
                    HStack(alignment: .top, spacing: 14) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 17, style: .continuous)
                            .fill(FieldLGXTheme.lime)
                        Text(job.scheduledTime ?? "GO")
                            .font(.system(size: 13, weight: .black))
                            .foregroundStyle(.black)
                            .lineLimit(1)
                            .minimumScaleFactor(0.62)
                            .padding(4)
                    }
                    .frame(width: 56, height: 56)
                    .shadow(color: FieldLGXTheme.lime.opacity(0.22), radius: 18, x: 0, y: 10)

                    VStack(alignment: .leading, spacing: 5) {
                        Text("NEXT IN FIELD")
                            .font(.system(size: 12, weight: .black))
                            .tracking(2.2)
                            .foregroundStyle(FieldLGXTheme.tertiaryText)

                        Text(job.customer.name)
                            .font(.system(size: 24, weight: .black, design: .rounded))
                            .foregroundStyle(FieldLGXTheme.text)
                            .lineLimit(2)
                            .minimumScaleFactor(0.78)

                        if shouldShowServiceSummary(for: job) {
                            Text(job.serviceSummary)
                                .font(.system(size: 15, weight: .semibold))
                                .foregroundStyle(FieldLGXTheme.secondaryText)
                                .lineLimit(2)
                        }

                        Text(job.property.address)
                            .font(.system(size: 13, weight: .bold))
                            .foregroundStyle(FieldLGXTheme.tertiaryText)
                            .lineLimit(1)
                    }

                    Spacer(minLength: 0)
                }

                    HStack(spacing: 8) {
                        fieldChip(job.assigned.crew ?? job.assigned.employee ?? "Unassigned", icon: "person.2")
                        fieldChip(job.status.replacingOccurrences(of: "_", with: " ").capitalized, icon: "checkmark.circle")
                    }
                }
                .padding(16)
                .frame(maxWidth: .infinity, minHeight: 172, alignment: .leading)
                .background(commandInsetBackground)
                .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
                .overlay(commandPanelStroke(cornerRadius: 24))
            }
            .buttonStyle(.plain)
        } else {
            HStack(spacing: 18) {
                ZStack {
                    RoundedRectangle(cornerRadius: 17, style: .continuous)
                        .fill(FieldLGXTheme.lime)
                    Image(systemName: "plus")
                        .font(.system(size: 22, weight: .black))
                        .foregroundStyle(.black)
                }
                .frame(width: 56, height: 56)
                .shadow(color: FieldLGXTheme.lime.opacity(0.22), radius: 18, x: 0, y: 10)

                VStack(alignment: .leading, spacing: 6) {
                    Text("NEXT IN FIELD")
                        .font(.system(size: 12, weight: .black))
                        .tracking(2.2)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)

                    Text("No field work scheduled")
                        .font(.system(size: 24, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                        .lineLimit(2)

                    Text("Create today’s first job or leave the day open.")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(16)
            .frame(maxWidth: .infinity, minHeight: 150, alignment: .leading)
            .background(commandInsetBackground)
            .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
            .overlay(commandPanelStroke(cornerRadius: 24))
        }
    }

    private func fieldActionDeck(_ command: CommandResponse) -> some View {
        HStack(spacing: 10) {
            NavigationLink {
                CalendarScreen(accessToken: accessToken)
            } label: {
                actionTile("Calendar", "Move work", "calendar", highlighted: true)
            }
            .buttonStyle(.plain)

            NavigationLink {
                WorkScreen(accessToken: accessToken)
            } label: {
                actionTile("Jobs", "\(command.summary.needsScheduled) to schedule", "checklist", highlighted: false)
            }
            .buttonStyle(.plain)

            NavigationLink {
                MoneyScreen(accessToken: accessToken)
            } label: {
                actionTile("Billing", "\(command.summary.readyToBill) ready", "dollarsign.circle", highlighted: false)
            }
            .buttonStyle(.plain)
        }
    }

    private func todayCommandStrip(_ command: CommandResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionKicker("OPERATIONS")
            HStack(spacing: 6) {
                ownerFocusMetric("Today", "\(command.summary.todayJobs)", "jobs")
                ownerFocusMetric("Crews", "\(command.summary.activeRoutes)", "routes")
                ownerFocusMetric("Open", "\(command.summary.unassignedJobs)", "need crew")
                ownerFocusMetric("Bill", money(command.summary.readyToBillTotal), "\(command.summary.readyToBill) visits")
            }
        }
        .padding(12)
        .background(commandPanelGradient)
        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 22))
    }

    private func ownerFocusMetric(_ label: String, _ value: String, _ detail: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label.uppercased())
                .font(.system(size: 9, weight: .black))
                .tracking(1.2)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
                .lineLimit(1)
            Text(value)
                .font(.system(size: 21, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(1)
                .minimumScaleFactor(0.56)
            Text(detail)
                .font(.system(size: 10, weight: .bold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
                .lineLimit(1)
                .minimumScaleFactor(0.62)
        }
        .frame(maxWidth: .infinity, minHeight: 58, alignment: .leading)
        .padding(.horizontal, 8)
        .padding(.vertical, 8)
        .background(commandInsetBackground)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 16))
    }

    private func todayScheduledValue(_ jobs: [TodayJob]) -> String {
        let total = jobs.reduce(Decimal.zero) { runningTotal, job in
            runningTotal + job.serviceItems.reduce(Decimal.zero) { itemTotal, item in
                itemTotal + ((Decimal(string: item.quantity) ?? 0) * (Decimal(string: item.unitPrice) ?? 0))
            }
        }
        guard total > 0 else { return "$0" }

        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.maximumFractionDigits = 0
        return formatter.string(from: total as NSDecimalNumber) ?? "$\(total)"
    }

    private func dispatchCommandStack(_ command: CommandResponse) -> some View {
        VStack(spacing: 8) {
            commandTile(label: "Today", detail: "scheduled visits", value: "\(command.summary.todayJobs)")
            commandTile(label: "Needs crew", detail: "unassigned jobs", value: "\(command.summary.unassignedJobs)")
            commandTile(label: "Scheduled value", detail: "\(command.summary.todayJobs) scheduled visits today", value: money(command.summary.scheduledValue))
        }
    }

    private func money(_ raw: String) -> String {
        let decimal = Decimal(string: raw) ?? 0
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.maximumFractionDigits = 0
        return formatter.string(from: decimal as NSDecimalNumber) ?? "$\(raw)"
    }

    private func shouldShowServiceSummary(for job: TodayJob) -> Bool {
        let summary = job.serviceSummary.trimmingCharacters(in: .whitespacesAndNewlines)
        let address = job.property.address.trimmingCharacters(in: .whitespacesAndNewlines)
        return !summary.isEmpty && summary.localizedCaseInsensitiveCompare(address) != .orderedSame
    }

    private func actionTile(_ title: String, _ detail: String, _ icon: String, highlighted: Bool) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 17, weight: .black))
                .foregroundStyle(highlighted ? .black : FieldLGXTheme.lime)
            Text(title)
                .font(.system(size: 14, weight: .black))
                .foregroundStyle(highlighted ? .black : FieldLGXTheme.text)
            Text(detail)
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(highlighted ? .black.opacity(0.62) : FieldLGXTheme.secondaryText)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity, minHeight: 88, alignment: .leading)
        .padding(12)
        .background(highlighted ? AnyShapeStyle(FieldLGXTheme.lime) : AnyShapeStyle(commandPanelGradient))
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 20).opacity(highlighted ? 0 : 1))
    }

    private func fieldPulse(_ summary: CommandSummary) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionKicker("FIELD PULSE")
            HStack(spacing: 8) {
                pulsePill("Today", "\(summary.todayJobs)", "stops")
                pulsePill("Crew", "\(summary.activeRoutes)", "routes")
                pulsePill("Open", "\(summary.unassignedJobs)", "need crew")
            }
        }
        .padding(16)
        .background(commandPanelGradient)
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 24))
    }

    private func pulsePill(_ label: String, _ value: String, _ detail: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label.uppercased())
                .font(.system(size: 9, weight: .black))
                .tracking(1.3)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            Text(value)
                .font(.system(size: 24, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
            Text(detail)
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
                .lineLimit(1)
                .minimumScaleFactor(0.72)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(commandInsetBackground)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 16))
    }

    private func businessContext(_ summary: CommandSummary) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionKicker("OFFICE CONTEXT")
            Text("Available when you need it")
                .font(.system(size: 22, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                compactMetric("Outstanding", "$\(summary.outstandingTotal)")
                compactMetric("Ready bill", "\(summary.readyToBill)")
                compactMetric("Estimates", "\(summary.openEstimates)")
                compactMetric("Clients", "\(summary.customers)")
            }
        }
        .padding(16)
        .background(commandPanelGradient)
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 24))
    }

    private func compactMetric(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 13, weight: .black))
                .foregroundStyle(FieldLGXTheme.secondaryText)
            Spacer()
            Text(value)
                .font(.system(size: 16, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .padding(12)
        .background(commandInsetBackground)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private func fieldChip(_ title: String, icon: String) -> some View {
        Label(title, systemImage: icon)
            .font(.system(size: 12, weight: .black))
            .foregroundStyle(FieldLGXTheme.secondaryText)
            .padding(.horizontal, 10)
            .frame(height: 32)
            .background(FieldLGXTheme.elevatedBackground)
            .clipShape(Capsule())
            .overlay(Capsule().stroke(FieldLGXTheme.panelStroke, lineWidth: 1))
    }

    private func commandTile(label: String, detail: String, value: String) -> some View {
        HStack(alignment: .center) {
            VStack(alignment: .leading, spacing: 4) {
                Text(label.uppercased())
                    .font(.system(size: 12, weight: .black))
                    .tracking(2.0)
                    .foregroundStyle(FieldLGXTheme.tertiaryText)

                Text(detail)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .lineLimit(1)
                    .minimumScaleFactor(0.74)
            }

            Spacer()

            Text(value)
                .font(.system(size: 34, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(1)
                .minimumScaleFactor(0.72)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 11)
        .frame(minHeight: 64)
        .background(commandInsetBackground)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 18))
    }

    private func morningBrief(_ attention: [CommandAttention]) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 6) {
                    sectionKicker("MORNING BRIEF")
                    Text("Needs your eye")
                        .font(.system(size: 28, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                }

                Spacer()

                Text("Live")
                    .font(.system(size: 14, weight: .black))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(commandInsetBackground)
                    .clipShape(Capsule())
                    .overlay(Capsule().stroke(FieldLGXTheme.panelStroke, lineWidth: 1))
            }

            if attention.isEmpty {
                briefRow(title: "Day looks stable", detail: "No urgent dispatch, billing, or scheduling issues found.", count: "OK", kind: "stable")
            } else {
                ForEach(attention) { item in
                    briefRow(title: item.title, detail: item.detail, count: "\(item.count)", kind: item.kind)
                }
            }
        }
        .padding(18)
        .background(commandPanelGradient)
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 28))
    }

    private func briefRow(title: String, detail: String, count: String, kind: String) -> some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: icon(for: kind))
                .font(.system(size: 16, weight: .black))
                .foregroundStyle(FieldLGXTheme.lime)
                .frame(width: 30, height: 30)
                .background(FieldLGXTheme.elevatedBackground.opacity(0.78))
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))

            VStack(alignment: .leading, spacing: 6) {
                Text(title)
                    .font(.system(size: 17, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                Text(detail)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer()

            Text(count)
                .font(.system(size: 18, weight: .black))
                .foregroundStyle(FieldLGXTheme.lime)
        }
        .padding(14)
        .background(commandInsetBackground)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 20))
    }

    private func statGrid(_ summary: CommandSummary) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
            metric("Outstanding", "$\(summary.outstandingTotal)", "open invoices")
            metric("Estimates", "\(summary.openEstimates)", "open quotes")
            metric("Customers", "\(summary.customers)", "active clients")
            metric("Needs scheduled", "\(summary.needsScheduled)", "queue")
        }
    }

    private func metric(_ label: String, _ value: String, _ detail: String) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(label.uppercased())
                .font(.system(size: 10, weight: .black))
                .tracking(1.8)
                .foregroundStyle(FieldLGXTheme.tertiaryText)

            Text(value)
                .font(.system(size: 30, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(1)
                .minimumScaleFactor(0.65)

            Text(detail)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, minHeight: 124, alignment: .leading)
        .padding(16)
        .background(commandPanelGradient)
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 24))
    }

    private func nextJobs(_ jobs: [TodayJob]) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 5) {
                    Text("TODAY'S WORK")
                        .font(.system(size: 12, weight: .black))
                        .tracking(2.2)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)

                    Text("Next jobs")
                        .font(.system(size: 28, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                }
                Spacer()
                Text("\(jobs.count)")
                    .font(.system(size: 15, weight: .black))
                    .foregroundStyle(FieldLGXTheme.lime)
            }

            if jobs.isEmpty {
                Text("No open field work scheduled today.")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(commandInsetBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                    .overlay(commandPanelStroke(cornerRadius: 20))
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
        .padding(18)
        .background(commandPanelGradient)
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 28))
    }

    private func errorState(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Could not load Command")
                .font(.system(size: 22, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
            Text(message)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(FieldLGXTheme.secondaryText)
            Button("Try again") {
                Task { await loadCommand() }
            }
            .buttonStyle(.borderedProminent)
            .tint(FieldLGXTheme.lime)
            .foregroundStyle(.black)
        }
        .padding(18)
        .background(commandPanelGradient)
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(commandPanelStroke(cornerRadius: 24))
    }

    private func loadCommand() async {
        guard let accessToken, accessToken != "preview-token" else {
            command = .preview
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            command = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).command()
        } catch {
            #if DEBUG
            print("FIELDLGX command load failed: \(error)")
            #endif
            errorMessage = "Check your connection and try again."
        }
    }

    private func icon(for kind: String) -> String {
        switch kind {
        case "schedule": "calendar.badge.clock"
        case "crew": "person.2.badge.gearshape"
        case "billing": "dollarsign.circle"
        case "stable": "checkmark.circle"
        default: "exclamationmark.circle"
        }
    }

    private func sectionKicker(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 12, weight: .black))
            .tracking(2.3)
            .foregroundStyle(FieldLGXTheme.tertiaryText)
    }

    private var commandPanelGradient: LinearGradient {
        FieldLGXTheme.panelGradient
    }

    private var commandInsetBackground: some ShapeStyle {
        FieldLGXTheme.elevatedBackground.opacity(0.78)
    }

    private var commandGridPanel: some View {
        ZStack {
            commandPanelGradient
            FieldLGXGridPattern()
                .stroke(FieldLGXTheme.gridLine, lineWidth: 1)
        }
    }

    private func commandPanelStroke(cornerRadius: CGFloat) -> some View {
        RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
            .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
    }
}

private extension TodayJob {
    var serviceSummary: String {
        if let first = serviceItems.first {
            let detail = first.detailDescription.isEmpty ? first.name : "\(first.name) · \(first.detailDescription)"
            if serviceItems.count > 1 {
                return "\(detail) + \(serviceItems.count - 1) more"
            }
            return detail
        }
        return property.address
    }
}

private extension CommandResponse {
    static let preview = CommandResponse(
        date: "2026-05-06",
        summary: CommandSummary(
            todayJobs: 6,
            activeRoutes: 2,
            unassignedJobs: 1,
            needsScheduled: 3,
            readyToBill: 4,
            readyToBillTotal: "1400.00",
            scheduledValue: "2250.00",
            outstandingTotal: "850.00",
            openEstimates: 2,
            customers: 18
        ),
        attention: [
            CommandAttention(kind: "schedule", title: "Needs scheduled", detail: "3 jobs waiting for a date.", count: 3),
            CommandAttention(kind: "billing", title: "Ready to bill", detail: "4 completed visits ready for invoice review.", count: 4),
        ],
        nextJobs: TodayResponse.preview.jobs,
        serverTime: "2026-05-06T12:00:00Z"
    )
}
