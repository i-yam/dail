//
//  AIValidationBlock.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import SwiftUI

enum TruthBluffChoice: String, Equatable {
    case truth
    case bluff

    var title: String {
        rawValue.capitalized
    }

    var iconName: String {
        switch self {
        case .truth:
            return "sparkles"
        case .bluff:
            return "eye.trianglebadge.exclamationmark"
        }
    }

    var tint: Color {
        switch self {
        case .truth:
            return Color(red: 0.13, green: 0.57, blue: 0.68)
        case .bluff:
            return Color(red: 0.69, green: 0.25, blue: 0.50)
        }
    }

    var glowColors: [Color] {
        switch self {
        case .truth:
            return [Color(red: 0.76, green: 0.93, blue: 0.95), Color(red: 0.83, green: 0.96, blue: 0.89)]
        case .bluff:
            return [Color(red: 0.96, green: 0.86, blue: 0.94), Color(red: 0.92, green: 0.80, blue: 0.86)]
        }
    }
}

struct AIValidationReveal: Equatable {
    let prediction: TruthBluffChoice
    let confidence: Int
    let personality: String

    var title: String {
        "AI Prediction: \(prediction.title)"
    }
}

enum AIValidationPhase: Equatable {
    case loading(step: Int)
    case reveal(AIValidationReveal)

    var loadingMessage: String {
        switch self {
        case .loading(let step):
            return [
                "Analyzing statement…",
                "Cross-checking facts…",
                "Detecting bluff patterns…"
            ][step]
        case .reveal:
            return ""
        }
    }
}

struct AIValidationBlock: View {
    let phase: AIValidationPhase
    let glowPulse: Bool
    @State private var scanActive = false

    var body: some View {
        Group {
            switch phase {
            case .loading(let step):
                VStack(alignment: .leading, spacing: 16) {
                    HStack(spacing: 12) {
                        LieRadarView(scanActive: scanActive)
                            .frame(width: 44, height: 44)

                        VStack(alignment: .leading, spacing: 6) {
                            Text("AI Validator")
                                .font(.caption.weight(.bold))
                                .foregroundStyle(.secondary)
                            Text(phase.loadingMessage)
                                .font(.headline)
                        }
                    }

                    LoadingDotsView(activeIndex: step)

                    Text("Running quick signal checks before the call.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

            case .reveal(let reveal):
                VStack(alignment: .leading, spacing: 14) {
                    HStack {
                        Label(reveal.title, systemImage: reveal.prediction.iconName)
                            .font(.headline.weight(.semibold))
                            .foregroundStyle(reveal.prediction.tint)

                        Spacer()

                        Text("\(reveal.confidence)% confidence")
                            .font(.subheadline.weight(.bold))
                            .foregroundStyle(reveal.prediction.tint)
                    }

                    TrustMeterView(confidence: reveal.confidence, tint: reveal.prediction.tint)

                    Text(reveal.personality)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .scaleEffect(glowPulse ? 1.03 : 0.98)
                .shadow(color: reveal.prediction.tint.opacity(glowPulse ? 0.28 : 0.12), radius: glowPulse ? 28 : 18)
            }
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(backgroundView)
        .overlay {
            RoundedRectangle(cornerRadius: 26, style: .continuous)
                .strokeBorder(borderColor, lineWidth: 1)
        }
        .shadow(color: shadowColor, radius: 20, y: 10)
        .onAppear {
            scanActive = true
        }
    }

    @ViewBuilder
    private var backgroundView: some View {
        RoundedRectangle(cornerRadius: 26, style: .continuous)
            .fill(.ultraThinMaterial)
            .background {
                RoundedRectangle(cornerRadius: 26, style: .continuous)
                    .fill(fillGradient)
            }
    }

    private var fillGradient: LinearGradient {
        switch phase {
        case .loading:
            return LinearGradient(
                colors: [Color.white.opacity(0.80), Color(red: 0.92, green: 0.95, blue: 0.99).opacity(0.92)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        case .reveal(let reveal):
            return LinearGradient(
                colors: reveal.prediction.glowColors.map { $0.opacity(glowPulse ? 0.88 : 0.74) },
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        }
    }

    private var borderColor: Color {
        switch phase {
        case .loading:
            return Color.white.opacity(0.55)
        case .reveal(let reveal):
            return reveal.prediction.tint.opacity(glowPulse ? 0.42 : 0.26)
        }
    }

    private var shadowColor: Color {
        switch phase {
        case .loading:
            return Color.black.opacity(0.08)
        case .reveal(let reveal):
            return reveal.prediction.tint.opacity(glowPulse ? 0.20 : 0.10)
        }
    }
}

private struct LoadingDotsView: View {
    let activeIndex: Int

    var body: some View {
        HStack(spacing: 10) {
            ForEach(0..<3, id: \.self) { index in
                Circle()
                    .fill(index <= activeIndex ? Color.indigo.opacity(0.85) : Color.indigo.opacity(0.22))
                    .frame(width: 9, height: 9)
                    .scaleEffect(index == activeIndex ? 1.15 : 0.92)
                    .animation(.easeInOut(duration: 0.24), value: activeIndex)
            }
        }
    }
}

private struct TrustMeterView: View {
    let confidence: Int
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Trust Meter")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)

            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(Color.white.opacity(0.45))

                    Capsule()
                        .fill(
                            LinearGradient(
                                colors: [tint.opacity(0.72), tint],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: geometry.size.width * CGFloat(confidence) / 100)
                }
            }
            .frame(height: 10)
        }
    }
}

private struct LieRadarView: View {
    let scanActive: Bool

    var body: some View {
        ZStack {
            Circle()
                .stroke(Color.indigo.opacity(0.18), lineWidth: 1)

            Circle()
                .stroke(Color.indigo.opacity(0.25), lineWidth: 1)
                .padding(6)

            Circle()
                .fill(Color.indigo.opacity(0.12))

            Rectangle()
                .fill(
                    LinearGradient(
                        colors: [Color.clear, Color.indigo.opacity(0.42), Color.clear],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
                .frame(width: 2, height: 36)
                .rotationEffect(.degrees(scanActive ? 360 : 0))
                .animation(.linear(duration: 1.5).repeatForever(autoreverses: false), value: scanActive)

            Circle()
                .fill(Color.indigo.opacity(0.76))
                .frame(width: 6, height: 6)
        }
    }
}
