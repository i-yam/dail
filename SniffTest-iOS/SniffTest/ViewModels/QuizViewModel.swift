//
//  QuizViewModel.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import Combine
import Foundation

final class QuizViewModel: ObservableObject {
    @Published private(set) var showsOverview = true
    @Published private(set) var currentLevel: QuizLevel = .beginner
    @Published private(set) var questions: [QuizQuestion] = []
    @Published private(set) var currentQuestionIndex = 0
    @Published private(set) var feedback: AnswerFeedback?
    @Published private(set) var selectedAnswer: QuizAnswer?
    @Published private(set) var hasAnsweredCurrentQuestion = false
    @Published private(set) var isRoundComplete = false
    @Published private(set) var didEndEarly = false
    @Published private(set) var numberOfCorrectAnswers = 0
    @Published private(set) var remainingTime = 0
    @Published private(set) var isLoadingModelPrediction = false

    private let advancedTimeLimit = 5
    private let beginnerAPIClient = BeginnerLevelAPIClient()
    private let intermediateAPIClient = IntermediateLevelAPIClient()
    private var timer: Timer?
    private var modelPredictionTask: Task<Void, Never>?

    init() {
        load(level: .beginner)
        showsOverview = true
    }

    deinit {
        modelPredictionTask?.cancel()
        stopTimer()
    }

    var currentQuestion: QuizQuestion? {
        guard questions.indices.contains(currentQuestionIndex) else { return nil }
        return questions[currentQuestionIndex]
    }

    var progressTitle: String {
        guard !questions.isEmpty else { return "No questions yet" }
        return "Question \(currentQuestionIndex + 1) of \(questions.count)"
    }

    var scoreTitle: String {
        "\(numberOfCorrectAnswers) correct"
    }

    var showsTimer: Bool {
        currentLevel == .advanced && !isRoundComplete
    }

    var completionMessage: String {
        if didEndEarly {
            return "You ended this round early. You can restart this level or continue when you're ready."
        }

        switch currentLevel {
        case .beginner:
            return "You handled the core red flags. Next up: naming the exact disinformation technique."
        case .intermediate:
            return "You are ready for the visual challenge."
        case .advanced:
            return "Nice work. You completed the timed real-vs-AI image challenge."
        }
    }

    var completionTitle: String {
        didEndEarly ? "\(currentLevel.title) ended early" : currentLevel.completionTitle
    }

    var primaryCompletionActionTitle: String {
        switch currentLevel {
        case .beginner:
            return "Go to Intermediate"
        case .intermediate:
            return "Go to Advanced"
        case .advanced:
            return "Play Advanced Again"
        }
    }

    var feedbackButtonTitle: String {
        isLoadingModelPrediction ? "Checking..." : "OK"
    }

    func submit(_ answer: QuizAnswer) {
        guard let currentQuestion, !hasAnsweredCurrentQuestion, !isRoundComplete else { return }

        modelPredictionTask?.cancel()
        hasAnsweredCurrentQuestion = true
        selectedAnswer = answer
        stopTimer()

        let isCorrect = currentQuestion.isCorrect(answer)
        if isCorrect {
            numberOfCorrectAnswers += 1
        }

        let feedbackTitle = isCorrect ? "Nice catch" : "Almost there"
        let feedbackKind: FeedbackKind = isCorrect ? .success : .warning

        if currentLevel == .beginner || currentLevel == .intermediate {
            isLoadingModelPrediction = true
            feedback = AnswerFeedback(
                title: feedbackTitle,
                message: loadingMessage(for: currentLevel),
                detailMessages: [],
                kind: feedbackKind
            )

            modelPredictionTask = Task { [weak self] in
                guard let self else { return }

                let message: String
                let detailMessages: [String]

                do {
                    let predictionInput = predictionText(for: currentQuestion)
                    let prediction = try await predictionForCurrentLevel(
                        text: predictionInput,
                        level: currentLevel
                    )
                    message = currentQuestion.explanation
                    detailMessages = predictionDetailLines(for: prediction)
                } catch {
                    let apiError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
                    message = currentQuestion.explanation
                    detailMessages = ["Prediction check failed: \(apiError)"]
                }

                guard !Task.isCancelled else { return }

                feedback = AnswerFeedback(
                    title: feedbackTitle,
                    message: message,
                    detailMessages: detailMessages,
                    kind: feedbackKind
                )
                isLoadingModelPrediction = false
            }
        } else {
            isLoadingModelPrediction = false
            feedback = AnswerFeedback(
                title: feedbackTitle,
                message: currentQuestion.explanation,
                detailMessages: [],
                kind: feedbackKind
            )
        }
    }

    func advance() {
        guard hasAnsweredCurrentQuestion, !isLoadingModelPrediction else { return }

        feedback = nil
        selectedAnswer = nil

        let nextIndex = currentQuestionIndex + 1
        if questions.indices.contains(nextIndex) {
            currentQuestionIndex = nextIndex
            hasAnsweredCurrentQuestion = false
            startTimerIfNeeded()
        } else {
            isRoundComplete = true
            stopTimer()
        }
    }

    func advanceToNextLevel() {
        switch currentLevel {
        case .beginner:
            load(level: .intermediate)
        case .intermediate:
            load(level: .advanced)
        case .advanced:
            load(level: .advanced)
        }
    }

    func restartCurrentLevel() {
        load(level: currentLevel)
    }

    func resetToBeginning() {
        load(level: .beginner)
    }

    func startQuiz() {
        showsOverview = false
    }

    func endRoundEarly() {
        guard !showsOverview, !isRoundComplete else { return }

        modelPredictionTask?.cancel()
        feedback = nil
        selectedAnswer = nil
        hasAnsweredCurrentQuestion = false
        isRoundComplete = true
        didEndEarly = true
        remainingTime = 0
        isLoadingModelPrediction = false
        stopTimer()
    }

    func returnToOverview() {
        modelPredictionTask?.cancel()
        stopTimer()
        currentLevel = .beginner
        questions = questionsForLevel(.beginner)
        currentQuestionIndex = 0
        feedback = nil
        selectedAnswer = nil
        hasAnsweredCurrentQuestion = false
        isRoundComplete = false
        didEndEarly = false
        numberOfCorrectAnswers = 0
        remainingTime = 0
        isLoadingModelPrediction = false
        showsOverview = true
    }

    private func load(level: QuizLevel) {
        modelPredictionTask?.cancel()
        showsOverview = false
        currentLevel = level
        questions = questionsForLevel(level)
        currentQuestionIndex = 0
        feedback = nil
        selectedAnswer = nil
        hasAnsweredCurrentQuestion = false
        isRoundComplete = false
        didEndEarly = false
        numberOfCorrectAnswers = 0
        remainingTime = showsTimer ? advancedTimeLimit : 0
        isLoadingModelPrediction = false
        startTimerIfNeeded()
    }

    private func questionsForLevel(_ level: QuizLevel) -> [QuizQuestion] {
        switch level {
        case .beginner:
            return QuizContent.beginnerQuestions
        case .intermediate:
            return QuizContent.intermediateQuestions
        case .advanced:
            return QuizContent.advancedQuestions
        }
    }

    private func startTimerIfNeeded() {
        stopTimer()

        guard currentLevel == .advanced, !hasAnsweredCurrentQuestion, !isRoundComplete else {
            remainingTime = 0
            return
        }

        remainingTime = advancedTimeLimit
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            self?.tickTimer()
        }
    }

    private func tickTimer() {
        guard currentLevel == .advanced, !hasAnsweredCurrentQuestion else {
            stopTimer()
            return
        }

        if remainingTime > 0 {
            remainingTime -= 1
        }

        if remainingTime == 0 {
            handleTimeExpired()
        }
    }

    private func handleTimeExpired() {
        guard let currentQuestion, !hasAnsweredCurrentQuestion else { return }

        hasAnsweredCurrentQuestion = true
        stopTimer()
        feedback = AnswerFeedback(
            title: "Time's up",
            message: currentQuestion.explanation,
            detailMessages: [],
            kind: .timeout
        )
    }

    private func stopTimer() {
        timer?.invalidate()
        timer = nil
    }

    private func predictionDetailLines(for prediction: BeginnerPrediction) -> [String] {
        let displayLabel = prediction.label.map { $0 == "FAKE" ? "Bluff" : $0 }
        let probabilityLines = prediction.probabilities
            .sorted { $0.value > $1.value }
            .map { "\($0.key): \($0.value.formatted(.percent.precision(.fractionLength(1...2))))" }
            .joined(separator: ", ")

        let fakeRealLines = [
            prediction.probFake.map { "Bluff: \($0.formatted(.percent.precision(.fractionLength(1...2))))" },
            prediction.probReal.map { "Real: \($0.formatted(.percent.precision(.fractionLength(1...2))))" }
        ]
        .compactMap { $0 }
        .joined(separator: ", ")

        return [
            displayLabel.map { "**Label:** \($0)" },
            prediction.predictedCategory.map { "**Category:** \($0)" },
            prediction.confidence.map { "**Confidence:** \($0.formatted(.percent.precision(.fractionLength(1...2))))" },
            fakeRealLines.isEmpty ? nil : "**Scores:** \(fakeRealLines)",
            probabilityLines.isEmpty ? nil : "**Scores:** \(probabilityLines)"
        ]
        .compactMap { $0 }
    }

    private func predictionText(for question: QuizQuestion) -> String {
        if let statementText = question.statementText {
            return statementText
        }

        return "\(question.title) \(question.detail)"
    }

    private func predictionForCurrentLevel(
        text: String,
        level: QuizLevel
    ) async throws -> BeginnerPrediction {
        switch level {
        case .beginner:
            return try await beginnerAPIClient.predict(text: text)
        case .intermediate:
            return try await intermediateAPIClient.predict(text: text)
        case .advanced:
            throw IntermediateLevelAPIError.invalidResponse
        }
    }

    private func loadingMessage(for level: QuizLevel) -> String {
        switch level {
        case .beginner:
            return "Checking the statement..."
        case .intermediate:
            return "Checking the technique..."
        case .advanced:
            return "Checking..."
        }
    }
}
