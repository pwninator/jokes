import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/startup/startup_task.dart';
import 'package:snickerdoodle/src/startup/startup_tasks.dart';

const int _feedWindowSize =
    initialFeedWindowEndIndex - initialFeedWindowStartIndex + 1;
const int _partialFeedWindowSize = _feedWindowSize > 1
    ? _feedWindowSize - 1
    : 0;

class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

class FakeJoke extends Fake implements Joke {}

void main() {
  setUpAll(() {
    registerFallbackValue(FakeJoke());
    registerFallbackValue(<JokeInteraction>[]);
    registerFallbackValue(
      const JokeListPageCursor(orderValue: 'cursor', docId: 'cursor'),
    );
  });

  late MockJokeRepository mockJokeRepository;
  late MockJokeInteractionsRepository mockInteractionsRepository;

  setUp(() {
    mockJokeRepository = MockJokeRepository();
    mockInteractionsRepository = MockJokeInteractionsRepository();

    when(
      () =>
          mockInteractionsRepository.syncFeedJokes(jokes: any(named: 'jokes')),
    ).thenAnswer((_) async => true);

    when(
      () =>
          mockInteractionsRepository.watchFeedHead(limit: any(named: 'limit')),
    ).thenAnswer((invocation) {
      final limit = invocation.namedArguments[#limit] as int;
      return Stream.value(_buildInteractions(limit));
    });

    when(
      () => mockJokeRepository.readFeedJokes(cursor: any(named: 'cursor')),
    ).thenAnswer(
      (_) async =>
          const JokeListPage(ids: [], cursor: null, hasMore: false, jokes: []),
    );
  });

  StartupTask getTask() {
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
        return mockInteractionsRepository as T;
      }
      throw UnimplementedError('Unknown provider: $provider');
    }

    return reader;
  }

  test('completes when initial watcher batch already has window', () async {
    final task = getTask();
    final reader = createReader();

    await task.execute(reader);

    verify(
      () => mockInteractionsRepository.watchFeedHead(limit: _feedWindowSize),
    ).called(1);
    verify(
      () => mockJokeRepository.readFeedJokes(cursor: any(named: 'cursor')),
    ).called(1);
  });

  test('waits for watcher when feed window missing', () async {
    final controller = StreamController<List<JokeInteraction>>();

    when(
      () =>
          mockInteractionsRepository.watchFeedHead(limit: any(named: 'limit')),
    ).thenAnswer((_) => controller.stream);

    final task = getTask();
    final reader = createReader();

    var completed = false;
    final future = task.execute(reader).then((value) => completed = true);

    controller.add(_buildInteractions(_partialFeedWindowSize));
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(completed, isFalse);

    controller.add(_buildInteractions(_feedWindowSize));
    await future;
    expect(completed, isTrue);
    await controller.close();
  });

  test('background sync continues after task completes', () async {
    final cursor1 = JokeListPageCursor(orderValue: 'doc1', docId: 'doc1');
    final cursor2 = JokeListPageCursor(orderValue: 'doc2', docId: 'doc2');

    when(() => mockJokeRepository.readFeedJokes(cursor: null)).thenAnswer(
      (_) async => JokeListPage(
        ids: ['joke-1'],
        cursor: cursor1,
        hasMore: true,
        jokes: [
          Joke(id: 'joke-1', setupText: 'setup1', punchlineText: 'punch1'),
        ],
      ),
    );

    when(() => mockJokeRepository.readFeedJokes(cursor: cursor1)).thenAnswer(
      (_) async => JokeListPage(
        ids: ['joke-2'],
        cursor: cursor2,
        hasMore: true,
        jokes: [
          Joke(id: 'joke-2', setupText: 'setup2', punchlineText: 'punch2'),
        ],
      ),
    );

    when(() => mockJokeRepository.readFeedJokes(cursor: cursor2)).thenAnswer(
      (_) async => JokeListPage(
        ids: ['joke-3'],
        cursor: null,
        hasMore: false,
        jokes: [
          Joke(id: 'joke-3', setupText: 'setup3', punchlineText: 'punch3'),
        ],
      ),
    );

    final task = getTask();
    final reader = createReader();

    await task.execute(reader);

    await untilCalled(() => mockJokeRepository.readFeedJokes(cursor: cursor2));

    verify(() => mockJokeRepository.readFeedJokes(cursor: null)).called(1);
    verify(() => mockJokeRepository.readFeedJokes(cursor: cursor1)).called(1);
    verify(() => mockJokeRepository.readFeedJokes(cursor: cursor2)).called(1);
  });

  test('background sync errors do not fail startup task', () async {
    when(
      () => mockJokeRepository.readFeedJokes(cursor: any(named: 'cursor')),
    ).thenThrow(Exception('network error'));

    final task = getTask();
    final reader = createReader();

    await task.execute(reader);

    verify(
      () => mockJokeRepository.readFeedJokes(cursor: any(named: 'cursor')),
    ).called(1);
  });

  test('watchFeedHead errors do not prevent completion', () async {
    final controller = StreamController<List<JokeInteraction>>();

    when(
      () =>
          mockInteractionsRepository.watchFeedHead(limit: any(named: 'limit')),
    ).thenAnswer((_) => controller.stream);

    final task = getTask();
    final reader = createReader();

    final future = task.execute(reader);

    controller.addError(Exception('db error'));
    await Future<void>.delayed(const Duration(milliseconds: 10));
    controller.add(_buildInteractions(_feedWindowSize));

    await future;
    await controller.close();
  });
}

List<JokeInteraction> _buildInteractions(int count) {
  final now = DateTime.now();
  return List.generate(
    count,
    (index) => JokeInteraction(
      jokeId: 'joke-$index',
      lastUpdateTimestamp: now.add(Duration(milliseconds: index)),
      feedIndex: index,
    ),
  );
}
