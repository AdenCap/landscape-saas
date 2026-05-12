import SwiftUI

struct ClientDetailScreen: View {
    let clientID: Int
    let accessToken: String?
    let previewClient: MobileClient

    @Environment(\.openURL) private var openURL
    @State private var client: MobileClient?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    if let activeClient {
                        header(activeClient)
                        quickActions(activeClient)
                        billingCard(activeClient)
                        notesCard(activeClient)
                        propertyList(activeClient.properties)
                    } else if isLoading {
                        ProgressView()
                            .tint(FieldLGXTheme.lime)
                            .frame(maxWidth: .infinity, minHeight: 240)
                    } else if let errorMessage {
                        errorState(errorMessage)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 20)
                .padding(.bottom, 18)
            }
            .refreshable {
                await loadClient()
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .task {
            await loadClient()
        }
    }

    private var activeClient: MobileClient? {
        client ?? previewClient
    }

    private func header(_ client: MobileClient) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text("CLIENT PROFILE")
                .font(.system(size: 12, weight: .black))
                .tracking(2.5)
                .foregroundStyle(FieldLGXTheme.lime)

            Text(client.name)
                .font(.system(size: 38, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
                .fixedSize(horizontal: false, vertical: true)

            Text(client.primaryAddress)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
        }
    }

    private func quickActions(_ client: MobileClient) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
            actionButton("Call", icon: "phone.fill", value: client.phone) {
                openPhone(client.phone)
            }
            actionButton("Email", icon: "envelope.fill", value: client.email) {
                openEmail(client.email)
            }
            actionButton("Route", icon: "map.fill", value: client.primaryAddress) {
                openMaps(client.primaryAddress)
            }
            actionButton("Jobs", icon: "checklist", value: "\(client.stats.jobs)") {}
        }
    }

    private func actionButton(_ title: String, icon: String, value: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 7) {
                Image(systemName: icon)
                    .font(.system(size: 17, weight: .black))
                    .foregroundStyle(FieldLGXTheme.lime)
                Text(title)
                    .font(.system(size: 16, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                Text(value.isEmpty ? "Not set" : value)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .lineLimit(1)
            }
            .padding(16)
            .frame(maxWidth: .infinity, minHeight: 112, alignment: .leading)
            .background(FieldLGXTheme.panelGradient)
            .clipShape(RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous)
                    .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }

    private func billingCard(_ client: MobileClient) -> some View {
        card(title: "Billing") {
            row("Invoice rhythm", value: client.billing.invoiceFrequency.isEmpty ? "Choose per job" : client.billing.invoiceFrequency.capitalized)
            row("Card on file", value: client.billing.hasCardOnFile ? "\(client.billing.cardBrand.uppercased()) \(client.billing.cardLast4)" : "No")
            row("Auto charge monthly", value: client.billing.autoChargeMonthlyInvoices ? "On" : "Off")
            row("Invoices", value: "\(client.stats.invoices)")
            row("Estimates", value: "\(client.stats.estimates)")
        }
    }

    private func notesCard(_ client: MobileClient) -> some View {
        card(title: "Notes") {
            Text(client.notes.isEmpty ? "No client notes yet." : client.notes)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func propertyList(_ properties: [MobileClientProperty]) -> some View {
        card(title: "Properties") {
            if properties.isEmpty {
                Text("No properties yet.")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
            } else {
                ForEach(properties) { property in
                    VStack(alignment: .leading, spacing: 7) {
                        Text(property.address)
                            .font(.system(size: 17, weight: .black))
                            .foregroundStyle(FieldLGXTheme.text)
                        HStack(spacing: 12) {
                            if !property.gateCode.isEmpty {
                                Label(property.gateCode, systemImage: "lock.fill")
                            }
                            if property.hasDog {
                                Label("Dog on site", systemImage: "exclamationmark.triangle.fill")
                            }
                        }
                        .font(.system(size: 12, weight: .black))
                        .foregroundStyle(FieldLGXTheme.lime)
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(FieldLGXTheme.elevatedBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                }
            }
        }
    }

    private func card<Content: View>(title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(title.uppercased())
                .font(.system(size: 11, weight: .black))
                .tracking(2.2)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            content()
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(FieldLGXTheme.panelGradient)
        .clipShape(RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous)
                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
        )
    }

    private func row(_ label: String, value: String) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(FieldLGXTheme.secondaryText)
            Spacer()
            Text(value)
                .font(.system(size: 14, weight: .black))
                .foregroundStyle(FieldLGXTheme.text)
        }
    }

    private func errorState(_ message: String) -> some View {
        Text(message)
            .font(.system(size: 15, weight: .semibold))
            .foregroundStyle(FieldLGXTheme.secondaryText)
            .padding(18)
            .background(FieldLGXTheme.panel)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private func loadClient() async {
        guard let accessToken, accessToken != "preview-token" else {
            client = previewClient
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            client = try await APIClient(baseURL: FieldLGXConfig.apiBaseURL, accessToken: accessToken)
                .client(id: clientID)
                .client
        } catch {
            errorMessage = "Could not load this client."
        }
    }

    private func openPhone(_ phone: String) {
        let digits = phone.filter(\.isNumber)
        guard !digits.isEmpty, let url = URL(string: "tel://\(digits)") else { return }
        openURL(url)
    }

    private func openEmail(_ email: String) {
        guard !email.isEmpty, let url = URL(string: "mailto:\(email)") else { return }
        openURL(url)
    }

    private func openMaps(_ address: String) {
        guard !address.isEmpty else { return }
        let encoded = address.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? address
        if let url = URL(string: "maps://?q=\(encoded)") {
            openURL(url)
        }
    }
}
