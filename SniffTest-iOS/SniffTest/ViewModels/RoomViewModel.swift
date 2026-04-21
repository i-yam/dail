//
//  RoomViewModel.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import Combine
import Foundation

final class RoomViewModel: ObservableObject {
    @Published var mode: RoomMode = .create
    @Published var phase: RoomPhase = .setup
    @Published var selectedPlayerCount = 4
    @Published var playerName = "Ava"
    @Published var joinCode = "ABCD"
    @Published var roomCode = "ABCD"
    @Published var roomName = "Bluff Lounge"
    @Published private(set) var players: [RoomPlayer] = []

    let availablePlayerCounts = Array(2...6)
    var joinedCountText: String {
        "\(players.count) / \(selectedPlayerCount) players joined"
    }

    var canStartGame: Bool {
        players.count >= 2
    }

    var canAddDemoPlayer: Bool {
        players.count < selectedPlayerCount
    }

    var hostPlayer: RoomPlayer? {
        players.first(where: \.isHost)
    }

    var answeringPlayer: RoomPlayer? {
        guard players.count > 1 else { return nil }
        return players[1]
    }

    func createRoom() {
        roomCode = generateRoomCode()
        roomName = generateRoomName()
        players = [RoomPlayer(name: sanitizedPlayerName, isHost: true)]
        phase = .lobby
    }

    func joinRoom() {
        roomCode = normalizedJoinCode
        roomName = generateRoomName()
        let hostName = "Host"
        players = [
            RoomPlayer(name: hostName, isHost: true),
            RoomPlayer(name: sanitizedPlayerName, isHost: false)
        ]
        selectedPlayerCount = max(selectedPlayerCount, players.count)
        phase = .lobby
    }

    func addDemoPlayer() {
        guard canAddDemoPlayer else { return }

        let demoNames = ["Ben", "Cora", "Dax", "Iris", "Leo", "Mina", "Noah", "Zara"]
        let availableName = demoNames.first { candidate in
            players.contains(where: { $0.name == candidate }) == false
        } ?? "Player \(players.count + 1)"

        players.append(RoomPlayer(name: availableName, isHost: false))
    }

    func resetRoom() {
        phase = .setup
        players = []
    }

    func startGame() {
        guard canStartGame else { return }
        phase = .game
    }

    func refreshRoomName() {
        roomName = generateRoomName()
    }

    private var sanitizedPlayerName: String {
        let trimmed = playerName.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? "Player 1" : trimmed
    }

    private var normalizedJoinCode: String {
        let trimmed = joinCode.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        return trimmed.isEmpty ? generateRoomCode() : String(trimmed.prefix(4))
    }

    private func generateRoomCode() -> String {
        let letters = Array("ABCDEFGHJKLMNPQRSTUVWXYZ")
        return String((0..<4).compactMap { _ in letters.randomElement() })
    }

    private func generateRoomName() -> String {
        let adjectives = [
            "Bluff",
            "Truth",
            "Signal",
            "Radar",
            "Cipher",
            "Echo",
            "Pulse",
            "Spotlight"
        ]
        let nouns = [
            "Lounge",
            "Lab",
            "Den",
            "Arena",
            "Circle",
            "Studio",
            "Hub",
            "Room"
        ]

        return "\(adjectives.randomElement() ?? "Truth") \(nouns.randomElement() ?? "Room")"
    }
}
