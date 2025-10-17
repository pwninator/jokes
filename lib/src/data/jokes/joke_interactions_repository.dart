import 'package:drift/drift.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';

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

  Future<List<JokeInteraction>> getAllJokeInteractions() async => runWithTrace(
    name: TraceName.driftGetAllJokeInteractions,
    traceKey: 'all_interactions',
    body: () async {
      return await _db.select(_db.jokeInteractions).get();
    },
    fallback: <JokeInteraction>[],
    perf: _perf,
  );

  Future<JokeInteraction?> getJokeInteraction(String jokeId) async =>
      runWithTrace(
        name: TraceName.driftGetInteraction,
        traceKey: 'joke_interaction',
        body: () async {
          final query = _db.select(_db.jokeInteractions)
            ..where((tbl) => tbl.jokeId.equals(jokeId));
          final rows = await query.get();
          if (rows.isEmpty) return null;
          return rows.first;
        },
        fallback: null,
        perf: _perf,
      );

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
      final query = _db.select(_db.jokeInteractions)
        ..where((tbl) => tbl.viewedTimestamp.isNotNull());
      final rows = await query.get();
      return rows.length;
    },
    fallback: 0,
    perf: _perf,
  );

  /// Count jokes that are currently saved
  Future<int> countSaved() async => runWithTrace(
    name: TraceName.driftGetInteractionCount,
    traceKey: 'count_saved',
    body: () async {
      final query = _db.select(_db.jokeInteractions)
        ..where((tbl) => tbl.savedTimestamp.isNotNull());
      final rows = await query.get();
      return rows.length;
    },
    fallback: 0,
    perf: _perf,
  );

  /// Count jokes that have been shared at least once
  Future<int> countShared() async => runWithTrace(
    name: TraceName.driftGetInteractionCount,
    traceKey: 'count_shared',
    body: () async {
      final query = _db.select(_db.jokeInteractions)
        ..where((tbl) => tbl.sharedTimestamp.isNotNull());
      final rows = await query.get();
      return rows.length;
    },
    fallback: 0,
    perf: _perf,
  );
}
