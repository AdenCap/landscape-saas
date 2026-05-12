import SwiftData
import SwiftUI

struct ClientsScreen: View {
    let accessToken: String?

    @State private var response: ClientsResponse?
    @State private var searchText = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingCreate = false

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    header
                    searchBar

                    if isLoading && response == nil {
                        ProgressView()
                            .tint(FieldLGXTheme.lime)
                            .frame(maxWidth: .infinity, minHeight: 220)
                    } else if let response {
                        clientList(response.clients, total: response.summary.total)
                    } else if let errorMessage {
                        errorState(errorMessage)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 16)
                .padding(.bottom, 18)
            }
            .refreshable {
                await loadClients()
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .navigationBarBackButtonHidden(true)
        .sheet(isPresented: $showingCreate) {
            CreateClientSheet(accessToken: accessToken) { _ in
                await loadClients()
            }
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
        .task {
            await loadClients()
        }
    }

    private var header: some View {
        FieldLGXMobileHeader(
            eyebrow: "Client command",
            title: "Clients",
            subtitle: "Profiles, properties, notes, billing settings, and job history."
        ) {
            FieldLGXIconAction(systemImage: "plus", accessibilityLabel: "Create client") {
                showingCreate = true
            }
        }
    }

    private var searchBar: some View {
        HStack(spacing: 10) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(FieldLGXTheme.tertiaryText)

            TextField("Search clients, phone, address", text: $searchText)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled(true)
                .foregroundStyle(FieldLGXTheme.text)
                .submitLabel(.search)
                .onSubmit {
                    Task { await loadClients() }
                }

            if !searchText.isEmpty {
                Button {
                    searchText = ""
                    Task { await loadClients() }
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                }
            }
        }
        .font(.system(size: 16, weight: .semibold))
        .padding(17)
        .background(Color.black.opacity(0.24))
        .clipShape(RoundedRectangle(cornerRadius: 26, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 26, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func clientList(_ clients: [MobileClient], total: Int) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("ACTIVE BOOK")
                        .font(.system(size: 11, weight: .black))
                        .tracking(2.2)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                    Text("Client list")
                        .font(.system(size: 26, weight: .black, design: .rounded))
                        .foregroundStyle(FieldLGXTheme.text)
                }
                Spacer()
                Text("\(total)")
                    .font(.system(size: 15, weight: .black))
                    .foregroundStyle(FieldLGXTheme.lime)
            }

            if clients.isEmpty {
                Text("No clients found.")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(FieldLGXTheme.elevatedBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            } else {
                ForEach(clients) { client in
                    NavigationLink {
                        ClientDetailScreen(clientID: client.id, accessToken: accessToken, previewClient: client)
                    } label: {
                        ClientRow(client: client)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .fieldPanel(padding: 18)
    }

    private func errorState(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Could not load clients")
                .font(.system(size: 22, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
            Text(message)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(FieldLGXTheme.secondaryText)
            Button("Try again") {
                Task { await loadClients() }
            }
            .buttonStyle(.borderedProminent)
            .tint(FieldLGXTheme.lime)
            .foregroundStyle(.black)
        }
        .fieldPanel()
    }

    private func loadClients() async {
        guard let accessToken, accessToken != "preview-token" else {
            response = .preview
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            response = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
                .clients(query: searchText)
        } catch {
            errorMessage = "Check your connection and try again."
        }
    }
}

private struct ClientRow: View {
    let client: MobileClient

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Circle()
                .fill(FieldLGXTheme.lime)
                .frame(width: 10, height: 10)
                .padding(.top, 9)

            VStack(alignment: .leading, spacing: 5) {
                Text(client.name)
                    .font(.system(size: 17, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                Text(client.primaryAddress)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .lineLimit(2)
                HStack(spacing: 8) {
                    if client.billing.hasCardOnFile {
                        Label("Card", systemImage: "creditcard.fill")
                    }
                    if client.billing.invoiceFrequency == "monthly" {
                        Label("Monthly", systemImage: "calendar")
                    }
                }
                .font(.system(size: 12, weight: .black))
                .foregroundStyle(FieldLGXTheme.lime)
            }

            Spacer()

            Text("\(client.stats.jobs)")
                .font(.system(size: 13, weight: .black))
                .foregroundStyle(FieldLGXTheme.secondaryText)
        }
        .padding(16)
        .background(FieldLGXTheme.elevatedBackground)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }
}

struct CreateClientSheet: View {
    let accessToken: String?
    let onCreated: (ClientDetailResponse) async -> Void

    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @State private var name = ""
    @State private var email = ""
    @State private var phone = ""
    @State private var address = ""
    @State private var notes = ""
    @State private var isSaving = false
    @State private var errorMessage: String?
    @State private var offlineMessage: String?

    var body: some View {
        NavigationStack {
            ZStack {
                FieldLGXScreenBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        Text("NEW CLIENT")
                            .font(.system(size: 12, weight: .black))
                            .tracking(2.4)
                            .foregroundStyle(FieldLGXTheme.lime)
                        Text("Create client")
                            .font(.system(size: 34, weight: .black, design: .rounded))
                            .foregroundStyle(FieldLGXTheme.text)

                        sheetField("Name", text: $name)
                        sheetField("Email", text: $email)
                        sheetField("Phone", text: $phone)
                        sheetField("Service address", text: $address)
                        sheetField("Notes", text: $notes, axis: .vertical)

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
                                Text(isSaving ? "Creating" : "Create client")
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
                        .disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isSaving)
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
    }

    private func sheetField(_ label: String, text: Binding<String>, axis: Axis = .horizontal) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label.uppercased())
                .font(.system(size: 10, weight: .black))
                .tracking(1.8)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            TextField(label, text: text, axis: axis)
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

    private func save() async {
        guard let accessToken, accessToken != "preview-token" else {
            dismiss()
            return
        }
        isSaving = true
        errorMessage = nil
        defer { isSaving = false }

        do {
            let response = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
                .createClient(name: name, email: email, phone: phone, address: address, notes: notes)
            await onCreated(response)
            dismiss()
        } catch {
            do {
                try SyncQueue(modelContext: modelContext).enqueue(
                    entityType: "client",
                    serverID: nil,
                    operation: .create,
                    payload: [
                        "name": name,
                        "email": email,
                        "phone": phone,
                        "address": address,
                        "notes": notes,
                    ],
                    baseRevision: nil
                )
                offlineMessage = "Saved offline. This client will sync when service is back."
                dismiss()
            } catch {
                errorMessage = "Could not create this client or save it offline."
            }
        }
    }
}

private extension ClientsResponse {
    static let preview = ClientsResponse(
        summary: ClientsSummary(total: 1, shown: 1),
        clients: [.preview],
        serverTime: "2026-05-07T12:00:00Z"
    )
}

extension MobileClient {
    static let preview = MobileClient(
        id: 1,
        name: "Willow Creek",
        email: "willow@example.com",
        phone: "555-1000",
        primaryAddress: "42 Willow Lane",
        mailingAddress: "42 Willow Lane",
        notes: "Prefers Thursday mornings.",
        billing: ClientBilling(
            invoiceFrequency: "monthly",
            monthlyInvoiceSendDay: 1,
            invoiceDueDays: 15,
            hasCardOnFile: true,
            cardLast4: "4242",
            cardBrand: "visa",
            autoCharge: false,
            autoChargeCompletedJobs: false,
            autoChargeMonthlyInvoices: true
        ),
        stats: ClientStats(jobs: 12, invoices: 3, estimates: 1),
        properties: [
            MobileClientProperty(
                id: 1,
                address: "42 Willow Lane",
                latitude: nil,
                longitude: nil,
                notes: "",
                gateCode: "9012",
                hasDog: true,
                yardSqft: 12000
            )
        ],
        updatedAt: "2026-05-07T12:00:00Z"
    )
}
