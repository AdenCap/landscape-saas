import SwiftUI

struct TodayScreen: View {
    let accessToken: String?

    @State private var today: TodayResponse?
    @State private var isLoading = false
    @State private var errorMessage: String?

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
                        summary(today.summary)

                        if today.jobs.isEmpty {
                            emptyState
                        } else {
                            ForEach(today.jobs) { job in
                                TodayJobCard(job: job)
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
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .task {
            await loadToday()
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
        guard let accessToken else {
            today = .preview
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            today = try await APIClient(
                baseURL: URL(string: "http://127.0.0.1:8004")!,
                accessToken: accessToken
            ).today()
        } catch {
            errorMessage = "Check your connection and try again."
        }
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
