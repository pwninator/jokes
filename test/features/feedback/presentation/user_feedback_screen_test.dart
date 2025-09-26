import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/feedback_prompt_state_store.dart';
import 'package:snickerdoodle/src/core/services/feedback_service.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/feedback/presentation/user_feedback_screen.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';

import '../../../test_helpers/test_helpers.dart';

class MockFeedbackService extends Mock implements FeedbackService {}

class MockFeedbackPromptStateStore extends Mock
    implements FeedbackPromptStateStore {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

void main() {
  setUpAll(() {
    registerAnalyticsFallbackValues();
    registerFallbackValue(SpeakerType.user);
    registerFallbackValue(JokeViewerMode.reveal);
    registerFallbackValue(AppTab.dailyJokes);
  });

  setUp(() {
    TestHelpers.resetAllMocks();
  });

  group('UserFeedbackScreen', () {
    late MockFeedbackService mockFeedbackService;
    late MockFeedbackPromptStateStore mockPromptStore;
    late MockAnalyticsService mockAnalyticsService;

    ProviderScope buildWidget({
      required Stream<List<FeedbackEntry>> feedbackStream,
      List<Override> additionalOverrides = const [],
    }) {
      final overrides = TestHelpers.getAllMockOverrides(
        testUser: TestHelpers.anonymousUser,
        additionalOverrides: [
          feedbackServiceProvider.overrideWithValue(mockFeedbackService),
          feedbackPromptStateStoreProvider.overrideWithValue(mockPromptStore),
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          currentUserProvider.overrideWithValue(TestHelpers.anonymousUser),
          userFeedbackProvider.overrideWith((ref) => feedbackStream),
          ...additionalOverrides,
        ],
      );

      return ProviderScope(
        overrides: overrides,
        child: const MaterialApp(home: UserFeedbackScreen()),
      );
    }

    setUp(() {
      mockFeedbackService = MockFeedbackService();
      mockPromptStore = MockFeedbackPromptStateStore();
      mockAnalyticsService = MockAnalyticsService();

      when(() => mockPromptStore.markViewed()).thenAnswer((_) async {});
      when(
        () => mockAnalyticsService.logFeedbackDialogShown(),
      ).thenReturn(null);
      when(() => mockAnalyticsService.logFeedbackSubmitted()).thenReturn(null);
      when(
        () => mockAnalyticsService.logErrorFeedbackSubmit(
          errorMessage: any(named: 'errorMessage'),
        ),
      ).thenReturn(null);
      when(
        () => mockFeedbackService.updateLastUserViewTime(any()),
      ).thenAnswer((_) async {});
      when(
        () => mockFeedbackService.addConversationMessage(any(), any(), any()),
      ).thenAnswer((_) async {});
      when(
        () => mockFeedbackService.submitFeedback(any(), any()),
      ).thenAnswer((_) async {});
    });

    testWidgets('marks prompt viewed and shows initial form', (tester) async {
      final widget = buildWidget(feedbackStream: Stream.value([]));

      await tester.pumpWidget(widget);
      await tester.pumpAndSettle();

      verify(() => mockPromptStore.markViewed()).called(1);
      expect(
        find.byKey(const Key('feedback_screen-initial-message-field')),
        findsOneWidget,
      );
    });

    testWidgets('submitting initial feedback calls service', (tester) async {
      const message = 'Love the jokes! Keep it up!';
      final widget = buildWidget(feedbackStream: Stream.value([]));

      await tester.pumpWidget(widget);
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('feedback_screen-initial-message-field')),
        message,
      );
      await tester.tap(find.byKey(const Key('feedback_screen-submit-button')));
      await tester.pumpAndSettle();

      verify(
        () => mockFeedbackService.submitFeedback(
          message,
          TestHelpers.anonymousUser,
        ),
      ).called(1);
      expect(find.text('Thanks for your feedback!'), findsOneWidget);
    });

    testWidgets('conversation view sends follow-up messages', (tester) async {
      final initialTime = DateTime.now();
      final feedbackEntry = FeedbackEntry(
        id: 'user-123',
        userId: 'user-123',
        creationTime: initialTime,
        conversation: [
          FeedbackConversationEntry(
            speaker: SpeakerType.user,
            text: 'Hello from user',
            timestamp: initialTime,
          ),
          FeedbackConversationEntry(
            speaker: SpeakerType.admin,
            text: 'Admin reply',
            timestamp: initialTime.add(const Duration(minutes: 1)),
          ),
        ],
        lastAdminViewTime: null,
        lastUserViewTime: null,
      );

      final widget = buildWidget(feedbackStream: Stream.value([feedbackEntry]));

      await tester.pumpWidget(widget);
      await tester.pumpAndSettle();

      verify(
        () => mockFeedbackService.updateLastUserViewTime('user-123'),
      ).called(1);

      await tester.enterText(
        find.byKey(const Key('feedback_screen-message-field')),
        'New message',
      );
      await tester.tap(find.byKey(const Key('feedback_screen-send-button')));
      await tester.pumpAndSettle();

      verify(
        () => mockFeedbackService.addConversationMessage(
          'user-123',
          'New message',
          SpeakerType.user,
        ),
      ).called(1);
    });
  });
}
