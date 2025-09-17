import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/features/admin/presentation/admin_feedback/admin_feedback_details_page.dart';

import '../../../../test_helpers/firebase_mocks.dart';

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

  Widget createWidget(String feedbackId) {
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

  testWidgets('updates last admin view time on init and displays conversation',
      (tester) async {
    final now = DateTime.now();
    final feedbackEntry = FeedbackEntry(
      id: '1',
      creationTime: now,
      userId: 'userA',
      conversation: [
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
      ],
      lastAdminViewTime: null,
    );

    when(() => repo.watchAllFeedback())
        .thenAnswer((_) => Stream.value([feedbackEntry]));
    when(() => repo.updateLastAdminViewTime('1')).thenAnswer((_) async {});

    await tester.pumpWidget(createWidget('1'));
    await tester.pumpAndSettle();

    verify(() => repo.updateLastAdminViewTime('1')).called(1);

    expect(find.text('Hello'), findsOneWidget);
    expect(find.text('Hi there'), findsOneWidget);
  });

  testWidgets('sending a message calls repository', (tester) async {
    final now = DateTime.now();
    final feedbackEntry = FeedbackEntry(
      id: '1',
      creationTime: now,
      userId: 'userA',
      conversation: [
        FeedbackConversationEntry(
          speaker: SpeakerType.user,
          text: 'Hello',
          timestamp: now,
        ),
      ],
      lastAdminViewTime: null,
    );

    when(() => repo.watchAllFeedback())
        .thenAnswer((_) => Stream.value([feedbackEntry]));
    when(() => repo.updateLastAdminViewTime('1')).thenAnswer((_) async {});
    when(() => repo.addConversationMessage(any(), any(), any()))
        .thenAnswer((_) async {});

    await tester.pumpWidget(createWidget('1'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'Test reply');
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();

    verify(() => repo.addConversationMessage('1', 'Test reply', SpeakerType.admin))
        .called(1);
  });
}
