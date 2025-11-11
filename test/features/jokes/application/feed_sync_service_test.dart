import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:riverpod/riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/feed_sync_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() {
    registerFallbackValue(
      const JokeListPageCursor(orderValue: '0', docId: '0'),
    );
  });

  late ProviderContainer container;
  late MockJokeRepository mockJokeRepo;
  late MockJokeInteractionsRepository mockInteractionsRepo;

  Future<void> stubWatchWithCounts(List<int> counts) async {
    // Create a stream that emits lists of length = each count entry
    final controller = StreamController<List<JokeInteraction>>.broadcast();
    when(
      () => mockInteractionsRepo.watchFeedHead(limit: any(named: 'limit')),
    ).thenAnswer((_) => controller.stream);
    // Emit asynchronously to allow triggerSync to subscribe
    Future.microtask(() async {
      for (final c in counts) {
        final now = DateTime.now();
        final items = List<JokeInteraction>.generate(
          c,
          (i) => JokeInteraction(
            jokeId: 'j$i',
            navigatedTimestamp: null,
            viewedTimestamp: null,
            savedTimestamp: null,
            sharedTimestamp: null,
            lastUpdateTimestamp: now,
            setupText: null,
            punchlineText: null,
            setupImageUrl: null,
            punchlineImageUrl: null,
            feedIndex: i,
          ),
        );
        controller.add(items);
      }
    });
  }

  JokeListPage makePage({required int count, required bool hasMore}) {
    final jokes = List<Joke>.generate(
      count,
      (i) => Joke(
        id: 'id_$i',
        setupText: 's$i',
        punchlineText: 'p$i',
        setupImageUrl: null,
        punchlineImageUrl: null,
      ),
    );
    return JokeListPage(
      ids: jokes.map((e) => e.id).toList(),
      cursor: const JokeListPageCursor(orderValue: 'nxt', docId: 'nxt'),
      hasMore: hasMore,
      jokes: jokes,
    );
  }

  setUp(() {
    mockJokeRepo = MockJokeRepository();
    mockInteractionsRepo = MockJokeInteractionsRepository();

    container = ProviderContainer(
      overrides: [
        jokeRepositoryProvider.overrideWithValue(mockJokeRepo),
        jokeInteractionsRepositoryProvider.overrideWithValue(
          mockInteractionsRepo,
        ),
      ],
    );
  });

  tearDown(() {
    container.dispose();
  });

  test(
    'First startup (empty DB) triggers sync and composite reset after 50',
    () async {
      when(
        () => mockInteractionsRepo.countFeedJokes(),
      ).thenAnswer((_) async => 0);
      when(
        () => mockInteractionsRepo.syncFeedJokes(jokes: any(named: 'jokes')),
      ).thenAnswer((_) async => true);
      when(
        () => mockJokeRepo.readFeedJokes(cursor: any(named: 'cursor')),
      ).thenAnswer((_) async => makePage(count: 60, hasMore: false));

      await stubWatchWithCounts([10, 30, 50]);

      final service = container.read(feedSyncServiceProvider);
      final before = container.read(compositeJokesResetTriggerProvider);
      final triggered = await service.triggerSync(forceSync: true);
      final after = container.read(compositeJokesResetTriggerProvider);

      expect(triggered, true);
      expect(after, greaterThan(before));
      verify(
        () => mockJokeRepo.readFeedJokes(cursor: any(named: 'cursor')),
      ).called(greaterThanOrEqualTo(1));
    },
  );

  test(
    'Connectivity/manual sync skipped when DB already has feed jokes',
    () async {
      when(
        () => mockInteractionsRepo.countFeedJokes(),
      ).thenAnswer((_) async => 10);
      final service = container.read(feedSyncServiceProvider);
      final triggered = await service.triggerSync(forceSync: false);
      expect(triggered, false);
    },
  );

  test(
    'Startup sync runs even when DB already has feed jokes and does not reset',
    () async {
      when(
        () => mockInteractionsRepo.countFeedJokes(),
      ).thenAnswer((_) async => 10);
      when(
        () => mockInteractionsRepo.syncFeedJokes(jokes: any(named: 'jokes')),
      ).thenAnswer((_) async => true);
      when(
        () => mockJokeRepo.readFeedJokes(cursor: any(named: 'cursor')),
      ).thenAnswer((_) async => makePage(count: 10, hasMore: false));

      await stubWatchWithCounts([50]);

      final before = container.read(compositeJokesResetTriggerProvider);
      final service = container.read(feedSyncServiceProvider);
      final triggered = await service.triggerSync(forceSync: true);
      final after = container.read(compositeJokesResetTriggerProvider);

      expect(triggered, true);
      expect(after, equals(before)); // no reset, DB was not empty at start
    },
  );
}
