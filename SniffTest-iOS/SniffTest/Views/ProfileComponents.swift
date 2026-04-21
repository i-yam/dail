//
//  ProfileComponents.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import SwiftUI

struct ProfileGlassCard<Content: View>: View {
    @ViewBuilder let content: Content
    @State private var appeared = false

    var body: some View {
        content
            .padding(20)
            .background(
                LinearGradient(
                    colors: [
                        Color(red: 0.40, green: 0.32, blue: 0.93).opacity(0.16),
                        Color(red: 0.17, green: 0.58, blue: 0.97).opacity(0.14),
                        Color(red: 0.94, green: 0.30, blue: 0.71).opacity(0.16),
                        AppTheme.quizContainer.opacity(0.92)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                ),
                in: RoundedRectangle(cornerRadius: 28, style: .continuous)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .stroke(Color.white.opacity(0.55), lineWidth: 1)
            )
            .shadow(color: Color(red: 0.51, green: 0.27, blue: 0.92).opacity(0.14), radius: 22, y: 10)
            .offset(y: appeared ? 0 : 10)
            .opacity(appeared ? 1 : 0)
            .onAppear {
                withAnimation(.easeOut(duration: 0.26)) {
                    appeared = true
                }
            }
    }
}

struct ProfileAvatarBadge: View {
    let avatar: ProfileAvatar
    let size: CGFloat

    var body: some View {
        ZStack {
            Circle()
                .fill(
                    AngularGradient(
                        colors: [Color.blue, Color.purple, Color.pink, Color.blue],
                        center: .center
                    )
                )
                .frame(width: size, height: size)

            Circle()
                .fill(Color.white.opacity(0.90))
                .frame(width: size - 8, height: size - 8)

            Circle()
                .fill(
                    LinearGradient(
                        colors: [Color.indigo, Color.cyan, Color.pink],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: size - 16, height: size - 16)
                .overlay(
                    Image(systemName: avatar.symbolName)
                        .font(.system(size: size * 0.32, weight: .bold))
                        .foregroundStyle(.white)
                )
        }
        .shadow(color: Color.pink.opacity(0.24), radius: 14)
    }
}

struct StatTile: View {
    let title: String
    let value: String
    let icon: String

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Text(icon)
                Text(title)
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.secondary)
            }

            Text(value)
                .font(.title3.bold())
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(
            LinearGradient(
                colors: [Color.white.opacity(0.82), Color(red: 0.95, green: 0.93, blue: 1.0).opacity(0.76)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 22, style: .continuous)
        )
        .shadow(color: Color.blue.opacity(0.08), radius: 12, y: 6)
    }
}

struct BadgeChip: View {
    let badge: ProfileBadge
    @State private var animate = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Image(systemName: badge.symbolName)
                .font(.title3)
                .foregroundStyle(badge.isUnlocked ? .yellow : .gray)

            Text(badge.title)
                .font(.headline)

            Text(badge.subtitle)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(width: 150, alignment: .leading)
        .padding(16)
        .background(
            badge.isUnlocked ?
            LinearGradient(colors: [Color.yellow.opacity(0.24), Color.pink.opacity(0.16), Color.white.opacity(0.88)], startPoint: .topLeading, endPoint: .bottomTrailing) :
            LinearGradient(colors: [Color.white.opacity(0.50), Color.white.opacity(0.36)], startPoint: .topLeading, endPoint: .bottomTrailing),
            in: RoundedRectangle(cornerRadius: 22, style: .continuous)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(badge.isUnlocked ? Color.yellow.opacity(0.4) : Color.gray.opacity(0.2), lineWidth: 1)
        )
        .shadow(color: badge.isUnlocked ? Color.yellow.opacity(animate ? 0.24 : 0.12) : .clear, radius: animate ? 18 : 8)
        .scaleEffect(badge.isUnlocked && animate ? 1.03 : 1.0)
        .onAppear {
            guard badge.isUnlocked else { return }
            withAnimation(.easeInOut(duration: 0.28).repeatCount(2, autoreverses: true)) {
                animate = true
            }
        }
    }
}

struct ProfileToast: View {
    let message: String

    var body: some View {
        Text(message)
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(.white)
            .padding(.horizontal, 18)
            .padding(.vertical, 12)
            .background(Color.black.opacity(0.76), in: Capsule())
    }
}

struct ProfileActionButtonStyle: ButtonStyle {
    let tint: Color

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline.weight(.semibold))
            .foregroundStyle(.white)
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(
                LinearGradient(
                    colors: [tint, tint.opacity(0.82), Color.pink.opacity(0.78)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                ),
                in: RoundedRectangle(cornerRadius: 16, style: .continuous)
            )
            .shadow(color: tint.opacity(0.22), radius: 12, y: 6)
            .scaleEffect(configuration.isPressed ? 0.96 : 1.0)
            .animation(.spring(response: 0.22, dampingFraction: 0.62), value: configuration.isPressed)
    }
}
