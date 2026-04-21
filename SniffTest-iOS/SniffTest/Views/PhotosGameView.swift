//
//  PhotosGameView.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import SwiftUI

struct PhotosGameView: View {
    @ObservedObject var viewModel: QuizViewModel

    var body: some View {
        NavigationStack {
            ZStack {
                AppTheme.background
                    .ignoresSafeArea()

                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        if viewModel.showsOverview {
                            overviewCard
                        } else {
                            levelHeader
                        }

                        if viewModel.showsOverview {
                            EmptyView()
                        } else if viewModel.isRoundComplete {
                            completionCard
                        } else if let question = viewModel.currentQuestion {
                            questionCard(question)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.top)
                }
                .blur(radius: viewModel.feedback == nil ? 0 : 2)
                .overlay {
                    if viewModel.feedback != nil {
                        Color.black.opacity(0.18)
                            .ignoresSafeArea()
                    }
                }
                .disabled(viewModel.feedback != nil)

                if let feedback = viewModel.feedback {
                    FeedbackOverlayView(
                        feedback: feedback,
                        actionTitle: viewModel.feedbackButtonTitle,
                        isActionDisabled: viewModel.isLoadingModelPrediction,
                        action: viewModel.advance
                    )
                        .padding(.horizontal, 24)
                        .transition(.scale(scale: 0.96).combined(with: .opacity))
                }
            }
            .animation(.spring(duration: 0.3), value: viewModel.feedback?.id)
            .animation(.easeInOut, value: viewModel.isRoundComplete)
            .toolbar(viewModel.showsOverview ? .visible : .hidden, for: .tabBar)
            .toolbar {
                if !viewModel.showsOverview {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("End Game") {
                            if viewModel.isRoundComplete {
                                viewModel.returnToOverview()
                            } else {
                                viewModel.endRoundEarly()
                            }
                        }
                    }
                }
            }
        }
    }

    private var overviewCard: some View {
        VStack(alignment: .leading, spacing: 24) {
            VStack(alignment: .leading, spacing: 12) {
                Text("Detect Disinformation")
                    .font(.largeTitle.bold())

                Text("Train yourself to spot misleading content before you share it.")
                    .font(.title3)
                    .foregroundStyle(.secondary)
            }

            VStack(alignment: .leading, spacing: 16) {
                QuizRuleRow(
                    icon: "1.circle.fill",
                    title: "Beginner",
                    message: "Read a short post and decide whether it feels trustworthy: true or false."
                )
                QuizRuleRow(
                    icon: "2.circle.fill",
                    title: "Intermediate",
                    message: "Name the type of disinformation, like false context, parody, or manipulated content."
                )
                QuizRuleRow(
                    icon: "3.circle.fill",
                    title: "Advanced",
                    message: "Race through a timed set of images and decide whether each one is real or AI-generated."
                )
                QuizRuleRow(
                    icon: "text.bubble.fill",
                    title: "After every answer",
                    message: "You will get a friendly explanation banner so the app teaches, not just scores."
                )
            }
            .padding(24)
            .background(.white, in: RoundedRectangle(cornerRadius: 28, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .stroke(.indigo, lineWidth: 1)
            )
            
            Spacer()

            HStack {
                Spacer()
                Button(action: viewModel.startQuiz) {
                    Text("Start")
                        .font(.headline)
                        .padding(.vertical, 8)
                        .padding(.horizontal, 52)
                }
                .appPrimaryButtonStyle()
                Spacer()
            }
        }
        .padding(.top, 8)
    }

    private var levelHeader: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(viewModel.currentLevel.title)
                        .font(.title.bold())
                    Text(viewModel.currentLevel.subtitle)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                if viewModel.showsTimer {
                    TimerBadgeView(remainingTime: viewModel.remainingTime)
                }
            }

            HStack {
                Label(viewModel.progressTitle, systemImage: "list.number")
                Spacer()
                Label(viewModel.scoreTitle, systemImage: "checkmark.seal")
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)
        }
    }

    private func questionCard(_ question: QuizQuestion) -> some View {
        VStack(alignment: .leading, spacing: 20) {
            if question.level == .advanced {
                DemoQuestionMediaView(question: question)

                VStack(alignment: .leading, spacing: 10) {
                    Text(question.title)
                        .font(.title3.weight(.semibold))

                    Text(question.detail)
                        .foregroundStyle(.secondary)
                }
            } else {
                Text(textOnlyStatement(for: question))
                    .font(.title3.weight(.semibold))
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            VStack(spacing: 12) {
                ForEach(question.answers) { answer in
                    AnswerButton(
                        title: question.label(for: answer),
                        isDisabled: viewModel.hasAnsweredCurrentQuestion,
                        isSelected: viewModel.selectedAnswer == answer
                    ) {
                        viewModel.submit(answer)
                    }
                }
            }
        }
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .fill(AppTheme.quizContainer)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .stroke(Color.black.opacity(0.08), lineWidth: 1)
        )
    }

    private func textOnlyStatement(for question: QuizQuestion) -> String {
        if let statementText = question.statementText {
            return statementText
        }

        return "\(question.title) \(question.detail)"
    }

    private var completionCard: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(viewModel.completionTitle)
                .font(.title2.bold())

            Text(viewModel.completionMessage)
                .foregroundStyle(.secondary)

            HStack {
                Label(viewModel.scoreTitle, systemImage: "star.fill")
                Spacer()
                Label("\(viewModel.questions.count) total", systemImage: "number")
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)

            Button(action: viewModel.advanceToNextLevel) {
                Text(viewModel.primaryCompletionActionTitle)
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
            }
            .appPrimaryButtonStyle()

            Button(action: viewModel.restartCurrentLevel) {
                Text("Restart Level")
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
            }
            .buttonStyle(.bordered)

            if viewModel.currentLevel != .beginner {
                Button(action: viewModel.resetToBeginning) {
                    Text("Back to Beginner")
                        .font(.subheadline.weight(.semibold))
                }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
            }
        }
        .padding(24)
        .background(
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .fill(AppTheme.quizContainer)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .stroke(Color.black.opacity(0.08), lineWidth: 1)
        )
    }
}

private struct QuizRuleRow: View {
    let icon: String
    let title: String
    let message: String

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(.indigo)
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.headline)

                Text(message)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

private struct AnswerButton: View {
    let title: String
    let isDisabled: Bool
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack {
                Text(title)
                    .font(.headline)
                Spacer()
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .foregroundStyle(isSelected ? .indigo : .secondary)
            }
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(isSelected ? Color.indigo.opacity(0.14) : .white.opacity(0.88))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(isSelected ? Color.indigo : Color.gray.opacity(0.18), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .disabled(isDisabled)
        .opacity(isDisabled && !isSelected ? 0.65 : 1)
    }
}

private struct FeedbackOverlayView: View {
    let feedback: AnswerFeedback
    let actionTitle: String
    let isActionDisabled: Bool
    let action: () -> Void

    private var messageText: AttributedString {
        if let markdown = try? AttributedString(markdown: feedback.message) {
            return markdown
        }

        return AttributedString(feedback.message)
    }

    private var detailMessageTexts: [AttributedString] {
        feedback.detailMessages.compactMap { detailMessage in
            if let markdown = try? AttributedString(markdown: detailMessage) {
                return markdown
            }

            return AttributedString(detailMessage)
        }
    }

    private var tint: Color {
        switch feedback.kind {
        case .success:
            return .green
        case .warning:
            return .orange
        case .timeout:
            return .pink
        }
    }

    private var iconName: String {
        switch feedback.kind {
        case .success:
            return "checkmark.circle.fill"
        case .warning:
            return "lightbulb.fill"
        case .timeout:
            return "timer"
        }
    }

    var body: some View {
        VStack(spacing: 18) {
            Image(systemName: iconName)
                .font(.system(size: 28, weight: .semibold))
                .foregroundStyle(tint)

            VStack(alignment: .center, spacing: 8) {
                Text(feedback.title)
                    .font(.title3.weight(.semibold))

                Text(messageText)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.leading)

                if !detailMessageTexts.isEmpty {
                    Color.clear
                        .frame(height: 10)

                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(Array(detailMessageTexts.enumerated()), id: \.offset) { _, detailMessageText in
                            Text(detailMessageText)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.leading)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }

            Button(action: action) {
                HStack {
                    if isActionDisabled {
                        ProgressView()
                            .tint(.white)
                    }

                    Text(actionTitle)
                        .font(.headline)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
            }
            .appPrimaryButtonStyle()
            .disabled(isActionDisabled)
        }
        .padding(24)
        .frame(maxWidth: 360)
        .background(.white, in: RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(tint.opacity(0.35), lineWidth: 1.5)
        )
        .shadow(color: .black.opacity(0.12), radius: 24, y: 12)
    }
}

private struct DemoQuestionMediaView: View {
    let question: QuizQuestion

    private var palette: [Color] {
        switch question.tone {
        case .sky:
            return [.blue.opacity(0.24), .cyan.opacity(0.16)]
        case .amber:
            return [.orange.opacity(0.24), .yellow.opacity(0.16)]
        case .mint:
            return [.green.opacity(0.22), .mint.opacity(0.16)]
        case .coral:
            return [.red.opacity(0.20), .orange.opacity(0.16)]
        case .violet:
            return [.indigo.opacity(0.22), .purple.opacity(0.16)]
        case .slate:
            return [.gray.opacity(0.28), .blue.opacity(0.10)]
        case .rose:
            return [.pink.opacity(0.22), .red.opacity(0.12)]
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Label(question.mediaSource, systemImage: "person.crop.rectangle")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.secondary)

                Spacer()

                Text(question.mediaBadge)
                    .font(.caption.weight(.bold))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(.white.opacity(0.7), in: Capsule())
            }

            if let mediaAssetName = question.mediaAssetName {
                Image(mediaAssetName)
                    .resizable()
                    .scaledToFit()
                    .frame(maxWidth: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 24, style: .continuous)
                            .stroke(Color.black.opacity(0.08), lineWidth: 1)
                    )
            } else {
                ZStack {
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .fill(
                            LinearGradient(
                                colors: palette,
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(minHeight: 220)

                    VStack(spacing: 12) {
                        Image(systemName: question.mediaSymbol)
                            .font(.system(size: 48))
                            .foregroundStyle(.primary)

                        Text(question.mediaHeadline)
                            .font(.headline)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }
                    .padding(24)
                }

                Text("Demo visual for prototype. Replace with your real screenshot or photo later.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

private struct TimerBadgeView: View {
    let remainingTime: Int

    private var tint: Color {
        remainingTime <= 5 ? .pink : .indigo
    }

    var body: some View {
        Label("\(remainingTime)s", systemImage: "timer")
            .font(.headline)
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(tint.opacity(0.12), in: Capsule())
            .foregroundStyle(tint)
    }
}

struct PhotosGameView_Previews: PreviewProvider {
    static var previews: some View {
        PhotosGameView(viewModel: QuizViewModel())
    }
}
