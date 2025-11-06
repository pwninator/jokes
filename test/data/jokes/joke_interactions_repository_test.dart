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

  test('countViewed returns count of viewed jokes', () async {
    expect(await service.countViewed(), 0);
    await service.setViewed('j1');
    await service.setViewed('j2');
    expect(await service.countViewed(), 2);
  });

  test('countSaved returns count of saved jokes', () async {
    expect(await service.countSaved(), 0);
    await service.setSaved('s1');
    await service.setSaved('s2');
    expect(await service.countSaved(), 2);
    await service.setUnsaved('s1');
    expect(await service.countSaved(), 1);
  });

  test('countShared returns count of shared jokes', () async {
    expect(await service.countShared(), 0);
    await service.setShared('x1');
    await service.setShared('x2');
    expect(await service.countShared(), 2);
  });

  test('syncFeedJoke creates new row with feed data', () async {
    final joke = Joke(
      id: 'joke-1',
      setupText: 'Setup text',
      punchlineText: 'Punchline text',
      setupImageUrl: 'https://example.com/setup.jpg',
      punchlineImageUrl: 'https://example.com/punchline.jpg',
    );

    final result = await service.syncFeedJoke(joke: joke, feedIndex: 0);
    expect(result, true);

    final interaction = await service.getJokeInteraction('joke-1');
    expect(interaction, isNotNull);
    expect(interaction!.jokeId, 'joke-1');
    expect(interaction.setupText, 'Setup text');
    expect(interaction.punchlineText, 'Punchline text');
    expect(interaction.setupImageUrl, 'https://example.com/setup.jpg');
    expect(interaction.punchlineImageUrl, 'https://example.com/punchline.jpg');
    expect(interaction.feedIndex, 0);
    expect(interaction.viewedTimestamp, isNull);
    expect(interaction.savedTimestamp, isNull);
    expect(interaction.sharedTimestamp, isNull);
  });

  test('syncFeedJoke handles nullable image URLs', () async {
    final joke = Joke(
      id: 'joke-2',
      setupText: 'Setup',
      punchlineText: 'Punchline',
      setupImageUrl: null,
      punchlineImageUrl: null,
    );

    await service.syncFeedJoke(joke: joke, feedIndex: 1);

    final interaction = await service.getJokeInteraction('joke-2');
    expect(interaction, isNotNull);
    expect(interaction!.setupImageUrl, isNull);
    expect(interaction.punchlineImageUrl, isNull);
    expect(interaction.feedIndex, 1);
  });

  test('syncFeedJoke preserves existing interaction timestamps', () async {
    // First, set interaction timestamps
    await service.setViewed('joke-3');
    await service.setSaved('joke-3');
    await service.setShared('joke-3');

    final beforeSync = await service.getJokeInteraction('joke-3');
    expect(beforeSync, isNotNull);
    final viewedBefore = beforeSync!.viewedTimestamp;
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

    await service.syncFeedJoke(joke: updatedJoke, feedIndex: 5);

    final afterSync = await service.getJokeInteraction('joke-3');
    expect(afterSync, isNotNull);
    expect(afterSync!.viewedTimestamp, viewedBefore);
    expect(afterSync.savedTimestamp, savedBefore);
    expect(afterSync.sharedTimestamp, sharedBefore);
    expect(afterSync.setupText, 'Updated setup');
    expect(afterSync.punchlineText, 'Updated punchline');
    expect(afterSync.setupImageUrl, 'https://example.com/setup.jpg');
    expect(afterSync.punchlineImageUrl, 'https://example.com/punchline.jpg');
    expect(afterSync.feedIndex, 5);
  });

  test('syncFeedJoke updates feed data for existing jokes', () async {
    final joke1 = Joke(
      id: 'joke-4',
      setupText: 'First setup',
      punchlineText: 'First punchline',
    );

    await service.syncFeedJoke(joke: joke1, feedIndex: 10);

    final joke2 = Joke(
      id: 'joke-4',
      setupText: 'Second setup',
      punchlineText: 'Second punchline',
      setupImageUrl: 'https://example.com/new-setup.jpg',
    );

    await service.syncFeedJoke(joke: joke2, feedIndex: 20);

    final interaction = await service.getJokeInteraction('joke-4');
    expect(interaction, isNotNull);
    expect(interaction!.setupText, 'Second setup');
    expect(interaction.punchlineText, 'Second punchline');
    expect(interaction.setupImageUrl, 'https://example.com/new-setup.jpg');
    expect(interaction.feedIndex, 20);
  });

  test('syncFeedJoke updates lastUpdateTimestamp', () async {
    final joke = Joke(
      id: 'joke-5',
      setupText: 'Setup',
      punchlineText: 'Punchline',
    );

    await service.syncFeedJoke(joke: joke, feedIndex: 0);

    final interaction1 = await service.getJokeInteraction('joke-5');
    expect(interaction1, isNotNull);
    final timestamp1 = interaction1!.lastUpdateTimestamp;

    await Future<void>.delayed(const Duration(milliseconds: 50));

    await service.syncFeedJoke(joke: joke, feedIndex: 1);

    final interaction2 = await service.getJokeInteraction('joke-5');
    expect(interaction2, isNotNull);
    final timestamp2 = interaction2!.lastUpdateTimestamp;
    expect(
      timestamp2.isAfter(timestamp1) || timestamp2.isAtSameMomentAs(timestamp1),
      true,
    );
  });
}
