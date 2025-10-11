// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'app_database.dart';

// ignore_for_file: type=lint
class $JokeInteractionsTable extends JokeInteractions
    with TableInfo<$JokeInteractionsTable, JokeInteraction> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $JokeInteractionsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _jokeIdMeta = const VerificationMeta('jokeId');
  @override
  late final GeneratedColumn<String> jokeId = GeneratedColumn<String>(
    'joke_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _viewedTimestampMeta = const VerificationMeta(
    'viewedTimestamp',
  );
  @override
  late final GeneratedColumn<DateTime> viewedTimestamp =
      GeneratedColumn<DateTime>(
        'viewed_timestamp',
        aliasedName,
        true,
        type: DriftSqlType.dateTime,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _savedTimestampMeta = const VerificationMeta(
    'savedTimestamp',
  );
  @override
  late final GeneratedColumn<DateTime> savedTimestamp =
      GeneratedColumn<DateTime>(
        'saved_timestamp',
        aliasedName,
        true,
        type: DriftSqlType.dateTime,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _sharedTimestampMeta = const VerificationMeta(
    'sharedTimestamp',
  );
  @override
  late final GeneratedColumn<DateTime> sharedTimestamp =
      GeneratedColumn<DateTime>(
        'shared_timestamp',
        aliasedName,
        true,
        type: DriftSqlType.dateTime,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _lastUpdateTimestampMeta =
      const VerificationMeta('lastUpdateTimestamp');
  @override
  late final GeneratedColumn<DateTime> lastUpdateTimestamp =
      GeneratedColumn<DateTime>(
        'last_update_timestamp',
        aliasedName,
        false,
        type: DriftSqlType.dateTime,
        requiredDuringInsert: true,
      );
  @override
  List<GeneratedColumn> get $columns => [
    jokeId,
    viewedTimestamp,
    savedTimestamp,
    sharedTimestamp,
    lastUpdateTimestamp,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'joke_interactions';
  @override
  VerificationContext validateIntegrity(
    Insertable<JokeInteraction> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('joke_id')) {
      context.handle(
        _jokeIdMeta,
        jokeId.isAcceptableOrUnknown(data['joke_id']!, _jokeIdMeta),
      );
    } else if (isInserting) {
      context.missing(_jokeIdMeta);
    }
    if (data.containsKey('viewed_timestamp')) {
      context.handle(
        _viewedTimestampMeta,
        viewedTimestamp.isAcceptableOrUnknown(
          data['viewed_timestamp']!,
          _viewedTimestampMeta,
        ),
      );
    }
    if (data.containsKey('saved_timestamp')) {
      context.handle(
        _savedTimestampMeta,
        savedTimestamp.isAcceptableOrUnknown(
          data['saved_timestamp']!,
          _savedTimestampMeta,
        ),
      );
    }
    if (data.containsKey('shared_timestamp')) {
      context.handle(
        _sharedTimestampMeta,
        sharedTimestamp.isAcceptableOrUnknown(
          data['shared_timestamp']!,
          _sharedTimestampMeta,
        ),
      );
    }
    if (data.containsKey('last_update_timestamp')) {
      context.handle(
        _lastUpdateTimestampMeta,
        lastUpdateTimestamp.isAcceptableOrUnknown(
          data['last_update_timestamp']!,
          _lastUpdateTimestampMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_lastUpdateTimestampMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {jokeId};
  @override
  JokeInteraction map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return JokeInteraction(
      jokeId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}joke_id'],
      )!,
      viewedTimestamp: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}viewed_timestamp'],
      ),
      savedTimestamp: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}saved_timestamp'],
      ),
      sharedTimestamp: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}shared_timestamp'],
      ),
      lastUpdateTimestamp: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}last_update_timestamp'],
      )!,
    );
  }

  @override
  $JokeInteractionsTable createAlias(String alias) {
    return $JokeInteractionsTable(attachedDatabase, alias);
  }
}

class JokeInteraction extends DataClass implements Insertable<JokeInteraction> {
  final String jokeId;
  final DateTime? viewedTimestamp;
  final DateTime? savedTimestamp;
  final DateTime? sharedTimestamp;
  final DateTime lastUpdateTimestamp;
  const JokeInteraction({
    required this.jokeId,
    this.viewedTimestamp,
    this.savedTimestamp,
    this.sharedTimestamp,
    required this.lastUpdateTimestamp,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['joke_id'] = Variable<String>(jokeId);
    if (!nullToAbsent || viewedTimestamp != null) {
      map['viewed_timestamp'] = Variable<DateTime>(viewedTimestamp);
    }
    if (!nullToAbsent || savedTimestamp != null) {
      map['saved_timestamp'] = Variable<DateTime>(savedTimestamp);
    }
    if (!nullToAbsent || sharedTimestamp != null) {
      map['shared_timestamp'] = Variable<DateTime>(sharedTimestamp);
    }
    map['last_update_timestamp'] = Variable<DateTime>(lastUpdateTimestamp);
    return map;
  }

  JokeInteractionsCompanion toCompanion(bool nullToAbsent) {
    return JokeInteractionsCompanion(
      jokeId: Value(jokeId),
      viewedTimestamp: viewedTimestamp == null && nullToAbsent
          ? const Value.absent()
          : Value(viewedTimestamp),
      savedTimestamp: savedTimestamp == null && nullToAbsent
          ? const Value.absent()
          : Value(savedTimestamp),
      sharedTimestamp: sharedTimestamp == null && nullToAbsent
          ? const Value.absent()
          : Value(sharedTimestamp),
      lastUpdateTimestamp: Value(lastUpdateTimestamp),
    );
  }

  factory JokeInteraction.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return JokeInteraction(
      jokeId: serializer.fromJson<String>(json['jokeId']),
      viewedTimestamp: serializer.fromJson<DateTime?>(json['viewedTimestamp']),
      savedTimestamp: serializer.fromJson<DateTime?>(json['savedTimestamp']),
      sharedTimestamp: serializer.fromJson<DateTime?>(json['sharedTimestamp']),
      lastUpdateTimestamp: serializer.fromJson<DateTime>(
        json['lastUpdateTimestamp'],
      ),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'jokeId': serializer.toJson<String>(jokeId),
      'viewedTimestamp': serializer.toJson<DateTime?>(viewedTimestamp),
      'savedTimestamp': serializer.toJson<DateTime?>(savedTimestamp),
      'sharedTimestamp': serializer.toJson<DateTime?>(sharedTimestamp),
      'lastUpdateTimestamp': serializer.toJson<DateTime>(lastUpdateTimestamp),
    };
  }

  JokeInteraction copyWith({
    String? jokeId,
    Value<DateTime?> viewedTimestamp = const Value.absent(),
    Value<DateTime?> savedTimestamp = const Value.absent(),
    Value<DateTime?> sharedTimestamp = const Value.absent(),
    DateTime? lastUpdateTimestamp,
  }) => JokeInteraction(
    jokeId: jokeId ?? this.jokeId,
    viewedTimestamp: viewedTimestamp.present
        ? viewedTimestamp.value
        : this.viewedTimestamp,
    savedTimestamp: savedTimestamp.present
        ? savedTimestamp.value
        : this.savedTimestamp,
    sharedTimestamp: sharedTimestamp.present
        ? sharedTimestamp.value
        : this.sharedTimestamp,
    lastUpdateTimestamp: lastUpdateTimestamp ?? this.lastUpdateTimestamp,
  );
  JokeInteraction copyWithCompanion(JokeInteractionsCompanion data) {
    return JokeInteraction(
      jokeId: data.jokeId.present ? data.jokeId.value : this.jokeId,
      viewedTimestamp: data.viewedTimestamp.present
          ? data.viewedTimestamp.value
          : this.viewedTimestamp,
      savedTimestamp: data.savedTimestamp.present
          ? data.savedTimestamp.value
          : this.savedTimestamp,
      sharedTimestamp: data.sharedTimestamp.present
          ? data.sharedTimestamp.value
          : this.sharedTimestamp,
      lastUpdateTimestamp: data.lastUpdateTimestamp.present
          ? data.lastUpdateTimestamp.value
          : this.lastUpdateTimestamp,
    );
  }

  @override
  String toString() {
    return (StringBuffer('JokeInteraction(')
          ..write('jokeId: $jokeId, ')
          ..write('viewedTimestamp: $viewedTimestamp, ')
          ..write('savedTimestamp: $savedTimestamp, ')
          ..write('sharedTimestamp: $sharedTimestamp, ')
          ..write('lastUpdateTimestamp: $lastUpdateTimestamp')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    jokeId,
    viewedTimestamp,
    savedTimestamp,
    sharedTimestamp,
    lastUpdateTimestamp,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is JokeInteraction &&
          other.jokeId == this.jokeId &&
          other.viewedTimestamp == this.viewedTimestamp &&
          other.savedTimestamp == this.savedTimestamp &&
          other.sharedTimestamp == this.sharedTimestamp &&
          other.lastUpdateTimestamp == this.lastUpdateTimestamp);
}

class JokeInteractionsCompanion extends UpdateCompanion<JokeInteraction> {
  final Value<String> jokeId;
  final Value<DateTime?> viewedTimestamp;
  final Value<DateTime?> savedTimestamp;
  final Value<DateTime?> sharedTimestamp;
  final Value<DateTime> lastUpdateTimestamp;
  final Value<int> rowid;
  const JokeInteractionsCompanion({
    this.jokeId = const Value.absent(),
    this.viewedTimestamp = const Value.absent(),
    this.savedTimestamp = const Value.absent(),
    this.sharedTimestamp = const Value.absent(),
    this.lastUpdateTimestamp = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  JokeInteractionsCompanion.insert({
    required String jokeId,
    this.viewedTimestamp = const Value.absent(),
    this.savedTimestamp = const Value.absent(),
    this.sharedTimestamp = const Value.absent(),
    required DateTime lastUpdateTimestamp,
    this.rowid = const Value.absent(),
  }) : jokeId = Value(jokeId),
       lastUpdateTimestamp = Value(lastUpdateTimestamp);
  static Insertable<JokeInteraction> custom({
    Expression<String>? jokeId,
    Expression<DateTime>? viewedTimestamp,
    Expression<DateTime>? savedTimestamp,
    Expression<DateTime>? sharedTimestamp,
    Expression<DateTime>? lastUpdateTimestamp,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (jokeId != null) 'joke_id': jokeId,
      if (viewedTimestamp != null) 'viewed_timestamp': viewedTimestamp,
      if (savedTimestamp != null) 'saved_timestamp': savedTimestamp,
      if (sharedTimestamp != null) 'shared_timestamp': sharedTimestamp,
      if (lastUpdateTimestamp != null)
        'last_update_timestamp': lastUpdateTimestamp,
      if (rowid != null) 'rowid': rowid,
    });
  }

  JokeInteractionsCompanion copyWith({
    Value<String>? jokeId,
    Value<DateTime?>? viewedTimestamp,
    Value<DateTime?>? savedTimestamp,
    Value<DateTime?>? sharedTimestamp,
    Value<DateTime>? lastUpdateTimestamp,
    Value<int>? rowid,
  }) {
    return JokeInteractionsCompanion(
      jokeId: jokeId ?? this.jokeId,
      viewedTimestamp: viewedTimestamp ?? this.viewedTimestamp,
      savedTimestamp: savedTimestamp ?? this.savedTimestamp,
      sharedTimestamp: sharedTimestamp ?? this.sharedTimestamp,
      lastUpdateTimestamp: lastUpdateTimestamp ?? this.lastUpdateTimestamp,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (jokeId.present) {
      map['joke_id'] = Variable<String>(jokeId.value);
    }
    if (viewedTimestamp.present) {
      map['viewed_timestamp'] = Variable<DateTime>(viewedTimestamp.value);
    }
    if (savedTimestamp.present) {
      map['saved_timestamp'] = Variable<DateTime>(savedTimestamp.value);
    }
    if (sharedTimestamp.present) {
      map['shared_timestamp'] = Variable<DateTime>(sharedTimestamp.value);
    }
    if (lastUpdateTimestamp.present) {
      map['last_update_timestamp'] = Variable<DateTime>(
        lastUpdateTimestamp.value,
      );
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('JokeInteractionsCompanion(')
          ..write('jokeId: $jokeId, ')
          ..write('viewedTimestamp: $viewedTimestamp, ')
          ..write('savedTimestamp: $savedTimestamp, ')
          ..write('sharedTimestamp: $sharedTimestamp, ')
          ..write('lastUpdateTimestamp: $lastUpdateTimestamp, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

abstract class _$AppDatabase extends GeneratedDatabase {
  _$AppDatabase(QueryExecutor e) : super(e);
  $AppDatabaseManager get managers => $AppDatabaseManager(this);
  late final $JokeInteractionsTable jokeInteractions = $JokeInteractionsTable(
    this,
  );
  late final Index idxLastUpdateTimestamp = Index(
    'idx_last_update_timestamp',
    'CREATE INDEX idx_last_update_timestamp ON joke_interactions (last_update_timestamp)',
  );
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [
    jokeInteractions,
    idxLastUpdateTimestamp,
  ];
}

typedef $$JokeInteractionsTableCreateCompanionBuilder =
    JokeInteractionsCompanion Function({
      required String jokeId,
      Value<DateTime?> viewedTimestamp,
      Value<DateTime?> savedTimestamp,
      Value<DateTime?> sharedTimestamp,
      required DateTime lastUpdateTimestamp,
      Value<int> rowid,
    });
typedef $$JokeInteractionsTableUpdateCompanionBuilder =
    JokeInteractionsCompanion Function({
      Value<String> jokeId,
      Value<DateTime?> viewedTimestamp,
      Value<DateTime?> savedTimestamp,
      Value<DateTime?> sharedTimestamp,
      Value<DateTime> lastUpdateTimestamp,
      Value<int> rowid,
    });

class $$JokeInteractionsTableFilterComposer
    extends Composer<_$AppDatabase, $JokeInteractionsTable> {
  $$JokeInteractionsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get jokeId => $composableBuilder(
    column: $table.jokeId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get viewedTimestamp => $composableBuilder(
    column: $table.viewedTimestamp,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get savedTimestamp => $composableBuilder(
    column: $table.savedTimestamp,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get sharedTimestamp => $composableBuilder(
    column: $table.sharedTimestamp,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get lastUpdateTimestamp => $composableBuilder(
    column: $table.lastUpdateTimestamp,
    builder: (column) => ColumnFilters(column),
  );
}

class $$JokeInteractionsTableOrderingComposer
    extends Composer<_$AppDatabase, $JokeInteractionsTable> {
  $$JokeInteractionsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get jokeId => $composableBuilder(
    column: $table.jokeId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get viewedTimestamp => $composableBuilder(
    column: $table.viewedTimestamp,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get savedTimestamp => $composableBuilder(
    column: $table.savedTimestamp,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get sharedTimestamp => $composableBuilder(
    column: $table.sharedTimestamp,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get lastUpdateTimestamp => $composableBuilder(
    column: $table.lastUpdateTimestamp,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$JokeInteractionsTableAnnotationComposer
    extends Composer<_$AppDatabase, $JokeInteractionsTable> {
  $$JokeInteractionsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get jokeId =>
      $composableBuilder(column: $table.jokeId, builder: (column) => column);

  GeneratedColumn<DateTime> get viewedTimestamp => $composableBuilder(
    column: $table.viewedTimestamp,
    builder: (column) => column,
  );

  GeneratedColumn<DateTime> get savedTimestamp => $composableBuilder(
    column: $table.savedTimestamp,
    builder: (column) => column,
  );

  GeneratedColumn<DateTime> get sharedTimestamp => $composableBuilder(
    column: $table.sharedTimestamp,
    builder: (column) => column,
  );

  GeneratedColumn<DateTime> get lastUpdateTimestamp => $composableBuilder(
    column: $table.lastUpdateTimestamp,
    builder: (column) => column,
  );
}

class $$JokeInteractionsTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $JokeInteractionsTable,
          JokeInteraction,
          $$JokeInteractionsTableFilterComposer,
          $$JokeInteractionsTableOrderingComposer,
          $$JokeInteractionsTableAnnotationComposer,
          $$JokeInteractionsTableCreateCompanionBuilder,
          $$JokeInteractionsTableUpdateCompanionBuilder,
          (
            JokeInteraction,
            BaseReferences<
              _$AppDatabase,
              $JokeInteractionsTable,
              JokeInteraction
            >,
          ),
          JokeInteraction,
          PrefetchHooks Function()
        > {
  $$JokeInteractionsTableTableManager(
    _$AppDatabase db,
    $JokeInteractionsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$JokeInteractionsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$JokeInteractionsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$JokeInteractionsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> jokeId = const Value.absent(),
                Value<DateTime?> viewedTimestamp = const Value.absent(),
                Value<DateTime?> savedTimestamp = const Value.absent(),
                Value<DateTime?> sharedTimestamp = const Value.absent(),
                Value<DateTime> lastUpdateTimestamp = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => JokeInteractionsCompanion(
                jokeId: jokeId,
                viewedTimestamp: viewedTimestamp,
                savedTimestamp: savedTimestamp,
                sharedTimestamp: sharedTimestamp,
                lastUpdateTimestamp: lastUpdateTimestamp,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String jokeId,
                Value<DateTime?> viewedTimestamp = const Value.absent(),
                Value<DateTime?> savedTimestamp = const Value.absent(),
                Value<DateTime?> sharedTimestamp = const Value.absent(),
                required DateTime lastUpdateTimestamp,
                Value<int> rowid = const Value.absent(),
              }) => JokeInteractionsCompanion.insert(
                jokeId: jokeId,
                viewedTimestamp: viewedTimestamp,
                savedTimestamp: savedTimestamp,
                sharedTimestamp: sharedTimestamp,
                lastUpdateTimestamp: lastUpdateTimestamp,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$JokeInteractionsTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $JokeInteractionsTable,
      JokeInteraction,
      $$JokeInteractionsTableFilterComposer,
      $$JokeInteractionsTableOrderingComposer,
      $$JokeInteractionsTableAnnotationComposer,
      $$JokeInteractionsTableCreateCompanionBuilder,
      $$JokeInteractionsTableUpdateCompanionBuilder,
      (
        JokeInteraction,
        BaseReferences<_$AppDatabase, $JokeInteractionsTable, JokeInteraction>,
      ),
      JokeInteraction,
      PrefetchHooks Function()
    >;

class $AppDatabaseManager {
  final _$AppDatabase _db;
  $AppDatabaseManager(this._db);
  $$JokeInteractionsTableTableManager get jokeInteractions =>
      $$JokeInteractionsTableTableManager(_db, _db.jokeInteractions);
}
