import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_widget.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/feedback_prompt_state_store.dart';
import 'package:snickerdoodle/src/core/services/feedback_service.dart';
import 'package:snickerdoodle/src/features/feedback/presentation/user_feedback_screen.dart';

class MockFeedbackService extends Mock implements FeedbackService {}

class MockFeedbackPromptStateStore extends Mock
    implements FeedbackPromptStateStore {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

void main() {
  setUpAll(() {
    registerFallbackValue(SpeakerType.user);
  });

  final testFeedbackEntry = FeedbackEntry(
    id: 'test-id',
    userId: 'test-user-id',
    creationTime: DateTime.now(),
    conversation: [
      FeedbackConversationEntry(
        speaker: SpeakerType.user,
        text: 'This is a test feedback message.',
        timestamp: DateTime.now(),
      ),
      FeedbackConversationEntry(
        speaker: SpeakerType.admin,
        text: 'This is a test admin response.',
        timestamp: DateTime.now().add(const Duration(minutes: 5)),
      ),
    ],
    lastAdminViewTime: null,
    lastUserViewTime: null,
  );

  late MockFeedbackService mockFeedbackService;
  late MockFeedbackPromptStateStore mockPromptStore;
  late MockAnalyticsService mockAnalyticsService;

  setUp(() {
    mockFeedbackService = MockFeedbackService();
    mockPromptStore = MockFeedbackPromptStateStore();
    mockAnalyticsService = MockAnalyticsService();

    when(() => mockPromptStore.markViewed()).thenAnswer((_) async {});
    when(() => mockAnalyticsService.logFeedbackDialogShown()).thenReturn(null);
    when(
      () => mockFeedbackService.updateLastUserViewTime(any()),
    ).thenAnswer((_) async {});
    when(
      () => mockFeedbackService.addConversationMessage(any(), any(), any()),
    ).thenAnswer((_) async {});
  });

  testWidgets(
    'AppBarWidget should show feedback icon with unread feedback and hide it without',
    (tester) async {
      // This StateProvider will allow us to control the state of unreadFeedbackProvider
      final unreadFeedbackStateProvider =
          StateProvider<List<FeedbackEntry>>((ref) => [testFeedbackEntry]);

      final container = ProviderContainer(
        overrides: [
          // Make unreadFeedbackProvider listen to our local state provider
          unreadFeedbackProvider.overrideWith(
            (ref) => ref.watch(unreadFeedbackStateProvider),
          ),
          feedbackServiceProvider.overrideWithValue(mockFeedbackService),
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          feedbackPromptStateStoreProvider.overrideWithValue(mockPromptStore),
          userFeedbackProvider.overrideWith(
            (ref) => Stream.value([testFeedbackEntry]),
          ),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(appBar: AppBarWidget(title: 'Test')),
          ),
        ),
      );

      // At first, we have unread feedback, so the icon should be visible.
      await tester.pumpAndSettle();
      expect(
          find.byKey(const Key('feedback-notification-icon')), findsOneWidget);

      // Tapping the icon should navigate to the feedback screen.
      await tester
          .tap(find.byKey(const Key('feedback_notification_icon-open-button')));
      await tester.pumpAndSettle();
      expect(find.byType(UserFeedbackScreen), findsOneWidget);
      verify(() => mockFeedbackService.updateLastUserViewTime(testFeedbackEntry.id))
          .called(1);

      // After navigating back...
      await tester.pageBack();
      await tester.pumpAndSettle();

      // ...we update the state to have no unread feedback.
      container.read(unreadFeedbackStateProvider.notifier).state = [];
      await tester.pump();

      // The icon should now be hidden.
      expect(find.byKey(const Key('feedback-notification-icon')), findsNothing);
    },
  );
}