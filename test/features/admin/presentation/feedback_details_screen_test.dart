import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/core/services/feedback_service.dart';
import 'package:snickerdoodle/src/features/feedback/presentation/feedback_conversation_screen.dart';

import '../../../test_helpers/firebase_mocks.dart';

class _MockFeedbackService extends Mock implements FeedbackService {}

class _MockFeedbackRepository extends Mock implements FeedbackRepository {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() {
    registerFallbackValue(SpeakerType.user);
  });

  ProviderContainer createContainer(
    FeedbackEntry entry,
    FeedbackService service,
    FeedbackRepository repository,
  ) {
    return ProviderContainer(
      overrides: [
        ...FirebaseMocks.getFirebaseProviderOverrides(),
        feedbackRepositoryProvider.overrideWithValue(repository),
        feedbackServiceProvider.overrideWithValue(service),
        feedbackProvider.overrideWith((ref, id) {
          if (id == entry.id) {
            return Stream.value(entry);
          }
          return const Stream.empty();
        }),
      ],
    );
  }

  group('FeedbackConversationScreen.admin', () {
    late _MockFeedbackService mockService;
    late _MockFeedbackRepository mockRepository;
    late FeedbackEntry feedback;

    setUp(() {
      mockService = _MockFeedbackService();
      mockRepository = _MockFeedbackRepository();
      final timestamp = DateTime(2025, 1, 2, 3, 4, 5);
      feedback = FeedbackEntry(
        id: 'test_feedback_id',
        creationTime: timestamp,
        conversation: [
          FeedbackConversationEntry(
            speaker: SpeakerType.user,
            text: 'Love the jokes!',
            timestamp: timestamp,
          ),
          FeedbackConversationEntry(
            speaker: SpeakerType.admin,
            text: 'Thank you for the feedback!',
            timestamp: timestamp.add(const Duration(minutes: 5)),
          ),
        ],
        userId: 'test_user',
        lastAdminViewTime: null,
        lastUserViewTime: null,
      );

      when(
        () => mockService.addConversationMessage(any(), any(), any()),
      ).thenAnswer((_) async {});
      when(
        () => mockRepository.updateLastAdminViewTime(any()),
      ).thenAnswer((_) async {});
    });

    testWidgets('displays conversation and input controls', (tester) async {
      final container = createContainer(feedback, mockService, mockRepository);
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: FeedbackConversationScreen.admin(
              feedbackId: 'test_feedback_id',
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Feedback from test_user'), findsOneWidget);
      expect(
        find.byKey(const Key('feedback_conversation-message-field-admin')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('feedback_conversation-send-button-admin')),
        findsOneWidget,
      );
    });

    testWidgets('sends message when send button is tapped', (tester) async {
      final container = createContainer(feedback, mockService, mockRepository);
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: FeedbackConversationScreen.admin(
              feedbackId: 'test_feedback_id',
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('feedback_conversation-message-field-admin')),
        'Admin response',
      );

      await tester.tap(
        find.byKey(const Key('feedback_conversation-send-button-admin')),
      );
      await tester.pumpAndSettle();

      verify(
        () => mockService.addConversationMessage(
          'test_feedback_id',
          'Admin response',
          SpeakerType.admin,
        ),
      ).called(1);

      final textField = tester.widget<TextField>(
        find.byKey(const Key('feedback_conversation-message-field-admin')),
      );
      expect(textField.controller?.text, isEmpty);
    });

    testWidgets('does not send empty message', (tester) async {
      final container = createContainer(feedback, mockService, mockRepository);
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: FeedbackConversationScreen.admin(
              feedbackId: 'test_feedback_id',
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      await tester.tap(
        find.byKey(const Key('feedback_conversation-send-button-admin')),
      );
      await tester.pumpAndSettle();

      verifyNever(
        () => mockService.addConversationMessage(any(), any(), any()),
      );
    });
  });
}
