import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/app_version_provider.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/feedback_prompt_state_store.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/feedback/presentation/user_feedback_screen.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';
import 'package:snickerdoodle/src/features/settings/application/theme_settings_service.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';

class MockFeedbackRepository extends Mock implements FeedbackRepository {}

class MockFeedbackPromptStateStore extends Mock
    implements FeedbackPromptStateStore {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockSettingsService extends Mock implements SettingsService {}

class MockThemeSettingsService extends Mock implements ThemeSettingsService {}

class MockJokeViewerSettingsService extends Mock
    implements JokeViewerSettingsService {}

class MockNotificationService extends Mock implements NotificationService {}

class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

class MockFirebaseAuth extends Mock implements FirebaseAuth {}

class MockGoogleSignIn extends Mock implements GoogleSignIn {}

// Helper methods
AppUser get anonymousUser => AppUser.anonymous('anonymous_user_id');

void registerAnalyticsFallbackValues() {
  registerFallbackValue(JokeViewerMode.reveal);
  registerFallbackValue(Brightness.light);
  registerFallbackValue(RemoteParam.defaultJokeViewerReveal);
  registerFallbackValue(SpeakerType.user);
}

List<Override> getAllMockOverrides({AppUser? testUser}) {
  final mockAnalyticsService = MockAnalyticsService();
  final mockSettingsService = MockSettingsService();
  final mockThemeSettingsService = MockThemeSettingsService();
  final mockJokeViewerSettingsService = MockJokeViewerSettingsService();
  final mockFirebaseAuth = MockFirebaseAuth();
  final mockGoogleSignIn = MockGoogleSignIn();
  final mockDailyJokeSubscriptionService = MockDailyJokeSubscriptionService();

  // Setup default behaviors for mocks
  when(() => mockAnalyticsService.initialize()).thenAnswer((_) async {});
  when(
    () => mockAnalyticsService.setUserProperties(any()),
  ).thenAnswer((_) async {});
  when(() => mockSettingsService.getBool(any())).thenReturn(false);
  when(
    () => mockSettingsService.setBool(any(), any()),
  ).thenAnswer((_) async {});
  when(
    () => mockThemeSettingsService.getThemeMode(),
  ).thenAnswer((_) async => ThemeMode.system);
  when(
    () => mockJokeViewerSettingsService.getReveal(),
  ).thenAnswer((_) async => false);
  when(
    () => mockFirebaseAuth.authStateChanges(),
  ).thenAnswer((_) => Stream<User?>.value(null));
  when(
    () => mockDailyJokeSubscriptionService.ensureSubscriptionSync(
      unsubscribeOthers: any(named: 'unsubscribeOthers'),
    ),
  ).thenAnswer((_) async => true);

  return [
    analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
    settingsServiceProvider.overrideWithValue(mockSettingsService),
    firebaseAuthProvider.overrideWithValue(mockFirebaseAuth),
    googleSignInProvider.overrideWithValue(mockGoogleSignIn),
    currentUserProvider.overrideWith((ref) => testUser),
    authStateProvider.overrideWith((ref) => Stream.value(testUser)),
    appVersionProvider.overrideWith((ref) => Future.value('1.0.0')),
    themeSettingsServiceProvider.overrideWithValue(mockThemeSettingsService),
    themeModeProvider.overrideWith(
      (ref) => ThemeModeNotifier(mockThemeSettingsService),
    ),
    jokeViewerSettingsServiceProvider.overrideWithValue(
      mockJokeViewerSettingsService,
    ),
    jokeViewerRevealProvider.overrideWith(
      (ref) => JokeViewerRevealNotifier(mockJokeViewerSettingsService),
    ),
    subscriptionProvider.overrideWith(
      (ref) => SubscriptionNotifier(
        mockSettingsService,
        mockDailyJokeSubscriptionService,
        MockNotificationService(),
      ),
    ),
  ];
}

void main() {
  setUpAll(() {
    registerAnalyticsFallbackValues();
    registerFallbackValue(SpeakerType.user);
  });

  setUp(() {
    // No longer needed - using local mocks
  });

  ProviderScope wrapWidget(
    Widget child, {
    required MockFeedbackPromptStateStore mockPromptStore,
    required MockAnalyticsService mockAnalytics,
    List<Override> additionalOverrides = const [],
  }) {
    final overrides = getAllMockOverrides(testUser: anonymousUser)
      ..addAll([
        feedbackPromptStateStoreProvider.overrideWithValue(mockPromptStore),
        analyticsServiceProvider.overrideWithValue(mockAnalytics),
        userFeedbackProvider.overrideWith((ref) => Stream.value([])),
        ...additionalOverrides,
      ]);

    return ProviderScope(
      overrides: overrides,
      child: MaterialApp(
        theme: lightTheme,
        darkTheme: darkTheme,
        home: Scaffold(body: child),
      ),
    );
  }

  testWidgets('Shows Suggestions/Feedback button and opens screen', (
    tester,
  ) async {
    final mockPromptStore = MockFeedbackPromptStateStore();
    final mockAnalytics = MockAnalyticsService();

    when(() => mockPromptStore.markViewed()).thenAnswer((_) async {});
    when(() => mockAnalytics.logFeedbackDialogShown()).thenReturn(null);

    await tester.pumpWidget(
      wrapWidget(
        const UserSettingsScreen(),
        mockPromptStore: mockPromptStore,
        mockAnalytics: mockAnalytics,
      ),
    );
    await tester.pumpAndSettle();

    final btn = find.byKey(const Key('settings-feedback-button'));
    expect(btn, findsOneWidget);
    await tester.ensureVisible(btn);
    await tester.pump();
    await tester.tap(btn);
    await tester.pumpAndSettle();

    expect(find.byType(UserFeedbackScreen), findsOneWidget);
    expect(find.text('Help Us Perfect the Recipe!'), findsOneWidget);
  });

  testWidgets('Submitting feedback calls service and logs analytics', (
    tester,
  ) async {
    final mockRepository = MockFeedbackRepository();
    final mockPromptStore = MockFeedbackPromptStateStore();
    final mockAnalytics = MockAnalyticsService();

    when(() => mockPromptStore.markViewed()).thenAnswer((_) async {});
    when(() => mockAnalytics.logFeedbackDialogShown()).thenReturn(null);
    when(() => mockAnalytics.logFeedbackSubmitted()).thenReturn(null);
    when(
      () => mockRepository.submitFeedback(any(), any()),
    ).thenAnswer((_) async {});

    final overrides = <Override>[
      feedbackRepositoryProvider.overrideWithValue(mockRepository),
    ];

    await tester.pumpWidget(
      wrapWidget(
        const UserSettingsScreen(),
        mockPromptStore: mockPromptStore,
        mockAnalytics: mockAnalytics,
        additionalOverrides: overrides,
      ),
    );
    await tester.pumpAndSettle();

    final btn = find.byKey(const Key('settings-feedback-button'));
    await tester.ensureVisible(btn);
    await tester.tap(btn);
    await tester.pumpAndSettle();

    const feedback = 'Love the jokes! Maybe add categories.';
    await tester.enterText(
      find.byKey(const Key('feedback_screen-initial-message-field')),
      feedback,
    );
    await tester.tap(find.byKey(const Key('feedback_screen-submit-button')));
    await tester.pumpAndSettle();

    verify(
      () => mockRepository.submitFeedback(feedback, anonymousUser.id),
    ).called(1);
    verify(() => mockAnalytics.logFeedbackSubmitted()).called(1);
    expect(find.text('Thanks for your feedback!'), findsOneWidget);
  });
}
