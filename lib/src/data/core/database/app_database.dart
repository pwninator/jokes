import 'package:drift/drift.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';

import 'app_database_platform.dart' as platform;

part 'app_database.g.dart';

@Riverpod(keepAlive: true)
AppDatabase appDatabase(Ref ref) {
  throw StateError(
    'AppDatabase must be overridden. If this is a data repository test, you should override with an in-memory database. If this is a test of a higher level component, you should mock the repository/service instead.',
  );
}

// Drift table for joke interactions
@TableIndex(name: 'idx_last_update_timestamp', columns: {#lastUpdateTimestamp})
@TableIndex(name: 'idx_feed_index', columns: {#feedIndex})
class JokeInteractions extends Table {
  // Primary key: one row per joke
  TextColumn get jokeId => text()();

  // Nullable interaction timestamps
  DateTimeColumn get viewedTimestamp => dateTime().nullable()();
  DateTimeColumn get savedTimestamp => dateTime().nullable()();
  DateTimeColumn get sharedTimestamp => dateTime().nullable()();

  // Last updated timestamp (required)
  DateTimeColumn get lastUpdateTimestamp => dateTime()();

  // Feed joke content (nullable)
  TextColumn get setupText => text().nullable()();
  TextColumn get punchlineText => text().nullable()();
  TextColumn get setupImageUrl => text().nullable()();
  TextColumn get punchlineImageUrl => text().nullable()();

  // Feed index (nullable, for jokes added later)
  IntColumn get feedIndex => integer().nullable()();

  @override
  Set<Column<Object>>? get primaryKey => {jokeId};
}

// Drift table for category interactions (one row per category)
@TableIndex(name: 'idx_category_last_update', columns: {#lastUpdateTimestamp})
class CategoryInteractions extends Table {
  // Primary key: one row per category
  TextColumn get categoryId => text()();

  // Nullable viewed timestamp
  DateTimeColumn get viewedTimestamp => dateTime().nullable()();

  // Last updated timestamp (required)
  DateTimeColumn get lastUpdateTimestamp => dateTime()();

  @override
  Set<Column<Object>>? get primaryKey => {categoryId};
}

@DriftDatabase(tables: [JokeInteractions, CategoryInteractions])
class AppDatabase extends _$AppDatabase {
  AppDatabase._internal(super.e);

  static AppDatabase? _instance;

  static AppDatabase get instance {
    final existing = _instance;
    if (existing == null) {
      throw StateError(
        'AppDatabase.initialize() must be called before accessing instance.',
      );
    }
    return existing;
  }

  static Future<void> initialize() async {
    if (_instance != null) return;
    final executor = await platform.openExecutor();
    _instance = AppDatabase._internal(executor);
  }

  @override
  int get schemaVersion => 4;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (m) async => m.createAll(),
    onUpgrade: (m, from, to) async {
      if (from < 2) {
        await m.addColumn(
          jokeInteractions,
          jokeInteractions.lastUpdateTimestamp,
        );
        // Backfill existing rows with current timestamp
        final nowIso = DateTime.now().toIso8601String();
        await customStatement(
          'UPDATE joke_interactions SET last_update_timestamp = ?',
          [nowIso],
        );
      }
      if (from < 3) {
        await m.createTable(categoryInteractions);
      }
      if (from < 4) {
        await m.addColumn(jokeInteractions, jokeInteractions.setupText);
        await m.addColumn(jokeInteractions, jokeInteractions.punchlineText);
        await m.addColumn(jokeInteractions, jokeInteractions.setupImageUrl);
        await m.addColumn(jokeInteractions, jokeInteractions.punchlineImageUrl);
        await m.addColumn(jokeInteractions, jokeInteractions.feedIndex);
      }
    },
  );

  // For tests
  static AppDatabase inMemory() =>
      AppDatabase._internal(platform.inMemoryExecutor());
}

/// Shared helper for running DB operations within a performance trace
Future<T> runWithTrace<T>({
  required TraceName name,
  String? traceKey,
  required Future<T> Function() body,
  required T fallback,
  required PerformanceService perf,
}) async {
  perf.startNamedTrace(name: name, key: traceKey);
  try {
    return await body();
  } catch (e) {
    AppLogger.fatal("APP_DATABASE: $name (${traceKey ?? ''}) failed: $e");
    return fallback;
  } finally {
    perf.stopNamedTrace(name: name, key: traceKey);
  }
}
