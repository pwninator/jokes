import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/features/admin/presentation/admin_feedback/admin_feedback_details_page.dart';

import '../../../test_helpers/firebase_mocks.dart';

class _MockFeedbackRepository extends Mock implements FeedbackRepository {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late _MockFeedbackRepository repo;

  setUp(() {
    repo = _MockFeedbackRepository();
  });

  setUpAll(() {
    registerFallbackValue(SpeakerType.user);
  });

  FeedbackEntry _createTestFeedback({
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

  Widget _createWidget(String feedbackId, {FeedbackEntry? feedbackEntry}) {
    final entry = feedbackEntry ?? _createTestFeedback(id: feedbackId);

    when(
      () => repo.watchAllFeedback(),
    ).thenAnswer((_) => Stream.value([entry]));
    when(() => repo.updateLastAdminViewTime(any())).thenAnswer((_) async {});
    when(
      () => repo.addConversationMessage(any(), any(), any()),
    ).thenAnswer((_) async {});

    return ProviderScope(
      overrides: [
        feedbackRepositoryProvider.overrideWithValue(repo),
        ...FirebaseMocks.getFirebaseProviderOverrides(),
      ],
      child: MaterialApp(
        home: AdminFeedbackDetailsPage(feedbackId: feedbackId),
      ),
    );
  }

  group('AdminFeedbackDetailsPage', () {
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

      final feedbackEntry = _createTestFeedback(
        id: '1',
        conversation: conversation,
      );

      await tester.pumpWidget(_createWidget('1', feedbackEntry: feedbackEntry));
      await tester.pumpAndSettle();

      // Verify last admin view time is updated
      verify(() => repo.updateLastAdminViewTime('1')).called(1);

      // Verify conversation is displayed
      expect(find.text('Hello'), findsOneWidget);
      expect(find.text('Hi there'), findsOneWidget);
    });

    testWidgets('sending a message calls repository with correct parameters', (
      tester,
    ) async {
      final feedbackEntry = _createTestFeedback(id: '1');

      await tester.pumpWidget(_createWidget('1', feedbackEntry: feedbackEntry));
      await tester.pumpAndSettle();

      // Enter and send a message
      await tester.enterText(find.byType(TextField), 'Test reply');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      // Verify repository method was called with correct parameters
      verify(
        () => repo.addConversationMessage('1', 'Test reply', SpeakerType.admin),
      ).called(1);
    });

    testWidgets('handles empty conversation', (tester) async {
      final feedbackEntry = _createTestFeedback(id: '1', conversation: []);

      await tester.pumpWidget(_createWidget('1', feedbackEntry: feedbackEntry));
      await tester.pumpAndSettle();

      // Should still update last admin view time even with empty conversation
      verify(() => repo.updateLastAdminViewTime('1')).called(1);

      // Should still show send interface
      expect(find.byType(TextField), findsOneWidget);
      expect(find.byIcon(Icons.send), findsOneWidget);
    });

    testWidgets('handles repository error gracefully', (tester) async {
      // Mock repository to throw error
      when(
        () => repo.watchAllFeedback(),
      ).thenAnswer((_) => Stream.error('Network error'));

      await tester.pumpWidget(_createWidget('1'));
      await tester.pumpAndSettle();

      // Should handle error without crashing
      expect(find.byType(AdminFeedbackDetailsPage), findsOneWidget);
    });
  });
}
