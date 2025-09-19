import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/core/services/feedback_service.dart';
import 'package:snickerdoodle/src/features/admin/presentation/feedback_details_screen.dart';

import '../../../test_helpers/firebase_mocks.dart';

class _MockFeedbackService extends Mock implements FeedbackService {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() {
    registerFallbackValue(SpeakerType.user);
  });

  testWidgets('displays conversation and input controls', (tester) async {
    final mockService = _MockFeedbackService();

    final now = DateTime(2025, 1, 2, 3, 4, 5);
    final feedback = FeedbackEntry(
      id: 'test_feedback_id',
      creationTime: now,
      conversation: [
        FeedbackConversationEntry(
          speaker: SpeakerType.user,
          text: 'Love the jokes!',
          timestamp: now,
        ),
        FeedbackConversationEntry(
          speaker: SpeakerType.admin,
          text: 'Thank you for the feedback!',
          timestamp: now.add(const Duration(minutes: 5)),
        ),
      ],
      userId: 'test_user',
      lastAdminViewTime: null,
        lastUserViewTime: null,
    );

    when(
      () => mockService.addConversationMessage(any(), any(), any()),
    ).thenAnswer((_) async {});

    final container = ProviderContainer(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(
        additionalOverrides: [
          feedbackServiceProvider.overrideWithValue(mockService),
        ],
      ),
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(home: FeedbackDetailsScreen(feedback: feedback)),
      ),
    );

    await tester.pumpAndSettle();

    // Verify that the screen displays the feedback details
    expect(find.text('Feedback from test_user'), findsOneWidget);

    // Verify that the text input and send button are present
    expect(find.byType(TextField), findsOneWidget);
    expect(find.byIcon(Icons.send), findsOneWidget);
  });

  testWidgets('sends message when send button is tapped', (tester) async {
    final mockService = _MockFeedbackService();

    final now = DateTime(2025, 1, 2, 3, 4, 5);
    final feedback = FeedbackEntry(
      id: 'test_feedback_id',
      creationTime: now,
      conversation: [
        FeedbackConversationEntry(
          speaker: SpeakerType.user,
          text: 'Initial feedback',
          timestamp: now,
        ),
      ],
      userId: 'test_user',
      lastAdminViewTime: null,
        lastUserViewTime: null,
    );

    when(
      () => mockService.addConversationMessage(any(), any(), any()),
    ).thenAnswer((_) async {});

    final container = ProviderContainer(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(
        additionalOverrides: [
          feedbackServiceProvider.overrideWithValue(mockService),
        ],
      ),
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(home: FeedbackDetailsScreen(feedback: feedback)),
      ),
    );

    await tester.pumpAndSettle();

    // Type a message
    await tester.enterText(find.byType(TextField), 'Admin response');

    // Tap send button
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();

    // Verify that the service was called with correct parameters
    verify(
      () => mockService.addConversationMessage(
        'test_feedback_id',
        'Admin response',
        SpeakerType.admin,
      ),
    ).called(1);

    // Verify that the text field is cleared
    expect(find.byType(TextField), findsOneWidget);
    final textField = tester.widget<TextField>(find.byType(TextField));
    expect(textField.controller?.text, isEmpty);
  });

  testWidgets('does not send empty message', (tester) async {
    final mockService = _MockFeedbackService();

    final now = DateTime(2025, 1, 2, 3, 4, 5);
    final feedback = FeedbackEntry(
      id: 'test_feedback_id',
      creationTime: now,
      conversation: [
        FeedbackConversationEntry(
          speaker: SpeakerType.user,
          text: 'Initial feedback',
          timestamp: now,
        ),
      ],
      userId: 'test_user',
      lastAdminViewTime: null,
        lastUserViewTime: null,
    );

    when(
      () => mockService.addConversationMessage(any(), any(), any()),
    ).thenAnswer((_) async {});

    final container = ProviderContainer(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(
        additionalOverrides: [
          feedbackServiceProvider.overrideWithValue(mockService),
        ],
      ),
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(home: FeedbackDetailsScreen(feedback: feedback)),
      ),
    );

    await tester.pumpAndSettle();

    // Tap send button without entering any text
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();

    // Verify that the service was not called
    verifyNever(() => mockService.addConversationMessage(any(), any(), any()));
  });
}
