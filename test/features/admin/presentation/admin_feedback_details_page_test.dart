import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/core/services/feedback_service.dart';
import 'package:snickerdoodle/src/features/feedback/presentation/feedback_conversation_screen.dart';

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
    FeedbackConversationRole role = FeedbackConversationRole.admin,
  }) {
    final entry = feedbackEntry ?? createTestFeedback(id: feedbackId);

    when(
      () => repo.watchAllFeedback(),
    ).thenAnswer((_) => streamOverride ?? Stream.value([entry]));
    when(() => repo.updateLastAdminViewTime(any())).thenAnswer((_) async {});
    when(
      () => service.addConversationMessage(any(), any(), any()),
    ).thenAnswer((_) async {});
    when(() => service.updateLastUserViewTime(any())).thenAnswer((_) async {});

    final screen = role == FeedbackConversationRole.admin
        ? const FeedbackConversationScreen.admin(feedbackId: '1')
        : const FeedbackConversationScreen.user(feedbackId: '1');

    return ProviderScope(
      overrides: [
        feedbackRepositoryProvider.overrideWithValue(repo),
        feedbackServiceProvider.overrideWithValue(service),
      ],
      child: MaterialApp(home: screen),
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

    testWidgets('shows loading state initially', (tester) async {
      await tester.pumpWidget(
        createWidget('1', streamOverride: Stream<List<FeedbackEntry>>.empty()),
      );
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('shows feedback not found when entry is null', (tester) async {
      await tester.pumpWidget(
        createWidget('1', streamOverride: Stream.value([])),
      );
      await tester.pumpAndSettle();

      expect(find.text('Feedback not found.'), findsOneWidget);
    });

    testWidgets('handles message send error gracefully', (tester) async {
      when(
        () => service.addConversationMessage(any(), any(), any()),
      ).thenThrow(Exception('Send failed'));

      await tester.pumpWidget(createWidget('1'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('feedback_conversation-message-field-admin')),
        'Test message',
      );
      await tester.tap(
        find.byKey(const Key('feedback_conversation-send-button-admin')),
      );
      await tester.pumpAndSettle();

      // Verify the service was called (error handling is internal)
      verify(
        () => service.addConversationMessage(
          '1',
          'Test message',
          SpeakerType.admin,
        ),
      ).called(1);
    });

    testWidgets('prevents sending empty messages', (tester) async {
      await tester.pumpWidget(createWidget('1'));
      await tester.pumpAndSettle();

      await tester.tap(
        find.byKey(const Key('feedback_conversation-send-button-admin')),
      );
      await tester.pumpAndSettle();

      verifyNever(() => service.addConversationMessage(any(), any(), any()));
    });

    testWidgets('handles async message sending', (tester) async {
      final completer = Completer<void>();
      when(
        () => service.addConversationMessage(any(), any(), any()),
      ).thenAnswer((_) => completer.future);

      await tester.pumpWidget(createWidget('1'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('feedback_conversation-message-field-admin')),
        'Test message',
      );
      await tester.tap(
        find.byKey(const Key('feedback_conversation-send-button-admin')),
      );
      await tester.pump();

      // Verify the service was called
      verify(
        () => service.addConversationMessage(
          '1',
          'Test message',
          SpeakerType.admin,
        ),
      ).called(1);

      // Complete the send operation
      completer.complete();
      await tester.pumpAndSettle();
    });
  });

  group('FeedbackConversationScreen.user', () {
    testWidgets('displays conversation without updating admin view time', (
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

      await tester.pumpWidget(
        createWidget(
          '1',
          feedbackEntry: feedbackEntry,
          role: FeedbackConversationRole.user,
        ),
      );
      await tester.pumpAndSettle();

      // Should not call updateLastAdminViewTime for user role
      verifyNever(() => repo.updateLastAdminViewTime('1'));
      expect(find.text('Hello'), findsOneWidget);
      expect(find.text('Hi there'), findsOneWidget);
    });

    testWidgets(
      'marks conversation as viewed for user when admin message exists',
      (tester) async {
        final now = DateTime.now();
        final conversation = [
          FeedbackConversationEntry(
            speaker: SpeakerType.admin,
            text: 'Admin response',
            timestamp: now,
          ),
        ];

        final feedbackEntry = createTestFeedback(
          id: '1',
          conversation: conversation,
          lastAdminViewTime: null, // User hasn't viewed yet
        );

        await tester.pumpWidget(
          createWidget(
            '1',
            feedbackEntry: feedbackEntry,
            role: FeedbackConversationRole.user,
          ),
        );
        await tester.pumpAndSettle();

        verify(() => service.updateLastUserViewTime('1')).called(1);
      },
    );

    testWidgets('sending a message calls service with user speaker type', (
      tester,
    ) async {
      final feedbackEntry = createTestFeedback(id: '1');

      await tester.pumpWidget(
        createWidget(
          '1',
          feedbackEntry: feedbackEntry,
          role: FeedbackConversationRole.user,
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('feedback_conversation-message-field-user')),
        'User reply',
      );
      await tester.tap(
        find.byKey(const Key('feedback_conversation-send-button-user')),
      );
      await tester.pumpAndSettle();

      verify(
        () =>
            service.addConversationMessage('1', 'User reply', SpeakerType.user),
      ).called(1);
    });

    testWidgets('does not mark conversation viewed when no admin messages', (
      tester,
    ) async {
      final now = DateTime.now();
      final conversation = [
        FeedbackConversationEntry(
          speaker: SpeakerType.user,
          text: 'User message',
          timestamp: now,
        ),
      ];

      final feedbackEntry = createTestFeedback(
        id: '1',
        conversation: conversation,
      );

      await tester.pumpWidget(
        createWidget(
          '1',
          feedbackEntry: feedbackEntry,
          role: FeedbackConversationRole.user,
        ),
      );
      await tester.pumpAndSettle();

      verifyNever(() => service.updateLastUserViewTime('1'));
    });
  });
}
