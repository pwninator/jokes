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

extension _GoRouterStubs on MockGoRouter {
  void stubPushNamed() {
    when(
      () => pushNamed(
        any(),
        pathParameters: any(named: 'pathParameters'),
        queryParameters: any(named: 'queryParameters'),
        extra: any(named: 'extra'),
      ),
    ).thenAnswer((_) async => null);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late _MockFeedbackRepository repo;
  late MockGoRouter mockGoRouter;

  setUp(() {
    repo = _MockFeedbackRepository();
    mockGoRouter = MockGoRouter();
    mockGoRouter.stubPushNamed();
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

  testWidgets('renders feedback and checks icon colors and styles', (
    tester,
  ) async {
    final now = DateTime.now();
    final entries = [
      // User message - unread by admin (yellow, solid)
      FeedbackEntry(
        id: '1',
        creationTime: now,
        userId: 'userA',
        conversation: [
          FeedbackConversationEntry(
            speaker: SpeakerType.user,
            text: 'Help!',
            timestamp: now,
          ),
        ],
        lastAdminViewTime: null,
        lastUserViewTime: null,
      ),
      // User message - read by admin (yellow, outline)
      FeedbackEntry(
        id: '2',
        creationTime: now,
        userId: 'userB',
        conversation: [
          FeedbackConversationEntry(
            speaker: SpeakerType.user,
            text: 'Thanks!',
            timestamp: now.subtract(const Duration(hours: 1)),
          ),
        ],
        lastAdminViewTime: now, // Admin viewed after user's message
        lastUserViewTime: null,
      ),
      // Admin message - unread by user (green, solid)
      FeedbackEntry(
        id: '3',
        creationTime: now,
        userId: 'userC',
        conversation: [
          FeedbackConversationEntry(
            speaker: SpeakerType.admin,
            text: 'I got you',
            timestamp: now,
          ),
        ],
        lastAdminViewTime: now.subtract(const Duration(hours: 1)),
        lastUserViewTime: null,
      ),
      // Admin message - read by user (green, outline)
      FeedbackEntry(
        id: '4',
        creationTime: now,
        userId: 'userD',
        conversation: [
          FeedbackConversationEntry(
            speaker: SpeakerType.admin,
            text: 'How can I help?',
            timestamp: now.subtract(const Duration(hours: 1)),
          ),
        ],
        lastAdminViewTime: now.subtract(const Duration(hours: 2)),
        lastUserViewTime: now, // User viewed after admin's message
      ),
    ];

    when(
      () => repo.watchAllFeedback(),
    ).thenAnswer((_) => Stream.value(entries));

    await tester.pumpWidget(createWidget());
    await tester.pumpAndSettle();

    expect(find.text('Help!'), findsOneWidget);
    expect(find.text('Thanks!'), findsOneWidget);
    // When last message is from admin, title shows 'Admin response only'
    expect(find.text('Admin response only'), findsNWidgets(2));
    expect(
      find.text('How can I help?'),
      findsNothing,
    ); // Admin message shown as 'Admin response only'

    final icon1 = tester.widget<Icon>(
      find.descendant(
        of: find.byType(ListTile).at(0),
        matching: find.byType(Icon),
      ),
    );
    final icon2 = tester.widget<Icon>(
      find.descendant(
        of: find.byType(ListTile).at(1),
        matching: find.byType(Icon),
      ),
    );
    final icon3 = tester.widget<Icon>(
      find.descendant(
        of: find.byType(ListTile).at(2),
        matching: find.byType(Icon),
      ),
    );
    final icon4 = tester.widget<Icon>(
      find.descendant(
        of: find.byType(ListTile).at(3),
        matching: find.byType(Icon),
      ),
    );

    // Check colors
    expect(icon1.color, Colors.yellow); // User message - yellow
    expect(icon2.color, Colors.yellow); // User message - yellow
    expect(icon3.color, Colors.green); // Admin message - green
    expect(icon4.color, Colors.green); // Admin message - green

    // Check icon types
    expect(icon1.icon, Icons.feedback); // User message, unread by admin - solid
    expect(
      icon2.icon,
      Icons.feedback_outlined,
    ); // User message, read by admin - outline
    expect(icon3.icon, Icons.feedback); // Admin message, unread by user - solid
    expect(
      icon4.icon,
      Icons.feedback_outlined,
    ); // Admin message, read by user - outline
  });

  testWidgets('tapping a feedback item navigates to details page', (
    tester,
  ) async {
    final now = DateTime.now();
    final entries = [
      FeedbackEntry(
        id: '1',
        creationTime: now,
        userId: 'userA',
        lastAdminViewTime: null,
        lastUserViewTime: null,
        conversation: [
          FeedbackConversationEntry(
            speaker: SpeakerType.user,
            text: 'Help!',
            timestamp: now,
          ),
        ],
      ),
    ];

    when(
      () => repo.watchAllFeedback(),
    ).thenAnswer((_) => Stream.value(entries));

    await tester.pumpWidget(createWidget());
    await tester.pumpAndSettle();

    await tester.tap(find.byType(ListTile));
    await tester.pumpAndSettle();

    verify(
      () => mockGoRouter.pushNamed(
        RouteNames.adminFeedbackDetails,
        pathParameters: {'feedbackId': '1'},
      ),
    ).called(1);
  });
}
