import 'package:drift/drift.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';

part 'category_interactions_service.g.dart';

@Riverpod(keepAlive: true)
CategoryInteractionsService categoryInteractionsService(Ref ref) {
  final perf = ref.read(performanceServiceProvider);
  final db = ref.read(appDatabaseProvider);
  final service = CategoryInteractionsService(performanceService: perf, db: db);
  return service;
}

class CategoryInteractionsService {
  CategoryInteractionsService({
    required PerformanceService performanceService,
    required AppDatabase db,
  }) : _perf = performanceService,
       _db = db;

  final PerformanceService _perf;
  final AppDatabase _db;

  Future<bool> setViewed(String categoryId) async => runWithTrace(
    perf: _perf,
    name: TraceName.driftSetInteraction,
    traceKey: 'category_viewed',
    body: () async {
      final now = DateTime.now();
      await _db
          .into(_db.categoryInteractions)
          .insertOnConflictUpdate(
            CategoryInteractionsCompanion.insert(
              categoryId: categoryId,
              viewedTimestamp: Value(now),
              lastUpdateTimestamp: now,
            ),
          );
      return true;
    },
    fallback: false,
  );
}
