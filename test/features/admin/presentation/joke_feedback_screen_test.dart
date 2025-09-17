import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_feedback_screen.dart';

import '../../../test_helpers/firebase_mocks.dart';

class _MockFeedbackRepository extends Mock implements FeedbackRepository {}

class MockGoRouter extends Mock implements GoRouter {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late _MockFeedbackRepository repo;
  late MockGoRouter mockGoRouter;

  setUp(() {
    repo = _MockFeedbackRepository();
    mockGoRouter = MockGoRouter();
  });

  Widget createWidget() {
    return ProviderScope(
      overrides: [
        feedbackRepositoryProvider.overrideWithValue(repo),
        ...FirebaseMocks.getFirebaseProviderOverrides(),
      ],
      child: MaterialApp(
        home: InheritedGoRouter(
          goRouter: mockGoRouter,
          child: const JokeFeedbackScreen(),
        ),
      ),
    );
  }

  testWidgets('renders feedback and checks icon colors', (tester) async {
    final now = DateTime.now();
    final entries = [
      // Red case
      FeedbackEntry(
        id: '1',
        creationTime: now,
        userId: 'userA',
        lastAdminViewTime: null,
        messages: [Message(text: 'Help!', timestamp: now, isFromAdmin: false)],
        lastMessage: Message(text: 'Help!', timestamp: now, isFromAdmin: false),
      ),
      // Yellow case
      FeedbackEntry(
        id: '2',
        creationTime: now,
        userId: 'userB',
        lastAdminViewTime: now,
        messages: [
          Message(
              text: 'Thanks!',
              timestamp: now.subtract(const Duration(hours: 1)),
              isFromAdmin: false)
        ],
        lastMessage: Message(
            text: 'Thanks!',
            timestamp: now.subtract(const Duration(hours: 1)),
            isFromAdmin: false),
      ),
      // Green case
      FeedbackEntry(
        id: '3',
        creationTime: now,
        userId: 'userC',
        lastAdminViewTime: now.subtract(const Duration(hours: 1)),
        messages: [
          Message(text: 'I got you', timestamp: now, isFromAdmin: true)
        ],
        lastMessage:
            Message(text: 'I got you', timestamp: now, isFromAdmin: true),
      ),
    ];

    when(() => repo.watchAllFeedback())
        .thenAnswer((_) => Stream.value(entries));

    await tester.pumpWidget(createWidget());
    await tester.pumpAndSettle();

    expect(find.text('Help!'), findsOneWidget);
    expect(find.text('Thanks!'), findsOneWidget);
    expect(find.text('I got you'), findsOneWidget);

    final icon1 = tester.widget<Icon>(
        find.descendant(of: find.byType(ListTile).at(0), matching: find.byType(Icon)));
    final icon2 = tester.widget<Icon>(
        find.descendant(of: find.byType(ListTile).at(1), matching: find.byType(Icon)));
    final icon3 = tester.widget<Icon>(
        find.descendant(of: find.byType(ListTile).at(2), matching: find.byType(Icon)));

    expect(icon1.color, Theme.of(tester.element(find.byType(ListTile).at(0))).colorScheme.error);
    expect(icon2.color, Colors.yellow);
    expect(icon3.color, Colors.green);
  });

  testWidgets('tapping a feedback item navigates to details page',
      (tester) async {
    final now = DateTime.now();
    final entries = [
      FeedbackEntry(
        id: '1',
        creationTime: now,
        userId: 'userA',
        lastAdminViewTime: null,
        messages: [Message(text: 'Help!', timestamp: now, isFromAdmin: false)],
        lastMessage: Message(text: 'Help!', timestamp: now, isFromAdmin: false),
      ),
    ];

    when(() => repo.watchAllFeedback())
        .thenAnswer((_) => Stream.value(entries));

    await tester.pumpWidget(createWidget());
    await tester.pumpAndSettle();

    await tester.tap(find.byType(ListTile));
    await tester.pumpAndSettle();

    verify(() => mockGoRouter.goNamed(RouteNames.adminFeedbackDetails,
        pathParameters: {'feedbackId': '1'})).called(1);
  });
}
