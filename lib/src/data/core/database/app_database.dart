import 'package:drift/drift.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'app_database_platform.dart' as platform;

part 'app_database.g.dart';

@Riverpod(keepAlive: true)
Future<AppDatabase> appDatabase(Ref ref) async {
  final executor = await platform.openExecutor();
  return AppDatabase._internal(executor);
}

// Drift table for joke interactions
@TableIndex(name: 'idx_last_update_timestamp', columns: {#lastUpdateTimestamp})
class JokeInteractions extends Table {
  // Primary key: one row per joke
  TextColumn get jokeId => text()();

  // Nullable interaction timestamps
  DateTimeColumn get viewedTimestamp => dateTime().nullable()();
  DateTimeColumn get savedTimestamp => dateTime().nullable()();
  DateTimeColumn get sharedTimestamp => dateTime().nullable()();

  // Last updated timestamp (required)
  DateTimeColumn get lastUpdateTimestamp => dateTime()();

  @override
  Set<Column<Object>>? get primaryKey => {jokeId};
}

@DriftDatabase(tables: [JokeInteractions])
class AppDatabase extends _$AppDatabase {
  AppDatabase._internal(super.e);

  @override
  int get schemaVersion => 2;

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
    },
  );

  // For tests
  static AppDatabase inMemory() =>
      AppDatabase._internal(platform.inMemoryExecutor());
}
