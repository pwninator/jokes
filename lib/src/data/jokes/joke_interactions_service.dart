import 'package:drift/drift.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/providers/app_providers.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';

part 'joke_interactions_service.g.dart';

@Riverpod(keepAlive: true)
Future<JokeInteractionsService> jokeInteractionsService(Ref ref) async {
  final perf = ref.watch(performanceServiceProvider);
  final db = await ref.read(appDatabaseProvider.future);
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

  Future<T> _runTrace<T>({
    required TraceName name,
    String? key,
    required Future<T> Function() body,
    required T fallback,
  }) async {
    _perf.startNamedTrace(name: name, key: key);
    try {
      return await body();
    } catch (e) {
      AppLogger.fatal("JokeInteractionService '$name ($key) failed: $e");
      return fallback;
    } finally {
      _perf.stopNamedTrace(name: name, key: key);
    }
  }

  Future<bool> setViewed(String jokeId) async => _runTrace(
    name: TraceName.driftSetInteraction,
    key: 'viewed',
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
  );

  Future<bool> setSaved(String jokeId) async => _runTrace(
    name: TraceName.driftSetInteraction,
    key: 'saved',
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
  );

  Future<bool> setShared(String jokeId) async => _runTrace(
    name: TraceName.driftSetInteraction,
    key: 'shared',
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
  );

  Future<bool> setUnsaved(String jokeId) async => _runTrace(
    name: TraceName.driftSetInteraction,
    key: 'unsaved',
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
  );

  Future<List<JokeInteraction>> getSavedJokeInteractions() async => _runTrace(
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
  );

  Future<List<JokeInteraction>> getAllJokeInteractions() async => _runTrace(
    name: TraceName.driftGetAllJokeInteractions,
    key: 'all_interactions',
    body: () async {
      return await _db.select(_db.jokeInteractions).get();
    },
    fallback: <JokeInteraction>[],
  );
}
