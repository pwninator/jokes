import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_management_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';

// Test helpers import
import '../../../test_helpers/test_helpers.dart';

// Mock classes
class MockJokeRepository extends Mock implements JokeRepository {}

void main() {
  group('JokeManagementScreen', () {
    late MockJokeRepository mockJokeRepository;

    setUp(() {
      TestHelpers.resetAllMocks();
      mockJokeRepository = MockJokeRepository();
    });

    testWidgets('should display filter bar with unrated only button', (
      tester,
    ) async {
      // arrange
      when(
        () => mockJokeRepository.getJokes(),
      ).thenAnswer((_) => Stream.value(<Joke>[]));

      // act
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...TestHelpers.getAllMockOverrides(),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
          child: const MaterialApp(home: JokeManagementScreen()),
        ),
      );

      // Wait for widget to settle
      await tester.pumpAndSettle();

      // assert
      expect(find.text('Filters'), findsOneWidget);
      expect(find.text('Unrated only'), findsOneWidget);
      expect(find.byType(FilterChip), findsOneWidget);

      // Filter should be off by default
      final filterChip = tester.widget<FilterChip>(find.byType(FilterChip));
      expect(filterChip.selected, false);
    });

    testWidgets('should toggle filter when chip is tapped', (tester) async {
      // arrange
      when(
        () => mockJokeRepository.getJokes(),
      ).thenAnswer((_) => Stream.value(<Joke>[]));

      // act
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...TestHelpers.getAllMockOverrides(),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
          child: const MaterialApp(home: JokeManagementScreen()),
        ),
      );

      await tester.pumpAndSettle();

      // Tap the filter chip
      await tester.tap(find.byType(FilterChip));
      await tester.pumpAndSettle();

      // assert
      final filterChip = tester.widget<FilterChip>(find.byType(FilterChip));
      expect(filterChip.selected, true);
    });

    testWidgets('should display correct empty message when filter is off', (
      tester,
    ) async {
      // arrange
      when(
        () => mockJokeRepository.getJokes(),
      ).thenAnswer((_) => Stream.value(<Joke>[]));

      // act
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...TestHelpers.getAllMockOverrides(),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
          child: const MaterialApp(home: JokeManagementScreen()),
        ),
      );

      await tester.pump();
      await tester.pump();

      // assert
      expect(find.text('No jokes yet!'), findsOneWidget);
      expect(
        find.text('Tap the + button to add your first joke'),
        findsOneWidget,
      );
    });

    testWidgets('should display correct empty message when filter is on', (
      tester,
    ) async {
      // arrange
      when(
        () => mockJokeRepository.getJokes(),
      ).thenAnswer((_) => Stream.value(<Joke>[]));

      // act
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...TestHelpers.getAllMockOverrides(),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
          child: const MaterialApp(home: JokeManagementScreen()),
        ),
      );

      await tester.pumpAndSettle();

      // Tap the filter chip to turn on filter
      await tester.tap(find.byType(FilterChip));
      await tester.pumpAndSettle();

      // assert
      expect(find.text('No unrated jokes with images found!'), findsOneWidget);
      expect(
        find.text('Try turning off the filter or add some jokes with images'),
        findsOneWidget,
      );
    });

    testWidgets('should display all jokes when filter is off', (tester) async {
      // arrange - use jokes without images to avoid network issues in tests
      final testJokes = [
        const Joke(
          id: '1',
          setupText: 'Setup 1',
          punchlineText: 'Punchline 1',
          numThumbsUp: 0,
          numThumbsDown: 0,
        ),
        const Joke(
          id: '2',
          setupText: 'Setup 2',
          punchlineText: 'Punchline 2',
          numThumbsUp: 0,
          numThumbsDown: 0,
        ),
        const Joke(
          id: '3',
          setupText: 'Setup 3',
          punchlineText: 'Punchline 3',
          numThumbsUp: 5,
          numThumbsDown: 0,
        ),
      ];

      when(
        () => mockJokeRepository.getJokes(),
      ).thenAnswer((_) => Stream.value(testJokes));

      // act
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...TestHelpers.getAllMockOverrides(),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
          child: const MaterialApp(home: JokeManagementScreen()),
        ),
      );

      // Wait for async providers to emit data and render
      await tester.pump(); // Initial pump to start the async operation
      await tester.pump(); // Second pump to handle provider state changes
      await tester.pump(); // Third pump to ensure all widgets are rendered

      // assert
      expect(find.text('Setup 1'), findsOneWidget);
      expect(find.text('Setup 2'), findsOneWidget);
      expect(find.text('Setup 3'), findsOneWidget);
    });

    testWidgets(
      'should show empty state when filter is on and no matching jokes',
      (tester) async {
        // arrange - use jokes without images so they get filtered out
        final testJokes = [
          const Joke(
            id: '1',
            setupText: 'Setup 1',
            punchlineText: 'Punchline 1',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
          const Joke(
            id: '2',
            setupText: 'Setup 2',
            punchlineText: 'Punchline 2',
            numThumbsUp: 5,
            numThumbsDown: 0,
          ),
        ];

        when(
          () => mockJokeRepository.getJokes(),
        ).thenAnswer((_) => Stream.value(testJokes));

        // act
        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              ...TestHelpers.getAllMockOverrides(),
              jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
            ],
            child: const MaterialApp(home: JokeManagementScreen()),
          ),
        );

        // Wait for async providers to emit data and render
        await tester.pump(); // Initial pump to start the async operation
        await tester.pump(); // Second pump to handle provider state changes
        await tester.pump(); // Third pump to ensure all widgets are rendered

        // Tap the filter chip to turn on filter
        await tester.tap(find.byKey(const Key('unrated-only-filter-chip')));
        await tester.pump(); // Pump to handle filter state change

        // assert - should show empty state since no jokes have images
        expect(
          find.text('No unrated jokes with images found!'),
          findsOneWidget,
        );
        expect(
          find.text('Try turning off the filter or add some jokes with images'),
          findsOneWidget,
        );
      },
    );

    testWidgets('should display loading indicator when jokes are loading', (
      tester,
    ) async {
      // arrange
      when(
        () => mockJokeRepository.getJokes(),
      ).thenAnswer((_) => Stream<List<Joke>>.empty());

      // act
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...TestHelpers.getAllMockOverrides(),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
          child: const MaterialApp(home: JokeManagementScreen()),
        ),
      );

      // Note: Don't call pumpAndSettle() here as we want to catch the loading state
      await tester.pump();

      // assert
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Loading jokes...'), findsOneWidget);
    });

    testWidgets('should display error message when jokes fail to load', (
      tester,
    ) async {
      // arrange
      const error = 'Failed to load jokes';
      when(
        () => mockJokeRepository.getJokes(),
      ).thenAnswer((_) => Stream<List<Joke>>.error(error));

      // act
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...TestHelpers.getAllMockOverrides(),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
          child: const MaterialApp(home: JokeManagementScreen()),
        ),
      );

      // Allow the error to propagate
      await tester.pump();
      await tester.pump();

      // assert
      expect(find.text('Error loading jokes'), findsOneWidget);
      expect(find.text(error), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('should display floating action button', (tester) async {
      // arrange
      when(
        () => mockJokeRepository.getJokes(),
      ).thenAnswer((_) => Stream.value(<Joke>[]));

      // act
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...TestHelpers.getAllMockOverrides(),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
          child: const MaterialApp(home: JokeManagementScreen()),
        ),
      );

      await tester.pumpAndSettle();

      // assert
      expect(find.byType(FloatingActionButton), findsOneWidget);
      expect(find.byIcon(Icons.add), findsOneWidget);
    });
  });
}
