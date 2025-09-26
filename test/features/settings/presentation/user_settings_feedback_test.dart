import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/core/services/feedback_prompt_state_store.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/feedback/presentation/user_feedback_screen.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';

import '../../../test_helpers/test_helpers.dart';

class MockFeedbackRepository extends Mock implements FeedbackRepository {}

class MockFeedbackPromptStateStore extends Mock
    implements FeedbackPromptStateStore {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

void main() {
  setUpAll(() {
    registerAnalyticsFallbackValues();
    registerFallbackValue(SpeakerType.user);
  });

  setUp(() {
    TestHelpers.resetAllMocks();
  });

  ProviderScope wrapWidget(
    Widget child, {
    required MockFeedbackPromptStateStore mockPromptStore,
    required MockAnalyticsService mockAnalytics,
    List<Override> additionalOverrides = const [],
  }) {
    final overrides = TestHelpers.getAllMockOverrides(
      testUser: TestHelpers.anonymousUser,
      additionalOverrides: [
        feedbackPromptStateStoreProvider.overrideWithValue(mockPromptStore),
        analyticsServiceProvider.overrideWithValue(mockAnalytics),
        userFeedbackProvider.overrideWith((ref) => Stream.value([])),
        ...additionalOverrides,
      ],
    );

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
      () =>
          mockRepository.submitFeedback(feedback, TestHelpers.anonymousUser.id),
    ).called(1);
    verify(() => mockAnalytics.logFeedbackSubmitted()).called(1);
    expect(find.text('Thanks for your feedback!'), findsOneWidget);
  });
}
