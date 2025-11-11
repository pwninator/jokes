import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class _NoopPerf implements PerformanceService {
  @override
  void dropNamedTrace({required TraceName name, String? key}) {}

  @override
  void putNamedTraceAttributes({
    required TraceName name,
    String? key,
    required Map<String, String> attributes,
  }) {}

  @override
  void startNamedTrace({
    required TraceName name,
    String? key,
    Map<String, String>? attributes,
  }) {}

  @override
  void stopNamedTrace({required TraceName name, String? key}) {}
}

void main() {
  late AppDatabase db;
  late JokeInteractionsRepository service;

  setUp(() {
    db = AppDatabase.inMemory();
    service = JokeInteractionsRepository(
      performanceService: _NoopPerf(),
      db: db,
    );
  });

  tearDown(() async {
    await db.close();
  });

  test('setSaved upserts and getSavedJokeInteractions orders ASC', () async {
    await service.setSaved('a');
    await Future<void>.delayed(const Duration(milliseconds: 2));
    await service.setSaved('b');

    final rows = await service.getSavedJokeInteractions();
    expect(rows.map((e) => e.jokeId).toList(), ['a', 'b']);
  });

  test(
    'setUnsaved clears savedTimestamp so not returned by getSavedJokeInteractions',
    () async {
      await service.setSaved('x');
      await service.setUnsaved('x');

      final rows = await service.getSavedJokeInteractions();
      expect(rows, isEmpty);
    },
  );

  test('setNavigated upserts navigated timestamp', () async {
    await service.setNavigated('nav-1');

    final interaction = await service.getJokeInteraction('nav-1');
    expect(interaction, isNotNull);
    expect(interaction!.navigatedTimestamp, isNotNull);
  });

  test('countViewed returns count of viewed jokes', () async {
    expect(await service.countViewed(), 0);
    await service.setViewed('j1');
    await service.setViewed('j2');
    expect(await service.countViewed(), 2);
  });

  test('countNavigated returns count of navigated jokes', () async {
    expect(await service.countNavigated(), 0);
    await service.setNavigated('n1');
    await service.setNavigated('n2');
    expect(await service.countNavigated(), 2);
  });

  test('countSaved returns count of saved jokes', () async {
    expect(await service.countSaved(), 0);
    await service.setSaved('s1');
    await service.setSaved('s2');
    expect(await service.countSaved(), 2);
    await service.setUnsaved('s1');
    expect(await service.countSaved(), 1);
  });

  test('getNavigatedJokeInteractions orders ASC', () async {
    await service.setNavigated('n1');
    await Future<void>.delayed(const Duration(milliseconds: 2));
    await service.setNavigated('n2');

    final rows = await service.getNavigatedJokeInteractions();
    expect(rows.map((e) => e.jokeId).toList(), ['n1', 'n2']);
  });

  test('countShared returns count of shared jokes', () async {
    expect(await service.countShared(), 0);
    await service.setShared('x1');
    await service.setShared('x2');
    expect(await service.countShared(), 2);
  });

  test('syncFeedJokes creates new row with feed data', () async {
    final joke = Joke(
      id: 'joke-1',
      setupText: 'Setup text',
      punchlineText: 'Punchline text',
      setupImageUrl: 'https://example.com/setup.jpg',
      punchlineImageUrl: 'https://example.com/punchline.jpg',
    );

    final result = await service.syncFeedJokes(
      jokes: [(joke: joke, feedIndex: 0)],
    );
    expect(result, true);

    final interaction = await service.getJokeInteraction('joke-1');
    expect(interaction, isNotNull);
    expect(interaction!.jokeId, 'joke-1');
    expect(interaction.setupText, 'Setup text');
    expect(interaction.punchlineText, 'Punchline text');
    expect(interaction.setupImageUrl, 'https://example.com/setup.jpg');
    expect(interaction.punchlineImageUrl, 'https://example.com/punchline.jpg');
    expect(interaction.feedIndex, 0);
    expect(interaction.navigatedTimestamp, isNull);
    expect(interaction.viewedTimestamp, isNull);
    expect(interaction.savedTimestamp, isNull);
    expect(interaction.sharedTimestamp, isNull);
  });

  test('syncFeedJokes handles nullable image URLs', () async {
    final joke = Joke(
      id: 'joke-2',
      setupText: 'Setup',
      punchlineText: 'Punchline',
      setupImageUrl: null,
      punchlineImageUrl: null,
    );

    await service.syncFeedJokes(jokes: [(joke: joke, feedIndex: 1)]);

    final interaction = await service.getJokeInteraction('joke-2');
    expect(interaction, isNotNull);
    expect(interaction!.setupImageUrl, isNull);
    expect(interaction.punchlineImageUrl, isNull);
    expect(interaction.feedIndex, 1);
  });

  test('syncFeedJokes preserves existing interaction timestamps', () async {
    // First, set interaction timestamps
    await service.setNavigated('joke-3');
    await service.setViewed('joke-3');
    await service.setSaved('joke-3');
    await service.setShared('joke-3');

    final beforeSync = await service.getJokeInteraction('joke-3');
    expect(beforeSync, isNotNull);
    final navigatedBefore = beforeSync!.navigatedTimestamp;
    final viewedBefore = beforeSync.viewedTimestamp;
    final savedBefore = beforeSync.savedTimestamp;
    final sharedBefore = beforeSync.sharedTimestamp;

    // Sync feed data
    final updatedJoke = Joke(
      id: 'joke-3',
      setupText: 'Updated setup',
      punchlineText: 'Updated punchline',
      setupImageUrl: 'https://example.com/setup.jpg',
      punchlineImageUrl: 'https://example.com/punchline.jpg',
    );

    await service.syncFeedJokes(jokes: [(joke: updatedJoke, feedIndex: 5)]);

    final afterSync = await service.getJokeInteraction('joke-3');
    expect(afterSync, isNotNull);
    expect(afterSync!.navigatedTimestamp, navigatedBefore);
    expect(afterSync.viewedTimestamp, viewedBefore);
    expect(afterSync.savedTimestamp, savedBefore);
    expect(afterSync.sharedTimestamp, sharedBefore);
    expect(afterSync.setupText, 'Updated setup');
    expect(afterSync.punchlineText, 'Updated punchline');
    expect(afterSync.setupImageUrl, 'https://example.com/setup.jpg');
    expect(afterSync.punchlineImageUrl, 'https://example.com/punchline.jpg');
    expect(afterSync.feedIndex, 5);
  });

  test('syncFeedJokes updates feed data for existing jokes', () async {
    final joke1 = Joke(
      id: 'joke-4',
      setupText: 'First setup',
      punchlineText: 'First punchline',
    );

    await service.syncFeedJokes(jokes: [(joke: joke1, feedIndex: 10)]);

    final joke2 = Joke(
      id: 'joke-4',
      setupText: 'Second setup',
      punchlineText: 'Second punchline',
      setupImageUrl: 'https://example.com/new-setup.jpg',
    );

    await service.syncFeedJokes(jokes: [(joke: joke2, feedIndex: 20)]);

    final interaction = await service.getJokeInteraction('joke-4');
    expect(interaction, isNotNull);
    expect(interaction!.setupText, 'Second setup');
    expect(interaction.punchlineText, 'Second punchline');
    expect(interaction.setupImageUrl, 'https://example.com/new-setup.jpg');
    expect(interaction.feedIndex, 20);
  });

  test('syncFeedJokes updates lastUpdateTimestamp', () async {
    final joke = Joke(
      id: 'joke-5',
      setupText: 'Setup',
      punchlineText: 'Punchline',
    );

    await service.syncFeedJokes(jokes: [(joke: joke, feedIndex: 0)]);

    final interaction1 = await service.getJokeInteraction('joke-5');
    expect(interaction1, isNotNull);
    final timestamp1 = interaction1!.lastUpdateTimestamp;

    await Future<void>.delayed(const Duration(milliseconds: 50));

    await service.syncFeedJokes(jokes: [(joke: joke, feedIndex: 1)]);

    final interaction2 = await service.getJokeInteraction('joke-5');
    expect(interaction2, isNotNull);
    final timestamp2 = interaction2!.lastUpdateTimestamp;
    expect(
      timestamp2.isAfter(timestamp1) || timestamp2.isAtSameMomentAs(timestamp1),
      true,
    );
  });

  test('syncFeedJokes handles multiple jokes in batch', () async {
    final joke1 = Joke(
      id: 'joke-6',
      setupText: 'Setup 1',
      punchlineText: 'Punchline 1',
    );
    final joke2 = Joke(
      id: 'joke-7',
      setupText: 'Setup 2',
      punchlineText: 'Punchline 2',
    );
    final joke3 = Joke(
      id: 'joke-8',
      setupText: 'Setup 3',
      punchlineText: 'Punchline 3',
    );

    await service.syncFeedJokes(
      jokes: [
        (joke: joke1, feedIndex: 0),
        (joke: joke2, feedIndex: 1),
        (joke: joke3, feedIndex: 2),
      ],
    );

    final interaction1 = await service.getJokeInteraction('joke-6');
    expect(interaction1, isNotNull);
    expect(interaction1!.feedIndex, 0);

    final interaction2 = await service.getJokeInteraction('joke-7');
    expect(interaction2, isNotNull);
    expect(interaction2!.feedIndex, 1);

    final interaction3 = await service.getJokeInteraction('joke-8');
    expect(interaction3, isNotNull);
    expect(interaction3!.feedIndex, 2);
  });

  test('syncFeedJokes handles empty list', () async {
    final result = await service.syncFeedJokes(jokes: []);
    expect(result, true);
  });

  group('getFeedJokeInteractions', () {
    test(
      'returns jokes ordered by feedIndex ascending when no cursor provided',
      () async {
        final joke1 = Joke(
          id: 'joke-1',
          setupText: 'Setup 1',
          punchlineText: 'Punchline 1',
        );
        final joke2 = Joke(
          id: 'joke-2',
          setupText: 'Setup 2',
          punchlineText: 'Punchline 2',
        );
        final joke3 = Joke(
          id: 'joke-3',
          setupText: 'Setup 3',
          punchlineText: 'Punchline 3',
        );

        await service.syncFeedJokes(
          jokes: [
            (joke: joke2, feedIndex: 2),
            (joke: joke1, feedIndex: 1),
            (joke: joke3, feedIndex: 3),
          ],
        );

        final interactions = await service.getFeedJokes(limit: 10);
        expect(interactions.length, 3);
        expect(interactions[0].jokeId, 'joke-1');
        expect(interactions[0].feedIndex, 1);
        expect(interactions[1].jokeId, 'joke-2');
        expect(interactions[1].feedIndex, 2);
        expect(interactions[2].jokeId, 'joke-3');
        expect(interactions[2].feedIndex, 3);
      },
    );

    test(
      'returns jokes starting after cursor feedIndex when cursor provided',
      () async {
        final joke1 = Joke(
          id: 'joke-1',
          setupText: 'Setup 1',
          punchlineText: 'Punchline 1',
        );
        final joke2 = Joke(
          id: 'joke-2',
          setupText: 'Setup 2',
          punchlineText: 'Punchline 2',
        );
        final joke3 = Joke(
          id: 'joke-3',
          setupText: 'Setup 3',
          punchlineText: 'Punchline 3',
        );
        final joke4 = Joke(
          id: 'joke-4',
          setupText: 'Setup 4',
          punchlineText: 'Punchline 4',
        );

        await service.syncFeedJokes(
          jokes: [
            (joke: joke1, feedIndex: 1),
            (joke: joke2, feedIndex: 2),
            (joke: joke3, feedIndex: 3),
            (joke: joke4, feedIndex: 4),
          ],
        );

        final interactions = await service.getFeedJokes(
          cursorFeedIndex: 2,
          limit: 10,
        );
        expect(interactions.length, 2);
        expect(interactions[0].jokeId, 'joke-3');
        expect(interactions[0].feedIndex, 3);
        expect(interactions[1].jokeId, 'joke-4');
        expect(interactions[1].feedIndex, 4);
      },
    );

    test('respects limit parameter correctly', () async {
      final jokes = List.generate(
        10,
        (i) => Joke(
          id: 'joke-$i',
          setupText: 'Setup $i',
          punchlineText: 'Punchline $i',
        ),
      );

      await service.syncFeedJokes(
        jokes: jokes
            .asMap()
            .entries
            .map((e) => (joke: e.value, feedIndex: e.key))
            .toList(),
      );

      final interactions = await service.getFeedJokes(limit: 5);
      expect(interactions.length, 5);
      expect(interactions[0].feedIndex, 0);
      expect(interactions[4].feedIndex, 4);
    });

    test('returns empty list when no jokes with feedIndex exist', () async {
      // Only add jokes without feedIndex (via setViewed)
      await service.setViewed('joke-1');
      await service.setSaved('joke-2');

      final interactions = await service.getFeedJokes(limit: 10);
      expect(interactions, isEmpty);
    });

    test('only returns jokes where feedIndex is not null', () async {
      final joke1 = Joke(
        id: 'joke-1',
        setupText: 'Setup 1',
        punchlineText: 'Punchline 1',
      );

      await service.syncFeedJokes(jokes: [(joke: joke1, feedIndex: 1)]);
      await service.setViewed('joke-2'); // This won't have feedIndex

      final interactions = await service.getFeedJokes(limit: 10);
      expect(interactions.length, 1);
      expect(interactions[0].jokeId, 'joke-1');
      expect(interactions[0].feedIndex, 1);
    });

    test('filters out jokes that have been viewed', () async {
      final joke1 = Joke(
        id: 'joke-1',
        setupText: 'Setup 1',
        punchlineText: 'Punchline 1',
      );
      final joke2 = Joke(
        id: 'joke-2',
        setupText: 'Setup 2',
        punchlineText: 'Punchline 2',
      );

      await service.syncFeedJokes(
        jokes: [(joke: joke1, feedIndex: 1), (joke: joke2, feedIndex: 2)],
      );

      await service.setViewed('joke-1');

      final interactions = await service.getFeedJokes(limit: 10);
      expect(interactions.length, 1);
      expect(interactions[0].jokeId, 'joke-2');
      expect(interactions[0].feedIndex, 2);
      expect(interactions[0].viewedTimestamp, isNull);
    });

    test(
      'handles pagination correctly (first page, subsequent pages)',
      () async {
        final jokes = List.generate(
          10,
          (i) => Joke(
            id: 'joke-$i',
            setupText: 'Setup $i',
            punchlineText: 'Punchline $i',
          ),
        );

        await service.syncFeedJokes(
          jokes: jokes
              .asMap()
              .entries
              .map((e) => (joke: e.value, feedIndex: e.key))
              .toList(),
        );

        // First page
        final page1 = await service.getFeedJokes(limit: 3);
        expect(page1.length, 3);
        expect(page1[0].feedIndex, 0);
        expect(page1[2].feedIndex, 2);

        // Second page
        final page2 = await service.getFeedJokes(cursorFeedIndex: 2, limit: 3);
        expect(page2.length, 3);
        expect(page2[0].feedIndex, 3);
        expect(page2[2].feedIndex, 5);
      },
    );

    test('empty database returns empty list', () async {
      final interactions = await service.getFeedJokes(limit: 10);
      expect(interactions, isEmpty);
    });

    test('cursor at end of data returns empty list', () async {
      final joke = Joke(
        id: 'joke-1',
        setupText: 'Setup',
        punchlineText: 'Punchline',
      );
      await service.syncFeedJokes(jokes: [(joke: joke, feedIndex: 1)]);

      final interactions = await service.getFeedJokes(
        cursorFeedIndex: 1,
        limit: 10,
      );
      expect(interactions, isEmpty);
    });

    test('cursor beyond maximum feedIndex returns empty list', () async {
      final joke = Joke(
        id: 'joke-1',
        setupText: 'Setup',
        punchlineText: 'Punchline',
      );
      await service.syncFeedJokes(jokes: [(joke: joke, feedIndex: 1)]);

      final interactions = await service.getFeedJokes(
        cursorFeedIndex: 10,
        limit: 10,
      );
      expect(interactions, isEmpty);
    });

    test('limit of 0 returns empty list', () async {
      final joke = Joke(
        id: 'joke-1',
        setupText: 'Setup',
        punchlineText: 'Punchline',
      );
      await service.syncFeedJokes(jokes: [(joke: joke, feedIndex: 1)]);

      final interactions = await service.getFeedJokes(limit: 0);
      expect(interactions, isEmpty);
    });

    test('limit larger than available jokes returns all available', () async {
      final joke1 = Joke(
        id: 'joke-1',
        setupText: 'Setup 1',
        punchlineText: 'Punchline 1',
      );
      final joke2 = Joke(
        id: 'joke-2',
        setupText: 'Setup 2',
        punchlineText: 'Punchline 2',
      );

      await service.syncFeedJokes(
        jokes: [(joke: joke1, feedIndex: 1), (joke: joke2, feedIndex: 2)],
      );

      final interactions = await service.getFeedJokes(limit: 10);
      expect(interactions.length, 2);
    });

    test('jokes with same feedIndex are handled deterministically', () async {
      // This shouldn't happen in practice, but test the behavior
      final joke1 = Joke(
        id: 'joke-a',
        setupText: 'Setup 1',
        punchlineText: 'Punchline 1',
      );
      final joke2 = Joke(
        id: 'joke-b',
        setupText: 'Setup 2',
        punchlineText: 'Punchline 2',
      );

      await service.syncFeedJokes(
        jokes: [(joke: joke2, feedIndex: 1), (joke: joke1, feedIndex: 1)],
      );

      final interactions = await service.getFeedJokes(limit: 10);
      expect(interactions.length, 2);
      // Should be ordered by jokeId as secondary sort
      expect(interactions[0].jokeId, 'joke-a');
      expect(interactions[1].jokeId, 'joke-b');
    });

    test('very large feedIndex values handled correctly', () async {
      final joke = Joke(
        id: 'joke-1',
        setupText: 'Setup',
        punchlineText: 'Punchline',
      );
      await service.syncFeedJokes(jokes: [(joke: joke, feedIndex: 999999)]);

      final interactions = await service.getFeedJokes(limit: 10);
      expect(interactions.length, 1);
      expect(interactions[0].feedIndex, 999999);
    });
  });
}
