import SwiftUI

struct AppShell: View {
    @Bindable var session: AuthSession
    @Environment(\.scenePhase) private var scenePhase
    @State private var selectedOwnerTab: AppTab = Self.initialOwnerTab()
    @State private var activeCreateFlow: OwnerCreateFlow?
    @State private var showingCommandMenu = false

    var body: some View {
        Group {
            if session.isBiometricLocked && session.currentUser == nil && session.hasSavedSession {
                FieldLGXUnlockScreen(
                    unlock: {
                        Task { await session.unlockWithDeviceAuthentication() }
                    },
                    signOut: session.signOut
                )
            } else if let user = session.currentUser {
                ZStack {
                    if user.role == .owner || user.role == .manager {
                        ownerShell(user: user)
                    } else {
                        TabView {
                            ForEach(AppTab.tabs(for: user.role)) { tab in
                                NavigationStack {
                                    screen(for: tab, user: user)
                                }
                                .tabItem {
                                    Label(tab.title, systemImage: tab.systemImage)
                                }
                            }
                        }
                        .tint(FieldLGXTheme.lime)
                    }

                    if session.isBiometricLocked {
                        FieldLGXUnlockScreen(
                            unlock: {
                                Task { await session.unlockWithDeviceAuthentication() }
                            },
                            signOut: session.signOut
                        )
                        .transition(.opacity)
                        .zIndex(30)
                    }
                }
            } else if session.isRestoring {
                RestoreSessionScreen()
            } else {
                AuthScreen(session: session)
            }
        }
        .task {
            await session.restoreSessionIfPossible()
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active {
                Task {
                    await session.refreshSessionIfNeeded()
                }
            } else if phase == .background {
                session.lockForQuickUnlock()
            }
        }
    }

    private var ownerTabs: [AppTab] {
        [.command, .work, .calendar, .clients, .money, .estimates, .financials, .employees, .agreements, .mowing, .fertilization, .today, .route, .time, .settings, .more]
    }

    private func ownerShell(user: MobileUser) -> some View {
        ZStack {
            NavigationStack {
                screen(for: selectedOwnerTab, user: user)
            }
            .environment(\.fieldLGXUsesOwnerChrome, true)
            .safeAreaInset(edge: .top, spacing: 0) {
                FieldLGXTopChrome {
                    showingCommandMenu = true
                }
            }
            .safeAreaInset(edge: .bottom, spacing: 0) {
                FieldLGXBottomChrome(
                    selectedTab: $selectedOwnerTab
                ) {
                    activeCreateFlow = .menu
                }
            }

            if showingCommandMenu {
                FieldLGXCommandDrawer(
                    selectedTab: $selectedOwnerTab,
                    create: {
                        showingCommandMenu = false
                        activeCreateFlow = .menu
                    },
                    signOut: {
                        showingCommandMenu = false
                        session.signOut()
                    },
                    close: {
                        showingCommandMenu = false
                    }
                )
                .transition(.opacity.combined(with: .move(edge: .bottom)))
                .zIndex(20)
            }
        }
        .sheet(item: $activeCreateFlow) { flow in
            switch flow {
            case .menu:
                OwnerQuickCreateSheet { selectedFlow in
                    activeCreateFlow = selectedFlow
                }
                .presentationDetents([.medium])
                .presentationDragIndicator(.visible)
            case .client:
                CreateClientSheet(accessToken: session.accessToken) { _ in
                    selectedOwnerTab = .clients
                }
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
            case .job:
                CreateJobSheet(accessToken: session.accessToken) {
                    selectedOwnerTab = .calendar
                }
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
            case .quote:
                CreateEstimateSheet(accessToken: session.accessToken) {
                    selectedOwnerTab = .estimates
                }
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
            case .invoice:
                CreateInvoiceSheet(
                    accessToken: session.accessToken,
                    defaultCardPaymentEnabled: session.business?.defaultInvoiceCardPaymentsEnabled ?? true
                ) {
                    selectedOwnerTab = .money
                }
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
            case .fieldCapture:
                CreateReceiptSheet(accessToken: session.accessToken)
                    .presentationDetents([.large])
                    .presentationDragIndicator(.visible)
            }
        }
        .tint(FieldLGXTheme.lime)
        .animation(.spring(response: 0.32, dampingFraction: 0.9), value: showingCommandMenu)
    }

    private static func initialOwnerTab() -> AppTab {
        #if DEBUG
        let prefix = "--fieldlgx-preview-tab="
        if let argument = ProcessInfo.processInfo.arguments.first(where: { $0.hasPrefix(prefix) }) {
            let value = String(argument.dropFirst(prefix.count))
            return AppTab(rawValue: value) ?? .command
        }
        #endif
        return .command
    }

    @ViewBuilder
    private func screen(for tab: AppTab, user: MobileUser) -> some View {
        if tab == .command {
            CommandScreen(
                accessToken: session.accessToken,
                businessName: session.business?.name ?? "FIELDLGX",
                signOut: session.signOut
            )
        } else if tab == .calendar {
            CalendarScreen(accessToken: session.accessToken)
        } else if tab == .work {
            WorkScreen(accessToken: session.accessToken)
        } else if tab == .mowing {
            WorkScreen(
                accessToken: session.accessToken,
                initialService: "mowing",
                pageTitle: "Mowing",
                pageEyebrow: "Mowing route",
                pageSubtitle: "Recurring lawns, one-time cuts, crew notes, photos, and billing from one mobile page.",
                lockServiceFilter: true
            )
        } else if tab == .fertilization {
            WorkScreen(
                accessToken: session.accessToken,
                initialService: "fertilization",
                pageTitle: "Fertilization",
                pageEyebrow: "Fertilization",
                pageSubtitle: "Applications, rounds, property notes, job progress, and follow-up work for the field.",
                lockServiceFilter: true
            )
        } else if tab == .clients {
            ClientsScreen(accessToken: session.accessToken)
        } else if tab == .money {
            MoneyScreen(
                accessToken: session.accessToken,
                defaultCardPaymentEnabled: session.business?.defaultInvoiceCardPaymentsEnabled ?? true
            )
        } else if tab == .estimates {
            EstimatesScreen(accessToken: session.accessToken)
        } else if tab == .financials {
            FinancialsScreen(accessToken: session.accessToken)
        } else if tab == .employees {
            EmployeesScreen(accessToken: session.accessToken)
        } else if tab == .agreements {
            AgreementsScreen(accessToken: session.accessToken)
        } else if tab == .today {
            TodayScreen(accessToken: session.accessToken)
        } else if tab == .route {
            RouteScreen(accessToken: session.accessToken)
        } else if tab == .time {
            TimeScreen(accessToken: session.accessToken)
        } else if tab == .settings {
            OwnerSettingsScreen(accessToken: session.accessToken, signOut: session.signOut)
        } else if tab == .more {
            MoreScreen(user: user, businessName: session.business?.name ?? "FIELDLGX", signOut: session.signOut)
        } else {
            MoreScreen(user: user, businessName: session.business?.name ?? "FIELDLGX", signOut: session.signOut)
        }
    }
}

private struct FieldLGXUnlockScreen: View {
    let unlock: () -> Void
    let signOut: () -> Void

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()
            VStack(spacing: 18) {
                Image("FieldLGXMonogram")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 92, height: 92)
                    .shadow(color: FieldLGXTheme.lime.opacity(0.4), radius: 24)

                VStack(spacing: 7) {
                    Text("FIELDLGX")
                        .font(.system(size: 24, weight: .black))
                        .tracking(4)
                        .foregroundStyle(FieldLGXTheme.text)
                    Text("Unlock your saved session")
                        .font(.system(size: 15, weight: .bold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                }

                Button(action: unlock) {
                    Label("Unlock with Face ID", systemImage: "faceid")
                        .font(.system(size: 17, weight: .black))
                        .foregroundStyle(.black)
                        .frame(maxWidth: .infinity)
                        .frame(height: 54)
                        .background(FieldLGXTheme.lime)
                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                }
                .padding(.top, 8)

                Button(action: signOut) {
                    Text("Use a different account")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                }
            }
            .padding(22)
            .frame(maxWidth: 360)
        }
    }
}

private enum OwnerCreateFlow: String, Identifiable {
    case menu
    case client
    case quote
    case job
    case invoice
    case fieldCapture

    var id: String { rawValue }
}

private struct OwnerQuickCreateSheet: View {
    let select: (OwnerCreateFlow) -> Void
    @Environment(\.dismiss) private var dismiss

    private let actions: [(OwnerCreateFlow, String, String, String)] = [
        (.client, "New client", "Add a customer and property", "person.badge.plus"),
        (.quote, "New quote", "Build and send an estimate", "doc.badge.plus"),
        (.job, "New job", "Schedule field work", "checkmark.circle.badge.plus"),
        (.invoice, "New invoice", "Bill a customer", "doc.text"),
        (.fieldCapture, "Field capture", "Save a receipt or field record", "camera.viewfinder")
    ]

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()
            VStack(alignment: .leading, spacing: 16) {
                FieldLGXMobileHeader(
                    eyebrow: "Create",
                    title: "What are you adding?",
                    subtitle: "Start the exact workflow without hunting through the app."
                )

                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                    ForEach(actions, id: \.0) { action in
                        Button {
                            dismiss()
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.18) {
                                select(action.0)
                            }
                        } label: {
                            VStack(alignment: .leading, spacing: 12) {
                                Image(systemName: action.3)
                                    .font(.system(size: 20, weight: .black))
                                    .foregroundStyle(action.0 == .job ? .black : FieldLGXTheme.lime)
                                    .frame(width: 42, height: 42)
                                    .background(action.0 == .job ? FieldLGXTheme.lime : FieldLGXTheme.elevatedBackground)
                                    .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))

                                VStack(alignment: .leading, spacing: 3) {
                                    Text(action.1)
                                        .font(.system(size: 15, weight: .black))
                                        .foregroundStyle(FieldLGXTheme.text)
                                    Text(action.2)
                                        .font(.system(size: 11, weight: .bold))
                                        .foregroundStyle(FieldLGXTheme.secondaryText)
                                        .fixedSize(horizontal: false, vertical: true)
                                }
                            }
                            .frame(maxWidth: .infinity, minHeight: 124, alignment: .topLeading)
                            .padding(14)
                            .background(FieldLGXTheme.panelGradient)
                            .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                            .overlay(
                                RoundedRectangle(cornerRadius: 22, style: .continuous)
                                    .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
                            )
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .padding(16)
        }
    }
}

private struct FieldLGXCommandDrawer: View {
    @Binding var selectedTab: AppTab
    let create: () -> Void
    let signOut: () -> Void
    let close: () -> Void

    private let routeSections: [CommandMenuSection] = [
        CommandMenuSection(
            title: "Field",
            routes: [
                CommandMenuRoute(tab: .command, title: "Dashboard", subtitle: "Next action", icon: "square.grid.2x2"),
                CommandMenuRoute(tab: .calendar, title: "Calendar", subtitle: "Schedule", icon: "calendar"),
                CommandMenuRoute(tab: .mowing, title: "Mowing", subtitle: "Lawns", icon: "leaf"),
                CommandMenuRoute(tab: .fertilization, title: "Fertilization", subtitle: "Rounds", icon: "sprout"),
                CommandMenuRoute(tab: .today, title: "Crew Today", subtitle: "Live route", icon: "sun.max"),
                CommandMenuRoute(tab: .route, title: "Routes", subtitle: "Stops", icon: "map")
            ]
        ),
        CommandMenuSection(
            title: "Office",
            routes: [
                CommandMenuRoute(tab: .work, title: "Jobs", subtitle: "Pipeline", icon: "checklist"),
                CommandMenuRoute(tab: .clients, title: "Clients", subtitle: "Profiles", icon: "person.2"),
                CommandMenuRoute(tab: .money, title: "Invoices", subtitle: "Money", icon: "doc.text"),
                CommandMenuRoute(tab: .estimates, title: "Estimates", subtitle: "Quotes", icon: "doc.badge.plus"),
                CommandMenuRoute(tab: .agreements, title: "Agreements", subtitle: "Plans", icon: "doc.plaintext")
            ]
        ),
        CommandMenuSection(
            title: "Business",
            routes: [
                CommandMenuRoute(tab: .financials, title: "Financials", subtitle: "Cash flow", icon: "chart.line.uptrend.xyaxis"),
                CommandMenuRoute(tab: .employees, title: "Employees", subtitle: "Team", icon: "person.3"),
                CommandMenuRoute(tab: .time, title: "Time Clock", subtitle: "Tracking", icon: "clock"),
                CommandMenuRoute(tab: .settings, title: "Settings", subtitle: "Defaults", icon: "gearshape")
            ]
        )
    ]

    var body: some View {
        GeometryReader { proxy in
            ZStack(alignment: .bottom) {
                Color.black.opacity(0.62)
                    .ignoresSafeArea()
                    .onTapGesture(perform: close)

                VStack(alignment: .leading, spacing: 12) {
                    HStack(spacing: 10) {
                        Image("FieldLGXMonogram")
                            .resizable()
                            .scaledToFit()
                            .frame(width: 28, height: 28)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("FIELDLGX")
                                .font(.system(size: 13, weight: .black))
                                .tracking(2.4)
                                .foregroundStyle(FieldLGXTheme.lime)
                            Text("Command")
                                .font(.system(size: 22, weight: .black, design: .rounded))
                                .foregroundStyle(FieldLGXTheme.text)
                        }

                        Spacer()

                        Button(action: close) {
                            Image(systemName: "xmark")
                                .font(.system(size: 15, weight: .black))
                                .foregroundStyle(FieldLGXTheme.text)
                                .frame(width: 38, height: 38)
                                .background(FieldLGXTheme.elevatedBackground)
                                .clipShape(Circle())
                        }
                        .accessibilityLabel("Close command menu")
                    }

                    Button(action: create) {
                        Label("Create", systemImage: "plus")
                            .font(.system(size: 16, weight: .black))
                            .foregroundStyle(.black)
                            .frame(maxWidth: .infinity)
                            .frame(height: 48)
                            .background(FieldLGXTheme.lime)
                            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                    }

                    ScrollView(showsIndicators: false) {
                        VStack(alignment: .leading, spacing: 12) {
                            ForEach(routeSections) { section in
                                VStack(alignment: .leading, spacing: 8) {
                                    Text(section.title.uppercased())
                                        .font(.system(size: 10, weight: .black))
                                        .tracking(2.0)
                                        .foregroundStyle(FieldLGXTheme.tertiaryText)

                                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                                        ForEach(section.routes) { route in
                                            routeTile(route)
                                        }
                                    }
                                }
                            }

                            Button(role: .destructive, action: signOut) {
                                Label("Sign out", systemImage: "rectangle.portrait.and.arrow.right")
                                    .font(.system(size: 14, weight: .black))
                                    .frame(maxWidth: .infinity)
                                    .frame(height: 44)
                                    .background(FieldLGXTheme.elevatedBackground)
                                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                            }
                        }
                        .padding(.bottom, 4)
                    }
                }
                .padding(14)
                .frame(maxHeight: min(proxy.size.height - 118, 620), alignment: .top)
                .background(FieldLGXTheme.panelGradient)
                .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 28, style: .continuous)
                        .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
                )
                .shadow(color: Color.black.opacity(0.45), radius: 28, x: 0, y: 18)
                .padding(.horizontal, 12)
                .padding(.bottom, 72)
            }
        }
    }

    private func routeTile(_ route: CommandMenuRoute) -> some View {
        let isSelected = selectedTab == route.tab

        return Button {
            selectedTab = route.tab
            close()
        } label: {
            VStack(alignment: .leading, spacing: 8) {
                Image(systemName: route.icon)
                    .font(.system(size: 18, weight: .black))
                    .foregroundStyle(isSelected ? .black : FieldLGXTheme.lime)

                VStack(alignment: .leading, spacing: 3) {
                    Text(route.title)
                        .font(.system(size: 12, weight: .black))
                        .foregroundStyle(isSelected ? .black : FieldLGXTheme.text)
                        .lineLimit(1)
                        .minimumScaleFactor(0.72)
                    Text(route.subtitle)
                        .font(.system(size: 9, weight: .bold))
                        .foregroundStyle(isSelected ? .black.opacity(0.62) : FieldLGXTheme.secondaryText)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                }
            }
            .frame(maxWidth: .infinity, minHeight: 58, alignment: .leading)
            .padding(9)
            .background(isSelected ? AnyShapeStyle(FieldLGXTheme.lime) : AnyShapeStyle(FieldLGXTheme.panelGradient))
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(isSelected ? Color.clear : FieldLGXTheme.panelStroke, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}

private struct CommandMenuSection: Identifiable {
    var id: String { title }

    let title: String
    let routes: [CommandMenuRoute]
}

private struct CommandMenuRoute: Identifiable {
    var id: AppTab { tab }

    let tab: AppTab
    let title: String
    let subtitle: String
    let icon: String
}

private struct FieldLGXBottomChrome: View {
    @Binding var selectedTab: AppTab
    let create: () -> Void

    var body: some View {
        HStack(alignment: .bottom, spacing: 0) {
            bottomItem(.command, title: "Dashboard", image: "square.grid.2x2")
            bottomItem(.work, title: "Jobs", image: "checklist")
            bottomItem(.calendar, title: "Calendar", image: "calendar")

            Button(action: create) {
                VStack(spacing: 7) {
                    Image(systemName: "plus")
                        .font(.system(size: 19, weight: .black))
                    Text("Create")
                        .font(.system(size: 12, weight: .black))
                }
                .foregroundStyle(.black)
                .frame(width: 86, height: 52)
                .background(FieldLGXTheme.lime)
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
            .accessibilityLabel("Create")
        }
        .padding(.horizontal, 16)
        .padding(.top, 7)
        .padding(.bottom, 5)
        .frame(maxWidth: .infinity)
        .background(FieldLGXTheme.background.opacity(0.98))
        .overlay(alignment: .top) {
            Rectangle()
                .fill(Color.white.opacity(0.08))
                .frame(height: 1)
        }
    }

    private func bottomItem(_ tab: AppTab, title: String, image: String) -> some View {
        Button {
            selectedTab = tab
        } label: {
            VStack(spacing: 5) {
                Image(systemName: image)
                    .font(.system(size: 17, weight: .bold))
                Text(title)
                    .font(.system(size: 10, weight: .bold))
                    .lineLimit(1)
                    .minimumScaleFactor(0.75)
            }
            .foregroundStyle(selectedTab == tab ? FieldLGXTheme.lime : FieldLGXTheme.secondaryText)
            .frame(maxWidth: .infinity, minHeight: 40)
        }
        .buttonStyle(.plain)
    }
}

private struct MoreScreen: View {
    let user: MobileUser
    let businessName: String
    let signOut: () -> Void

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    FieldLGXMobileHeader(
                        eyebrow: "FIELDLGX",
                        title: "More",
                        subtitle: "Account, field access, sync readiness, and workspace controls."
                    )

                    accountCard
                    permissionsCard
                    supportCard

                    Button(action: signOut) {
                        Label("Sign out", systemImage: "rectangle.portrait.and.arrow.right")
                            .font(.system(size: 17, weight: .black))
                            .foregroundStyle(.black)
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(FieldLGXPrimaryButtonStyle())
                }
                .padding(.horizontal, 16)
                .padding(.top, FieldLGXTheme.ownerTopOffset)
                .padding(.bottom, 96)
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .navigationBarBackButtonHidden(true)
    }

    private var accountCard: some View {
        moreCard(title: "Account") {
            moreRow("Workspace", businessName, "building.2")
            moreRow("Signed in as", user.name, "person.crop.circle")
            moreRow("Role", user.role.title, "checkmark.seal")
        }
    }

    private var permissionsCard: some View {
        moreCard(title: "Field access") {
            moreRow("Location", "Used while clocked in for time and route context.", "location.fill")
            moreRow("Camera", "Used for completion proof, site photos, and issues.", "camera.fill")
            moreRow("Photos", "Used to attach existing job and estimate images.", "photo.fill")
        }
    }

    private var supportCard: some View {
        moreCard(title: "Readiness") {
            moreRow("Offline queue", "Field actions are queued when service drops.", "arrow.triangle.2.circlepath")
            moreRow("Sync", "Pull down on screens to refresh latest office changes.", "icloud.and.arrow.down")
        }
    }

    private func moreCard<Content: View>(title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(title.uppercased())
                .font(.system(size: 12, weight: .black))
                .tracking(2.2)
                .foregroundStyle(FieldLGXTheme.tertiaryText)
            content()
        }
        .fieldPanel()
    }

    private func moreRow(_ title: String, _ detail: String, _ systemImage: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: systemImage)
                .font(.system(size: 16, weight: .black))
                .foregroundStyle(FieldLGXTheme.lime)
                .frame(width: 24)
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.system(size: 16, weight: .black))
                    .foregroundStyle(FieldLGXTheme.text)
                Text(detail)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer()
        }
        .padding(14)
        .fieldInsetSurface()
    }
}

private struct RestoreSessionScreen: View {
    var body: some View {
        ZStack {
            FieldLGXScreenBackground()
            VStack(spacing: 16) {
                Image("FieldLGXMonogram")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 54, height: 54)
                ProgressView()
                    .tint(FieldLGXTheme.lime)
                Text("Opening FIELDLGX")
                    .font(.system(size: 16, weight: .black))
                    .tracking(1.2)
                    .foregroundStyle(FieldLGXTheme.text)
            }
        }
    }
}

#Preview("Owner") {
    AppShell(session: AuthSession(currentUser: .previewOwner))
}

#Preview("Signed Out") {
    AppShell(session: AuthSession())
}
