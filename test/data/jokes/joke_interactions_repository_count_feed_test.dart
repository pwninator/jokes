import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:drift/drift.dart';

class _NoopPerformanceService extends PerformanceService {
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
  late JokeInteractionsRepository repo;

  setUp(() {
    db = AppDatabase.inMemory();
    repo = JokeInteractionsRepository(
      performanceService: _NoopPerformanceService(),
      db: db,
    );
  });

  tearDown(() async {
    await db.close();
  });

  test('countFeedJokes returns 0 for empty DB', () async {
    final count = await repo.countFeedJokes();
    expect(count, 0);
  });

  test('countFeedJokes counts rows with non-null feedIndex', () async {
    final now = DateTime.now();
    await db
        .into(db.jokeInteractions)
        .insert(
          JokeInteractionsCompanion.insert(
            jokeId: 'j1',
            lastUpdateTimestamp: now,
            feedIndex: const Value(0),
          ),
        );
    await db
        .into(db.jokeInteractions)
        .insert(
          JokeInteractionsCompanion.insert(
            jokeId: 'j2',
            lastUpdateTimestamp: now,
            feedIndex: const Value(1),
          ),
        );
    // Row with null feedIndex should not be counted
    await db
        .into(db.jokeInteractions)
        .insert(
          JokeInteractionsCompanion.insert(
            jokeId: 'j3',
            lastUpdateTimestamp: now,
          ),
        );

    final count = await repo.countFeedJokes();
    expect(count, 2);
  });
}
