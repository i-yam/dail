//
//  BeginnerLevelAPIClient.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import Foundation

struct BeginnerLevelAPIClient {
    private let endpoint = URL(string: "http://100.82.237.37:5000/predict")!
    private let decoder = JSONDecoder()

    func predict(text: String) async throws -> BeginnerPrediction {
        debugLog("Starting beginner request to \(endpoint.absoluteString)")
        debugLog("Input text: \(text)")

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(BeginnerPredictionRequest(text: text))

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            debugLog("Response was not an HTTPURLResponse.")
            throw BeginnerLevelAPIError.invalidResponse
        }

        debugLog("HTTP status code: \(httpResponse.statusCode)")

        guard 200 ... 299 ~= httpResponse.statusCode else {
            let message = String(data: data, encoding: .utf8)?
                .trimmingCharacters(in: .whitespacesAndNewlines)
            debugLog("Server error body: \(message ?? "<empty>")")
            throw BeginnerLevelAPIError.serverError(
                statusCode: httpResponse.statusCode,
                message: message?.isEmpty == false ? message : nil
            )
        }

        let decodedResponse: BeginnerPredictionResponse

        do {
            decodedResponse = try decoder.decode(BeginnerPredictionResponse.self, from: data)
        } catch {
            debugLog("Decoding failed: \(error.localizedDescription)")
            debugLog("Raw body: \(String(data: data, encoding: .utf8) ?? "<non-utf8>")")
            throw BeginnerLevelAPIError.decodingFailed
        }

        guard let prediction = decodedResponse.predictions.first else {
            debugLog("Predictions array was empty.")
            throw BeginnerLevelAPIError.emptyPredictions
        }

        if let predictedCategory = prediction.predictedCategory {
            debugLog("Predicted category: \(predictedCategory)")
        }

        if let confidence = prediction.confidence {
            debugLog("Confidence: \(confidence)")
        }

        if let label = prediction.label {
            debugLog("Label: \(label)")
        }

        return prediction
    }

    private func debugLog(_ message: String) {
#if DEBUG
        print("[BeginnerLevelAPIClient] \(message)")
#endif
    }
}

enum BeginnerLevelAPIError: LocalizedError {
    case invalidResponse
    case decodingFailed
    case emptyPredictions
    case serverError(statusCode: Int, message: String?)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "The app received an invalid response from the beginner API."
        case .decodingFailed:
            return "The app could not decode the beginner API response."
        case .emptyPredictions:
            return "The beginner API returned no predictions."
        case let .serverError(statusCode, message):
            if let message, !message.isEmpty {
                return "Beginner API error \(statusCode): \(message)"
            }
            return "Beginner API error \(statusCode)."
        }
    }
}
