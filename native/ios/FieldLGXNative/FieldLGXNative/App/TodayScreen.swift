import CoreLocation
import SwiftData
import SwiftUI

struct TodayScreen: View {
    let accessToken: String?

    @Environment(\.modelContext) private var modelContext

    @State private var today: TodayResponse?
    @State private var timeClock: TimeClockResponse?
    @State private var isLoading = false
    @State private var isClocking = false
    @State private var errorMessage: String?
    @State private var timeClockMessage: String?
    @State private var locationProvider = FieldLocationProvider()

    var body: some View {
        ZStack {
            FieldLGXTheme.background.ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    header

                    if isLoading {
                        ProgressView()
                            .tint(FieldLGXTheme.lime)
                            .frame(maxWidth: .infinity, minHeight: 180)
                    } else if let today {
                        timeClockCard
                        summary(today.summary)

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
                .padding(24)
            }
            .refreshable {
                await loadToday()
                await loadTimeClock()
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .task {
            await loadToday()
            await loadTimeClock()
        }
        .task(id: timeClock?.isClockedIn ?? false) {
            guard timeClock?.isClockedIn == true else { return }
            await runLocationPingLoop()
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("FIELD ROUTE")
                .font(.system(size: 12, weight: .black))
                .tracking(2.5)
                .foregroundStyle(FieldLGXTheme.lime)

            Text("Today")
                .font(.system(size: 44, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
        }
    }

    private func summary(_ summary: TodaySummary) -> some View {
        HStack(spacing: 10) {
            metric("Stops", summary.total)
            metric("Open", summary.remaining)
            metric("Done", summary.completed)
        }
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
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .padding(18)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
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
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
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
        .padding(18)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
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
            try? await Task.sleep(for: .seconds(120))
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

    private var apiClient: APIClient {
        APIClient(
            baseURL: URL(string: "http://127.0.0.1:8004")!,
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
}

private final class FieldLocationProvider: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private var continuation: CheckedContinuation<CLLocationCoordinate2D?, Never>?

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
    }

    func currentCoordinate() async -> CLLocationCoordinate2D? {
        let status = manager.authorizationStatus
        if status == .notDetermined {
            manager.requestWhenInUseAuthorization()
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

private struct TodayJobCard: View {
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
        .padding(18)
        .background(FieldLGXTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private var timeText: String {
        job.scheduledTime ?? "Anytime"
    }
}

#Preview {
    TodayScreen(accessToken: nil)
        .preferredColorScheme(.dark)
}
