import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_widget.dart';
import 'package:snickerdoodle/src/common_widgets/feedback_dialog.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/core/services/feedback_service.dart';

class MockFeedbackService extends Mock implements FeedbackService {}

void main() {
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

  setUp(() {
    mockFeedbackService = MockFeedbackService();
    registerFallbackValue(testFeedbackEntry);
  });

  testWidgets('shows feedback icon when unread feedback exists and opens dialog on tap',
      (tester) async {
    when(() => mockFeedbackService.updateLastUserViewTime(any()))
        .thenAnswer((_) async {});

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          unreadFeedbackProvider.overrideWithValue([testFeedbackEntry]),
          feedbackServiceProvider.overrideWithValue(mockFeedbackService),
        ],
        child: const MaterialApp(
          home: Scaffold(appBar: AppBarWidget(title: 'Test')),
        ),
      ),
    );

    await tester.pumpAndSettle();
    expect(find.byKey(const Key('feedback-notification-icon')), findsOneWidget);

    await tester.tap(find.byKey(const Key('feedback-notification-icon')));
    await tester.pumpAndSettle();

    expect(find.byType(FeedbackDialog), findsOneWidget);

    verify(() => mockFeedbackService.updateLastUserViewTime(testFeedbackEntry.id))
        .called(1);
  });

  testWidgets('does not show feedback icon when there is no unread feedback',
      (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          unreadFeedbackProvider.overrideWithValue([]),
        ],
        child: const MaterialApp(
          home: Scaffold(appBar: AppBarWidget(title: 'Test')),
        ),
      ),
    );

    await tester.pumpAndSettle();
    expect(find.byKey(const Key('feedback-notification-icon')), findsNothing);
  });
}
