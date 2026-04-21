//
//  RoomComponents.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import SwiftUI

struct RoomCard<Content: View>: View {
    @ViewBuilder let content: Content

    var body: some View {
        content
            .padding(20)
            .background(AppTheme.quizContainer.opacity(0.94), in: RoundedRectangle(cornerRadius: 28, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .stroke(Color.white.opacity(0.45), lineWidth: 1)
            )
            .shadow(color: Color.indigo.opacity(0.10), radius: 18, y: 10)
    }
}

struct PlayerCountChip: View {
    let count: Int
    let isSelected: Bool

    var body: some View {
        Text("\(count)")
            .font(.headline.weight(.bold))
            .foregroundStyle(isSelected ? .white : .primary)
            .frame(width: 48, height: 48)
            .background(
                Circle()
                    .fill(isSelected ? Color.indigo : Color.white.opacity(0.82))
            )
            .overlay(
                Circle()
                    .stroke(isSelected ? Color.indigo.opacity(0.25) : Color.black.opacity(0.08), lineWidth: 1)
                    .shadow(color: isSelected ? Color.indigo.opacity(0.35) : .clear, radius: 12)
            )
            .scaleEffect(isSelected ? 1.1 : 1.0)
            .animation(.spring(response: 0.25, dampingFraction: 0.72), value: isSelected)
    }
}

struct WaitingDotsLabel: View {
    @State private var dotCount = 1

    var body: some View {
        Text("Waiting for players" + String(repeating: ".", count: dotCount))
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(.secondary)
            .onAppear {
                Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in
                    dotCount = dotCount == 3 ? 1 : dotCount + 1
                }
            }
    }
}

struct LobbySlotsView: View {
    let players: [RoomPlayer]
    let capacity: Int

    private let columns = [
        GridItem(.flexible(), spacing: 14),
        GridItem(.flexible(), spacing: 14)
    ]

    var body: some View {
        LazyVGrid(columns: columns, spacing: 14) {
            ForEach(0..<capacity, id: \.self) { index in
                if players.indices.contains(index) {
                    JoinedPlayerCard(player: players[index])
                        .transition(.scale(scale: 0.8).combined(with: .opacity))
                } else {
                    WaitingPlayerCard()
                }
            }
        }
        .animation(.spring(response: 0.32, dampingFraction: 0.76), value: players)
    }
}

private struct JoinedPlayerCard: View {
    let player: RoomPlayer

    private var initials: String {
        String(player.name.prefix(1)).uppercased()
    }

    var body: some View {
        VStack(spacing: 10) {
            ZStack(alignment: .topTrailing) {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Color.indigo, Color.blue],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 62, height: 62)
                    .overlay(
                        Text(initials)
                            .font(.title3.bold())
                            .foregroundStyle(.white)
                    )

                if player.isHost {
                    Image(systemName: "crown.fill")
                        .font(.caption2)
                        .foregroundStyle(.yellow)
                        .padding(6)
                        .background(Color.white, in: Circle())
                        .offset(x: 4, y: -4)
                }
            }

            Text(player.name)
                .font(.subheadline.weight(.semibold))
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 16)
        .background(Color.white.opacity(0.78), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
    }
}

private struct WaitingPlayerCard: View {
    @State private var isPulsing = false

    var body: some View {
        VStack(spacing: 10) {
            Circle()
                .strokeBorder(Color.indigo.opacity(0.28), style: StrokeStyle(lineWidth: 1.4, dash: [4, 5]))
                .frame(width: 62, height: 62)
                .overlay(
                    Text("+")
                        .font(.title2.weight(.bold))
                        .foregroundStyle(.indigo.opacity(0.7))
                )

            Text("Waiting…")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 16)
        .background(Color.white.opacity(0.5), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .opacity(isPulsing ? 1 : 0.68)
        .onAppear {
            withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) {
                isPulsing = true
            }
        }
    }
}
