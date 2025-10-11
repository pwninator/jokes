import 'package:drift/drift.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';

part 'joke_interactions_service.g.dart';

@Riverpod(keepAlive: true)
JokeInteractionsService jokeInteractionsService(Ref ref) {
  final perf = ref.read(performanceServiceProvider);
  final db = ref.read(appDatabaseProvider);
  final service = JokeInteractionsService(performanceService: perf, db: db);
  return service;
}

class JokeInteractionsService {
  JokeInteractionsService({
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

  Future<bool> setSaved(String jokeId) async => runWithTrace(
    name: TraceName.driftSetInteraction,
    traceKey: 'saved',
    body: () async {
      final now = DateTime.now();
      await _db
          .into(_db.jokeInteractions)
          .insertOnConflictUpdate(
            JokeInteractionsCompanion.insert(
              jokeId: jokeId,
              savedTimestamp: Value(now),
              lastUpdateTimestamp: now,
            ),
          );
      return true;
    },
    fallback: false,
    perf: _perf,
  );

  Future<bool> setShared(String jokeId) async => runWithTrace(
    name: TraceName.driftSetInteraction,
    traceKey: 'shared',
    body: () async {
      final now = DateTime.now();
      await _db
          .into(_db.jokeInteractions)
          .insertOnConflictUpdate(
            JokeInteractionsCompanion.insert(
              jokeId: jokeId,
              sharedTimestamp: Value(now),
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
}
