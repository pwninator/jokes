import 'package:drift/drift.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

part 'joke_interactions_repository.g.dart';

@Riverpod(keepAlive: true)
JokeInteractionsRepository jokeInteractionsRepository(Ref ref) {
  final perf = ref.read(performanceServiceProvider);
  final db = ref.read(appDatabaseProvider);
  final service = JokeInteractionsRepository(performanceService: perf, db: db);
  return service;
}

class JokeInteractionsRepository {
  JokeInteractionsRepository({
    required PerformanceService performanceService,
    required AppDatabase db,
  }) : _perf = performanceService,
       _db = db;

  final PerformanceService _perf;
  final AppDatabase _db;

  Future<bool> setViewed(String jokeId) async => runWithTrace(
    name: TraceName.driftSetInteraction,
    traceKey: 'viewed',
    body: () async {
      final now = DateTime.now();
      await _db
          .into(_db.jokeInteractions)
          .insertOnConflictUpdate(
            JokeInteractionsCompanion.insert(
              jokeId: jokeId,
              viewedTimestamp: Value(now),
              lastUpdateTimestamp: now,
            ),
          );
      return true;
    },
    fallback: false,
    perf: _perf,
  );

  Future<bool> setSaved(String jokeId) async {
    return setSavedAt(jokeId, DateTime.now());
  }

  /// Set saved at a specific timestamp (used for migrations)
  Future<bool> setSavedAt(String jokeId, DateTime at) async => runWithTrace(
    name: TraceName.driftSetInteraction,
    traceKey: 'saved',
    body: () async {
      final now = DateTime.now();
      await _db
          .into(_db.jokeInteractions)
          .insertOnConflictUpdate(
            JokeInteractionsCompanion.insert(
              jokeId: jokeId,
              savedTimestamp: Value(at),
              lastUpdateTimestamp: now,
            ),
          );
      return true;
    },
    fallback: false,
    perf: _perf,
  );

  Future<bool> setShared(String jokeId) async {
    return setSharedAt(jokeId, DateTime.now());
  }

  /// Set shared at a specific timestamp (used for migrations)
  Future<bool> setSharedAt(String jokeId, DateTime at) async => runWithTrace(
    name: TraceName.driftSetInteraction,
    traceKey: 'shared',
    body: () async {
      final now = DateTime.now();
      await _db
          .into(_db.jokeInteractions)
          .insertOnConflictUpdate(
            JokeInteractionsCompanion.insert(
              jokeId: jokeId,
              sharedTimestamp: Value(at),
              lastUpdateTimestamp: now,
            ),
          );
      return true;
    },
    fallback: false,
    perf: _perf,
  );

  Future<bool> setUnsaved(String jokeId) async => runWithTrace(
    name: TraceName.driftSetInteraction,
    traceKey: 'unsaved',
    body: () async {
      final now = DateTime.now();
      await _db
          .into(_db.jokeInteractions)
          .insertOnConflictUpdate(
            JokeInteractionsCompanion.insert(
              jokeId: jokeId,
              savedTimestamp: const Value(null),
              lastUpdateTimestamp: now,
            ),
          );
      return true;
    },
    fallback: false,
    perf: _perf,
  );

  Future<List<JokeInteraction>> getViewedJokeInteractions() async =>
      runWithTrace(
        name: TraceName.driftGetViewedJokeInteractions,
        body: () async {
          final query = _db.select(_db.jokeInteractions)
            ..where((tbl) => tbl.viewedTimestamp.isNotNull())
            ..orderBy([
              (t) => OrderingTerm(
                expression: t.viewedTimestamp,
                mode: OrderingMode.asc,
              ),
            ]);
          return await query.get();
        },
        fallback: <JokeInteraction>[],
        perf: _perf,
      );

  Future<List<JokeInteraction>> getSavedJokeInteractions() async =>
      runWithTrace(
        name: TraceName.driftGetSavedJokeInteractions,
        body: () async {
          final query = _db.select(_db.jokeInteractions)
            ..where((tbl) => tbl.savedTimestamp.isNotNull())
            ..orderBy([
              (t) => OrderingTerm(
                expression: t.savedTimestamp,
                mode: OrderingMode.asc,
              ),
            ]);
          return await query.get();
        },
        fallback: <JokeInteraction>[],
        perf: _perf,
      );

  Future<List<JokeInteraction>> getSharedJokeInteractions() async =>
      runWithTrace(
        name: TraceName.driftGetSharedJokeInteractions,
        body: () async {
          final query = _db.select(_db.jokeInteractions)
            ..where((tbl) => tbl.sharedTimestamp.isNotNull())
            ..orderBy([
              (t) => OrderingTerm(
                expression: t.sharedTimestamp,
                mode: OrderingMode.asc,
              ),
            ]);
          return await query.get();
        },
        fallback: <JokeInteraction>[],
        perf: _perf,
      );

  Future<List<JokeInteraction>> getAllJokeInteractions() async => runWithTrace(
    name: TraceName.driftGetAllJokeInteractions,
    traceKey: 'all_interactions',
    body: () async {
      return await _db.select(_db.jokeInteractions).get();
    },
    fallback: <JokeInteraction>[],
    perf: _perf,
  );

  Future<List<JokeInteraction>> getJokeInteractions(
    List<String> jokeIds,
  ) async => runWithTrace(
    name: TraceName.driftGetInteraction,
    traceKey: 'joke_interactions_batch',
    body: () async {
      if (jokeIds.isEmpty) return <JokeInteraction>[];
      final query = _db.select(_db.jokeInteractions)
        ..where((tbl) => tbl.jokeId.isIn(jokeIds));
      return await query.get();
    },
    fallback: <JokeInteraction>[],
    perf: _perf,
  );

  Future<JokeInteraction?> getJokeInteraction(String jokeId) async {
    final interactions = await getJokeInteractions([jokeId]);
    return interactions.isEmpty ? null : interactions.first;
  }

  Future<bool> isJokeSaved(String jokeId) async {
    JokeInteraction? interaction = await getJokeInteraction(jokeId);
    return interaction?.savedTimestamp != null;
  }

  Future<bool> isJokeShared(String jokeId) async {
    JokeInteraction? interaction = await getJokeInteraction(jokeId);
    return interaction?.sharedTimestamp != null;
  }

  /// Watch a single joke interaction row and emit updates reactively
  Stream<JokeInteraction?> watchJokeInteraction(String jokeId) {
    final query = _db.select(_db.jokeInteractions)
      ..where((tbl) => tbl.jokeId.equals(jokeId));
    return query.watchSingleOrNull();
  }

  /// Count jokes that have been viewed at least once
  Future<int> countViewed() async => runWithTrace(
    name: TraceName.driftGetInteractionCount,
    traceKey: 'count_viewed',
    body: () async {
      final query = _db.selectOnly(_db.jokeInteractions)
        ..addColumns([_db.jokeInteractions.jokeId.count()])
        ..where(_db.jokeInteractions.viewedTimestamp.isNotNull());
      final result = await query.getSingle();
      return result.read(_db.jokeInteractions.jokeId.count()) ?? 0;
    },
    fallback: 0,
    perf: _perf,
  );

  /// Count jokes that are currently saved
  Future<int> countSaved() async => runWithTrace(
    name: TraceName.driftGetInteractionCount,
    traceKey: 'count_saved',
    body: () async {
      final query = _db.selectOnly(_db.jokeInteractions)
        ..addColumns([_db.jokeInteractions.jokeId.count()])
        ..where(_db.jokeInteractions.savedTimestamp.isNotNull());
      final result = await query.getSingle();
      return result.read(_db.jokeInteractions.jokeId.count()) ?? 0;
    },
    fallback: 0,
    perf: _perf,
  );

  /// Count jokes that have been shared at least once
  Future<int> countShared() async => runWithTrace(
    name: TraceName.driftGetInteractionCount,
    traceKey: 'count_shared',
    body: () async {
      final query = _db.selectOnly(_db.jokeInteractions)
        ..addColumns([_db.jokeInteractions.jokeId.count()])
        ..where(_db.jokeInteractions.sharedTimestamp.isNotNull());
      final result = await query.getSingle();
      return result.read(_db.jokeInteractions.jokeId.count()) ?? 0;
    },
    fallback: 0,
    perf: _perf,
  );

  /// Sync feed jokes to local database in a single batch transaction.
  ///
  /// Updates the feed-related columns (setupText, punchlineText, setupImageUrl,
  /// punchlineImageUrl, feedIndex) while preserving viewedTimestamp, savedTimestamp,
  /// and sharedTimestamp if they already exist.
  Future<bool> syncFeedJokes({
    required List<({Joke joke, int feedIndex})> jokes,
  }) async => runWithTrace(
    name: TraceName.driftSetInteraction,
    traceKey: 'sync_feed_jokes_batch',
    body: () async {
      if (jokes.isEmpty) return true;

      final now = DateTime.now();
      await _db.transaction(() async {
        for (final entry in jokes) {
          await _db
              .into(_db.jokeInteractions)
              .insertOnConflictUpdate(
                JokeInteractionsCompanion(
                  jokeId: Value(entry.joke.id),
                  setupText: Value(entry.joke.setupText),
                  punchlineText: Value(entry.joke.punchlineText),
                  setupImageUrl: Value(entry.joke.setupImageUrl),
                  punchlineImageUrl: Value(entry.joke.punchlineImageUrl),
                  feedIndex: Value(entry.feedIndex),
                  lastUpdateTimestamp: Value(now),
                  viewedTimestamp: const Value.absent(),
                  savedTimestamp: const Value.absent(),
                  sharedTimestamp: const Value.absent(),
                ),
              );
        }
      });
      return true;
    },
    fallback: false,
    perf: _perf,
  );

  /// Get feed jokes ordered by feedIndex with cursor-based pagination.
  ///
  /// Returns jokes where feedIndex is not null, ordered by feedIndex ascending.
  /// [cursorFeedIndex] is the feedIndex to start after (exclusive). If null, starts from the beginning.
  /// [limit] is the maximum number of results to return.
  Future<List<JokeInteraction>> getFeedJokes({
    int? cursorFeedIndex,
    required int limit,
  }) async => runWithTrace(
    name: TraceName.driftGetAllJokeInteractions,
    traceKey: 'feed_jokes',
    body: () async {
      if (limit <= 0) return <JokeInteraction>[];

      final query = _db.select(_db.jokeInteractions);
      query.where(
        (tbl) => tbl.feedIndex.isNotNull() & tbl.viewedTimestamp.isNull(),
      );

      if (cursorFeedIndex != null) {
        query.where((tbl) => tbl.feedIndex.isBiggerThanValue(cursorFeedIndex));
      }

      query
        ..orderBy([
          (t) => OrderingTerm(expression: t.feedIndex, mode: OrderingMode.asc),
          (t) => OrderingTerm(expression: t.jokeId, mode: OrderingMode.asc),
        ])
        ..limit(limit);

      return await query.get();
    },
    fallback: <JokeInteraction>[],
    perf: _perf,
  );

  /// Watch the leading portion of the feed-ordered joke interactions.
  Stream<List<JokeInteraction>> watchFeedHead({required int limit}) {
    assert(limit > 0, 'watchFeedHead limit must be positive');
    final query = _db.select(_db.jokeInteractions)
      ..where((tbl) => tbl.feedIndex.isNotNull())
      ..orderBy([
        (t) => OrderingTerm(expression: t.feedIndex, mode: OrderingMode.asc),
        (t) => OrderingTerm(expression: t.jokeId, mode: OrderingMode.asc),
      ])
      ..limit(limit);
    return query.watch();
  }
}
