//
//  QuizTabView.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import SwiftUI

struct QuizTabView: View {
    @StateObject private var viewModel = QuizViewModel()

    var body: some View {
        PhotosGameView(viewModel: viewModel)
    }
}
