//
//  AppViewModel.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import Combine

final class AppViewModel: ObservableObject {
    @Published var hasStarted = false
    @Published var selectedTab: AppTab = .quiz

    func startExperience() {
        selectedTab = .quiz
        hasStarted = true
    }
}
