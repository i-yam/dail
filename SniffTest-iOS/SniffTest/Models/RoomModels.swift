//
//  RoomModels.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import Foundation

enum RoomMode: String, CaseIterable, Identifiable {
    case create
    case join

    var id: String { rawValue }

    var title: String {
        switch self {
        case .create:
            return "Create"
        case .join:
            return "Join"
        }
    }
}

enum RoomPhase {
    case setup
    case lobby
    case game
}

struct RoomPlayer: Identifiable, Equatable {
    let id = UUID()
    let name: String
    let isHost: Bool
}
