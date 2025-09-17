import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/features/admin/presentation/admin_feedback/admin_feedback_details_page.dart';

import '../../../../test_helpers/firebase_mocks.dart';

class _MockFeedbackRepository extends Mock implements FeedbackRepository {}

class _FakeMessage extends Fake implements Message {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late _MockFeedbackRepository repo;

  setUp(() {
    repo = _MockFeedbackRepository();
    registerFallbackValue(_FakeMessage());
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

  testWidgets('updates view time on init and displays messages',
      (tester) async {
    final now = DateTime.now();
    final feedbackEntry = FeedbackEntry(
      id: '1',
      creationTime: now,
      userId: 'userA',
      lastAdminViewTime: null,
      messages: [
        Message(text: 'Hello', timestamp: now, isFromAdmin: false),
        Message(
            text: 'Hi there',
            timestamp: now.add(const Duration(minutes: 1)),
            isFromAdmin: true),
      ],
      lastMessage: Message(
          text: 'Hi there',
          timestamp: now.add(const Duration(minutes: 1)),
          isFromAdmin: true),
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
      lastAdminViewTime: null,
      messages: [Message(text: 'Hello', timestamp: now, isFromAdmin: false)],
      lastMessage: Message(text: 'Hello', timestamp: now, isFromAdmin: false),
    );

    when(() => repo.watchAllFeedback())
        .thenAnswer((_) => Stream.value([feedbackEntry]));
    when(() => repo.updateLastAdminViewTime('1')).thenAnswer((_) async {});
    when(() => repo.addMessage(any(), any())).thenAnswer((_) async {});

    await tester.pumpWidget(createWidget('1'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'Test reply');
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();

    verify(() => repo.addMessage('1', any())).called(1);
  });
}
