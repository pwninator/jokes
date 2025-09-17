import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_feedback_screen.dart';

import '../../../test_helpers/firebase_mocks.dart';

class _MockFeedbackRepository extends Mock implements FeedbackRepository {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('renders feedback and marks NEW items as READ', (tester) async {
    final repo = _MockFeedbackRepository();

    final now = DateTime(2025, 1, 2, 3, 4, 5);
    final entries = [
      FeedbackEntry(
        id: '20250102_030405_userA',
        creationTime: now,
        conversation: [
          FeedbackConversationEntry(
            speaker: SpeakerType.user,
            text: 'Love the jokes!',
            timestamp: now,
          ),
        ],
        userId: 'userA',
        state: FeedbackState.NEW,
      ),
      FeedbackEntry(
        id: '20250101_020304_userB',
        creationTime: now.subtract(const Duration(days: 1)),
        conversation: [
          FeedbackConversationEntry(
            speaker: SpeakerType.user,
            text: 'Could use more puns',
            timestamp: now.subtract(const Duration(days: 1)),
          ),
        ],
        userId: 'userB',
        state: FeedbackState.READ,
      ),
    ];

    when(
      () => repo.watchAllFeedback(),
    ).thenAnswer((_) => Stream.value(entries));
    when(() => repo.watchUnreadCount()).thenAnswer((_) => Stream.value(1));
    when(() => repo.markFeedbackRead(any())).thenAnswer((_) async {});

    final container = ProviderContainer(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(
        additionalOverrides: [
          feedbackRepositoryProvider.overrideWithValue(repo),
          // Provide usage counters for each user
          jokeUserUsageProvider.overrideWithProvider(
            (userId) => StreamProvider((ref) {
              if (userId == 'userA') {
                return Stream.value(
                  JokeUserUsage(
                    clientNumDaysUsed: 3,
                    clientNumViewed: 10,
                    clientNumSaved: 2,
                    clientNumShared: 1,
                    lastLoginAt: now.subtract(const Duration(hours: 2)),
                  ),
                );
              }
              return Stream.value(
                JokeUserUsage(
                  clientNumDaysUsed: 1,
                  clientNumViewed: 4,
                  clientNumSaved: 0,
                  clientNumShared: 0,
                  lastLoginAt: now.subtract(const Duration(days: 2)),
                ),
              );
            }),
          ),
        ],
      ),
    );
    addTearDown(container.dispose);

    // Force portrait so AdaptiveAppBarScreen shows title reliably
    final originalSize = tester.view.physicalSize;
    tester.view.physicalSize = const Size(600, 800);
    addTearDown(() => tester.view.physicalSize = originalSize);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: JokeFeedbackScreen()),
      ),
    );

    // Let streams emit
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pumpAndSettle(const Duration(milliseconds: 50));

    expect(find.text('Feedback'), findsOneWidget);
    expect(find.text('Love the jokes!'), findsOneWidget);
    // Last login label appears when provided
    expect(find.textContaining('Last login'), findsOneWidget);
    // Scroll to build next items lazily
    final scrollable = find.byType(Scrollable);
    await tester.drag(scrollable, const Offset(0, -400));
    await tester.pump();
    expect(find.text('Could use more puns'), findsOneWidget);

    // Mark-as-read should have been triggered for NEW entry
    await tester.pump(const Duration(milliseconds: 50));
    verify(() => repo.markFeedbackRead('20250102_030405_userA')).called(1);
  });
}
