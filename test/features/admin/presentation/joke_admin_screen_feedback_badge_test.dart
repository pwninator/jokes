import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_admin_screen.dart';

class MockFeedbackRepository extends Mock implements FeedbackRepository {}

void main() {
  setUpAll(() {
    registerFallbackValue(SpeakerType.user);
  });

  late MockFeedbackRepository mockRepository;

  setUp(() {
    // Create fresh mock per test
    mockRepository = MockFeedbackRepository();

    // Stub default behavior
    when(
      () => mockRepository.watchAllFeedback(),
    ).thenAnswer((_) => Stream.value([]));
  });

  testWidgets('shows unread badge when unread feedback > 0', (tester) async {
    // Arrange: Create test feedback with unread message
    final now = DateTime.now();
    final entries = [
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
        lastAdminViewTime: null, // This makes it unread
        lastUserViewTime: null,
      ),
    ];

    when(
      () => mockRepository.watchAllFeedback(),
    ).thenAnswer((_) => Stream.value(entries));

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          feedbackRepositoryProvider.overrideWithValue(mockRepository),
        ],
        child: const MaterialApp(home: JokeAdminScreen()),
      ),
    );

    await tester.pumpAndSettle();

    // Assert: Should display feedback tile and unread badge
    expect(find.text('Feedback'), findsOneWidget);
    expect(find.text('1'), findsOneWidget); // The badge text
  });

  testWidgets('shows no badge when no unread feedback', (tester) async {
    // Arrange: Create test feedback with read message
    final now = DateTime.now();
    final entries = [
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
        lastAdminViewTime: now.add(
          const Duration(minutes: 1),
        ), // This makes it read
        lastUserViewTime: null,
      ),
    ];

    when(
      () => mockRepository.watchAllFeedback(),
    ).thenAnswer((_) => Stream.value(entries));

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          feedbackRepositoryProvider.overrideWithValue(mockRepository),
        ],
        child: const MaterialApp(home: JokeAdminScreen()),
      ),
    );

    await tester.pumpAndSettle();

    // Assert: Should display feedback tile but no badge
    expect(find.text('Feedback'), findsOneWidget);
    expect(find.text('1'), findsNothing); // No badge should be shown
  });

  testWidgets('shows badge with 99+ for large unread counts', (tester) async {
    // Arrange: Create many unread feedback entries
    final now = DateTime.now();
    final entries = List.generate(
      150,
      (index) => FeedbackEntry(
        id: '$index',
        creationTime: now,
        userId: 'user$index',
        conversation: [
          FeedbackConversationEntry(
            speaker: SpeakerType.user,
            text: 'Help $index!',
            timestamp: now,
          ),
        ],
        lastAdminViewTime: null, // All unread
        lastUserViewTime: null,
      ),
    );

    when(
      () => mockRepository.watchAllFeedback(),
    ).thenAnswer((_) => Stream.value(entries));

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          feedbackRepositoryProvider.overrideWithValue(mockRepository),
        ],
        child: const MaterialApp(home: JokeAdminScreen()),
      ),
    );

    await tester.pumpAndSettle();

    // Assert: Should display feedback tile and 99+ badge
    expect(find.text('Feedback'), findsOneWidget);
    expect(find.text('99+'), findsOneWidget); // Should cap at 99+
  });
}
