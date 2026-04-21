//
//  OnboardingView.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import SwiftUI

struct OnboardingView: View {
    private let introPages: [String] = [
        "This game is an educational tool designed to develop users’ ability to recognise common techniques of disinformation, including but not limited to loaded language, false dichotomy, manufactured consensus, cherry-picking, and whataboutism.",
        "The content presented within the game (including images, texts, and statements) may include AI-generated or modified materials created for training and illustrative purposes. The game provides users with structured feedback and explanations for each task to enhance critical thinking and media literacy skills.",
        "The game does not provide definitive verification of the objective truthfulness or falsity of real-world information. Instead, it focuses on identifying patterns and techniques commonly used in misleading or manipulative content.",
        "All outputs, feedback, and explanations generated within the game are probabilistic and educational in nature and should not be interpreted as factual conclusions or used as a basis for legal, journalistic, or other professional decision-making.",
        "This tool is developed in line with principles and laws of European union and Ukrainian legislation relevant to regulation of this problem.",
        "By continuing to use this game, you acknowledge that the tool serves solely educational purposes and does not replace independent critical evaluation of information."
    ]

    let onStart: () -> Void
    @State private var introPage = 0

    var body: some View {
        ZStack {
            AppTheme.background
                .ignoresSafeArea()

            ScrollView {
                introductionStep
                .padding(24)
            }
        }
    }

    private var introductionStep: some View {
        VStack(alignment: .leading, spacing: 24) {
            VStack(alignment: .leading, spacing: 12) {
                Text("Welcome!")
                    .font(.largeTitle.bold())

                Text("Please read each page before entering the main content.")
                    .font(.title3)
                    .foregroundStyle(.secondary)
            }

            VStack(alignment: .leading, spacing: 20) {
                TabView(selection: $introPage) {
                    ForEach(Array(introPages.enumerated()), id: \.offset) { index, text in
                        IntroPageCard(
                            pageNumber: index + 1,
                            totalPages: introPages.count,
                            text: text
                        )
                        .tag(index)
                    }
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                .frame(height: 320)

                HStack(spacing: 10) {
                    ForEach(Array(introPages.indices), id: \.self) { index in
                        Button {
                            withAnimation(.easeInOut) {
                                introPage = index
                            }
                        } label: {
                            Capsule()
                                .fill(index == introPage ? Color.indigo : Color.indigo.opacity(0.22))
                                .frame(width: index == introPage ? 28 : 10, height: 10)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .frame(maxWidth: .infinity)
            }
            .padding(24)
            .background(.white, in: RoundedRectangle(cornerRadius: 28, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .stroke(.indigo.opacity(0.3), lineWidth: 1)
            )

            HStack {
                Button("Back") {
                    guard introPage > 0 else { return }
                    withAnimation(.easeInOut) {
                        introPage -= 1
                    }
                }
                .buttonStyle(.plain)
                .foregroundStyle(introPage == 0 ? .tertiary : .secondary)
                .disabled(introPage == 0)

                Spacer()

                Button {
                    if introPage < introPages.count - 1 {
                        withAnimation(.easeInOut) {
                            introPage += 1
                        }
                    } else {
                        onStart()
                    }
                } label: {
                    Text(introPage == introPages.count - 1 ? "Enter App" : "Next")
                        .font(.headline)
                        .padding(.vertical, 8)
                        .padding(.horizontal, 40)
                }
                .appPrimaryButtonStyle()
            }
        }
    }
}

private struct IntroParagraph: View {
    let text: String

    var body: some View {
        Text(text)
            .foregroundStyle(.primary)
            .fixedSize(horizontal: false, vertical: true)
    }
}

private struct IntroPageCard: View {
    let pageNumber: Int
    let totalPages: Int
    let text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Page \(pageNumber) of \(totalPages)")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.secondary)

            IntroParagraph(text: text)
                .font(.body)

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }
}

struct OnboardingView_Previews: PreviewProvider {
    static var previews: some View {
        OnboardingView(onStart: {})
    }
}
