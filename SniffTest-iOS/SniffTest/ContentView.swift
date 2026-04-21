//
//  ContentView.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import SwiftUI

struct ContentView: View {
    @StateObject private var appViewModel = AppViewModel()

    var body: some View {
        Group {
            if appViewModel.hasStarted {
                TabView(selection: $appViewModel.selectedTab) {
                    QuizTabView()
                        .tabItem {
                            Label("Quiz", systemImage: "questionmark.circle")
                        }
                        .tag(AppTab.quiz)

                    CheckerTabView()
                        .tabItem {
                            Label("Room", systemImage: "checkmark.shield")
                        }
                        .tag(AppTab.checker)

                    LegalTabView()
                        .tabItem {
                            Label("Legal", systemImage: "doc.text")
                        }
                        .tag(AppTab.legal)

                    ProfileTabView()
                        .tabItem {
                            Label("Profile", systemImage: "person.crop.circle")
                        }
                        .tag(AppTab.profile)
                }
                .background(AppTheme.background.ignoresSafeArea())
                .toolbarBackground(AppTheme.background, for: .tabBar)
                .toolbarBackground(.visible, for: .tabBar)
            } else {
                OnboardingView {
                    appViewModel.startExperience()
                }
            }
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
