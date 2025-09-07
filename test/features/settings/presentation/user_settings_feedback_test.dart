import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';

import '../../../test_helpers/test_helpers.dart';

class MockFeedbackRepository extends Mock implements FeedbackRepository {}

void main() {
  setUpAll(() {
    registerAnalyticsFallbackValues();
  });

  setUp(() {
    TestHelpers.resetAllMocks();
  });

  Widget wrapWidget(Widget child, {List<Override> overrides = const []}) {
    return ProviderScope(
      overrides: [
        ...TestHelpers.getAllMockOverrides(testUser: TestHelpers.anonymousUser),
        ...overrides,
      ],
      child: MaterialApp(
        theme: lightTheme,
        darkTheme: darkTheme,
        home: Scaffold(body: child),
      ),
    );
  }

  testWidgets('Shows Suggestions/Feedback button and opens dialog', (
    tester,
  ) async {
    await tester.pumpWidget(wrapWidget(const UserSettingsScreen()));
    await tester.pumpAndSettle();

    final btn = find.byKey(const Key('settings-feedback-button'));
    expect(btn, findsOneWidget);
    await tester.tap(btn);
    await tester.pumpAndSettle();

    expect(find.text('Help Us Perfect the Recipe! 🍪'), findsOneWidget);
    expect(find.text('Submit'), findsOneWidget);
    expect(find.text('Cancel'), findsOneWidget);
  });

  testWidgets('Submitting feedback calls repository and logs analytics', (
    tester,
  ) async {
    // Arrange repository mock
    final mockRepository = MockFeedbackRepository();
    when(
      () => mockRepository.submitFeedback(any(), any()),
    ).thenAnswer((_) async {});

    final overrides = <Override>[
      feedbackRepositoryProvider.overrideWithValue(mockRepository),
    ];

    await tester.pumpWidget(
      wrapWidget(const UserSettingsScreen(), overrides: overrides),
    );
    await tester.pumpAndSettle();

    // Open dialog
    await tester.tap(find.byKey(const Key('settings-feedback-button')));
    await tester.pumpAndSettle();

    // Enter text
    const feedback = 'Love the jokes! Maybe add categories.';
    await tester.enterText(find.byType(TextField), feedback);
    await tester.pump();

    // Submit
    await tester.tap(find.text('Submit'));
    await tester.pumpAndSettle();

    // Assert repository call with any user ID (could be anonymous user from test helpers)
    verify(() => mockRepository.submitFeedback(feedback, any())).called(1);

    // Analytics is handled by AnalyticsMocks; ensure method was called
    verify(
      () => AnalyticsMocks.mockAnalyticsService.logFeedbackSubmitted(),
    ).called(1);

    // Dialog closed and thanks snackbar shown
    expect(find.text('Help Us Perfect the Recipe! 🍪'), findsNothing);
    expect(find.text('Thanks for your feedback!'), findsOneWidget);
  });
}
