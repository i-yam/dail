//
//  AppTheme.swift
//  SniffTest
//
//  Created by Alina Andreieva on 21/4/26.
//

import SwiftUI

enum AppTheme {
    static let background = Color(
        red: 119.0 / 255.0,
        green: 177.0 / 255.0,
        blue: 212.0 / 255.0
    ).opacity(0.2)

    static let quizContainer = Color(.white)
}

private struct AdaptivePrimaryButtonStyleModifier: ViewModifier {
    let tint: Color

    @ViewBuilder
    func body(content: Content) -> some View {
        if #available(iOS 26, *) {
            content
                .buttonStyle(.glassProminent)
                .tint(tint)
        } else {
            content
                .buttonStyle(.borderedProminent)
                .tint(tint)
        }
    }
}

extension View {
    func appPrimaryButtonStyle(tint: Color = .indigo) -> some View {
        modifier(AdaptivePrimaryButtonStyleModifier(tint: tint))
    }
}
