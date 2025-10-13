import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';

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
    service = JokeInteractionsRepository(performanceService: _NoopPerf(), db: db);
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
}
