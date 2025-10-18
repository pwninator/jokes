import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/core/services/feedback_service.dart';
import 'package:snickerdoodle/src/features/feedback/presentation/feedback_conversation_screen.dart';

class MockFeedbackService extends Mock implements FeedbackService {}

class MockFeedbackRepository extends Mock implements FeedbackRepository {}

void main() {
  setUpAll(() {
    registerFallbackValue(SpeakerType.user);
  });

  late MockFeedbackService mockService;
  late MockFeedbackRepository mockRepository;

  setUp(() {
    // Create fresh mocks per test
    mockService = MockFeedbackService();
    mockRepository = MockFeedbackRepository();

    // Stub default behavior
    when(
      () => mockService.addConversationMessage(any(), any(), any()),
    ).thenAnswer((_) async {});
    when(
      () => mockService.updateLastUserViewTime(any()),
    ).thenAnswer((_) async {});
    when(
      () => mockRepository.updateLastAdminViewTime(any()),
    ).thenAnswer((_) async {});
  });

  group('FeedbackConversationScreen.admin', () {
    testWidgets('displays loading state initially', (tester) async {
      // Arrange: Mock empty stream to trigger loading state
      when(
        () => mockRepository.watchAllFeedback(),
      ).thenAnswer((_) => Stream.value([]));

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            feedbackRepositoryProvider.overrideWithValue(mockRepository),
            feedbackServiceProvider.overrideWithValue(mockService),
            feedbackProvider.overrideWith((ref, id) => Stream.value(null)),
          ],
          child: const MaterialApp(
            home: FeedbackConversationScreen.admin(
              feedbackId: 'test_feedback_id',
            ),
          ),
        ),
      );

      // Act & Assert: Should show loading indicator
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('displays error state when feedback provider errors', (
      tester,
    ) async {
      // Arrange: Mock error stream
      when(
        () => mockRepository.watchAllFeedback(),
      ).thenAnswer((_) => Stream.value([]));

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            feedbackRepositoryProvider.overrideWithValue(mockRepository),
            feedbackServiceProvider.overrideWithValue(mockService),
            feedbackProvider.overrideWith(
              (ref, id) => Stream.error(Exception('Test error')),
            ),
          ],
          child: const MaterialApp(
            home: FeedbackConversationScreen.admin(
              feedbackId: 'test_feedback_id',
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Assert: Should show error message
      expect(find.text('Error: Test error'), findsOneWidget);
    });

    testWidgets('displays not found message when feedback is null', (
      tester,
    ) async {
      // Arrange: Mock null feedback
      when(
        () => mockRepository.watchAllFeedback(),
      ).thenAnswer((_) => Stream.value([]));

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            feedbackRepositoryProvider.overrideWithValue(mockRepository),
            feedbackServiceProvider.overrideWithValue(mockService),
            feedbackProvider.overrideWith((ref, id) => Stream.value(null)),
          ],
          child: const MaterialApp(
            home: FeedbackConversationScreen.admin(
              feedbackId: 'test_feedback_id',
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Assert: Should show not found message
      expect(find.text('Feedback not found.'), findsOneWidget);
    });

    testWidgets(
      'displays conversation and input controls when feedback exists',
      (tester) async {
        // Arrange: Create test feedback
        final timestamp = DateTime(2025, 1, 2, 3, 4, 5);
        final feedback = FeedbackEntry(
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
          () => mockRepository.watchAllFeedback(),
        ).thenAnswer((_) => Stream.value([]));

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              feedbackRepositoryProvider.overrideWithValue(mockRepository),
              feedbackServiceProvider.overrideWithValue(mockService),
              feedbackProvider.overrideWith((ref, id) {
                if (id == 'test_feedback_id') {
                  return Stream.value(feedback);
                }
                return Stream.value(null);
              }),
            ],
            child: const MaterialApp(
              home: FeedbackConversationScreen.admin(
                feedbackId: 'test_feedback_id',
              ),
            ),
          ),
        );

        await tester.pumpAndSettle();

        // Assert: Should display feedback title and input controls
        expect(find.text('Feedback from test_user'), findsOneWidget);
        expect(
          find.byKey(const Key('feedback_conversation-message-field-admin')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('feedback_conversation-send-button-admin')),
          findsOneWidget,
        );

        // Verify admin view time is updated on init
        verify(
          () => mockRepository.updateLastAdminViewTime('test_feedback_id'),
        ).called(1);
      },
    );

    testWidgets('sends message when send button is tapped', (tester) async {
      // Arrange: Create test feedback
      final timestamp = DateTime(2025, 1, 2, 3, 4, 5);
      final feedback = FeedbackEntry(
        id: 'test_feedback_id',
        creationTime: timestamp,
        conversation: [
          FeedbackConversationEntry(
            speaker: SpeakerType.user,
            text: 'Love the jokes!',
            timestamp: timestamp,
          ),
        ],
        userId: 'test_user',
        lastAdminViewTime: null,
        lastUserViewTime: null,
      );

      when(
        () => mockRepository.watchAllFeedback(),
      ).thenAnswer((_) => Stream.value([]));

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            feedbackRepositoryProvider.overrideWithValue(mockRepository),
            feedbackServiceProvider.overrideWithValue(mockService),
            feedbackProvider.overrideWith((ref, id) {
              if (id == 'test_feedback_id') {
                return Stream.value(feedback);
              }
              return Stream.value(null);
            }),
          ],
          child: const MaterialApp(
            home: FeedbackConversationScreen.admin(
              feedbackId: 'test_feedback_id',
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Act: Enter text and tap send button
      await tester.enterText(
        find.byKey(const Key('feedback_conversation-message-field-admin')),
        'Admin response',
      );

      await tester.tap(
        find.byKey(const Key('feedback_conversation-send-button-admin')),
      );
      await tester.pumpAndSettle();

      // Assert: Should call service with correct parameters and clear text field
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

    testWidgets('does not send empty message when send button is tapped', (
      tester,
    ) async {
      // Arrange: Create test feedback
      final timestamp = DateTime(2025, 1, 2, 3, 4, 5);
      final feedback = FeedbackEntry(
        id: 'test_feedback_id',
        creationTime: timestamp,
        conversation: [
          FeedbackConversationEntry(
            speaker: SpeakerType.user,
            text: 'Love the jokes!',
            timestamp: timestamp,
          ),
        ],
        userId: 'test_user',
        lastAdminViewTime: null,
        lastUserViewTime: null,
      );

      when(
        () => mockRepository.watchAllFeedback(),
      ).thenAnswer((_) => Stream.value([]));

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            feedbackRepositoryProvider.overrideWithValue(mockRepository),
            feedbackServiceProvider.overrideWithValue(mockService),
            feedbackProvider.overrideWith((ref, id) {
              if (id == 'test_feedback_id') {
                return Stream.value(feedback);
              }
              return Stream.value(null);
            }),
          ],
          child: const MaterialApp(
            home: FeedbackConversationScreen.admin(
              feedbackId: 'test_feedback_id',
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Act: Tap send button without entering text
      await tester.tap(
        find.byKey(const Key('feedback_conversation-send-button-admin')),
      );
      await tester.pumpAndSettle();

      // Assert: Should not call service
      verifyNever(
        () => mockService.addConversationMessage(any(), any(), any()),
      );
    });

    testWidgets('handles send message error gracefully', (tester) async {
      // Arrange: Create test feedback and mock error
      final timestamp = DateTime(2025, 1, 2, 3, 4, 5);
      final feedback = FeedbackEntry(
        id: 'test_feedback_id',
        creationTime: timestamp,
        conversation: [
          FeedbackConversationEntry(
            speaker: SpeakerType.user,
            text: 'Love the jokes!',
            timestamp: timestamp,
          ),
        ],
        userId: 'test_user',
        lastAdminViewTime: null,
        lastUserViewTime: null,
      );

      when(
        () => mockRepository.watchAllFeedback(),
      ).thenAnswer((_) => Stream.value([]));
      when(
        () => mockService.addConversationMessage(any(), any(), any()),
      ).thenThrow(Exception('Send failed'));

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            feedbackRepositoryProvider.overrideWithValue(mockRepository),
            feedbackServiceProvider.overrideWithValue(mockService),
            feedbackProvider.overrideWith((ref, id) {
              if (id == 'test_feedback_id') {
                return Stream.value(feedback);
              }
              return Stream.value(null);
            }),
          ],
          child: const MaterialApp(
            home: FeedbackConversationScreen.admin(
              feedbackId: 'test_feedback_id',
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Act: Enter text and tap send button
      await tester.enterText(
        find.byKey(const Key('feedback_conversation-message-field-admin')),
        'Admin response',
      );

      await tester.tap(
        find.byKey(const Key('feedback_conversation-send-button-admin')),
      );
      await tester.pumpAndSettle();

      // Assert: Should show error snackbar
      expect(find.text('Failed to send message'), findsOneWidget);
    });
  });
}
