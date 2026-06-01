import CoreLocation
import SwiftData
import SwiftUI

struct TodayScreen: View {
    let accessToken: String?

    @Environment(\.modelContext) private var modelContext
    @Environment(\.openURL) private var openURL
    @Environment(\.fieldLGXUsesOwnerChrome) private var usesOwnerChrome

    @State private var today: TodayResponse?
    @State private var timeClock: TimeClockResponse?
    @State private var isLoading = false
    @State private var isClocking = false
    @State private var errorMessage: String?
    @State private var timeClockMessage: String?
    @State private var syncMessage: String?
    @State private var pendingOfflineCount = 0
    @State private var isSyncing = false
    @State private var locationProvider = FieldLocationProvider()

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    header

                    if isLoading {
                        ProgressView()
                            .tint(FieldLGXTheme.lime)
                            .frame(maxWidth: .infinity, minHeight: 180)
                    } else if let today {
                        syncCard
                        nextStopPanel(today)
                        fieldPacketCard
                        timeClockCard
                        routeStatusStrip(today.summary)

                        if today.jobs.isEmpty {
                            emptyState
                        } else {
                            ForEach(today.jobs) { job in
                                NavigationLink {
                                    JobDetailScreen(
                                        jobID: job.id,
                                        accessToken: accessToken,
                                        previewJob: job
                                    )
                                } label: {
                                    TodayJobCard(job: job)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    } else if let errorMessage {
                        errorState(errorMessage)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, usesOwnerChrome ? FieldLGXTheme.ownerTopOffset : 20)
                .padding(.bottom, 96)
            }
            .refreshable {
                await loadToday()
                await loadTimeClock()
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .navigationBarBackButtonHidden(true)
        .task {
            await loadToday()
            await loadTimeClock()
            refreshPendingCount()
        }
        .task(id: timeClock?.isClockedIn ?? false) {
            guard timeClock?.isClockedIn == true else { return }
            await runLocationPingLoop()
        }
    }

    private var header: some View {
        FieldLGXMobileHeader(
            eyebrow: "Field route",
            title: "Today",
            subtitle: "Clock in, follow the route, and update each job from the field."
        )
    }

    private func summary(_ summary: TodaySummary) -> some View {
        HStack(spacing: 10) {
            metric("Stops", summary.total)
            metric("Open", summary.remaining)
            metric("Done", summary.completed)
        }
    }

    @ViewBuilder
    private func nextStopPanel(_ today: TodayResponse) -> some View {
        if let job = today.jobs.first(where: { $0.status != "completed" && $0.status != "cancelled" }) ?? today.jobs.first {
            VStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .top, spacing: 12) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("NEXT STOP")
                            .font(.system(size: 11, weight: .black))
                            .tracking(2.0)
                            .foregroundStyle(FieldLGXTheme.tertiaryText)
                        Text(job.customer.name)
                            .font(.system(size: 28, weight: .black, design: .rounded))
                            .foregroundStyle(FieldLGXTheme.text)
                            .lineLimit(2)
                            .minimumScaleFactor(0.76)
                        Text(job.property.address)
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundStyle(FieldLGXTheme.secondaryText)
                            .lineLimit(2)
                    }

                    Spacer(minLength: 8)

                    Text(job.scheduledTime ?? "Any")
                        .font(.system(size: 15, weight: .black, design: .rounded))
                        .foregroundStyle(.black)
                        .frame(width: 62, height: 52)
                        .background(FieldLGXTheme.lime)
                        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                }

                HStack(spacing: 10) {
                    NavigationLink {
                        JobDetailScreen(jobID: job.id, accessToken: accessToken, previewJob: job)
                    } label: {
                        Label("Open job", systemImage: "arrow.right.circle.fill")
                            .font(.system(size: 15, weight: .black))
                            .frame(maxWidth: .infinity)
                            .frame(height: 48)
                    }
                    .foregroundStyle(.black)
                    .background(FieldLGXTheme.lime)
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))

                    Button {
                        openURL(directionsURL(for: job))
                    } label: {
                        Image(systemName: "location.fill")
                            .font(.system(size: 17, weight: .black))
                            .frame(width: 52, height: 48)
                    }
                    .foregroundStyle(FieldLGXTheme.text)
                    .background(FieldLGXTheme.elevatedBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
                    )
                    .accessibilityLabel("Open directions")
                }
            }
            .fieldPanel()
        }
    }

    private func routeStatusStrip(_ summary: TodaySummary) -> some View {
        HStack(spacing: 8) {
            routeStatusPill("Stops", summary.total)
            routeStatusPill("Open", summary.remaining)
            routeStatusPill("Done", summary.completed)
        }
    }

    private func routeStatusPill(_ label: String, _ value: Int) -> some View {
        HStack(spacing: 6) {
            Text(label)
                .font(.system(size: 11, weight: .black))
            Text("\(value)")
                .font(.system(size: 13, weight: .black))
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

    private var fieldPacketCard: some View {
        HStack(spacing: 12) {
            Image(systemName: pendingOfflineCount > 0 ? "arrow.triangle.2.circlepath" : "checkmark.seal.fill")
                .font(.system(size: 18, weight: .black))
                .foregroundStyle(FieldLGXTheme.lime)
                .frame(width: 42, height: 42)
                .background(FieldLGXTheme.elevatedBackground)
                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))

            VStack(alignment: .leading, spacing: 3) {
                Text(pendingOfflineCount > 0 ? "Offline actions waiting" : "Field packet ready")
                    .font(.system(size: 15, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                Text(pendingOfflineCount > 0 ? "\(pendingOfflineCount) update\(pendingOfflineCount == 1 ? "" : "s") will sync when connection returns." : "Today’s route is cached for low-service areas.")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 0)

            Button {
                Task { await flushOfflineActions() }
            } label: {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 15, weight: .black))
                    .foregroundStyle(.black)
                    .frame(width: 40, height: 40)
                    .background(FieldLGXTheme.lime)
                    .clipShape(Circle())
            }
            .disabled(isSyncing || pendingOfflineCount == 0)
            .opacity(pendingOfflineCount == 0 ? 0.42 : 1)
            .accessibilityLabel("Sync offline actions")
        }
        .fieldPanel(padding: 14)
    }

    private var timeClockCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("TIME CLOCK")
                        .font(.system(size: 10, weight: .black))
                        .tracking(2)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)

                    Text(timeClock?.isClockedIn == true ? "On shift" : "Ready to clock in")
                        .font(.system(size: 24, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)

                    Text(timeClockSubtitle)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                }

                Spacer()

                Circle()
                    .fill(timeClock?.isClockedIn == true ? FieldLGXTheme.lime : FieldLGXTheme.elevatedBackground)
                    .frame(width: 12, height: 12)
                    .overlay(
                        Circle()
                            .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
                    )
                    .padding(.top, 7)
            }

            if let timeClockMessage {
                Text(timeClockMessage)
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(FieldLGXTheme.lime)
            }

            Button {
                Task { await toggleTimeClock() }
            } label: {
                HStack {
                    Image(systemName: timeClock?.isClockedIn == true ? "stop.fill" : "play.fill")
                    Text(timeClock?.isClockedIn == true ? "Clock out" : "Clock in")
                    if isClocking {
                        Spacer()
                        ProgressView()
                            .tint(timeClock?.isClockedIn == true ? FieldLGXTheme.lime : .black)
                    }
                }
                .font(.system(size: 16, weight: .black))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
            }
            .disabled(isClocking)
            .foregroundStyle(timeClock?.isClockedIn == true ? FieldLGXTheme.text : .black)
            .background(timeClock?.isClockedIn == true ? FieldLGXTheme.elevatedBackground : FieldLGXTheme.lime)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        }
        .fieldPanel()
    }

    private var timeClockSubtitle: String {
        guard let timeClock else {
            return "Location is attached when available."
        }
        if timeClock.isClockedIn {
            return "\(timeClock.todayDisplay) tracked today"
        }
        return "\(timeClock.todayDisplay) logged today"
    }

    @ViewBuilder
    private var syncCard: some View {
        if pendingOfflineCount > 0 || syncMessage != nil {
            VStack(alignment: .leading, spacing: 10) {
                Label(
                    pendingOfflineCount > 0 ? "\(pendingOfflineCount) offline update\(pendingOfflineCount == 1 ? "" : "s") waiting" : "Sync is current",
                    systemImage: "arrow.triangle.2.circlepath"
                )
                .font(.system(size: 15, weight: .black))
                .foregroundStyle(FieldLGXTheme.text)

                if let syncMessage {
                    Text(syncMessage)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                }

                Button {
                    Task { await flushOfflineActions() }
                } label: {
                    HStack {
                        Text(isSyncing ? "Syncing" : "Sync now")
                        if isSyncing {
                            Spacer()
                            ProgressView()
                                .tint(.black)
                        }
                    }
                    .font(.system(size: 15, weight: .black))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                }
                .disabled(isSyncing || pendingOfflineCount == 0)
                .foregroundStyle(.black)
                .background(FieldLGXTheme.lime)
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
            .fieldPanel()
        }
    }

    private func metric(_ label: String, _ value: Int) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label.uppercased())
                .font(.system(size: 10, weight: .black))
                .tracking(1.8)
                .foregroundStyle(FieldLGXTheme.tertiaryText)

            Text("\(value)")
                .font(.system(size: 28, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .fieldPanel(padding: 14)
    }

    private var emptyState: some View {
        ContentUnavailableView(
            "No field work scheduled",
            systemImage: "checkmark.circle",
            description: Text("Your route is clear for today.")
        )
        .foregroundStyle(FieldLGXTheme.secondaryText)
        .padding(.top, 60)
    }

    private func errorState(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Could not load today")
                .font(.system(size: 22, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
            Text(message)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(FieldLGXTheme.secondaryText)
            Button("Try again") {
                Task { await loadToday() }
            }
            .buttonStyle(.borderedProminent)
            .tint(FieldLGXTheme.lime)
            .foregroundStyle(.black)
        }
        .fieldPanel()
    }

    private func loadToday() async {
        guard let accessToken, accessToken != "preview-token" else {
            today = .preview
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            let response = try await apiClient.today()
            today = response
            cacheToday(response)
        } catch {
            #if DEBUG
            print("FIELDLGX today load failed: \(error)")
            #endif
            if let cached = cachedToday() {
                today = cached
                errorMessage = nil
            } else {
                errorMessage = "Check your connection and try again."
            }
        }
    }

    private func loadTimeClock() async {
        guard let accessToken, accessToken != "preview-token" else {
            timeClock = .preview
            return
        }

        do {
            timeClock = try await apiClient.timeClockStatus()
        } catch {
            timeClockMessage = "Time clock will retry when connection is available."
        }
    }

    private func toggleTimeClock() async {
        guard let accessToken, accessToken != "preview-token" else {
            timeClock = TimeClockResponse(
                isClockedIn: !(timeClock?.isClockedIn ?? false),
                activeEntry: nil,
                todayMinutes: timeClock?.todayMinutes ?? 0,
                todayDisplay: timeClock?.todayDisplay ?? "0h 0m",
                serverTime: timeClock?.serverTime ?? ""
            )
            return
        }

        isClocking = true
        timeClockMessage = nil
        defer { isClocking = false }

        let coordinate = await locationProvider.currentCoordinate()
        do {
            if timeClock?.isClockedIn == true {
                timeClock = try await apiClient.clockOut(
                    latitude: coordinate?.latitude,
                    longitude: coordinate?.longitude
                )
                timeClockMessage = "Clocked out. Your shift is saved."
            } else {
                timeClock = try await apiClient.clockIn(
                    latitude: coordinate?.latitude,
                    longitude: coordinate?.longitude
                )
                if let coordinate {
                    await sendLocationPing(coordinate: coordinate)
                }
                timeClockMessage = "Clocked in. Location attached when available."
            }
        } catch {
            timeClockMessage = "Could not update time clock. Try again with service."
        }
    }

    private func runLocationPingLoop() async {
        while !Task.isCancelled && timeClock?.isClockedIn == true {
            if let coordinate = await locationProvider.currentCoordinate() {
                await sendLocationPing(coordinate: coordinate)
            }
            try? await Task.sleep(for: .seconds(300))
        }
    }

    private func sendLocationPing(coordinate: CLLocationCoordinate2D) async {
        guard accessToken != nil, accessToken != "preview-token" else { return }
        do {
            let response = try await apiClient.sendTimeClockLocation(
                latitude: coordinate.latitude,
                longitude: coordinate.longitude
            )
            timeClock = response.timeClock
        } catch {
            timeClockMessage = "Location will update again when service is available."
        }
    }

    private func flushOfflineActions() async {
        guard let accessToken, accessToken != "preview-token" else { return }
        isSyncing = true
        syncMessage = nil
        defer { isSyncing = false }

        let completed = await SyncQueue(modelContext: modelContext).flush(apiClient: apiClient)
        refreshPendingCount()
        if completed > 0 {
            syncMessage = "Synced \(completed) offline update\(completed == 1 ? "" : "s")."
            await loadToday()
        } else if pendingOfflineCount > 0 {
            syncMessage = "Some updates are still waiting. Try again when service improves."
        } else {
            syncMessage = "Everything is synced."
        }
    }

    private func refreshPendingCount() {
        pendingOfflineCount = (try? SyncQueue(modelContext: modelContext).pendingCount()) ?? 0
    }

    private var apiClient: APIClient {
        APIClient(
            baseURL: FieldLGXConfig.apiBaseURL,
            accessToken: accessToken
        )
    }

    private func cacheToday(_ response: TodayResponse) {
        guard let data = try? JSONEncoder().encode(response),
              let json = String(data: data, encoding: .utf8)
        else { return }
        let descriptor = FetchDescriptor<CachedTodaySnapshot>(
            predicate: #Predicate { $0.cacheKey == "today" }
        )
        if let existing = try? modelContext.fetch(descriptor).first {
            existing.payloadJSON = json
            existing.cachedAt = Date()
        } else {
            modelContext.insert(CachedTodaySnapshot(payloadJSON: json))
        }
        try? modelContext.save()
    }

    private func cachedToday() -> TodayResponse? {
        let descriptor = FetchDescriptor<CachedTodaySnapshot>(
            predicate: #Predicate { $0.cacheKey == "today" }
        )
        guard let snapshot = try? modelContext.fetch(descriptor).first,
              let data = snapshot.payloadJSON.data(using: .utf8)
        else { return nil }
        return try? JSONDecoder().decode(TodayResponse.self, from: data)
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
}

final class FieldLocationProvider: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private var continuation: CheckedContinuation<CLLocationCoordinate2D?, Never>?

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
        manager.distanceFilter = 75
        manager.allowsBackgroundLocationUpdates = true
        manager.pausesLocationUpdatesAutomatically = true
    }

    func currentCoordinate() async -> CLLocationCoordinate2D? {
        var status = manager.authorizationStatus
        if status == .notDetermined {
            manager.requestAlwaysAuthorization()
            status = manager.authorizationStatus
        }
        guard status == .authorizedAlways || status == .authorizedWhenInUse || manager.authorizationStatus == .authorizedAlways || manager.authorizationStatus == .authorizedWhenInUse else {
            return nil
        }
        return await withCheckedContinuation { continuation in
            self.continuation = continuation
            manager.requestLocation()
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        continuation?.resume(returning: locations.last?.coordinate)
        continuation = nil
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        continuation?.resume(returning: nil)
        continuation = nil
    }
}

struct TodayJobCard: View {
    let job: TodayJob

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 5) {
                    Text(job.customer.name)
                        .font(.system(size: 22, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                    Text(job.property.address)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                }

                Spacer()

                Text(timeText)
                    .font(.system(size: 13, weight: .black))
                    .foregroundStyle(FieldLGXTheme.lime)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(FieldLGXTheme.elevatedBackground)
                    .clipShape(Capsule())
            }

            if !job.serviceItems.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(job.serviceItems) { item in
                        VStack(alignment: .leading, spacing: 3) {
                            Text(item.name)
                                .font(.system(size: 16, weight: .bold))
                                .foregroundStyle(FieldLGXTheme.text)
                            if !item.detailDescription.isEmpty {
                                Text(item.detailDescription)
                                    .font(.system(size: 14, weight: .medium))
                                    .foregroundStyle(FieldLGXTheme.secondaryText)
                            }
                        }
                    }
                }
            }

            if !job.alerts.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(job.alerts) { alert in
                        Label {
                            Text("\(alert.label): \(alert.text)")
                        } icon: {
                            Image(systemName: "exclamationmark.circle")
                        }
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(FieldLGXTheme.lime)
                    }
                }
            }
        }
        .fieldPanel()
    }

    private var timeText: String {
        job.scheduledTime ?? "Anytime"
    }
}

struct RouteScreen: View {
    let accessToken: String?
    @Environment(\.fieldLGXUsesOwnerChrome) private var usesOwnerChrome

    @State private var today: TodayResponse?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    FieldLGXMobileHeader(
                        eyebrow: "Field route",
                        title: "Route",
                        subtitle: "Stop order, addresses, timing, and job context for the crew."
                    )

                    if isLoading {
                        ProgressView()
                            .tint(FieldLGXTheme.lime)
                            .frame(maxWidth: .infinity, minHeight: 220)
                    } else if let today {
                        routeSummary(today.summary)
                        if today.jobs.isEmpty {
                            routeEmpty
                        } else {
                            ForEach(Array(today.jobs.enumerated()), id: \.element.id) { index, job in
                                NavigationLink {
                                    JobDetailScreen(jobID: job.id, accessToken: accessToken, previewJob: job)
                                } label: {
                                    RouteStopCard(index: index + 1, job: job)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    } else if let errorMessage {
                        Text(errorMessage)
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundStyle(FieldLGXTheme.secondaryText)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, usesOwnerChrome ? FieldLGXTheme.ownerTopOffset : 20)
                .padding(.bottom, 96)
            }
            .refreshable {
                await loadRoute()
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .navigationBarBackButtonHidden(true)
        .task {
            await loadRoute()
        }
    }

    private func routeSummary(_ summary: TodaySummary) -> some View {
        HStack(spacing: 10) {
            routeMetric("Stops", summary.total)
            routeMetric("Open", summary.remaining)
            routeMetric("Done", summary.completed)
        }
    }

    private func routeMetric(_ title: String, _ value: Int) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title.uppercased())
                .font(.system(size: 10, weight: .black))
                .tracking(1.8)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            Text("\(value)")
                .font(.system(size: 28, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .fieldPanel(padding: 16)
    }

    private var routeEmpty: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("No route assigned.")
                .font(.system(size: 24, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
            Text("Assigned jobs will appear here with stop order, address, time, and job context.")
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
        }
        .fieldPanel()
    }

    private func loadRoute() async {
        guard let accessToken, accessToken != "preview-token" else {
            today = .preview
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            today = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).today()
        } catch {
            errorMessage = "Could not load route."
        }
    }
}

private struct RouteStopCard: View {
    let index: Int
    let job: TodayJob

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            Text("\(index)")
                .font(.system(size: 16, weight: .black))
                .foregroundStyle(.black)
                .frame(width: 34, height: 34)
                .background(FieldLGXTheme.lime)
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: 7) {
                Text(job.customer.name)
                    .font(.system(size: 21, weight: .black, design: .rounded))
                    .foregroundStyle(FieldLGXTheme.text)
                Text(job.property.address)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .lineLimit(2)
                HStack(spacing: 8) {
                    Label(job.scheduledTime ?? "Anytime", systemImage: "clock")
                    Label(job.status.capitalized, systemImage: "checklist")
                }
                .font(.system(size: 12, weight: .black))
                .foregroundStyle(FieldLGXTheme.lime)
            }
            Spacer()
        }
        .fieldPanel()
    }
}

struct TimeScreen: View {
    let accessToken: String?
    @Environment(\.fieldLGXUsesOwnerChrome) private var usesOwnerChrome

    @State private var timeClock: TimeClockResponse?
    @State private var isLoading = false
    @State private var isClocking = false
    @State private var message: String?
    @State private var errorMessage: String?
    @State private var locationProvider = FieldLocationProvider()

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()

            VStack(alignment: .leading, spacing: 18) {
                FieldLGXMobileHeader(
                    eyebrow: "Time clock",
                    title: "Time",
                    subtitle: "Clock in, track location while working, and keep payroll context clean."
                )

                if isLoading {
                    ProgressView()
                        .tint(FieldLGXTheme.lime)
                        .frame(maxWidth: .infinity, minHeight: 220)
                } else {
                    timeCard
                    detailCard
                    if let errorMessage {
                        Text(errorMessage)
                            .font(.system(size: 14, weight: .bold))
                            .foregroundStyle(.red)
                    }
                }
                Spacer()
            }
            .padding(.horizontal, 16)
            .padding(.top, usesOwnerChrome ? FieldLGXTheme.ownerTopOffset : 20)
            .padding(.bottom, 96)
        }
        .toolbar(.hidden, for: .navigationBar)
        .navigationBarBackButtonHidden(true)
        .task {
            await loadTime()
        }
        .task(id: timeClock?.isClockedIn ?? false) {
            guard timeClock?.isClockedIn == true else { return }
            await runLocationPingLoop()
        }
    }

    private var timeCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(timeClock?.isClockedIn == true ? "On shift" : "Ready")
                .font(.system(size: 34, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
            Text(timeClock?.todayDisplay ?? "0h 0m")
                .font(.system(size: 54, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.lime)
            if let message {
                Text(message)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
            }
            Button {
                Task { await toggleClock() }
            } label: {
                HStack {
                    Image(systemName: timeClock?.isClockedIn == true ? "stop.fill" : "play.fill")
                    Text(timeClock?.isClockedIn == true ? "Clock out" : "Clock in")
                    if isClocking {
                        Spacer()
                        ProgressView().tint(timeClock?.isClockedIn == true ? FieldLGXTheme.lime : .black)
                    }
                }
                .font(.system(size: 17, weight: .black))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 15)
            }
            .disabled(isClocking)
            .foregroundStyle(timeClock?.isClockedIn == true ? FieldLGXTheme.text : .black)
            .background(timeClock?.isClockedIn == true ? FieldLGXTheme.elevatedBackground : FieldLGXTheme.lime)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        }
        .fieldPanel(padding: 20)
    }

    private var detailCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Location timeline", systemImage: "location.fill")
                .font(.system(size: 16, weight: .black))
                .foregroundStyle(FieldLGXTheme.text)
            Text("When clocked in, FIELDLGX attaches periodic location context to the time record so the office can verify route progress and payroll history.")
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
                .fixedSize(horizontal: false, vertical: true)
        }
        .fieldPanel()
    }

    private func loadTime() async {
        guard let accessToken, accessToken != "preview-token" else {
            timeClock = TimeClockResponse.preview
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            timeClock = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken).timeClockStatus()
        } catch {
            errorMessage = "Could not load time clock."
        }
    }

    private func toggleClock() async {
        guard let accessToken, accessToken != "preview-token" else {
            timeClock = TimeClockResponse.previewClockedIn
            return
        }
        isClocking = true
        errorMessage = nil
        defer { isClocking = false }
        let coordinate = await locationProvider.currentCoordinate()
        do {
            let client = APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
            if timeClock?.isClockedIn == true {
                timeClock = try await client.clockOut(latitude: coordinate?.latitude, longitude: coordinate?.longitude)
                message = "Clocked out."
            } else {
                timeClock = try await client.clockIn(latitude: coordinate?.latitude, longitude: coordinate?.longitude)
                message = "Clocked in."
            }
        } catch {
            errorMessage = "Could not update time clock."
        }
    }

    private func runLocationPingLoop() async {
        guard let accessToken, accessToken != "preview-token" else { return }
        let client = APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
        while !Task.isCancelled && timeClock?.isClockedIn == true {
            if let coordinate = await locationProvider.currentCoordinate() {
                _ = try? await client.sendTimeClockLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)
            }
            try? await Task.sleep(for: .seconds(300))
        }
    }
}

#Preview {
    TodayScreen(accessToken: nil)
        .preferredColorScheme(.dark)
}
