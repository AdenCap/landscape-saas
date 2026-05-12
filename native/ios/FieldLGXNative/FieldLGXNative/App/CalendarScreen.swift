import SwiftData
import SwiftUI
import UniformTypeIdentifiers

struct CalendarScreen: View {
    let accessToken: String?

    @State private var calendar: CalendarResponse?
    @State private var selectedView = "day"
    @State private var selectedCrew = "all"
    @State private var focusedDate = Date()
    @State private var showingCreateJob = false
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var quickEditJob: TodayJob?
    @State private var scheduleMessage: String?

    private let views = ["day", "week", "month"]

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    calendarToolbar
                    viewPicker

                    if isLoading && calendar == nil {
                        ProgressView()
                            .tint(FieldLGXTheme.lime)
                            .frame(maxWidth: .infinity, minHeight: 220)
                    } else if let calendar {
                        dateCommandStrip(calendar)
                        crewFilterStrip(calendar)
                        if let scheduleMessage {
                            scheduleToast(scheduleMessage)
                        }
                        calendarBoard(calendar)
                        if selectedView != "day" {
                            jobsList(calendar)
                        }
                    } else if let errorMessage {
                        errorState(errorMessage)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 16)
                .padding(.bottom, 18)
            }
            .refreshable {
                await loadCalendar()
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .navigationBarBackButtonHidden(true)
        .sheet(isPresented: $showingCreateJob) {
            CreateJobSheet(accessToken: accessToken) {
                await loadCalendar()
            }
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
        .sheet(item: $quickEditJob) { job in
            CalendarQuickEditSheet(accessToken: accessToken, job: job) {
                await loadCalendar()
            }
            .presentationDetents([.medium, .large])
            .presentationDragIndicator(.visible)
        }
        .task(id: "\(selectedView)-\(Self.dayFormatter.string(from: focusedDate))") {
            await loadCalendar()
        }
    }

    private var calendarToolbar: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 8) {
                    Circle()
                        .fill(FieldLGXTheme.lime)
                        .frame(width: 8, height: 8)
                    Text("SCHEDULE COMMAND")
                        .font(.system(size: 12, weight: .black))
                        .tracking(2.2)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                }

                Text("Schedule")
                    .font(.system(size: 26, weight: .black, design: .rounded))
                    .foregroundStyle(FieldLGXTheme.text)
                Text("Drag jobs onto days or time rows. Tap to edit details.")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer()

            Button {
                showingCreateJob = true
            } label: {
                Image(systemName: "plus")
                    .font(.system(size: 24, weight: .black))
                    .foregroundStyle(.black)
                    .frame(width: 48, height: 48)
                    .background(FieldLGXTheme.lime)
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
        }
    }

    private var viewPicker: some View {
        HStack(spacing: 8) {
            ForEach(views, id: \.self) { item in
                Button {
                    selectedView = item
                } label: {
                    Text(item.capitalized)
                        .font(.system(size: 15, weight: .black))
                        .foregroundStyle(selectedView == item ? .black : FieldLGXTheme.secondaryText)
                        .frame(maxWidth: .infinity)
                        .frame(height: 40)
                        .background(selectedView == item ? FieldLGXTheme.lime : FieldLGXTheme.elevatedBackground)
                        .clipShape(Capsule())
                }
                .buttonStyle(.plain)
            }
        }
        .padding(5)
        .background(Color.black.opacity(0.22))
        .clipShape(Capsule())
        .overlay(Capsule().stroke(FieldLGXTheme.panelStroke, lineWidth: 1))
    }

    private func scheduleToast(_ message: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 16, weight: .black))
                .foregroundStyle(FieldLGXTheme.lime)
            Text(message)
                .font(.system(size: 13, weight: .black))
                .foregroundStyle(FieldLGXTheme.text)
            Spacer()
        }
        .padding(12)
        .background(FieldLGXTheme.elevatedBackground)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func dateCommandStrip(_ calendar: CalendarResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Button {
                    movePeriod(by: -1)
                } label: {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 18, weight: .black))
                        .frame(width: 44, height: 44)
                }

                Button {
                    focusedDate = Date()
                } label: {
                    Text("Today")
                        .font(.system(size: 14, weight: .black))
                        .frame(maxWidth: .infinity)
                        .frame(height: 44)
                }

                Button {
                    movePeriod(by: 1)
                } label: {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 18, weight: .black))
                        .frame(width: 44, height: 44)
                }
            }
            .foregroundStyle(FieldLGXTheme.text)
            .background(FieldLGXTheme.elevatedBackground)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
            )

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(dayChips(for: calendar), id: \.dateString) { chip in
                        Button {
                            if let date = Self.dayFormatter.date(from: chip.dateString) {
                                focusedDate = date
                                selectedView = "day"
                            }
                        } label: {
                            VStack(spacing: 4) {
                                Text(chip.weekday)
                                    .font(.system(size: 10, weight: .black))
                                    .tracking(1.1)
                                Text(chip.day)
                                    .font(.system(size: 17, weight: .black, design: .rounded))
                                Text("\(chip.count)")
                                    .font(.system(size: 10, weight: .black))
                                    .foregroundStyle(chip.count == 0 ? FieldLGXTheme.tertiaryText : FieldLGXTheme.lime)
                            }
                            .foregroundStyle(chip.isFocused ? .black : FieldLGXTheme.text)
                            .frame(width: 58, height: 68)
                            .background(chip.isFocused ? FieldLGXTheme.lime : FieldLGXTheme.elevatedBackground)
                            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                            .overlay(
                                RoundedRectangle(cornerRadius: 18, style: .continuous)
                                    .stroke(chip.isFocused ? FieldLGXTheme.lime : FieldLGXTheme.panelStroke, lineWidth: 1)
                            )
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
    }

    private func calendarFocusStrip(_ calendar: CalendarResponse) -> some View {
        HStack(spacing: 8) {
            focusMetric("Jobs", "\(calendar.summary.total)")
            focusMetric("Open", "\(max(calendar.summary.total - calendar.summary.completed, 0))")
            focusMetric("Need crew", "\(calendar.summary.unassigned)")

            Button {
                showingCreateJob = true
            } label: {
                Image(systemName: "plus")
                    .font(.system(size: 18, weight: .black))
                    .foregroundStyle(.black)
                    .frame(width: 48, height: 48)
                    .background(FieldLGXTheme.lime)
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
            }
        }
    }

    private func crewFilterStrip(_ calendar: CalendarResponse) -> some View {
        let crews = crewNames(from: calendar.jobs)
        return ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                crewFilterButton("All crews", value: "all", count: calendar.jobs.count)
                ForEach(crews, id: \.self) { crew in
                    crewFilterButton(crew, value: crew, count: calendar.jobs.filter { crewName(for: $0) == crew }.count)
                }
            }
        }
        .scrollClipDisabled()
    }

    private func crewFilterButton(_ label: String, value: String, count: Int) -> some View {
        Button {
            selectedCrew = value
        } label: {
            HStack(spacing: 8) {
                Text(label)
                    .font(.system(size: 13, weight: .black))
                    .lineLimit(1)
                Text("\(count)")
                    .font(.system(size: 11, weight: .black))
                    .foregroundStyle(selectedCrew == value ? .black.opacity(0.62) : FieldLGXTheme.lime)
                    .frame(minWidth: 24, minHeight: 24)
                    .background((selectedCrew == value ? Color.black : FieldLGXTheme.lime).opacity(0.12))
                    .clipShape(Circle())
            }
            .foregroundStyle(selectedCrew == value ? .black : FieldLGXTheme.text)
            .padding(.horizontal, 14)
            .frame(height: 42)
            .background(selectedCrew == value ? FieldLGXTheme.lime : FieldLGXTheme.elevatedBackground)
            .clipShape(Capsule())
            .overlay(Capsule().stroke(selectedCrew == value ? FieldLGXTheme.lime : FieldLGXTheme.panelStroke, lineWidth: 1))
        }
        .buttonStyle(.plain)
    }

    private func focusMetric(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label.uppercased())
                .font(.system(size: 9, weight: .black))
                .tracking(1.4)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            Text(value)
                .font(.system(size: 20, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
        }
        .frame(maxWidth: .infinity, minHeight: 48, alignment: .leading)
        .padding(.horizontal, 12)
        .background(FieldLGXTheme.panelGradient)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func summaryGrid(_ summary: CalendarSummary) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
            metric("Jobs", "\(summary.total)")
            metric("Open", "\(max(summary.total - summary.completed, 0))")
            metric("Crew", "\(summary.unassigned)")
        }
    }

    private func metric(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label.uppercased())
                .font(.system(size: 10, weight: .black))
                .tracking(1.8)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            Text(value)
                .font(.system(size: 28, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(FieldLGXTheme.panelGradient)
        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func jobsList(_ calendar: CalendarResponse) -> some View {
        let visibleJobs = jobsForActiveScope(calendar.jobs)
        return VStack(alignment: .leading, spacing: 14) {
            Text(activeRangeLabel(calendar))
                .font(.system(size: 12, weight: .black))
                .tracking(1.8)
                .foregroundStyle(FieldLGXTheme.tertiaryText)

            if visibleJobs.isEmpty {
                Text("No jobs scheduled in this view.")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(FieldLGXTheme.elevatedBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
            } else {
                ForEach(visibleJobs) { job in
                    CalendarAgendaRow(job: job, accessToken: accessToken) {
                        quickEditJob = job
                    }
                }
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

    private func calendarBoard(_ calendar: CalendarResponse) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Button { movePeriod(by: -1) } label: {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 24, weight: .black))
                        .foregroundStyle(FieldLGXTheme.text)
                        .frame(width: 52, height: 52)
                }
                .buttonStyle(.plain)

                Button { movePeriod(by: 1) } label: {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 24, weight: .black))
                        .foregroundStyle(FieldLGXTheme.text)
                        .frame(width: 52, height: 52)
                }
                .buttonStyle(.plain)

                Spacer()

                Text(activeRangeLabel(calendar))
                    .font(.system(size: 13, weight: .black))
                    .tracking(1.8)
                    .foregroundStyle(FieldLGXTheme.tertiaryText)
            }

            HStack(spacing: 8) {
                Label(calendarHint, systemImage: selectedView == "month" ? "slider.horizontal.3" : "hand.draw")
                    .font(.system(size: 12, weight: .black))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .lineLimit(2)
                Spacer()
            }
            .padding(.horizontal, 12)
            .frame(minHeight: 38)
            .background(Color.black.opacity(0.16))
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))

            if selectedView == "day" {
                dayTimelineBoard(calendar)
            } else if selectedView == "month" {
                monthOverview(calendar)
            } else {
                weekLaneBoard(calendar)
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

    private var calendarHint: String {
        switch selectedView {
        case "day":
            return "Hold and drag a job to a time row to reschedule today"
        case "week":
            return "Hold and drag a job to another day"
        default:
            return "Tap a day or job to edit schedule, status, notes, and details"
        }
    }

    private func dayTimelineBoard(_ calendar: CalendarResponse) -> some View {
        let visibleJobs = jobsForActiveScope(calendar.jobs)
        let unscheduledJobs = visibleJobs.filter { parsedHour(from: $0.scheduledTime) == nil }

        return VStack(alignment: .leading, spacing: 10) {
            if visibleJobs.isEmpty {
                Text("No crew work scheduled for this day.")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.black.opacity(0.16))
                    .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
            } else {
                if !unscheduledJobs.isEmpty {
                    dayTimelineRow(
                        label: "Any",
                        targetTime: nil,
                        jobs: unscheduledJobs,
                        isAnytime: true
                    )
                }

                ForEach(calendarHourRows, id: \.targetTime) { row in
                    let rowJobs = visibleJobs
                        .filter { parsedHour(from: $0.scheduledTime) == row.hour }
                        .sorted {
                            let lhsTime = $0.scheduledTime ?? "99:99"
                            let rhsTime = $1.scheduledTime ?? "99:99"
                            if lhsTime == rhsTime { return crewName(for: $0) < crewName(for: $1) }
                            return lhsTime < rhsTime
                        }
                    dayTimelineRow(
                        label: row.label,
                        targetTime: row.targetTime,
                        jobs: rowJobs,
                        isAnytime: false
                    )
                }
            }
        }
        .padding(10)
        .background(Color.black.opacity(0.16))
        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        )
    }

    private func dayTimelineRow(label: String, targetTime: String?, jobs: [TodayJob], isAnytime: Bool) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text(label)
                .font(.system(size: 12, weight: .black, design: .rounded))
                .foregroundStyle(isAnytime ? FieldLGXTheme.lime : FieldLGXTheme.tertiaryText)
                .frame(width: 48, alignment: .leading)
                .padding(.top, 13)

            VStack(alignment: .leading, spacing: 8) {
                if jobs.isEmpty {
                    Text("Drop here")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundStyle(FieldLGXTheme.tertiaryText.opacity(0.72))
                        .frame(maxWidth: .infinity, minHeight: 42, alignment: .leading)
                } else {
                    ForEach(jobs) { job in
                        dayTimelineJobCard(job)
                    }
                }
            }
            .padding(8)
            .frame(maxWidth: .infinity, minHeight: jobs.isEmpty ? 58 : nil, alignment: .topLeading)
            .background(Color.black.opacity(jobs.isEmpty ? 0.10 : 0.20))
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(jobs.isEmpty ? Color.white.opacity(0.055) : FieldLGXTheme.panelStroke, lineWidth: 1)
            )
            .onDrop(of: [UTType.text], isTargeted: nil) { providers in
                handleJobDrop(providers, targetDateString: focusedDateString, targetTime: targetTime)
            }
        }
    }

    private func dayTimelineJobCard(_ job: TodayJob) -> some View {
        let accent = serviceAccent(for: job)

        return Button {
            quickEditJob = job
        } label: {
            HStack(spacing: 10) {
                VStack(spacing: 2) {
                    Text(displayTime(for: job))
                        .font(.system(size: 11, weight: .black, design: .rounded))
                        .foregroundStyle(.black)
                        .lineLimit(1)
                        .minimumScaleFactor(0.66)
                    Text(job.status.replacingOccurrences(of: "_", with: " ").uppercased())
                        .font(.system(size: 7, weight: .black))
                        .foregroundStyle(.black.opacity(0.62))
                        .lineLimit(1)
                }
                .frame(width: 54, height: 48)
                .background(accent)
                .clipShape(RoundedRectangle(cornerRadius: 15, style: .continuous))

                VStack(alignment: .leading, spacing: 4) {
                    Text(job.customer.name)
                        .font(.system(size: 16, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                        .lineLimit(1)
                    Text(jobSubtitle(job))
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                        .lineLimit(2)
                    Text(crewName(for: job))
                        .font(.system(size: 10, weight: .black))
                        .tracking(1.1)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                        .lineLimit(1)
                }

                Spacer(minLength: 0)
                Image(systemName: "line.3.horizontal")
                    .font(.system(size: 15, weight: .black))
                    .foregroundStyle(FieldLGXTheme.tertiaryText)
            }
            .padding(10)
            .background(FieldLGXTheme.elevatedBackground)
            .overlay(alignment: .leading) {
                Rectangle()
                    .fill(accent)
                    .frame(width: 5)
            }
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(accent.opacity(0.32), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .onDrag {
            NSItemProvider(object: "\(job.id)" as NSString)
        }
    }

    private func dayCrewBoard(_ calendar: CalendarResponse) -> some View {
        let visibleJobs = jobsForActiveScope(calendar.jobs)
        let sections = crewSections(from: visibleJobs)

        return VStack(alignment: .leading, spacing: 10) {
            if sections.isEmpty {
                Text("No crew work scheduled for this day.")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.black.opacity(0.16))
                    .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
            } else {
                ForEach(sections) { section in
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(section.name.uppercased())
                                    .font(.system(size: 11, weight: .black))
                                    .tracking(1.8)
                                    .foregroundStyle(FieldLGXTheme.lime)
                                Text("\(section.jobs.count) \(section.jobs.count == 1 ? "stop" : "stops")")
                                    .font(.system(size: 13, weight: .bold))
                                    .foregroundStyle(FieldLGXTheme.secondaryText)
                            }
                            Spacer()
                            Image(systemName: "point.topleft.down.curvedto.point.bottomright.up")
                                .font(.system(size: 17, weight: .black))
                                .foregroundStyle(FieldLGXTheme.tertiaryText)
                        }

                        ForEach(section.jobs) { job in
                            let accent = serviceAccent(for: job)

                            Button {
                                quickEditJob = job
                            } label: {
                                HStack(spacing: 12) {
                                    VStack(spacing: 2) {
                                        Text(job.scheduledTime ?? "Any")
                                            .font(.system(size: 13, weight: .black, design: .rounded))
                                            .foregroundStyle(.black)
                                            .lineLimit(1)
                                            .minimumScaleFactor(0.65)
                                        Text(job.status.uppercased())
                                            .font(.system(size: 8, weight: .black))
                                            .foregroundStyle(.black.opacity(0.62))
                                            .lineLimit(1)
                                    }
                                    .frame(width: 58, height: 52)
                                    .background(accent)
                                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))

                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(job.customer.name)
                                            .font(.system(size: 17, weight: .black, design: .rounded))
                                            .foregroundStyle(FieldLGXTheme.text)
                                            .lineLimit(1)
                                        Text(jobSubtitle(job))
                                            .font(.system(size: 13, weight: .semibold))
                                            .foregroundStyle(FieldLGXTheme.secondaryText)
                                            .lineLimit(2)
                                        Text(job.property.address)
                                            .font(.system(size: 11, weight: .bold))
                                            .foregroundStyle(FieldLGXTheme.tertiaryText)
                                            .lineLimit(1)
                                    }

                                    Spacer(minLength: 0)
                                }
                                .padding(12)
                                .background(FieldLGXTheme.elevatedBackground)
                                .overlay(alignment: .leading) {
                                    Rectangle()
                                        .fill(accent)
                                        .frame(width: 5)
                                }
                                .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                                        .stroke(accent.opacity(0.32), lineWidth: 1)
                                )
                            }
                            .buttonStyle(.plain)
                            .onDrag {
                                NSItemProvider(object: "\(job.id)" as NSString)
                            }
                        }
                    }
                    .padding(14)
                    .background(Color.black.opacity(0.16))
                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 22, style: .continuous)
                            .stroke(Color.white.opacity(0.08), lineWidth: 1)
                    )
                }
            }
        }
    }

    private func weekTimeline(_ calendar: CalendarResponse) -> some View {
        VStack(spacing: 0) {
            weekHeader(calendar)
            allDayRow
            timeGrid(jobsForActiveScope(calendar.jobs))
        }
        .background(Color.black.opacity(0.16))
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        )
    }

    private func weekLaneBoard(_ calendar: CalendarResponse) -> some View {
        let days = weekDayModels(from: calendar.range.start)
        let scopedJobs = jobsForActiveScope(calendar.jobs)

        return ScrollView(.horizontal, showsIndicators: false) {
            HStack(alignment: .top, spacing: 10) {
                ForEach(days) { day in
                    let dayJobs = scopedJobs
                        .filter { jobOverlaps($0, dateString: day.dateString) }
                        .sorted {
                            let lhsTime = $0.scheduledTime ?? "99:99"
                            let rhsTime = $1.scheduledTime ?? "99:99"
                            if lhsTime == rhsTime { return crewName(for: $0) < crewName(for: $1) }
                            return lhsTime < rhsTime
                        }

                    VStack(alignment: .leading, spacing: 10) {
                        Button {
                            focusedDate = day.date
                            selectedView = "day"
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(day.weekday)
                                        .font(.system(size: 11, weight: .black))
                                        .tracking(1.7)
                                    Text(day.displayDate)
                                        .font(.system(size: 20, weight: .black, design: .rounded))
                                }
                                Spacer()
                                Text("\(dayJobs.count)")
                                    .font(.system(size: 13, weight: .black))
                                    .foregroundStyle(day.isFocused ? .black : FieldLGXTheme.lime)
                                    .frame(width: 30, height: 30)
                                    .background((day.isFocused ? Color.black : FieldLGXTheme.lime).opacity(0.12))
                                    .clipShape(Circle())
                            }
                            .foregroundStyle(day.isFocused ? .black : FieldLGXTheme.text)
                            .padding(12)
                            .background(day.isFocused ? FieldLGXTheme.lime : FieldLGXTheme.elevatedBackground)
                            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                            .overlay(
                                RoundedRectangle(cornerRadius: 18, style: .continuous)
                                    .stroke(day.isFocused ? FieldLGXTheme.lime : FieldLGXTheme.panelStroke, lineWidth: 1)
                            )
                        }
                        .buttonStyle(.plain)

                        if dayJobs.isEmpty {
                            Text("No jobs")
                                .font(.system(size: 13, weight: .bold))
                                .foregroundStyle(FieldLGXTheme.tertiaryText)
                                .frame(maxWidth: .infinity, minHeight: 72)
                                .background(Color.black.opacity(0.16))
                                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                        } else {
                            ForEach(dayJobs) { job in
                                weekLaneJobCard(job)
                            }
                        }
                    }
                    .padding(10)
                    .frame(width: 224, alignment: .topLeading)
                    .background(Color.black.opacity(0.16))
                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 22, style: .continuous)
                            .stroke(Color.white.opacity(0.08), lineWidth: 1)
                    )
                    .onDrop(of: [UTType.text], isTargeted: nil) { providers in
                        handleJobDrop(providers, targetDateString: day.dateString)
                    }
                }
            }
            .padding(.vertical, 2)
        }
        .scrollClipDisabled()
    }

    private func weekLaneJobCard(_ job: TodayJob) -> some View {
        let accent = serviceAccent(for: job)

        return Button {
            quickEditJob = job
        } label: {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Text(job.scheduledTime ?? "Any")
                        .font(.system(size: 12, weight: .black, design: .rounded))
                        .foregroundStyle(.black)
                        .padding(.horizontal, 8)
                        .frame(height: 28)
                        .background(accent)
                        .clipShape(Capsule())
                    Text(crewName(for: job).uppercased())
                        .font(.system(size: 9, weight: .black))
                        .tracking(1.2)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                        .lineLimit(1)
                    Spacer(minLength: 0)
                }

                Text(job.customer.name)
                    .font(.system(size: 16, weight: .black, design: .rounded))
                    .foregroundStyle(FieldLGXTheme.text)
                    .lineLimit(1)

                Text(jobSubtitle(job))
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .lineLimit(2)
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(FieldLGXTheme.elevatedBackground)
            .overlay(alignment: .leading) {
                Rectangle()
                    .fill(accent)
                    .frame(width: 5)
            }
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(accent.opacity(0.32), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .onDrag {
            NSItemProvider(object: "\(job.id)" as NSString)
        }
    }

    private func monthOverview(_ calendar: CalendarResponse) -> some View {
        let columns = Array(repeating: GridItem(.flexible(), spacing: 6), count: 7)
        let weekdayLabels = ["S", "M", "T", "W", "T", "F", "S"]

        return VStack(alignment: .leading, spacing: 12) {
            LazyVGrid(columns: columns, spacing: 6) {
                ForEach(Array(weekdayLabels.enumerated()), id: \.offset) { _, label in
                    Text(label)
                        .font(.system(size: 10, weight: .black))
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                        .frame(height: 22)
                }

                ForEach(monthCells(for: calendar)) { cell in
                    if let date = cell.date {
                        Button {
                            focusedDate = date
                            selectedView = "day"
                        } label: {
                            VStack(spacing: 4) {
                                Text(cell.day)
                                    .font(.system(size: 14, weight: .black, design: .rounded))
                                Text("\(cell.count)")
                                    .font(.system(size: 9, weight: .black))
                                    .foregroundStyle(cell.count == 0 ? FieldLGXTheme.tertiaryText : FieldLGXTheme.lime)
                            }
                            .foregroundStyle(cell.isFocused ? .black : FieldLGXTheme.text)
                            .frame(maxWidth: .infinity)
                            .frame(height: 48)
                            .background(cell.isFocused ? FieldLGXTheme.lime : FieldLGXTheme.elevatedBackground)
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                            .overlay(
                                RoundedRectangle(cornerRadius: 14, style: .continuous)
                                    .stroke(cell.isFocused ? FieldLGXTheme.lime : FieldLGXTheme.panelStroke, lineWidth: 1)
                            )
                        }
                        .buttonStyle(.plain)
                    } else {
                        Color.clear.frame(height: 48)
                    }
                }
            }

            Text("Tap a day to drill into crew lanes and quick-edit jobs in the field.")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
        }
        .padding(12)
        .background(Color.black.opacity(0.16))
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        )
    }

    private func weekHeader(_ calendar: CalendarResponse) -> some View {
        HStack(spacing: 0) {
            Color.clear
                .frame(width: 50)

            ForEach(weekDays(from: calendar.range.start), id: \.self) { label in
                Text(label)
                    .font(.system(size: 12, weight: .black))
                    .tracking(1.4)
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .lineLimit(2)
                    .minimumScaleFactor(0.7)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity)
                    .frame(height: 62)
                    .background(Color.black.opacity(0.30))
                    .overlay(alignment: .trailing) {
                        Rectangle()
                            .fill(Color.white.opacity(0.055))
                            .frame(width: 1)
                    }
            }
        }
    }

    private var allDayRow: some View {
        HStack(spacing: 0) {
            Text("all-day")
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(FieldLGXTheme.tertiaryText)
                .frame(width: 50, alignment: .leading)
                .padding(.leading, 6)
            Rectangle()
                .fill(Color.white.opacity(0.06))
                .frame(height: 1)
        }
        .frame(height: 28)
        .background(Color.black.opacity(0.14))
    }

    private func timeGrid(_ jobs: [TodayJob]) -> some View {
        ZStack(alignment: .topLeading) {
            VStack(spacing: 0) {
                ForEach(["7am", "8am", "9am", "10am", "11am"], id: \.self) { label in
                    HStack(spacing: 0) {
                        Text(label)
                            .font(.system(size: 12, weight: .bold))
                            .foregroundStyle(FieldLGXTheme.tertiaryText)
                            .frame(width: 50, alignment: .leading)
                            .padding(.leading, 6)

                        HStack(spacing: 0) {
                            ForEach(0..<7, id: \.self) { _ in
                                Rectangle()
                                    .fill(Color.clear)
                                    .overlay(alignment: .trailing) {
                                        Rectangle()
                                            .fill(Color.white.opacity(0.045))
                                            .frame(width: 1)
                                    }
                            }
                        }
                        .overlay(alignment: .top) {
                            Rectangle()
                                .fill(Color.white.opacity(0.055))
                                .frame(height: 1)
                        }
                    }
                    .frame(height: 92)
                }
            }

            ForEach(Array(jobs.prefix(3).enumerated()), id: \.element.id) { index, job in
                calendarJobBlock(job, index: index)
            }
        }
        .frame(height: 460)
        .clipped()
    }

    private func calendarJobBlock(_ job: TodayJob, index: Int) -> some View {
        let accent = serviceAccent(for: job)

        return Button {
            quickEditJob = job
        } label: {
            VStack(alignment: .leading, spacing: 3) {
                Text(job.customer.name)
                    .font(.system(size: 13, weight: .black))
                    .foregroundStyle(.white)
                    .lineLimit(2)
                Text(jobSubtitle(job))
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(.white.opacity(0.86))
                    .lineLimit(3)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            .frame(width: 124, height: 104, alignment: .topLeading)
            .background(serviceGradient(for: job))
            .overlay(alignment: .leading) {
                Rectangle()
                    .fill(accent)
                    .frame(width: 6)
            }
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            .shadow(color: Color.black.opacity(0.22), radius: 12, x: 0, y: 8)
        }
        .buttonStyle(.plain)
        .offset(x: 58 + CGFloat(index % 3) * 42, y: 120 + CGFloat(index) * 58)
    }

    private struct DayChip {
        let dateString: String
        let weekday: String
        let day: String
        let count: Int
        let isFocused: Bool
    }

    private struct CrewSection: Identifiable {
        let id: String
        let name: String
        let jobs: [TodayJob]
    }

    private struct MonthCell: Identifiable {
        let id: String
        let date: Date?
        let day: String
        let count: Int
        let isFocused: Bool
    }

    private struct WeekDayModel: Identifiable {
        var id: String { dateString }

        let date: Date
        let dateString: String
        let weekday: String
        let displayDate: String
        let isFocused: Bool
    }

    private struct CalendarHourRow {
        let hour: Int
        let label: String
        let targetTime: String
    }

    private var calendarHourRows: [CalendarHourRow] {
        (6...19).map { hour in
            let suffix = hour < 12 ? "AM" : "PM"
            let displayHour = hour == 12 ? 12 : hour % 12
            return CalendarHourRow(
                hour: hour,
                label: "\(displayHour) \(suffix)",
                targetTime: String(format: "%02d:00", hour)
            )
        }
    }

    private func dayChips(for calendar: CalendarResponse) -> [DayChip] {
        guard
            let start = Self.dayFormatter.date(from: calendar.range.start),
            let end = Self.dayFormatter.date(from: calendar.range.end)
        else { return [] }
        let focused = Self.dayFormatter.string(from: focusedDate)
        let dates = sequence(first: start) { current in
            Calendar.current.date(byAdding: .day, value: 1, to: current).flatMap { $0 <= end ? $0 : nil }
        }
        let weekdayFormatter = DateFormatter()
        weekdayFormatter.locale = Locale(identifier: "en_US_POSIX")
        weekdayFormatter.dateFormat = "EEE"
        let dayFormatter = DateFormatter()
        dayFormatter.locale = Locale(identifier: "en_US_POSIX")
        dayFormatter.dateFormat = "d"
        return dates.map { date in
            let value = Self.dayFormatter.string(from: date)
            let count = calendar.jobs.filter { job in
                guard let jobDate = job.scheduledDate else { return false }
                if let endDate = job.scheduledEndDate {
                    return jobDate <= value && value <= endDate
                }
                return jobDate == value
            }.count
            return DayChip(
                dateString: value,
                weekday: weekdayFormatter.string(from: date).uppercased(),
                day: dayFormatter.string(from: date),
                count: count,
                isFocused: value == focused
            )
        }
    }

    private func moveDate(by days: Int) {
        if let next = Calendar.current.date(byAdding: .day, value: days, to: focusedDate) {
            focusedDate = next
        }
    }

    private func movePeriod(by direction: Int) {
        if selectedView == "month" {
            if let next = Calendar.current.date(byAdding: .month, value: direction, to: focusedDate) {
                focusedDate = next
            }
        } else if selectedView == "week" {
            moveDate(by: direction * 7)
        } else {
            moveDate(by: direction)
        }
    }

    private func jobsForActiveScope(_ jobs: [TodayJob]) -> [TodayJob] {
        let crewFiltered = jobs.filter { selectedCrew == "all" || crewName(for: $0) == selectedCrew }
        guard selectedView == "day" else { return crewFiltered }
        return crewFiltered.filter { jobOverlaps($0, dateString: focusedDateString) }
    }

    private func jobOverlaps(_ job: TodayJob, dateString: String) -> Bool {
        guard let startDate = job.scheduledDate else { return false }
        if let endDate = job.scheduledEndDate {
            return startDate <= dateString && dateString <= endDate
        }
        return startDate == dateString
    }

    private func crewName(for job: TodayJob) -> String {
        job.assigned.crew ?? job.assigned.employee ?? "Unassigned"
    }

    private func crewNames(from jobs: [TodayJob]) -> [String] {
        Array(Set(jobs.map { crewName(for: $0) })).sorted { lhs, rhs in
            if lhs == "Unassigned" { return false }
            if rhs == "Unassigned" { return true }
            return lhs < rhs
        }
    }

    private func crewSections(from jobs: [TodayJob]) -> [CrewSection] {
        crewNames(from: jobs).map { crew in
            CrewSection(
                id: crew,
                name: crew,
                jobs: jobs
                    .filter { crewName(for: $0) == crew }
                    .sorted {
                        let lhsTime = $0.scheduledTime ?? "99:99"
                        let rhsTime = $1.scheduledTime ?? "99:99"
                        if lhsTime == rhsTime {
                            return $0.routeOrder < $1.routeOrder
                        }
                        return lhsTime < rhsTime
                    }
            )
        }
    }

    private func monthCells(for calendar: CalendarResponse) -> [MonthCell] {
        let systemCalendar = Calendar.current
        let focusedComponents = systemCalendar.dateComponents([.year, .month], from: focusedDate)
        guard
            let monthStart = systemCalendar.date(from: focusedComponents),
            let range = systemCalendar.range(of: .day, in: .month, for: monthStart)
        else { return [] }

        let leadingBlanks = max(systemCalendar.component(.weekday, from: monthStart) - 1, 0)
        let filteredJobs = jobsForActiveScope(calendar.jobs)
        var cells: [MonthCell] = (0..<leadingBlanks).map {
            MonthCell(id: "blank-\($0)", date: nil, day: "", count: 0, isFocused: false)
        }

        for day in range {
            guard let date = systemCalendar.date(byAdding: .day, value: day - 1, to: monthStart) else { continue }
            let dateString = Self.dayFormatter.string(from: date)
            let count = filteredJobs.filter { jobOverlaps($0, dateString: dateString) }.count
            cells.append(
                MonthCell(
                    id: dateString,
                    date: date,
                    day: "\(day)",
                    count: count,
                    isFocused: dateString == focusedDateString
                )
            )
        }
        return cells
    }

    private func activeRangeLabel(_ calendar: CalendarResponse) -> String {
        if selectedView == "day" {
            return focusedDateString
        }
        return "\(calendar.range.start) to \(calendar.range.end)"
    }

    private var focusedDateString: String {
        Self.dayFormatter.string(from: focusedDate)
    }

    private func weekDays(from start: String) -> [String] {
        let parser = DateFormatter()
        parser.calendar = Calendar(identifier: .gregorian)
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.dateFormat = "yyyy-MM-dd"

        let dayFormatter = DateFormatter()
        dayFormatter.locale = Locale(identifier: "en_US_POSIX")
        dayFormatter.dateFormat = "EEE\nM/d"

        guard let startDate = parser.date(from: start) else {
            return ["Sun\n4/26", "Mon\n4/27", "Tue\n4/28", "Wed\n4/29", "Thu\n4/30", "Fri\n5/1", "Sat\n5/2"]
        }

        return (0..<7).compactMap { offset in
            guard let date = Calendar.current.date(byAdding: .day, value: offset, to: startDate) else { return nil }
            return dayFormatter.string(from: date).uppercased()
        }
    }

    private func weekDayModels(from start: String) -> [WeekDayModel] {
        guard let startDate = Self.dayFormatter.date(from: start) else { return [] }
        let weekdayFormatter = DateFormatter()
        weekdayFormatter.locale = Locale(identifier: "en_US_POSIX")
        weekdayFormatter.dateFormat = "EEE"
        let dateFormatter = DateFormatter()
        dateFormatter.locale = Locale(identifier: "en_US_POSIX")
        dateFormatter.dateFormat = "M/d"

        return (0..<7).compactMap { offset in
            guard let date = Calendar.current.date(byAdding: .day, value: offset, to: startDate) else { return nil }
            let dateString = Self.dayFormatter.string(from: date)
            return WeekDayModel(
                date: date,
                dateString: dateString,
                weekday: weekdayFormatter.string(from: date).uppercased(),
                displayDate: dateFormatter.string(from: date),
                isFocused: dateString == focusedDateString
            )
        }
    }

    private func jobSubtitle(_ job: TodayJob) -> String {
        if let item = job.serviceItems.first {
            let detail = item.detailDescription.isEmpty ? item.name : "\(item.name) - \(item.detailDescription)"
            if job.serviceItems.count > 1 {
                return "\(detail) + \(job.serviceItems.count - 1) more"
            }
            return detail
        }
        return job.property.address
    }

    private func serviceAccent(for job: TodayJob) -> Color {
        if let override = job.jobColorOverride, let color = Color(hex: override) {
            return color
        }
        if let statusColor = job.statusColor, let color = Color(hex: statusColor) {
            return color
        }
        if let colorValue = job.color, let color = Color(hex: colorValue) {
            return color
        }
        let key = serviceKey(for: job)
        if key.contains("fert") || key.contains("spray") || key.contains("weed") {
            return Color(red: 0.64, green: 0.94, blue: 0.29)
        }
        if key.contains("land") || key.contains("mulch") || key.contains("install") || key.contains("project") {
            return Color(red: 0.98, green: 0.66, blue: 0.28)
        }
        if key.contains("snow") || key.contains("ice") {
            return Color(red: 0.55, green: 0.82, blue: 1.00)
        }
        if key.contains("hardscape") || key.contains("patio") || key.contains("stone") {
            return Color(red: 0.72, green: 0.66, blue: 1.00)
        }
        if key.contains("mow") || key.contains("lawn") {
            return Color(red: 0.25, green: 0.52, blue: 0.96)
        }
        return FieldLGXTheme.lime
    }

    private func serviceGradient(for job: TodayJob) -> LinearGradient {
        let accent = serviceAccent(for: job)
        return LinearGradient(
            colors: [
                accent.opacity(0.88),
                accent.opacity(0.58),
                Color.black.opacity(0.35)
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    private func serviceKey(for job: TodayJob) -> String {
        let names = job.serviceItems
            .map { "\($0.name) \($0.detailDescription)" }
            .joined(separator: " ")
            .lowercased()
        if !names.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return names
        }
        return "\(job.notes) \(job.property.address)".lowercased()
    }

    private func parsedHour(from value: String?) -> Int? {
        guard let value, !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return nil
        }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        for format in ["HH:mm", "H:mm", "h:mm a"] {
            let formatter = DateFormatter()
            formatter.locale = Locale(identifier: "en_US_POSIX")
            formatter.dateFormat = format
            if let date = formatter.date(from: trimmed) {
                return Calendar.current.component(.hour, from: date)
            }
        }
        if let hour = Int(trimmed.prefix(2)) {
            return hour
        }
        return nil
    }

    private func displayTime(for job: TodayJob) -> String {
        guard let value = job.scheduledTime, !value.isEmpty else { return "Any" }
        for format in ["HH:mm", "H:mm"] {
            let parser = DateFormatter()
            parser.locale = Locale(identifier: "en_US_POSIX")
            parser.dateFormat = format
            if let date = parser.date(from: value) {
                let display = DateFormatter()
                display.locale = Locale(identifier: "en_US_POSIX")
                display.dateFormat = "h:mm a"
                return display.string(from: date)
            }
        }
        return value
    }

    private func handleJobDrop(_ providers: [NSItemProvider], targetDateString: String, targetTime: String? = nil) -> Bool {
        guard let provider = providers.first(where: { $0.hasItemConformingToTypeIdentifier(UTType.text.identifier) }) else {
            return false
        }
        provider.loadItem(forTypeIdentifier: UTType.text.identifier, options: nil) { item, _ in
            let rawValue: String?
            if let data = item as? Data {
                rawValue = String(data: data, encoding: .utf8)
            } else {
                rawValue = item as? String
            }
            guard let rawValue, let jobID = Int(rawValue.trimmingCharacters(in: .whitespacesAndNewlines)) else { return }
            Task { @MainActor in
                await moveJob(jobID: jobID, to: targetDateString, at: targetTime)
            }
        }
        return true
    }

    @MainActor
    private func moveJob(jobID: Int, to targetDateString: String, at targetTime: String? = nil) async {
        guard let job = calendar?.jobs.first(where: { $0.id == jobID }) else { return }
        let requestedTime = targetTime ?? job.scheduledTime
        if job.scheduledDate == targetDateString && requestedTime == job.scheduledTime {
            scheduleMessage = "\(job.customer.name) is already scheduled there."
            return
        }

        guard let accessToken, accessToken != "preview-token" else {
            scheduleMessage = "Moved \(job.customer.name) to \(targetDateString)\(targetTime.map { " at \($0)" } ?? "")."
            return
        }

        let shiftedEndDate = shiftedEndDate(for: job, targetDateString: targetDateString)
        let shiftedEndTime = shiftedEndTime(for: job, targetTime: requestedTime)

        do {
            _ = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).updateJob(
                id: job.id,
                scheduledDate: targetDateString,
                scheduledTime: requestedTime ?? "08:00",
                scheduledEndDate: shiftedEndDate,
                scheduledEndTime: shiftedEndTime,
                notes: job.notes,
                status: job.status
            )
            scheduleMessage = "Moved \(job.customer.name) to \(targetDateString)\(targetTime.map { " at \($0)" } ?? "")."
            await loadCalendar()
        } catch {
            scheduleMessage = "Could not move \(job.customer.name). Open the job to edit it."
        }
    }

    private func shiftedEndTime(for job: TodayJob, targetTime: String?) -> String {
        guard
            let targetTime,
            let originalStart = parseTimeValue(job.scheduledTime),
            let originalEnd = parseTimeValue(job.scheduledEndTime),
            let targetStart = parseTimeValue(targetTime)
        else {
            return job.scheduledEndTime ?? ""
        }

        let duration = Calendar.current.dateComponents([.minute], from: originalStart, to: originalEnd).minute ?? 0
        guard duration > 0, let targetEnd = Calendar.current.date(byAdding: .minute, value: duration, to: targetStart) else {
            return job.scheduledEndTime ?? ""
        }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "HH:mm"
        return formatter.string(from: targetEnd)
    }

    private func parseTimeValue(_ value: String?) -> Date? {
        guard let value, !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return nil
        }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        for format in ["HH:mm", "H:mm", "h:mm a"] {
            let formatter = DateFormatter()
            formatter.locale = Locale(identifier: "en_US_POSIX")
            formatter.dateFormat = format
            if let date = formatter.date(from: trimmed) {
                return date
            }
        }
        return nil
    }

    private func shiftedEndDate(for job: TodayJob, targetDateString: String) -> String {
        guard
            let startString = job.scheduledDate,
            let endString = job.scheduledEndDate,
            let startDate = Self.dayFormatter.date(from: startString),
            let endDate = Self.dayFormatter.date(from: endString),
            let targetDate = Self.dayFormatter.date(from: targetDateString)
        else {
            return ""
        }

        let span = max(Calendar.current.dateComponents([.day], from: startDate, to: endDate).day ?? 0, 0)
        guard span > 0, let shiftedEnd = Calendar.current.date(byAdding: .day, value: span, to: targetDate) else {
            return ""
        }
        return Self.dayFormatter.string(from: shiftedEnd)
    }

    private func errorState(_ message: String) -> some View {
        Text(message)
            .font(.system(size: 15, weight: .semibold))
            .foregroundStyle(FieldLGXTheme.secondaryText)
            .padding(18)
            .background(FieldLGXTheme.panelGradient)
            .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
    }

    private func loadCalendar() async {
        guard let accessToken, accessToken != "preview-token" else {
            calendar = .preview
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            calendar = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
                .calendar(date: focusedDate, view: selectedView)
        } catch {
            #if DEBUG
            print("FIELDLGX calendar load failed: \(error)")
            #endif
            errorMessage = "Could not load the calendar."
        }
    }

    private static let dayFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()
}

private struct CalendarAgendaRow: View {
    let job: TodayJob
    let accessToken: String?
    let editSchedule: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 12) {
                VStack(spacing: 3) {
                    Text(timeText)
                        .font(.system(size: 15, weight: .black, design: .rounded))
                        .foregroundStyle(.black)
                    Text(dayText)
                        .font(.system(size: 9, weight: .black))
                        .tracking(1.0)
                        .foregroundStyle(.black.opacity(0.62))
                }
                .frame(width: 62, height: 58)
                .background(FieldLGXTheme.lime)
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))

                VStack(alignment: .leading, spacing: 5) {
                    Text(job.customer.name)
                        .font(.system(size: 18, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                        .lineLimit(1)
                    Text(subtitle)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                        .lineLimit(2)
                    Text(job.assigned.crew ?? job.assigned.employee ?? "Unassigned")
                        .font(.system(size: 11, weight: .black))
                        .tracking(1.4)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                        .lineLimit(1)
                }

                Spacer(minLength: 6)
            }

            HStack(spacing: 9) {
                Button(action: editSchedule) {
                    Label("Edit schedule", systemImage: "calendar.badge.clock")
                        .font(.system(size: 13, weight: .black))
                        .foregroundStyle(.black)
                        .frame(maxWidth: .infinity)
                        .frame(height: 42)
                        .background(FieldLGXTheme.lime)
                        .clipShape(Capsule())
                }

                NavigationLink {
                    JobDetailScreen(jobID: job.id, accessToken: accessToken, previewJob: job)
                } label: {
                    Label("Details", systemImage: "arrow.right")
                        .font(.system(size: 13, weight: .black))
                        .foregroundStyle(FieldLGXTheme.text)
                        .frame(maxWidth: .infinity)
                        .frame(height: 42)
                        .background(FieldLGXTheme.elevatedBackground)
                        .clipShape(Capsule())
                        .overlay(Capsule().stroke(FieldLGXTheme.panelStroke, lineWidth: 1))
                }
            }
        }
        .padding(14)
        .background(FieldLGXTheme.elevatedBackground)
        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private var subtitle: String {
        if let item = job.serviceItems.first {
            let detail = item.detailDescription.isEmpty ? item.name : "\(item.name) - \(item.detailDescription)"
            if job.serviceItems.count > 1 {
                return "\(detail) + \(job.serviceItems.count - 1) more"
            }
            return detail
        }
        return job.property.address
    }

    private var timeText: String {
        job.scheduledTime ?? "Any"
    }

    private var dayText: String {
        guard let value = job.scheduledDate else { return "DATE" }
        let parser = DateFormatter()
        parser.calendar = Calendar(identifier: .gregorian)
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.dateFormat = "yyyy-MM-dd"
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "MMM d"
        guard let date = parser.date(from: value) else { return "DATE" }
        return formatter.string(from: date).uppercased()
    }
}

private struct CalendarQuickEditSheet: View {
    let accessToken: String?
    let job: TodayJob
    let onSaved: () async -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var scheduledDate: Date
    @State private var scheduledEndDate: Date
    @State private var scheduledTime: Date
    @State private var scheduledEndTime: Date
    @State private var spansMultipleDays: Bool
    @State private var status: String
    @State private var notes: String
    @State private var selectedColor: String
    @State private var isSaving = false
    @State private var errorMessage: String?

    init(accessToken: String?, job: TodayJob, onSaved: @escaping () async -> Void) {
        self.accessToken = accessToken
        self.job = job
        self.onSaved = onSaved
        _scheduledDate = State(initialValue: Self.parseDay(job.scheduledDate))
        _scheduledEndDate = State(initialValue: Self.parseDay(job.scheduledEndDate ?? job.scheduledDate))
        _scheduledTime = State(initialValue: Self.parseTime(job.scheduledTime))
        _scheduledEndTime = State(initialValue: Self.parseTime(job.scheduledEndTime))
        _spansMultipleDays = State(initialValue: (job.scheduledEndDate ?? job.scheduledDate) != job.scheduledDate)
        _status = State(initialValue: job.status)
        _notes = State(initialValue: job.notes)
        _selectedColor = State(initialValue: job.jobColorOverride ?? job.statusColor ?? job.color ?? "#3b82f6")
    }

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()

            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("EDIT FROM CALENDAR")
                                .font(.system(size: 12, weight: .black))
                                .tracking(2.2)
                                .foregroundStyle(FieldLGXTheme.lime)
                            Text(job.customer.name)
                                .font(.system(size: 30, weight: .black, design: .rounded))
                                .foregroundStyle(FieldLGXTheme.text)
                                .lineLimit(2)
                            Text(job.property.address)
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(FieldLGXTheme.secondaryText)
                        }
                        Spacer()
                        Button {
                            Task { await save() }
                        } label: {
                            Text(isSaving ? "Saving" : "Save")
                                .font(.system(size: 14, weight: .black))
                                .foregroundStyle(.black)
                                .padding(.horizontal, 14)
                                .frame(height: 38)
                                .background(FieldLGXTheme.lime)
                                .clipShape(Capsule())
                        }
                        .disabled(isSaving)

                        Button(action: { dismiss() }) {
                            Image(systemName: "xmark")
                                .font(.system(size: 15, weight: .black))
                                .foregroundStyle(FieldLGXTheme.text)
                                .frame(width: 38, height: 38)
                                .background(FieldLGXTheme.elevatedBackground)
                                .clipShape(Circle())
                        }
                    }

                    HStack(spacing: 8) {
                        jumpButton("Tomorrow", days: 1)
                        jumpButton("+1 Week", days: 7)
                        jumpButton("+2 Weeks", days: 14)
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        sheetLabel("Schedule")
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
                    .fieldPanel(padding: 16)

                    VStack(alignment: .leading, spacing: 12) {
                        sheetLabel("Status")
                        Picker("Status", selection: $status) {
                            Text("Scheduled").tag("scheduled")
                            Text("In progress").tag("in_progress")
                            Text("Completed").tag("completed")
                            Text("Skipped").tag("skipped")
                        }
                        .pickerStyle(.segmented)
                    }
                    .fieldPanel(padding: 16)

                    VStack(alignment: .leading, spacing: 12) {
                        sheetLabel("Calendar color")
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
                                .accessibilityLabel("Set calendar color \(hex)")
                            }
                        }
                    }
                    .fieldPanel(padding: 16)

                    VStack(alignment: .leading, spacing: 10) {
                        sheetLabel("Crew notes")
                        TextField("Notes for this job", text: $notes, axis: .vertical)
                            .font(.system(size: 17, weight: .semibold))
                            .lineLimit(3...6)
                            .foregroundStyle(FieldLGXTheme.text)
                            .padding(14)
                            .fieldInsetSurface()
                    }
                    .fieldPanel(padding: 16)

                    if let errorMessage {
                        Text(errorMessage)
                            .font(.system(size: 14, weight: .bold))
                            .foregroundStyle(.red)
                    }

                    Button {
                        Task { await save() }
                    } label: {
                        HStack {
                            if isSaving {
                                ProgressView()
                                    .tint(.black)
                            }
                            Text(isSaving ? "Saving" : "Save schedule")
                            Spacer()
                            Image(systemName: "checkmark")
                        }
                        .font(.system(size: 17, weight: .black))
                        .foregroundStyle(.black)
                        .padding(.horizontal, 16)
                        .frame(height: 54)
                        .background(FieldLGXTheme.lime)
                        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                    }
                    .disabled(isSaving)
                }
                .padding(18)
            }
        }
        .preferredColorScheme(.dark)
    }

    private func jumpButton(_ title: String, days: Int) -> some View {
        Button {
            if let date = Calendar.current.date(byAdding: .day, value: days, to: Date()) {
                scheduledDate = date
            }
        } label: {
            Text(title)
                .font(.system(size: 13, weight: .black))
                .foregroundStyle(FieldLGXTheme.text)
                .frame(maxWidth: .infinity)
                .frame(height: 42)
                .background(FieldLGXTheme.elevatedBackground)
                .clipShape(Capsule())
                .overlay(Capsule().stroke(FieldLGXTheme.panelStroke, lineWidth: 1))
        }
    }

    private func sheetLabel(_ text: String) -> some View {
        Text(text.uppercased())
            .font(.system(size: 11, weight: .black))
            .tracking(1.8)
            .foregroundStyle(FieldLGXTheme.tertiaryText)
    }

    private func save() async {
        guard let accessToken, accessToken != "preview-token" else {
            await onSaved()
            dismiss()
            return
        }

        isSaving = true
        errorMessage = nil
        defer { isSaving = false }

        do {
            _ = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).updateJob(
                id: job.id,
                scheduledDate: Self.dayFormatter.string(from: scheduledDate),
                scheduledTime: Self.timeFormatter.string(from: scheduledTime),
                scheduledEndDate: spansMultipleDays ? Self.dayFormatter.string(from: scheduledEndDate) : "",
                scheduledEndTime: spansMultipleDays ? Self.timeFormatter.string(from: scheduledEndTime) : "",
                notes: notes,
                status: status,
                color: selectedColor
            )
            await onSaved()
            dismiss()
        } catch {
            errorMessage = "Could not update this job. Check the connection and try again."
        }
    }

    private static func parseDay(_ value: String?) -> Date {
        guard let value, let date = dayFormatter.date(from: value) else { return Date() }
        return date
    }

    private static let calendarColors = [
        "#3b82f6", "#22c55e", "#f59e0b", "#ef4444",
        "#8b5cf6", "#ec4899", "#06b6d4", "#94a3b8"
    ]

    private static func parseTime(_ value: String?) -> Date {
        guard let value, let date = timeFormatter.date(from: value) else { return Date() }
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
}

struct CreateJobSheet: View {
    let accessToken: String?
    let onCreated: () async -> Void

    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @State private var options: JobOptionsResponse?
    @State private var selectedPropertyID: Int?
    @State private var selectedServiceID: Int?
    @State private var selectedCrewID: Int?
    @State private var scheduledDate = Date()
    @State private var scheduledTime = Date()
    @State private var notes = ""
    @State private var serviceDetail = ""
    @State private var isSaving = false
    @State private var errorMessage: String?
    @State private var offlineMessage: String?
    @State private var showingCreateClient = false

    var body: some View {
        NavigationStack {
            ZStack {
                FieldLGXScreenBackground()

                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        Text("NEW JOB")
                            .font(.system(size: 12, weight: .black))
                            .tracking(2.4)
                            .foregroundStyle(FieldLGXTheme.lime)
                        Text("Create job")
                            .font(.system(size: 34, weight: .black, design: .rounded))
                            .foregroundStyle(FieldLGXTheme.text)

                        if let options {
                            pickerCard("Client property", selection: $selectedPropertyID, items: options.properties) { property in
                                "\(property.customerName) - \(property.address)"
                            }
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
                            pickerCard("Service", selection: $selectedServiceID, items: options.services) { service in
                                "\(service.name) - $\(service.unitPrice)"
                            }
                            pickerCard("Crew", selection: $selectedCrewID, items: options.crews) { crew in
                                crew.name
                            }
                            dateControls
                            field("Job notes", text: $notes, axis: .vertical)
                            field("Service description", text: $serviceDetail, axis: .vertical)
                        } else {
                            ProgressView()
                                .tint(FieldLGXTheme.lime)
                                .frame(maxWidth: .infinity, minHeight: 180)
                        }

                        if let errorMessage {
                            Text(errorMessage)
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(.red)
                        }
                        if let offlineMessage {
                            Text(offlineMessage)
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(FieldLGXTheme.lime)
                        }

                        Button {
                            Task { await save() }
                        } label: {
                            HStack {
                                Text(isSaving ? "Creating" : "Create job")
                                Spacer()
                                Image(systemName: "arrow.right")
                            }
                            .font(.system(size: 17, weight: .black))
                            .foregroundStyle(.black)
                            .padding(.horizontal, 16)
                            .frame(height: 52)
                            .background(FieldLGXTheme.lime)
                            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                        }
                        .disabled(selectedPropertyID == nil || isSaving || options == nil)
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
        .task {
            await loadOptions()
        }
        .sheet(isPresented: $showingCreateClient) {
            CreateClientSheet(accessToken: accessToken) { response in
                let propertyID = response.client.properties.first?.id
                await loadOptions(selecting: propertyID)
            }
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
    }

    private var dateControls: some View {
        VStack(alignment: .leading, spacing: 10) {
            DatePicker("Date", selection: $scheduledDate, displayedComponents: .date)
            DatePicker("Time", selection: $scheduledTime, displayedComponents: .hourAndMinute)
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

    private func pickerCard<Item: Identifiable>(_ title: String, selection: Binding<Int?>, items: [Item], label: @escaping (Item) -> String) -> some View where Item.ID == Int {
        VStack(alignment: .leading, spacing: 6) {
            Text(title.uppercased())
                .font(.system(size: 10, weight: .black))
                .tracking(1.8)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            Picker(title, selection: selection) {
                Text("Select").tag(Int?.none)
                ForEach(items) { item in
                    Text(label(item)).tag(Optional(item.id))
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

    private func field(_ title: String, text: Binding<String>, axis: Axis = .horizontal) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title.uppercased())
                .font(.system(size: 10, weight: .black))
                .tracking(1.8)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            TextField(title, text: text, axis: axis)
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

    private func loadOptions(selecting preferredPropertyID: Int? = nil) async {
        guard let accessToken, accessToken != "preview-token" else {
            options = .preview
            selectedPropertyID = preferredPropertyID ?? options?.properties.first?.id
            selectedServiceID = options?.services.first?.id
            return
        }

        do {
            let response = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).jobOptions()
            options = response
            selectedPropertyID = preferredPropertyID ?? response.properties.first?.id
            selectedServiceID = response.services.first?.id
            selectedCrewID = response.crews.first?.id
        } catch {
            errorMessage = "Could not load job options."
        }
    }

    private func save() async {
        guard let propertyID = selectedPropertyID else { return }
        guard let accessToken, accessToken != "preview-token" else {
            dismiss()
            return
        }
        isSaving = true
        errorMessage = nil
        defer { isSaving = false }

        let service = options?.services.first { $0.id == selectedServiceID }
        let item = service.map {
            JobCreateServiceItem(
                serviceID: $0.id,
                description: $0.name,
                detailDescription: serviceDetail,
                quantity: "1",
                unit: $0.unit,
                unitPrice: $0.unitPrice
            )
        }

        do {
            _ = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).createJob(
                propertyID: propertyID,
                scheduledDate: Self.dayFormatter.string(from: scheduledDate),
                scheduledTime: Self.timeFormatter.string(from: scheduledTime),
                notes: notes,
                serviceItem: item,
                crewID: selectedCrewID
            )
            await onCreated()
            dismiss()
        } catch {
            do {
                var payload: [String: Any] = [
                    "property_id": propertyID,
                    "scheduled_date": Self.dayFormatter.string(from: scheduledDate),
                    "scheduled_time": Self.timeFormatter.string(from: scheduledTime),
                    "notes": notes,
                ]
                if let selectedCrewID {
                    payload["assigned_crew_id"] = selectedCrewID
                }
                if let item {
                    payload["service_items"] = [item.dictionary]
                }
                try SyncQueue(modelContext: modelContext).enqueue(
                    entityType: "job",
                    serverID: nil,
                    operation: .create,
                    payload: payload,
                    baseRevision: nil
                )
                offlineMessage = "Saved offline. This job will sync when service is back."
                dismiss()
            } catch {
                errorMessage = "Could not create this job or save it offline."
            }
        }
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
}

private extension CalendarResponse {
    static let preview = CalendarResponse(
        view: "week",
        date: "2026-05-08",
        range: CalendarRange(start: "2026-05-04", end: "2026-05-10"),
        summary: CalendarSummary(total: 2, unassigned: 1, completed: 0),
        jobs: TodayResponse.preview.jobs,
        serverTime: "2026-05-08T12:00:00Z"
    )
}

private extension JobOptionsResponse {
    static let preview = JobOptionsResponse(
        properties: [
            JobOptionProperty(id: 1, customerID: 1, customerName: "Willow Creek", address: "42 Willow Lane")
        ],
        services: [
            JobOptionService(id: 1, name: "Mowing", unit: "visit", unitPrice: "65.00")
        ],
        crews: [
            JobOptionCrew(id: 1, name: "Crew A")
        ],
        serverTime: "2026-05-08T12:00:00Z"
    )
}
