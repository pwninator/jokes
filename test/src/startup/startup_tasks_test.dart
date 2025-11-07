import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/startup/startup_task.dart';
import 'package:snickerdoodle/src/startup/startup_tasks.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

class MockPerformanceService extends Mock implements PerformanceService {}

class FakeJoke extends Fake implements Joke {}

void main() {
  setUpAll(() {
    registerFallbackValue(FakeJoke());
  });

  late MockJokeRepository mockJokeRepository;
  late MockJokeInteractionsRepository mockJokeInteractionsRepository;

  setUp(() {
    mockJokeRepository = MockJokeRepository();
    mockJokeInteractionsRepository = MockJokeInteractionsRepository();

    when(
      () => mockJokeInteractionsRepository.syncFeedJokes(
        jokes: any(named: 'jokes'),
      ),
    ).thenAnswer((_) async => true);
  });

  StartupTask getSyncFeedJokesTask() {
    return bestEffortBlockingTasks.firstWhere(
      (task) => task.id == 'sync_feed_jokes',
    );
  }

  StartupReader createReader() {
    T reader<T>(ProviderListenable<T> provider) {
      if (identical(provider, jokeRepositoryProvider)) {
        return mockJokeRepository as T;
      }
      if (identical(provider, jokeInteractionsRepositoryProvider)) {
        return mockJokeInteractionsRepository as T;
      }
      throw UnimplementedError('Unknown provider: $provider');
    }

    return reader;
  }

  test(
    '_syncFeedJokes breaks when cursor is the same as previous cursor',
    () async {
      final cursor1 = JokeListPageCursor(orderValue: 'doc1', docId: 'doc1');
      final cursor2 = JokeListPageCursor(orderValue: 'doc2', docId: 'doc2');

      // First call returns page with jokes
      when(() => mockJokeRepository.readFeedJokes(cursor: null)).thenAnswer(
        (_) async => JokeListPage(
          ids: ['joke-1'],
          cursor: cursor1,
          hasMore: true,
          jokes: [
            Joke(
              id: 'joke-1',
              setupText: 'Setup 1',
              punchlineText: 'Punchline 1',
            ),
          ],
        ),
      );

      // Second call returns empty page with same cursor
      when(() => mockJokeRepository.readFeedJokes(cursor: cursor1)).thenAnswer(
        (_) async => JokeListPage(
          ids: [],
          cursor: cursor1, // Same cursor as previous
          hasMore: true,
          jokes: [],
        ),
      );

      // Create a StartupReader that provides our mocks
      final reader = createReader();

      // Execute the task
      final task = getSyncFeedJokesTask();
      await task.execute(reader);

      // Verify first call was made
      verify(() => mockJokeRepository.readFeedJokes(cursor: null)).called(1);

      // Verify second call was made
      verify(() => mockJokeRepository.readFeedJokes(cursor: cursor1)).called(1);

      // Verify syncFeedJokes was called with the first joke
      verify(
        () => mockJokeInteractionsRepository.syncFeedJokes(
          jokes: any(
            named: 'jokes',
            that: predicate<List<({Joke joke, int feedIndex})>>(
              (list) =>
                  list.length == 1 &&
                  list.first.joke.id == 'joke-1' &&
                  list.first.feedIndex == 0,
            ),
          ),
        ),
      ).called(1);

      // Verify no third call was made (should have broken due to same cursor)
      verifyNever(() => mockJokeRepository.readFeedJokes(cursor: cursor2));
    },
  );

  test('_syncFeedJokes processes multiple pages correctly', () async {
    final cursor1 = JokeListPageCursor(orderValue: 'doc1', docId: 'doc1');
    final cursor2 = JokeListPageCursor(orderValue: 'doc2', docId: 'doc2');

    // First page
    when(() => mockJokeRepository.readFeedJokes(cursor: null)).thenAnswer(
      (_) async => JokeListPage(
        ids: ['joke-1'],
        cursor: cursor1,
        hasMore: true,
        jokes: [
          Joke(
            id: 'joke-1',
            setupText: 'Setup 1',
            punchlineText: 'Punchline 1',
          ),
        ],
      ),
    );

    // Second page
    when(() => mockJokeRepository.readFeedJokes(cursor: cursor1)).thenAnswer(
      (_) async => JokeListPage(
        ids: ['joke-2'],
        cursor: cursor2,
        hasMore: true,
        jokes: [
          Joke(
            id: 'joke-2',
            setupText: 'Setup 2',
            punchlineText: 'Punchline 2',
          ),
        ],
      ),
    );

    // Third page (last)
    when(() => mockJokeRepository.readFeedJokes(cursor: cursor2)).thenAnswer(
      (_) async => JokeListPage(
        ids: ['joke-3'],
        cursor: null,
        hasMore: false,
        jokes: [
          Joke(
            id: 'joke-3',
            setupText: 'Setup 3',
            punchlineText: 'Punchline 3',
          ),
        ],
      ),
    );

    final reader = createReader();

    final task = getSyncFeedJokesTask();
    await task.execute(reader);

    // Verify all pages were fetched
    verify(() => mockJokeRepository.readFeedJokes(cursor: null)).called(1);
    verify(() => mockJokeRepository.readFeedJokes(cursor: cursor1)).called(1);
    verify(() => mockJokeRepository.readFeedJokes(cursor: cursor2)).called(1);

    // Verify all jokes were synced with correct feedIndex
    verify(
      () => mockJokeInteractionsRepository.syncFeedJokes(
        jokes: any(
          named: 'jokes',
          that: predicate<List<({Joke joke, int feedIndex})>>(
            (list) =>
                list.length == 1 &&
                list.first.joke.id == 'joke-1' &&
                list.first.feedIndex == 0,
          ),
        ),
      ),
    ).called(1);
    verify(
      () => mockJokeInteractionsRepository.syncFeedJokes(
        jokes: any(
          named: 'jokes',
          that: predicate<List<({Joke joke, int feedIndex})>>(
            (list) =>
                list.length == 1 &&
                list.first.joke.id == 'joke-2' &&
                list.first.feedIndex == 1,
          ),
        ),
      ),
    ).called(1);
    verify(
      () => mockJokeInteractionsRepository.syncFeedJokes(
        jokes: any(
          named: 'jokes',
          that: predicate<List<({Joke joke, int feedIndex})>>(
            (list) =>
                list.length == 1 &&
                list.first.joke.id == 'joke-3' &&
                list.first.feedIndex == 2,
          ),
        ),
      ),
    ).called(1);
  });

  test('_syncFeedJokes handles empty pages and continues', () async {
    final cursor1 = JokeListPageCursor(orderValue: 'doc1', docId: 'doc1');
    final cursor2 = JokeListPageCursor(orderValue: 'doc2', docId: 'doc2');

    // First page is empty but hasMore is true
    when(() => mockJokeRepository.readFeedJokes(cursor: null)).thenAnswer(
      (_) async =>
          JokeListPage(ids: [], cursor: cursor1, hasMore: true, jokes: []),
    );

    // Second page has jokes
    when(() => mockJokeRepository.readFeedJokes(cursor: cursor1)).thenAnswer(
      (_) async => JokeListPage(
        ids: ['joke-1'],
        cursor: cursor2,
        hasMore: false,
        jokes: [
          Joke(
            id: 'joke-1',
            setupText: 'Setup 1',
            punchlineText: 'Punchline 1',
          ),
        ],
      ),
    );

    final reader = createReader();

    final task = getSyncFeedJokesTask();
    await task.execute(reader);

    // Verify both pages were fetched
    verify(() => mockJokeRepository.readFeedJokes(cursor: null)).called(1);
    verify(() => mockJokeRepository.readFeedJokes(cursor: cursor1)).called(1);

    // Verify joke was synced
    verify(
      () => mockJokeInteractionsRepository.syncFeedJokes(
        jokes: any(
          named: 'jokes',
          that: predicate<List<({Joke joke, int feedIndex})>>(
            (list) =>
                list.length == 1 &&
                list.first.joke.id == 'joke-1' &&
                list.first.feedIndex == 0,
          ),
        ),
      ),
    ).called(1);
  });

  test('_syncFeedJokes handles errors gracefully', () async {
    when(
      () => mockJokeRepository.readFeedJokes(cursor: null),
    ).thenThrow(Exception('Network error'));

    final reader = createReader();

    // Should not throw
    final task = getSyncFeedJokesTask();
    await task.execute(reader);

    // Verify the call was made
    verify(() => mockJokeRepository.readFeedJokes(cursor: null)).called(1);
  });
}
