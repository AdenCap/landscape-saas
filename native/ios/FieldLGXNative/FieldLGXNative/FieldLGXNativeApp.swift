import SwiftData
import SwiftUI
import UIKit

@main
struct FieldLGXNativeApp: App {
    @State private var session: AuthSession

    init() {
        _session = State(initialValue: Self.initialSession())

        let appearance = UITabBarAppearance()
        appearance.configureWithOpaqueBackground()
        appearance.backgroundColor = UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(red: 0.018, green: 0.022, blue: 0.018, alpha: 0.98)
                : UIColor(red: 0.985, green: 0.995, blue: 0.965, alpha: 0.98)
        }

        let normalColor = UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor.white.withAlphaComponent(0.48)
                : UIColor(red: 0.27, green: 0.32, blue: 0.25, alpha: 0.70)
        }
        let selectedColor = UIColor(red: 0.63, green: 0.91, blue: 0.29, alpha: 1)
        for itemAppearance in [
            appearance.stackedLayoutAppearance,
            appearance.inlineLayoutAppearance,
            appearance.compactInlineLayoutAppearance
        ] {
            itemAppearance.normal.iconColor = normalColor
            itemAppearance.normal.titleTextAttributes = [
                .foregroundColor: normalColor,
                .font: UIFont.systemFont(ofSize: 11, weight: .bold)
            ]
            itemAppearance.selected.iconColor = selectedColor
            itemAppearance.selected.titleTextAttributes = [
                .foregroundColor: selectedColor,
                .font: UIFont.systemFont(ofSize: 11, weight: .heavy)
            ]
        }

        UITabBar.appearance().standardAppearance = appearance
        UITabBar.appearance().scrollEdgeAppearance = appearance
    }

    private static func initialSession() -> AuthSession {
        let session = AuthSession()
        #if DEBUG
        if ProcessInfo.processInfo.arguments.contains("--fieldlgx-preview-owner") {
            session.signInPreview(role: .owner)
        }
        #endif
        return session
    }

    var body: some Scene {
        WindowGroup {
            FieldLGXRootView(session: session)
        }
        .modelContainer(for: [PendingMutation.self, CachedTodaySnapshot.self])
    }
}

private struct FieldLGXRootView: View {
    @Bindable var session: AuthSession
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var showStartup = true

    var body: some View {
        ZStack {
            AppShell(session: session)

            if showStartup {
                FieldLGXStartupSplash(reduceMotion: reduceMotion) {
                    withAnimation(.easeInOut(duration: reduceMotion ? 0.12 : 0.34)) {
                        showStartup = false
                    }
                }
                .transition(.opacity)
                .zIndex(10)
            }
        }
    }
}

private struct FieldLGXStartupSplash: View {
    let reduceMotion: Bool
    let onFinished: () -> Void

    @State private var markScale = 0.76
    @State private var markOpacity = 0.0
    @State private var wordmarkOffset: CGFloat = 18
    @State private var wordmarkOpacity = 0.0
    @State private var sweepOffset: CGFloat = -220
    @State private var glowScale = 0.72
    @State private var glowOpacity = 0.0

    var body: some View {
        ZStack {
            FieldLGXScreenBackground()

            RadialGradient(
                colors: [
                    FieldLGXTheme.lime.opacity(glowOpacity),
                    FieldLGXTheme.lime.opacity(glowOpacity * 0.18),
                    .clear
                ],
                center: .center,
                startRadius: 10,
                endRadius: 260
            )
            .scaleEffect(glowScale)
            .ignoresSafeArea()

            FieldLGXGridPattern()
                .stroke(FieldLGXTheme.gridLine, lineWidth: 1)
                .ignoresSafeArea()

            VStack(spacing: 18) {
                ZStack {
                    RoundedRectangle(cornerRadius: 38, style: .continuous)
                        .fill(FieldLGXTheme.elevatedBackground.opacity(0.84))
                        .frame(width: 132, height: 132)
                        .overlay(
                            RoundedRectangle(cornerRadius: 38, style: .continuous)
                                .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
                        )

                    Image("FieldLGXMonogram")
                        .resizable()
                        .scaledToFit()
                        .frame(width: 92, height: 92)
                        .scaleEffect(markScale)
                        .opacity(markOpacity)
                        .shadow(color: FieldLGXTheme.lime.opacity(0.45), radius: 24, x: 0, y: 0)
                        .overlay {
                            LinearGradient(
                                colors: [.clear, .white.opacity(0.62), .clear],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                            .frame(width: 42, height: 126)
                            .rotationEffect(.degrees(18))
                            .offset(x: sweepOffset)
                            .blendMode(.screen)
                            .mask(
                                Image("FieldLGXMonogram")
                                    .resizable()
                                    .scaledToFit()
                                    .frame(width: 92, height: 92)
                            )
                        }
                }

                Text("FIELDLGX")
                    .font(.system(size: 24, weight: .black))
                    .tracking(4.4)
                    .foregroundStyle(FieldLGXTheme.text)
                    .offset(y: wordmarkOffset)
                    .opacity(wordmarkOpacity)

                Text("RUN THE DAY")
                    .font(.system(size: 10, weight: .black))
                    .tracking(3.0)
                    .foregroundStyle(FieldLGXTheme.lime)
                    .offset(y: wordmarkOffset)
                    .opacity(wordmarkOpacity * 0.86)
            }
        }
        .task {
            await animateAndFinish()
        }
    }

    @MainActor
    private func animateAndFinish() async {
        guard !reduceMotion else {
            markScale = 1
            markOpacity = 1
            wordmarkOffset = 0
            wordmarkOpacity = 1
            try? await Task.sleep(nanoseconds: 420_000_000)
            onFinished()
            return
        }

        withAnimation(.spring(response: 0.55, dampingFraction: 0.82)) {
            markScale = 1
            markOpacity = 1
            glowScale = 1.12
            glowOpacity = 0.22
        }

        withAnimation(.easeOut(duration: 0.62).delay(0.12)) {
            sweepOffset = 220
        }

        withAnimation(.spring(response: 0.54, dampingFraction: 0.86).delay(0.18)) {
            wordmarkOffset = 0
            wordmarkOpacity = 1
        }

        try? await Task.sleep(nanoseconds: 1_420_000_000)
        onFinished()
    }
}
