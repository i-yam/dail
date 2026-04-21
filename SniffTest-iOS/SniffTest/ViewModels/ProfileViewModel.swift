//
//  ProfileViewModel.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import Combine
import Foundation

final class ProfileViewModel: ObservableObject {
    @Published private(set) var profile: ProfileState
    @Published var showsEditProfile = false
    @Published var toastMessage: String?

    private let storageKey = "truth_bluff_profile_state"

    init() {
        if let data = UserDefaults.standard.data(forKey: storageKey),
           let decoded = try? JSONDecoder().decode(ProfileState.self, from: data) {
            profile = decoded
        } else {
            profile = .guest
        }
    }

    var copy: ProfileCopy {
        ProfileCopy(language: profile.language)
    }

    var levelTitle: String {
        switch profile.language {
        case .english:
            return "Level \(max(1, profile.stats.xp / 150))"
        case .german:
            return "Level \(max(1, profile.stats.xp / 150))"
        }
    }

    var xpProgress: Double {
        let span = max(1, profile.stats.nextLevelXP - profile.stats.currentLevelXP)
        let earned = max(0, profile.stats.xp - profile.stats.currentLevelXP)
        return min(1, Double(earned) / Double(span))
    }

    func updateNotifications(_ isEnabled: Bool) {
        profile.notificationsEnabled = isEnabled
        persist()
    }

    func updateSound(_ isEnabled: Bool) {
        profile.soundEnabled = isEnabled
        persist()
    }

    func updateLanguage(_ language: AppLanguage) {
        profile.language = language
        persist()
    }

    func saveProfile(nickname: String, avatar: ProfileAvatar) {
        profile.nickname = nickname.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? profile.nickname : nickname.trimmingCharacters(in: .whitespacesAndNewlines)
        profile.avatar = avatar
        profile.isGuestMode = false
        persist()
        showToast(copy.updatedToast)
    }

    func continueAsGuest(with nickname: String) {
        let trimmed = nickname.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty == false {
            profile.nickname = trimmed
        }
        profile.isGuestMode = true
        persist()
        showToast(copy.guestToast)
    }

    private func persist() {
        if let data = try? JSONEncoder().encode(profile) {
            UserDefaults.standard.set(data, forKey: storageKey)
        }
    }

    private func showToast(_ message: String) {
        toastMessage = message
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) { [weak self] in
            guard self?.toastMessage == message else { return }
            self?.toastMessage = nil
        }
    }
}
