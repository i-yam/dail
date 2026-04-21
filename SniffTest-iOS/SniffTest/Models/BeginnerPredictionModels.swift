//
//  BeginnerPredictionModels.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import Foundation

struct BeginnerPredictionRequest: Encodable {
    let text: String
}

struct BeginnerPredictionResponse: Decodable {
    let count: Int
    let predictions: [BeginnerPrediction]

    init(from decoder: Decoder) throws {
        if let container = try? decoder.container(keyedBy: CodingKeys.self),
           let predictions = try? container.decode([BeginnerPrediction].self, forKey: .predictions) {
            count = (try? container.decode(Int.self, forKey: .count)) ?? predictions.count
            self.predictions = predictions
            return
        }

        let singlePrediction = try BeginnerPrediction(from: decoder)
        count = 1
        predictions = [singlePrediction]
    }

    private enum CodingKeys: String, CodingKey {
        case count
        case predictions
    }
}

struct BeginnerPrediction: Decodable, Equatable {
    let statement: String?
    let predictedCategory: String?
    let confidence: Double?
    let probabilities: [String: Double]
    let label: String?
    let probFake: Double?
    let probReal: Double?

    init(
        statement: String?,
        predictedCategory: String?,
        confidence: Double?,
        probabilities: [String: Double],
        label: String?,
        probFake: Double?,
        probReal: Double?
    ) {
        self.statement = statement
        self.predictedCategory = predictedCategory
        self.confidence = confidence
        self.probabilities = probabilities
        self.label = label
        self.probFake = probFake
        self.probReal = probReal
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        let statement = try container.decodeIfPresent(String.self, forKey: .statement)
        let predictedCategory = try container.decodeIfPresent(String.self, forKey: .predictedCategory)
        let confidence = try container.decodeIfPresent(Double.self, forKey: .confidence)
        let probabilities = try container.decodeIfPresent([String: Double].self, forKey: .probabilities) ?? [:]
        let label = try container.decodeIfPresent(String.self, forKey: .label)
        let probFake = try container.decodeIfPresent(Double.self, forKey: .probFake)
        let probReal = try container.decodeIfPresent(Double.self, forKey: .probReal)

        self.init(
            statement: statement,
            predictedCategory: predictedCategory,
            confidence: confidence,
            probabilities: probabilities,
            label: label,
            probFake: probFake,
            probReal: probReal
        )
    }

    enum CodingKeys: String, CodingKey {
        case statement
        case predictedCategory = "predicted_category"
        case confidence
        case probabilities
        case label
        case probFake = "prob_fake"
        case probReal = "prob_real"
    }
}
