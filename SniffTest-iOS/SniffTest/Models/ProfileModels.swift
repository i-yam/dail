//
//  ProfileModels.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import Foundation
import SwiftUI

enum ProfileAvatar: String, CaseIterable, Codable, Identifiable {
    case comet
    case mask
    case spark
    case bolt
    case wave
    case prism

    var id: String { rawValue }

    var symbolName: String {
        switch self {
        case .comet:
            return "moon.stars.fill"
        case .mask:
            return "theatermasks.fill"
        case .spark:
            return "sparkles"
        case .bolt:
            return "bolt.fill"
        case .wave:
            return "dot.radiowaves.left.and.right"
        case .prism:
            return "diamond.fill"
        }
    }
}

enum AppLanguage: String, CaseIterable, Codable, Identifiable {
    case english = "English"
    case german = "German"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .english:
            return "English 🇬🇧"
        case .german:
            return "German 🇩🇪"
        }
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let rawValue = try container.decode(String.self)
        self = AppLanguage(rawValue: rawValue) ?? .english
    }
}

struct ProfileStats: Codable, Equatable {
    var streak: Int
    var roomsPlayed: Int
    var accuracyRate: Int
    var bluffSuccessRate: Int
    var xp: Int
    var currentLevelXP: Int
    var nextLevelXP: Int

    static let guest = ProfileStats(
        streak: 3,
        roomsPlayed: 12,
        accuracyRate: 78,
        bluffSuccessRate: 66,
        xp: 420,
        currentLevelXP: 300,
        nextLevelXP: 600
    )
}

struct ProfileBadge: Identifiable, Codable, Equatable {
    let id: String
    let title: String
    let subtitle: String
    let symbolName: String
    let isUnlocked: Bool

    static let starterSet: [ProfileBadge] = [
        ProfileBadge(id: "first-room", title: "First Room", subtitle: "Hosted your first match", symbolName: "door.left.hand.open", isUnlocked: true),
        ProfileBadge(id: "truth-streak", title: "Truth Seeker", subtitle: "5 correct truth calls", symbolName: "checkmark.seal.fill", isUnlocked: true),
        ProfileBadge(id: "bluff-hunter", title: "Bluff Hunter", subtitle: "Expose 10 bluffs", symbolName: "eye.fill", isUnlocked: false),
        ProfileBadge(id: "crowd-favorite", title: "Crowd Favorite", subtitle: "Play 25 rooms", symbolName: "person.3.fill", isUnlocked: false)
    ]
}

struct ProfileState: Codable, Equatable {
    var nickname: String
    var avatar: ProfileAvatar
    var isGuestMode: Bool
    var notificationsEnabled: Bool
    var soundEnabled: Bool
    var language: AppLanguage
    var stats: ProfileStats
    var badges: [ProfileBadge]

    static let guest = ProfileState(
        nickname: "Guest Sleuth",
        avatar: .spark,
        isGuestMode: true,
        notificationsEnabled: true,
        soundEnabled: true,
        language: .english,
        stats: .guest,
        badges: ProfileBadge.starterSet
    )
}

struct ProfileCopy {
    let language: AppLanguage

    var profileTitle: String {
        switch language {
        case .english:
            return "Profile"
        case .german:
            return "Profil"
        }
    }

    var guestModeTitle: String {
        switch language {
        case .english:
            return "Guest Mode Active"
        case .german:
            return "Gastmodus aktiv"
        }
    }

    var profileActiveTitle: String {
        switch language {
        case .english:
            return "Profile Active"
        case .german:
            return "Profil aktiv"
        }
    }

    var guestModeMessage: String {
        switch language {
        case .english:
            return "You can keep playing without signing up. Personalize the profile anytime."
        case .german:
            return "Du kannst ohne Anmeldung weiterspielen. Passe dein Profil jederzeit an."
        }
    }

    var profileActiveMessage: String {
        switch language {
        case .english:
            return "Your progress is stored locally and won’t interrupt room or game sessions."
        case .german:
            return "Dein Fortschritt wird lokal gespeichert und unterbricht keine Raum- oder Spielsitzungen."
        }
    }

    var guestRole: String {
        switch language {
        case .english:
            return "Guest detective"
        case .german:
            return "Gastdetektiv"
        }
    }

    var xpProgress: String {
        switch language {
        case .english:
            return "XP Progress"
        case .german:
            return "XP-Fortschritt"
        }
    }

    var stats: String {
        switch language {
        case .english:
            return "Stats"
        case .german:
            return "Statistiken"
        }
    }

    var badges: String {
        switch language {
        case .english:
            return "Badges"
        case .german:
            return "Abzeichen"
        }
    }

    var settings: String {
        switch language {
        case .english:
            return "Settings"
        case .german:
            return "Einstellungen"
        }
    }

    var languageTitle: String {
        switch language {
        case .english:
            return "Language"
        case .german:
            return "Sprache"
        }
    }

    var notifications: String {
        switch language {
        case .english:
            return "Notifications"
        case .german:
            return "Benachrichtigungen"
        }
    }

    var sound: String {
        switch language {
        case .english:
            return "Sound"
        case .german:
            return "Sound"
        }
    }

    var editProfile: String {
        switch language {
        case .english:
            return "Edit Profile"
        case .german:
            return "Profil bearbeiten"
        }
    }

    var nickname: String {
        switch language {
        case .english:
            return "Nickname"
        case .german:
            return "Spitzname"
        }
    }

    var keepGuestMode: String {
        switch language {
        case .english:
            return "Keep Guest Mode"
        case .german:
            return "Gastmodus behalten"
        }
    }

    var avatar: String {
        switch language {
        case .english:
            return "Avatar"
        case .german:
            return "Avatar"
        }
    }

    var close: String {
        switch language {
        case .english:
            return "Close"
        case .german:
            return "Schließen"
        }
    }

    var save: String {
        switch language {
        case .english:
            return "Save"
        case .german:
            return "Speichern"
        }
    }

    var streak: String {
        switch language {
        case .english:
            return "Streak"
        case .german:
            return "Serie"
        }
    }

    var roomsPlayed: String {
        switch language {
        case .english:
            return "Rooms Played"
        case .german:
            return "Gespielte Räume"
        }
    }

    var accuracy: String {
        switch language {
        case .english:
            return "Accuracy"
        case .german:
            return "Genauigkeit"
        }
    }

    var bluffSuccess: String {
        switch language {
        case .english:
            return "Bluff Success"
        case .german:
            return "Bluff-Erfolg"
        }
    }

    var updatedToast: String {
        switch language {
        case .english:
            return "Updated ✅"
        case .german:
            return "Aktualisiert ✅"
        }
    }

    var guestToast: String {
        switch language {
        case .english:
            return "Guest mode active"
        case .german:
            return "Gastmodus aktiv"
        }
    }
}
 
extension ProfileState {
    var backgroundColor: Color {
        AppTheme.background
    }

    var containerColor: Color {
        AppTheme.quizContainer
    }
}
