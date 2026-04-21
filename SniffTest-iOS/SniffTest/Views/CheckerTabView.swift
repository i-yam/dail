//
//  CheckerTabView.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import SwiftUI
import UIKit

struct CheckerTabView: View {
    @StateObject private var viewModel = RoomViewModel()
    @State private var animateEntrance = false
    @State private var selectedAnswer: TruthBluffChoice?
    @State private var validationPhase: AIValidationPhase?
    @State private var validationTask: Task<Void, Never>?
    @State private var glowPulse = false
    @State private var currentPromptIndex = 0

    var body: some View {
        NavigationStack {
            ZStack {
                AppTheme.background
                    .ignoresSafeArea()

                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 20) {
                        header

                        if viewModel.phase == .setup {
                            setupCard
                                .offset(y: animateEntrance ? 0 : 24)
                                .opacity(animateEntrance ? 1 : 0)
                        } else if viewModel.phase == .lobby {
                            lobbyCard
                                .transition(.move(edge: .trailing).combined(with: .opacity))
                        } else {
                            gameCard
                                .transition(.move(edge: .trailing).combined(with: .opacity))
                        }
                    }
                    .padding(24)
                }
            }
            .animation(.spring(response: 0.32, dampingFraction: 0.8), value: viewModel.phase)
            .onAppear {
                withAnimation(.easeOut(duration: 0.35)) {
                    animateEntrance = true
                }
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Truth / Bluff Room")
                .font(.largeTitle.bold())

            Text(headerSubtitle)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }

    private let prompts: [GamePrompt] = [
        GamePrompt(
            statement: "A viral post says the city canceled school tomorrow, but it links only to an unverified screenshot.",
            prediction: .bluff
        ),
        GamePrompt(
            statement: "The weather office alert includes a timestamp, official website link, and matching notice on the verified account.",
            prediction: .truth
        ),
        GamePrompt(
            statement: "A celebrity photo was edited to add a fake protest sign and is now being shared as real.",
            prediction: .bluff
        )
    ]

    private var headerSubtitle: String {
        switch viewModel.phase {
        case .setup:
            return "Create a room, choose any player count from 2 to 6, and wait for the crew to join."
        case .lobby:
            return "Watch players fill the room, then start once at least two have joined."
        case .game:
            return "The room is live. Use this screen as the starting point for the turn-based Truth / Bluff round."
        }
    }

    private var setupCard: some View {
        RoomCard {
            VStack(alignment: .leading, spacing: 20) {
                Picker("Room Mode", selection: $viewModel.mode) {
                    ForEach(RoomMode.allCases) { mode in
                        Text(mode.title).tag(mode)
                    }
                }
                .pickerStyle(.segmented)

                TextField("Your Name", text: $viewModel.playerName)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 14)
                    .background(Color.white.opacity(0.8), in: RoundedRectangle(cornerRadius: 18, style: .continuous))

                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Text("Room Name")
                            .font(.headline)
                        Spacer()
                        Button("Surprise Me") {
                            viewModel.refreshRoomName()
                        }
                        .font(.footnote.weight(.semibold))
                        .buttonStyle(.plain)
                        .foregroundStyle(.indigo)
                    }

                    Text(viewModel.roomName)
                        .font(.title3.weight(.semibold))
                        .padding(.horizontal, 16)
                        .padding(.vertical, 14)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.white.opacity(0.76), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                }

                if viewModel.mode == .join {
                    TextField("Room Code", text: $viewModel.joinCode)
                        .textInputAutocapitalization(.characters)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 14)
                        .background(Color.white.opacity(0.8), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                }

                VStack(alignment: .leading, spacing: 12) {
                    Text("Player Count")
                        .font(.headline)

                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 12) {
                            ForEach(viewModel.availablePlayerCounts, id: \.self) { count in
                                PlayerCountChip(count: count, isSelected: viewModel.selectedPlayerCount == count)
                                    .onTapGesture {
                                        withAnimation(.spring(response: 0.25, dampingFraction: 0.72)) {
                                            viewModel.selectedPlayerCount = count
                                        }
                                    }
                            }
                        }
                        .padding(.vertical, 4)
                    }

                    Text("Minimum 2 players. Maximum 6 players.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Button(viewModel.mode == .create ? "Create Room" : "Join Room") {
                    if viewModel.mode == .create {
                        viewModel.createRoom()
                    } else {
                        viewModel.joinRoom()
                    }
                }
                .frame(maxWidth: .infinity)
                .appPrimaryButtonStyle()
            }
        }
    }

    private var lobbyCard: some View {
        VStack(alignment: .leading, spacing: 18) {
            RoomCard {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Room Code")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(.secondary)

                    Text(viewModel.roomName)
                        .font(.title2.bold())

                    Text(viewModel.roomCode.map(String.init).joined(separator: " "))
                        .font(.system(size: 30, weight: .bold, design: .rounded))
                        .tracking(6)

                    Text(viewModel.joinedCountText)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.indigo)

                    WaitingDotsLabel()
                }
            }

            RoomCard {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Lobby")
                        .font(.headline)

                    LobbySlotsView(players: viewModel.players, capacity: viewModel.selectedPlayerCount)
                }
            }

            HStack(spacing: 12) {
                Button("Add Demo Player") {
                    viewModel.addDemoPlayer()
                }
                .frame(maxWidth: .infinity)
                .buttonStyle(.bordered)
                .disabled(!viewModel.canAddDemoPlayer)

                Button("Start Game") {
                    viewModel.startGame()
                }
                .frame(maxWidth: .infinity)
                .appPrimaryButtonStyle()
                .disabled(!viewModel.canStartGame)
                .opacity(viewModel.canStartGame ? 1 : 0.5)
            }

            Button("Back to Setup") {
                viewModel.resetRoom()
            }
            .buttonStyle(.plain)
            .foregroundStyle(.secondary)
        }
    }

    private var gameCard: some View {
        VStack(alignment: .leading, spacing: 18) {
            RoomCard {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Game Started")
                        .font(.title2.bold())

                    Text(viewModel.roomName)
                        .font(.title3.weight(.semibold))

                    Text("Room \(viewModel.roomCode.map(String.init).joined(separator: " "))")
                        .font(.headline)
                        .foregroundStyle(.indigo)

                    HStack(spacing: 12) {
                        turnRoleCard(
                            title: "Questioner",
                            playerName: viewModel.hostPlayer?.name ?? "Waiting",
                            tint: .indigo
                        )
                        turnRoleCard(
                            title: "Answering",
                            playerName: viewModel.answeringPlayer?.name ?? "Waiting",
                            tint: .blue
                        )
                    }

                    Text("Players in room")
                        .font(.headline)

                    LobbySlotsView(players: viewModel.players, capacity: viewModel.selectedPlayerCount)
                }
            }

            ZStack(alignment: .bottom) {
                RoomCard {
                    VStack(alignment: .leading, spacing: 18) {
                        Text("Round Statement")
                            .font(.headline)

                        Text(prompts[currentPromptIndex].statement)
                            .font(.body)
                            .foregroundStyle(.primary)
                            .padding(16)
                            .background(Color.white.opacity(0.76), in: RoundedRectangle(cornerRadius: 20, style: .continuous))

                        Text("Call it:")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.secondary)

                        HStack(spacing: 12) {
                            answerButton(.truth, tint: Color(red: 0.13, green: 0.57, blue: 0.68))
                            answerButton(.bluff, tint: Color(red: 0.69, green: 0.25, blue: 0.50))
                        }
                    }
                }

                if let validationPhase {
                    AIValidationBlock(phase: validationPhase, glowPulse: glowPulse)
                        .padding(.horizontal, 18)
                        .padding(.bottom, 28)
                        .transition(.scale(scale: 0.92).combined(with: .opacity))
                        .zIndex(1)
                }
            }

            HStack(spacing: 12) {
                Button("Back to Lobby") {
                    resetValidation()
                    viewModel.phase = .lobby
                }
                .frame(maxWidth: .infinity)
                .buttonStyle(.bordered)

                Button("Next Statement") {
                    advancePrompt()
                }
                .frame(maxWidth: .infinity)
                .appPrimaryButtonStyle(tint: .indigo)
            }

            Button("Reset Room") {
                resetValidation()
                viewModel.resetRoom()
            }
            .buttonStyle(.plain)
            .foregroundStyle(.secondary)
        }
    }

    private func turnRoleCard(title: String, playerName: String, tint: Color) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.caption.weight(.bold))
                .foregroundStyle(.secondary)

            Text(playerName)
                .font(.headline.weight(.semibold))
                .foregroundStyle(tint)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Color.white.opacity(0.75), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    private func answerButton(_ choice: TruthBluffChoice, tint: Color) -> some View {
        Button(choice.title) {
            startValidation(for: choice)
        }
        .font(.headline.weight(.semibold))
        .foregroundStyle(.white)
        .frame(maxWidth: .infinity)
        .padding(.vertical, 15)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(tint)
        )
        .scaleEffect(selectedAnswer == choice ? 0.98 : 1)
        .disabled(validationPhase != nil)
        .opacity(validationPhase == nil ? 1 : 0.7)
    }

    private func startValidation(for choice: TruthBluffChoice) {
        guard validationTask == nil else { return }

        selectedAnswer = choice
        glowPulse = false
        withAnimation(.spring(duration: 0.3)) {
            validationPhase = .loading(step: 0)
        }

        validationTask = Task {
            for step in [1, 2] {
                try? await Task.sleep(for: .milliseconds(700))
                guard !Task.isCancelled else { return }
                await MainActor.run {
                    withAnimation(.easeInOut(duration: 0.25)) {
                        validationPhase = .loading(step: step)
                    }
                }
            }

            try? await Task.sleep(for: .milliseconds(700))
            guard !Task.isCancelled else { return }

            let reveal = validationReveal(for: prompts[currentPromptIndex])
            await MainActor.run {
                withAnimation(.spring(response: 0.42, dampingFraction: 0.72)) {
                    validationPhase = .reveal(reveal)
                    glowPulse = true
                }
                triggerRevealFeedback()
            }

            try? await Task.sleep(for: .milliseconds(1100))
            guard !Task.isCancelled else { return }

            await MainActor.run {
                withAnimation(.easeInOut(duration: 0.25)) {
                    glowPulse = false
                }
                validationTask = nil
            }
        }
    }

    private func validationReveal(for prompt: GamePrompt) -> AIValidationReveal {
        let confidence: Int
        let personality: String

        switch prompt.prediction {
        case .truth:
            confidence = 82
            personality = "Hmm… this smells like truth 👀"
        case .bluff:
            confidence = 87
            personality = selectedAnswer == .bluff ? "I’m calling bluff on this one 😏" : "My circuits say… risky statement ⚠️"
        }

        return AIValidationReveal(
            prediction: prompt.prediction,
            confidence: confidence,
            personality: personality
        )
    }

    private func advancePrompt() {
        resetValidation()
        currentPromptIndex = (currentPromptIndex + 1) % prompts.count
    }

    private func resetValidation() {
        validationTask?.cancel()
        validationTask = nil
        selectedAnswer = nil
        glowPulse = false
        validationPhase = nil
    }

    private func triggerRevealFeedback() {
        let generator = UINotificationFeedbackGenerator()
        generator.prepare()
        generator.notificationOccurred(.success)
    }
}

private struct GamePrompt {
    let statement: String
    let prediction: TruthBluffChoice
}
