import SwiftUI

struct ProfileTabView: View {
    @StateObject private var viewModel = ProfileViewModel()
    @State private var draftNickname = ""
    @State private var draftAvatar: ProfileAvatar = .spark
    @State private var animateHeader = false

    var body: some View {
        NavigationStack {
            ZStack {
                
                // ✅ FIXED: Removed gradient → using AppTheme only
                AppTheme.background
                    .ignoresSafeArea()

                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 20) {
                        guestBanner
                        profileHeader
                        statsSection
                        badgesSection
                        settingsSection
                    }
                    .padding(24)
                }

                if let toast = viewModel.toastMessage {
                    VStack {
                        Spacer()
                        ProfileToast(message: toast)
                            .padding(.bottom, 24)
                    }
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .navigationTitle(viewModel.copy.profileTitle)
            .sheet(isPresented: $viewModel.showsEditProfile, onDismiss: syncDrafts) {
                editProfileSheet
            }
            .onAppear {
                syncDrafts()
                withAnimation(.easeOut(duration: 0.3)) {
                    animateHeader = true
                }
            }
        }
    }

    private var guestBanner: some View {
        ProfileGlassCard {
            HStack(alignment: .top, spacing: 14) {
                Image(systemName: "person.crop.circle.badge.questionmark")
                    .font(.title2)
                    .foregroundStyle(.purple)

                VStack(alignment: .leading, spacing: 6) {
                    Text(viewModel.profile.isGuestMode ? viewModel.copy.guestModeTitle : viewModel.copy.profileActiveTitle)
                        .font(.headline)

                    Text(viewModel.profile.isGuestMode ? viewModel.copy.guestModeMessage : viewModel.copy.profileActiveMessage)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    private var profileHeader: some View {
        ProfileGlassCard {
            VStack(alignment: .leading, spacing: 18) {
                HStack(alignment: .center) {
                    ProfileAvatarBadge(avatar: viewModel.profile.avatar, size: 84)

                    VStack(alignment: .leading, spacing: 6) {
                        Text(viewModel.profile.nickname)
                            .font(.title2.bold())

                        Text(viewModel.profile.isGuestMode ? viewModel.copy.guestRole : viewModel.levelTitle)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    Button(viewModel.copy.editProfile) {
                        syncDrafts()
                        viewModel.showsEditProfile = true
                    }
                    .buttonStyle(ProfileActionButtonStyle(tint: .indigo))
                }

                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text(viewModel.copy.xpProgress)
                            .font(.caption.weight(.bold))
                            .foregroundStyle(.secondary)
                        Spacer()
                        Text("\(viewModel.profile.stats.xp) XP")
                            .font(.caption.weight(.bold))
                            .foregroundStyle(.indigo)
                    }

                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            Capsule()
                                .fill(Color.white.opacity(0.56))

                            Capsule()
                                .fill(
                                    LinearGradient(
                                        colors: [.blue, .indigo], // ✅ removed pink
                                        startPoint: .leading,
                                        endPoint: .trailing
                                    )
                                )
                                .frame(width: geometry.size.width * viewModel.xpProgress)
                        }
                    }
                    .frame(height: 12)
                }
            }
        }
        .scaleEffect(animateHeader ? 1 : 0.98)
    }

    private var statsSection: some View {
        ProfileGlassCard {
            VStack(alignment: .leading, spacing: 16) {
                Text(viewModel.copy.stats)
                    .font(.headline)

                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                    StatTile(title: viewModel.copy.streak, value: "\(viewModel.profile.stats.streak)", icon: "🔥")
                    StatTile(title: viewModel.copy.roomsPlayed, value: "\(viewModel.profile.stats.roomsPlayed)", icon: "🎮")
                    StatTile(title: viewModel.copy.accuracy, value: "\(viewModel.profile.stats.accuracyRate)%", icon: "🧠")
                    StatTile(title: viewModel.copy.bluffSuccess, value: "\(viewModel.profile.stats.bluffSuccessRate)%", icon: "🎤")
                }
            }
        }
    }

    private var badgesSection: some View {
        ProfileGlassCard {
            VStack(alignment: .leading, spacing: 16) {
                Text(viewModel.copy.badges)
                    .font(.headline)

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 12) {
                        ForEach(viewModel.profile.badges) { badge in
                            BadgeChip(badge: badge)
                        }
                    }
                }
            }
        }
    }

    private var settingsSection: some View {
        ProfileGlassCard {
            VStack(alignment: .leading, spacing: 16) {
                Text(viewModel.copy.settings)
                    .font(.headline)

                Picker(viewModel.copy.languageTitle, selection: Binding(
                    get: { viewModel.profile.language },
                    set: { viewModel.updateLanguage($0) }
                )) {
                    ForEach(AppLanguage.allCases) { language in
                        Text(language.title).tag(language)
                    }
                }

                Toggle(viewModel.copy.notifications, isOn: Binding(
                    get: { viewModel.profile.notificationsEnabled },
                    set: { viewModel.updateNotifications($0) }
                ))

                Toggle(viewModel.copy.sound, isOn: Binding(
                    get: { viewModel.profile.soundEnabled },
                    set: { viewModel.updateSound($0) }
                ))

                Button(viewModel.copy.editProfile) {
                    syncDrafts()
                    viewModel.showsEditProfile = true
                }
                .buttonStyle(ProfileActionButtonStyle(tint: .purple))
            }
        }
    }

    private var editProfileSheet: some View {
        NavigationStack {
            Form {
                Section(viewModel.copy.nickname) {
                    TextField(viewModel.copy.nickname, text: $draftNickname)

                    if viewModel.profile.isGuestMode {
                        Button(viewModel.copy.keepGuestMode) {
                            viewModel.continueAsGuest(with: draftNickname)
                            viewModel.showsEditProfile = false
                        }
                    }
                }

                Section(viewModel.copy.avatar) {
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                        ForEach(ProfileAvatar.allCases) { avatar in
                            Button {
                                draftAvatar = avatar
                            } label: {
                                VStack(spacing: 8) {
                                    ProfileAvatarBadge(avatar: avatar, size: 54)
                                    Text(avatar.rawValue.capitalized)
                                        .font(.caption)
                                        .foregroundStyle(.primary)
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                                .background(
                                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                                        .fill(draftAvatar == avatar ? Color.indigo.opacity(0.12) : Color.clear)
                                )
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
            .navigationTitle(viewModel.copy.editProfile)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(viewModel.copy.close) {
                        viewModel.showsEditProfile = false
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(viewModel.copy.save) {
                        viewModel.saveProfile(nickname: draftNickname, avatar: draftAvatar)
                        viewModel.showsEditProfile = false
                    }
                }
            }
        }
    }

    private func syncDrafts() {
        draftNickname = viewModel.profile.nickname
        draftAvatar = viewModel.profile.avatar
    }
}
