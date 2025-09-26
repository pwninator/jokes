import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/core/services/feedback_service.dart';
import 'package:snickerdoodle/src/features/feedback/presentation/feedback_conversation_screen.dart';

import '../../../test_helpers/firebase_mocks.dart';

class _MockFeedbackRepository extends Mock implements FeedbackRepository {}

class _MockFeedbackService extends Mock implements FeedbackService {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late _MockFeedbackRepository repo;
  late _MockFeedbackService service;

  setUp(() {
    repo = _MockFeedbackRepository();
    service = _MockFeedbackService();
  });

  setUpAll(() {
    registerFallbackValue(SpeakerType.user);
  });

  FeedbackEntry createTestFeedback({
    String id = '1',
    String userId = 'user1',
    List<FeedbackConversationEntry>? conversation,
    DateTime? lastAdminViewTime,
  }) {
    final now = DateTime.now();
    return FeedbackEntry(
      id: id,
      creationTime: now,
      userId: userId,
      lastAdminViewTime: lastAdminViewTime,
      lastUserViewTime: null,
      conversation:
          conversation ??
          [
            FeedbackConversationEntry(
              speaker: SpeakerType.user,
              text: 'Hello from user',
              timestamp: now,
            ),
          ],
    );
  }

  Widget createWidget(
    String feedbackId, {
    FeedbackEntry? feedbackEntry,
    Stream<List<FeedbackEntry>>? streamOverride,
  }) {
    final entry = feedbackEntry ?? createTestFeedback(id: feedbackId);

    when(
      () => repo.watchAllFeedback(),
    ).thenAnswer((_) => streamOverride ?? Stream.value([entry]));
    when(() => repo.updateLastAdminViewTime(any())).thenAnswer((_) async {});
    when(
      () => service.addConversationMessage(any(), any(), any()),
    ).thenAnswer((_) async {});

    return ProviderScope(
      overrides: [
        ...FirebaseMocks.getFirebaseProviderOverrides(),
        feedbackRepositoryProvider.overrideWithValue(repo),
        feedbackServiceProvider.overrideWithValue(service),
      ],
      child: const MaterialApp(
        home: FeedbackConversationScreen.admin(feedbackId: '1'),
      ),
    );
  }

  group('FeedbackConversationScreen.admin', () {
    testWidgets('displays conversation and updates last admin view time', (
      tester,
    ) async {
      final now = DateTime.now();
      final conversation = [
        FeedbackConversationEntry(
          speaker: SpeakerType.user,
          text: 'Hello',
          timestamp: now,
        ),
        FeedbackConversationEntry(
          speaker: SpeakerType.admin,
          text: 'Hi there',
          timestamp: now.add(const Duration(minutes: 1)),
        ),
      ];

      final feedbackEntry = createTestFeedback(
        id: '1',
        conversation: conversation,
      );

      await tester.pumpWidget(createWidget('1', feedbackEntry: feedbackEntry));
      await tester.pumpAndSettle();

      verify(() => repo.updateLastAdminViewTime('1')).called(1);
      expect(find.text('Hello'), findsOneWidget);
      expect(find.text('Hi there'), findsOneWidget);
    });

    testWidgets('sending a message calls service with correct parameters', (
      tester,
    ) async {
      final feedbackEntry = createTestFeedback(id: '1');

      await tester.pumpWidget(createWidget('1', feedbackEntry: feedbackEntry));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('feedback_conversation-message-field-admin')),
        'Test reply',
      );
      await tester.tap(
        find.byKey(const Key('feedback_conversation-send-button-admin')),
      );
      await tester.pumpAndSettle();

      verify(
        () => service.addConversationMessage(
          '1',
          'Test reply',
          SpeakerType.admin,
        ),
      ).called(1);
    });

    testWidgets('handles empty conversation', (tester) async {
      final feedbackEntry = createTestFeedback(id: '1', conversation: []);

      await tester.pumpWidget(createWidget('1', feedbackEntry: feedbackEntry));
      await tester.pumpAndSettle();

      verify(() => repo.updateLastAdminViewTime('1')).called(1);
      expect(
        find.byKey(const Key('feedback_conversation-message-field-admin')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('feedback_conversation-send-button-admin')),
        findsOneWidget,
      );
    });

    testWidgets('handles repository error gracefully', (tester) async {
      await tester.pumpWidget(
        createWidget(
          '1',
          streamOverride: Stream<List<FeedbackEntry>>.error('Network error'),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Error: Network error'), findsOneWidget);
    });
  });
}
