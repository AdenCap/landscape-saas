import SwiftUI
import UIKit

enum FieldLGXTheme {
    private static func adaptive(light: UIColor, dark: UIColor) -> Color {
        Color(UIColor { traits in
            traits.userInterfaceStyle == .dark ? dark : light
        })
    }

    static let background = adaptive(
        light: UIColor(red: 0.965, green: 0.975, blue: 0.945, alpha: 1),
        dark: UIColor(red: 0.020, green: 0.025, blue: 0.020, alpha: 1)
    )
    static let elevatedBackground = adaptive(
        light: UIColor(red: 1.000, green: 1.000, blue: 0.985, alpha: 1),
        dark: UIColor(red: 0.055, green: 0.060, blue: 0.055, alpha: 1)
    )
    static let panel = adaptive(
        light: UIColor(red: 0.985, green: 0.995, blue: 0.965, alpha: 1),
        dark: UIColor(red: 0.100, green: 0.110, blue: 0.100, alpha: 1)
    )
    static let panelStroke = adaptive(
        light: UIColor(red: 0.090, green: 0.130, blue: 0.080, alpha: 0.14),
        dark: UIColor.white.withAlphaComponent(0.14)
    )
    static let lime = Color(red: 0.63, green: 0.91, blue: 0.29)
    static let text = adaptive(
        light: UIColor(red: 0.065, green: 0.095, blue: 0.060, alpha: 1),
        dark: UIColor.white
    )
    static let secondaryText = adaptive(
        light: UIColor(red: 0.260, green: 0.315, blue: 0.240, alpha: 1),
        dark: UIColor.white.withAlphaComponent(0.62)
    )
    static let tertiaryText = adaptive(
        light: UIColor(red: 0.415, green: 0.455, blue: 0.390, alpha: 1),
        dark: UIColor.white.withAlphaComponent(0.42)
    )
    static let gridLine = adaptive(
        light: UIColor(red: 0.090, green: 0.130, blue: 0.080, alpha: 0.040),
        dark: UIColor.white.withAlphaComponent(0.032)
    )

    static let cardRadius: CGFloat = 24
    static let pagePadding: CGFloat = 16

    static var panelGradient: LinearGradient {
        LinearGradient(
            colors: [
                elevatedBackground.opacity(0.96),
                panel.opacity(0.96),
                background.opacity(0.88)
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }
}

extension Color {
    init?(hex: String) {
        let cleaned = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        guard cleaned.count == 6, let value = UInt64(cleaned, radix: 16) else { return nil }
        let red = Double((value >> 16) & 0xFF) / 255.0
        let green = Double((value >> 8) & 0xFF) / 255.0
        let blue = Double(value & 0xFF) / 255.0
        self.init(red: red, green: green, blue: blue)
    }
}

struct FieldLGXScreenBackground: View {
    var body: some View {
        ZStack {
            FieldLGXTheme.background

            RadialGradient(
                colors: [
                    FieldLGXTheme.lime.opacity(0.16),
                    Color.clear
                ],
                center: .topTrailing,
                startRadius: 10,
                endRadius: 520
            )

            RadialGradient(
                colors: [
                    FieldLGXTheme.lime.opacity(0.08),
                    Color.clear
                ],
                center: .bottomLeading,
                startRadius: 20,
                endRadius: 460
            )

            FieldLGXGridPattern()
                .stroke(FieldLGXTheme.gridLine, lineWidth: 1)
        }
        .ignoresSafeArea()
    }
}

struct FieldLGXGridPattern: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let spacing: CGFloat = 58
        var x: CGFloat = 0
        while x <= rect.maxX {
            path.move(to: CGPoint(x: x, y: rect.minY))
            path.addLine(to: CGPoint(x: x, y: rect.maxY))
            x += spacing
        }

        var y: CGFloat = 0
        while y <= rect.maxY {
            path.move(to: CGPoint(x: rect.minX, y: y))
            path.addLine(to: CGPoint(x: rect.maxX, y: y))
            y += spacing
        }
        return path
    }
}

extension View {
    func fieldPanel(padding: CGFloat = 18) -> some View {
        self
            .padding(padding)
            .background(FieldLGXTheme.panelGradient)
            .clipShape(RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous)
                    .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
            )
            .shadow(color: Color.black.opacity(0.24), radius: 24, x: 0, y: 18)
    }

    func fieldInsetSurface() -> some View {
        self
            .background(FieldLGXTheme.elevatedBackground)
            .clipShape(RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous)
                    .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
            )
    }
}

struct FieldLGXPageTitle: View {
    let eyebrow: String
    let title: String
    var subtitle: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(spacing: 8) {
                Circle()
                    .fill(FieldLGXTheme.lime)
                    .frame(width: 8, height: 8)
                Text(eyebrow.uppercased())
                    .font(.system(size: 12, weight: .black))
                    .tracking(2.5)
                    .foregroundStyle(FieldLGXTheme.tertiaryText)
            }

            Text(title)
                .font(.system(size: 36, weight: .black, design: .rounded))
                .foregroundStyle(FieldLGXTheme.text)
                .lineLimit(2)
                .minimumScaleFactor(0.72)

            if let subtitle {
                Text(subtitle)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(FieldLGXTheme.secondaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

struct FieldLGXMobileHeader<Action: View>: View {
    let eyebrow: String
    let title: String
    var subtitle: String?
    @ViewBuilder var action: () -> Action

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 7) {
                HStack(spacing: 8) {
                    Circle()
                        .fill(FieldLGXTheme.lime)
                        .frame(width: 8, height: 8)
                    Text(eyebrow.uppercased())
                        .font(.system(size: 12, weight: .black))
                        .tracking(2.6)
                        .foregroundStyle(FieldLGXTheme.tertiaryText)
                }

                Text(title)
                    .font(.system(size: 34, weight: .black, design: .rounded))
                    .foregroundStyle(FieldLGXTheme.text)
                    .lineLimit(2)
                    .minimumScaleFactor(0.68)

                if let subtitle {
                    Text(subtitle)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(FieldLGXTheme.secondaryText)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

            Spacer(minLength: 10)
            action()
        }
    }
}

extension FieldLGXMobileHeader where Action == EmptyView {
    init(eyebrow: String, title: String, subtitle: String? = nil) {
        self.eyebrow = eyebrow
        self.title = title
        self.subtitle = subtitle
        self.action = { EmptyView() }
    }
}

struct FieldLGXIconAction: View {
    let systemImage: String
    let accessibilityLabel: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: systemImage)
                .font(.system(size: 18, weight: .black))
                .foregroundStyle(.black)
                .frame(width: 48, height: 48)
                .background(FieldLGXTheme.lime)
                .clipShape(RoundedRectangle(cornerRadius: 17, style: .continuous))
                .shadow(color: FieldLGXTheme.lime.opacity(0.22), radius: 18, x: 0, y: 10)
        }
        .accessibilityLabel(accessibilityLabel)
    }
}

struct FieldLGXPrimaryButtonStyle: ButtonStyle {
    var isEnabled = true

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 16, weight: .black))
            .foregroundStyle(.black)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(FieldLGXTheme.lime.opacity(isEnabled ? (configuration.isPressed ? 0.82 : 1) : 0.38))
            .clipShape(RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous))
            .shadow(color: FieldLGXTheme.lime.opacity(isEnabled ? 0.22 : 0), radius: 18, x: 0, y: 12)
    }
}

struct FieldLGXSecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 16, weight: .black))
            .foregroundStyle(FieldLGXTheme.text)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(configuration.isPressed ? FieldLGXTheme.panel : FieldLGXTheme.elevatedBackground)
            .clipShape(RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: FieldLGXTheme.cardRadius, style: .continuous)
                    .stroke(FieldLGXTheme.panelStroke, lineWidth: 1)
            )
    }
}
