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
  static const VerificationMeta _navigatedTimestampMeta =
      const VerificationMeta('navigatedTimestamp');
  @override
  late final GeneratedColumn<DateTime> navigatedTimestamp =
      GeneratedColumn<DateTime>(
        'navigated_timestamp',
        aliasedName,
        true,
        type: DriftSqlType.dateTime,
        requiredDuringInsert: false,
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
  static const VerificationMeta _setupTextMeta = const VerificationMeta(
    'setupText',
  );
  @override
  late final GeneratedColumn<String> setupText = GeneratedColumn<String>(
    'setup_text',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _punchlineTextMeta = const VerificationMeta(
    'punchlineText',
  );
  @override
  late final GeneratedColumn<String> punchlineText = GeneratedColumn<String>(
    'punchline_text',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _setupImageUrlMeta = const VerificationMeta(
    'setupImageUrl',
  );
  @override
  late final GeneratedColumn<String> setupImageUrl = GeneratedColumn<String>(
    'setup_image_url',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _punchlineImageUrlMeta = const VerificationMeta(
    'punchlineImageUrl',
  );
  @override
  late final GeneratedColumn<String> punchlineImageUrl =
      GeneratedColumn<String>(
        'punchline_image_url',
        aliasedName,
        true,
        type: DriftSqlType.string,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _feedIndexMeta = const VerificationMeta(
    'feedIndex',
  );
  @override
  late final GeneratedColumn<int> feedIndex = GeneratedColumn<int>(
    'feed_index',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  @override
  List<GeneratedColumn> get $columns => [
    jokeId,
    navigatedTimestamp,
    viewedTimestamp,
    savedTimestamp,
    sharedTimestamp,
    lastUpdateTimestamp,
    setupText,
    punchlineText,
    setupImageUrl,
    punchlineImageUrl,
    feedIndex,
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
    if (data.containsKey('navigated_timestamp')) {
      context.handle(
        _navigatedTimestampMeta,
        navigatedTimestamp.isAcceptableOrUnknown(
          data['navigated_timestamp']!,
          _navigatedTimestampMeta,
        ),
      );
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
    if (data.containsKey('setup_text')) {
      context.handle(
        _setupTextMeta,
        setupText.isAcceptableOrUnknown(data['setup_text']!, _setupTextMeta),
      );
    }
    if (data.containsKey('punchline_text')) {
      context.handle(
        _punchlineTextMeta,
        punchlineText.isAcceptableOrUnknown(
          data['punchline_text']!,
          _punchlineTextMeta,
        ),
      );
    }
    if (data.containsKey('setup_image_url')) {
      context.handle(
        _setupImageUrlMeta,
        setupImageUrl.isAcceptableOrUnknown(
          data['setup_image_url']!,
          _setupImageUrlMeta,
        ),
      );
    }
    if (data.containsKey('punchline_image_url')) {
      context.handle(
        _punchlineImageUrlMeta,
        punchlineImageUrl.isAcceptableOrUnknown(
          data['punchline_image_url']!,
          _punchlineImageUrlMeta,
        ),
      );
    }
    if (data.containsKey('feed_index')) {
      context.handle(
        _feedIndexMeta,
        feedIndex.isAcceptableOrUnknown(data['feed_index']!, _feedIndexMeta),
      );
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
      navigatedTimestamp: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}navigated_timestamp'],
      ),
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
      setupText: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}setup_text'],
      ),
      punchlineText: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}punchline_text'],
      ),
      setupImageUrl: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}setup_image_url'],
      ),
      punchlineImageUrl: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}punchline_image_url'],
      ),
      feedIndex: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}feed_index'],
      ),
    );
  }

  @override
  $JokeInteractionsTable createAlias(String alias) {
    return $JokeInteractionsTable(attachedDatabase, alias);
  }
}

class JokeInteraction extends DataClass implements Insertable<JokeInteraction> {
  final String jokeId;
  final DateTime? navigatedTimestamp;
  final DateTime? viewedTimestamp;
  final DateTime? savedTimestamp;
  final DateTime? sharedTimestamp;
  final DateTime lastUpdateTimestamp;
  final String? setupText;
  final String? punchlineText;
  final String? setupImageUrl;
  final String? punchlineImageUrl;
  final int? feedIndex;
  const JokeInteraction({
    required this.jokeId,
    this.navigatedTimestamp,
    this.viewedTimestamp,
    this.savedTimestamp,
    this.sharedTimestamp,
    required this.lastUpdateTimestamp,
    this.setupText,
    this.punchlineText,
    this.setupImageUrl,
    this.punchlineImageUrl,
    this.feedIndex,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['joke_id'] = Variable<String>(jokeId);
    if (!nullToAbsent || navigatedTimestamp != null) {
      map['navigated_timestamp'] = Variable<DateTime>(navigatedTimestamp);
    }
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
    if (!nullToAbsent || setupText != null) {
      map['setup_text'] = Variable<String>(setupText);
    }
    if (!nullToAbsent || punchlineText != null) {
      map['punchline_text'] = Variable<String>(punchlineText);
    }
    if (!nullToAbsent || setupImageUrl != null) {
      map['setup_image_url'] = Variable<String>(setupImageUrl);
    }
    if (!nullToAbsent || punchlineImageUrl != null) {
      map['punchline_image_url'] = Variable<String>(punchlineImageUrl);
    }
    if (!nullToAbsent || feedIndex != null) {
      map['feed_index'] = Variable<int>(feedIndex);
    }
    return map;
  }

  JokeInteractionsCompanion toCompanion(bool nullToAbsent) {
    return JokeInteractionsCompanion(
      jokeId: Value(jokeId),
      navigatedTimestamp: navigatedTimestamp == null && nullToAbsent
          ? const Value.absent()
          : Value(navigatedTimestamp),
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
      setupText: setupText == null && nullToAbsent
          ? const Value.absent()
          : Value(setupText),
      punchlineText: punchlineText == null && nullToAbsent
          ? const Value.absent()
          : Value(punchlineText),
      setupImageUrl: setupImageUrl == null && nullToAbsent
          ? const Value.absent()
          : Value(setupImageUrl),
      punchlineImageUrl: punchlineImageUrl == null && nullToAbsent
          ? const Value.absent()
          : Value(punchlineImageUrl),
      feedIndex: feedIndex == null && nullToAbsent
          ? const Value.absent()
          : Value(feedIndex),
    );
  }

  factory JokeInteraction.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return JokeInteraction(
      jokeId: serializer.fromJson<String>(json['jokeId']),
      navigatedTimestamp: serializer.fromJson<DateTime?>(
        json['navigatedTimestamp'],
      ),
      viewedTimestamp: serializer.fromJson<DateTime?>(json['viewedTimestamp']),
      savedTimestamp: serializer.fromJson<DateTime?>(json['savedTimestamp']),
      sharedTimestamp: serializer.fromJson<DateTime?>(json['sharedTimestamp']),
      lastUpdateTimestamp: serializer.fromJson<DateTime>(
        json['lastUpdateTimestamp'],
      ),
      setupText: serializer.fromJson<String?>(json['setupText']),
      punchlineText: serializer.fromJson<String?>(json['punchlineText']),
      setupImageUrl: serializer.fromJson<String?>(json['setupImageUrl']),
      punchlineImageUrl: serializer.fromJson<String?>(
        json['punchlineImageUrl'],
      ),
      feedIndex: serializer.fromJson<int?>(json['feedIndex']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'jokeId': serializer.toJson<String>(jokeId),
      'navigatedTimestamp': serializer.toJson<DateTime?>(navigatedTimestamp),
      'viewedTimestamp': serializer.toJson<DateTime?>(viewedTimestamp),
      'savedTimestamp': serializer.toJson<DateTime?>(savedTimestamp),
      'sharedTimestamp': serializer.toJson<DateTime?>(sharedTimestamp),
      'lastUpdateTimestamp': serializer.toJson<DateTime>(lastUpdateTimestamp),
      'setupText': serializer.toJson<String?>(setupText),
      'punchlineText': serializer.toJson<String?>(punchlineText),
      'setupImageUrl': serializer.toJson<String?>(setupImageUrl),
      'punchlineImageUrl': serializer.toJson<String?>(punchlineImageUrl),
      'feedIndex': serializer.toJson<int?>(feedIndex),
    };
  }

  JokeInteraction copyWith({
    String? jokeId,
    Value<DateTime?> navigatedTimestamp = const Value.absent(),
    Value<DateTime?> viewedTimestamp = const Value.absent(),
    Value<DateTime?> savedTimestamp = const Value.absent(),
    Value<DateTime?> sharedTimestamp = const Value.absent(),
    DateTime? lastUpdateTimestamp,
    Value<String?> setupText = const Value.absent(),
    Value<String?> punchlineText = const Value.absent(),
    Value<String?> setupImageUrl = const Value.absent(),
    Value<String?> punchlineImageUrl = const Value.absent(),
    Value<int?> feedIndex = const Value.absent(),
  }) => JokeInteraction(
    jokeId: jokeId ?? this.jokeId,
    navigatedTimestamp: navigatedTimestamp.present
        ? navigatedTimestamp.value
        : this.navigatedTimestamp,
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
    setupText: setupText.present ? setupText.value : this.setupText,
    punchlineText: punchlineText.present
        ? punchlineText.value
        : this.punchlineText,
    setupImageUrl: setupImageUrl.present
        ? setupImageUrl.value
        : this.setupImageUrl,
    punchlineImageUrl: punchlineImageUrl.present
        ? punchlineImageUrl.value
        : this.punchlineImageUrl,
    feedIndex: feedIndex.present ? feedIndex.value : this.feedIndex,
  );
  JokeInteraction copyWithCompanion(JokeInteractionsCompanion data) {
    return JokeInteraction(
      jokeId: data.jokeId.present ? data.jokeId.value : this.jokeId,
      navigatedTimestamp: data.navigatedTimestamp.present
          ? data.navigatedTimestamp.value
          : this.navigatedTimestamp,
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
      setupText: data.setupText.present ? data.setupText.value : this.setupText,
      punchlineText: data.punchlineText.present
          ? data.punchlineText.value
          : this.punchlineText,
      setupImageUrl: data.setupImageUrl.present
          ? data.setupImageUrl.value
          : this.setupImageUrl,
      punchlineImageUrl: data.punchlineImageUrl.present
          ? data.punchlineImageUrl.value
          : this.punchlineImageUrl,
      feedIndex: data.feedIndex.present ? data.feedIndex.value : this.feedIndex,
    );
  }

  @override
  String toString() {
    return (StringBuffer('JokeInteraction(')
          ..write('jokeId: $jokeId, ')
          ..write('navigatedTimestamp: $navigatedTimestamp, ')
          ..write('viewedTimestamp: $viewedTimestamp, ')
          ..write('savedTimestamp: $savedTimestamp, ')
          ..write('sharedTimestamp: $sharedTimestamp, ')
          ..write('lastUpdateTimestamp: $lastUpdateTimestamp, ')
          ..write('setupText: $setupText, ')
          ..write('punchlineText: $punchlineText, ')
          ..write('setupImageUrl: $setupImageUrl, ')
          ..write('punchlineImageUrl: $punchlineImageUrl, ')
          ..write('feedIndex: $feedIndex')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    jokeId,
    navigatedTimestamp,
    viewedTimestamp,
    savedTimestamp,
    sharedTimestamp,
    lastUpdateTimestamp,
    setupText,
    punchlineText,
    setupImageUrl,
    punchlineImageUrl,
    feedIndex,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is JokeInteraction &&
          other.jokeId == this.jokeId &&
          other.navigatedTimestamp == this.navigatedTimestamp &&
          other.viewedTimestamp == this.viewedTimestamp &&
          other.savedTimestamp == this.savedTimestamp &&
          other.sharedTimestamp == this.sharedTimestamp &&
          other.lastUpdateTimestamp == this.lastUpdateTimestamp &&
          other.setupText == this.setupText &&
          other.punchlineText == this.punchlineText &&
          other.setupImageUrl == this.setupImageUrl &&
          other.punchlineImageUrl == this.punchlineImageUrl &&
          other.feedIndex == this.feedIndex);
}

class JokeInteractionsCompanion extends UpdateCompanion<JokeInteraction> {
  final Value<String> jokeId;
  final Value<DateTime?> navigatedTimestamp;
  final Value<DateTime?> viewedTimestamp;
  final Value<DateTime?> savedTimestamp;
  final Value<DateTime?> sharedTimestamp;
  final Value<DateTime> lastUpdateTimestamp;
  final Value<String?> setupText;
  final Value<String?> punchlineText;
  final Value<String?> setupImageUrl;
  final Value<String?> punchlineImageUrl;
  final Value<int?> feedIndex;
  final Value<int> rowid;
  const JokeInteractionsCompanion({
    this.jokeId = const Value.absent(),
    this.navigatedTimestamp = const Value.absent(),
    this.viewedTimestamp = const Value.absent(),
    this.savedTimestamp = const Value.absent(),
    this.sharedTimestamp = const Value.absent(),
    this.lastUpdateTimestamp = const Value.absent(),
    this.setupText = const Value.absent(),
    this.punchlineText = const Value.absent(),
    this.setupImageUrl = const Value.absent(),
    this.punchlineImageUrl = const Value.absent(),
    this.feedIndex = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  JokeInteractionsCompanion.insert({
    required String jokeId,
    this.navigatedTimestamp = const Value.absent(),
    this.viewedTimestamp = const Value.absent(),
    this.savedTimestamp = const Value.absent(),
    this.sharedTimestamp = const Value.absent(),
    required DateTime lastUpdateTimestamp,
    this.setupText = const Value.absent(),
    this.punchlineText = const Value.absent(),
    this.setupImageUrl = const Value.absent(),
    this.punchlineImageUrl = const Value.absent(),
    this.feedIndex = const Value.absent(),
    this.rowid = const Value.absent(),
  }) : jokeId = Value(jokeId),
       lastUpdateTimestamp = Value(lastUpdateTimestamp);
  static Insertable<JokeInteraction> custom({
    Expression<String>? jokeId,
    Expression<DateTime>? navigatedTimestamp,
    Expression<DateTime>? viewedTimestamp,
    Expression<DateTime>? savedTimestamp,
    Expression<DateTime>? sharedTimestamp,
    Expression<DateTime>? lastUpdateTimestamp,
    Expression<String>? setupText,
    Expression<String>? punchlineText,
    Expression<String>? setupImageUrl,
    Expression<String>? punchlineImageUrl,
    Expression<int>? feedIndex,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (jokeId != null) 'joke_id': jokeId,
      if (navigatedTimestamp != null) 'navigated_timestamp': navigatedTimestamp,
      if (viewedTimestamp != null) 'viewed_timestamp': viewedTimestamp,
      if (savedTimestamp != null) 'saved_timestamp': savedTimestamp,
      if (sharedTimestamp != null) 'shared_timestamp': sharedTimestamp,
      if (lastUpdateTimestamp != null)
        'last_update_timestamp': lastUpdateTimestamp,
      if (setupText != null) 'setup_text': setupText,
      if (punchlineText != null) 'punchline_text': punchlineText,
      if (setupImageUrl != null) 'setup_image_url': setupImageUrl,
      if (punchlineImageUrl != null) 'punchline_image_url': punchlineImageUrl,
      if (feedIndex != null) 'feed_index': feedIndex,
      if (rowid != null) 'rowid': rowid,
    });
  }

  JokeInteractionsCompanion copyWith({
    Value<String>? jokeId,
    Value<DateTime?>? navigatedTimestamp,
    Value<DateTime?>? viewedTimestamp,
    Value<DateTime?>? savedTimestamp,
    Value<DateTime?>? sharedTimestamp,
    Value<DateTime>? lastUpdateTimestamp,
    Value<String?>? setupText,
    Value<String?>? punchlineText,
    Value<String?>? setupImageUrl,
    Value<String?>? punchlineImageUrl,
    Value<int?>? feedIndex,
    Value<int>? rowid,
  }) {
    return JokeInteractionsCompanion(
      jokeId: jokeId ?? this.jokeId,
      navigatedTimestamp: navigatedTimestamp ?? this.navigatedTimestamp,
      viewedTimestamp: viewedTimestamp ?? this.viewedTimestamp,
      savedTimestamp: savedTimestamp ?? this.savedTimestamp,
      sharedTimestamp: sharedTimestamp ?? this.sharedTimestamp,
      lastUpdateTimestamp: lastUpdateTimestamp ?? this.lastUpdateTimestamp,
      setupText: setupText ?? this.setupText,
      punchlineText: punchlineText ?? this.punchlineText,
      setupImageUrl: setupImageUrl ?? this.setupImageUrl,
      punchlineImageUrl: punchlineImageUrl ?? this.punchlineImageUrl,
      feedIndex: feedIndex ?? this.feedIndex,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (jokeId.present) {
      map['joke_id'] = Variable<String>(jokeId.value);
    }
    if (navigatedTimestamp.present) {
      map['navigated_timestamp'] = Variable<DateTime>(navigatedTimestamp.value);
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
    if (setupText.present) {
      map['setup_text'] = Variable<String>(setupText.value);
    }
    if (punchlineText.present) {
      map['punchline_text'] = Variable<String>(punchlineText.value);
    }
    if (setupImageUrl.present) {
      map['setup_image_url'] = Variable<String>(setupImageUrl.value);
    }
    if (punchlineImageUrl.present) {
      map['punchline_image_url'] = Variable<String>(punchlineImageUrl.value);
    }
    if (feedIndex.present) {
      map['feed_index'] = Variable<int>(feedIndex.value);
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
          ..write('navigatedTimestamp: $navigatedTimestamp, ')
          ..write('viewedTimestamp: $viewedTimestamp, ')
          ..write('savedTimestamp: $savedTimestamp, ')
          ..write('sharedTimestamp: $sharedTimestamp, ')
          ..write('lastUpdateTimestamp: $lastUpdateTimestamp, ')
          ..write('setupText: $setupText, ')
          ..write('punchlineText: $punchlineText, ')
          ..write('setupImageUrl: $setupImageUrl, ')
          ..write('punchlineImageUrl: $punchlineImageUrl, ')
          ..write('feedIndex: $feedIndex, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $CategoryInteractionsTable extends CategoryInteractions
    with TableInfo<$CategoryInteractionsTable, CategoryInteraction> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $CategoryInteractionsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _categoryIdMeta = const VerificationMeta(
    'categoryId',
  );
  @override
  late final GeneratedColumn<String> categoryId = GeneratedColumn<String>(
    'category_id',
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
    categoryId,
    viewedTimestamp,
    lastUpdateTimestamp,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'category_interactions';
  @override
  VerificationContext validateIntegrity(
    Insertable<CategoryInteraction> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('category_id')) {
      context.handle(
        _categoryIdMeta,
        categoryId.isAcceptableOrUnknown(data['category_id']!, _categoryIdMeta),
      );
    } else if (isInserting) {
      context.missing(_categoryIdMeta);
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
  Set<GeneratedColumn> get $primaryKey => {categoryId};
  @override
  CategoryInteraction map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return CategoryInteraction(
      categoryId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}category_id'],
      )!,
      viewedTimestamp: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}viewed_timestamp'],
      ),
      lastUpdateTimestamp: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}last_update_timestamp'],
      )!,
    );
  }

  @override
  $CategoryInteractionsTable createAlias(String alias) {
    return $CategoryInteractionsTable(attachedDatabase, alias);
  }
}

class CategoryInteraction extends DataClass
    implements Insertable<CategoryInteraction> {
  final String categoryId;
  final DateTime? viewedTimestamp;
  final DateTime lastUpdateTimestamp;
  const CategoryInteraction({
    required this.categoryId,
    this.viewedTimestamp,
    required this.lastUpdateTimestamp,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['category_id'] = Variable<String>(categoryId);
    if (!nullToAbsent || viewedTimestamp != null) {
      map['viewed_timestamp'] = Variable<DateTime>(viewedTimestamp);
    }
    map['last_update_timestamp'] = Variable<DateTime>(lastUpdateTimestamp);
    return map;
  }

  CategoryInteractionsCompanion toCompanion(bool nullToAbsent) {
    return CategoryInteractionsCompanion(
      categoryId: Value(categoryId),
      viewedTimestamp: viewedTimestamp == null && nullToAbsent
          ? const Value.absent()
          : Value(viewedTimestamp),
      lastUpdateTimestamp: Value(lastUpdateTimestamp),
    );
  }

  factory CategoryInteraction.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return CategoryInteraction(
      categoryId: serializer.fromJson<String>(json['categoryId']),
      viewedTimestamp: serializer.fromJson<DateTime?>(json['viewedTimestamp']),
      lastUpdateTimestamp: serializer.fromJson<DateTime>(
        json['lastUpdateTimestamp'],
      ),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'categoryId': serializer.toJson<String>(categoryId),
      'viewedTimestamp': serializer.toJson<DateTime?>(viewedTimestamp),
      'lastUpdateTimestamp': serializer.toJson<DateTime>(lastUpdateTimestamp),
    };
  }

  CategoryInteraction copyWith({
    String? categoryId,
    Value<DateTime?> viewedTimestamp = const Value.absent(),
    DateTime? lastUpdateTimestamp,
  }) => CategoryInteraction(
    categoryId: categoryId ?? this.categoryId,
    viewedTimestamp: viewedTimestamp.present
        ? viewedTimestamp.value
        : this.viewedTimestamp,
    lastUpdateTimestamp: lastUpdateTimestamp ?? this.lastUpdateTimestamp,
  );
  CategoryInteraction copyWithCompanion(CategoryInteractionsCompanion data) {
    return CategoryInteraction(
      categoryId: data.categoryId.present
          ? data.categoryId.value
          : this.categoryId,
      viewedTimestamp: data.viewedTimestamp.present
          ? data.viewedTimestamp.value
          : this.viewedTimestamp,
      lastUpdateTimestamp: data.lastUpdateTimestamp.present
          ? data.lastUpdateTimestamp.value
          : this.lastUpdateTimestamp,
    );
  }

  @override
  String toString() {
    return (StringBuffer('CategoryInteraction(')
          ..write('categoryId: $categoryId, ')
          ..write('viewedTimestamp: $viewedTimestamp, ')
          ..write('lastUpdateTimestamp: $lastUpdateTimestamp')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode =>
      Object.hash(categoryId, viewedTimestamp, lastUpdateTimestamp);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is CategoryInteraction &&
          other.categoryId == this.categoryId &&
          other.viewedTimestamp == this.viewedTimestamp &&
          other.lastUpdateTimestamp == this.lastUpdateTimestamp);
}

class CategoryInteractionsCompanion
    extends UpdateCompanion<CategoryInteraction> {
  final Value<String> categoryId;
  final Value<DateTime?> viewedTimestamp;
  final Value<DateTime> lastUpdateTimestamp;
  final Value<int> rowid;
  const CategoryInteractionsCompanion({
    this.categoryId = const Value.absent(),
    this.viewedTimestamp = const Value.absent(),
    this.lastUpdateTimestamp = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  CategoryInteractionsCompanion.insert({
    required String categoryId,
    this.viewedTimestamp = const Value.absent(),
    required DateTime lastUpdateTimestamp,
    this.rowid = const Value.absent(),
  }) : categoryId = Value(categoryId),
       lastUpdateTimestamp = Value(lastUpdateTimestamp);
  static Insertable<CategoryInteraction> custom({
    Expression<String>? categoryId,
    Expression<DateTime>? viewedTimestamp,
    Expression<DateTime>? lastUpdateTimestamp,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (categoryId != null) 'category_id': categoryId,
      if (viewedTimestamp != null) 'viewed_timestamp': viewedTimestamp,
      if (lastUpdateTimestamp != null)
        'last_update_timestamp': lastUpdateTimestamp,
      if (rowid != null) 'rowid': rowid,
    });
  }

  CategoryInteractionsCompanion copyWith({
    Value<String>? categoryId,
    Value<DateTime?>? viewedTimestamp,
    Value<DateTime>? lastUpdateTimestamp,
    Value<int>? rowid,
  }) {
    return CategoryInteractionsCompanion(
      categoryId: categoryId ?? this.categoryId,
      viewedTimestamp: viewedTimestamp ?? this.viewedTimestamp,
      lastUpdateTimestamp: lastUpdateTimestamp ?? this.lastUpdateTimestamp,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (categoryId.present) {
      map['category_id'] = Variable<String>(categoryId.value);
    }
    if (viewedTimestamp.present) {
      map['viewed_timestamp'] = Variable<DateTime>(viewedTimestamp.value);
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
    return (StringBuffer('CategoryInteractionsCompanion(')
          ..write('categoryId: $categoryId, ')
          ..write('viewedTimestamp: $viewedTimestamp, ')
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
  late final $CategoryInteractionsTable categoryInteractions =
      $CategoryInteractionsTable(this);
  late final Index idxLastUpdateTimestamp = Index(
    'idx_last_update_timestamp',
    'CREATE INDEX idx_last_update_timestamp ON joke_interactions (last_update_timestamp)',
  );
  late final Index idxFeedIndex = Index(
    'idx_feed_index',
    'CREATE INDEX idx_feed_index ON joke_interactions (feed_index)',
  );
  late final Index idxNavigatedTimestamp = Index(
    'idx_navigated_timestamp',
    'CREATE INDEX idx_navigated_timestamp ON joke_interactions (navigated_timestamp)',
  );
  late final Index idxViewedTimestamp = Index(
    'idx_viewed_timestamp',
    'CREATE INDEX idx_viewed_timestamp ON joke_interactions (viewed_timestamp)',
  );
  late final Index idxSavedTimestamp = Index(
    'idx_saved_timestamp',
    'CREATE INDEX idx_saved_timestamp ON joke_interactions (saved_timestamp)',
  );
  late final Index idxSharedTimestamp = Index(
    'idx_shared_timestamp',
    'CREATE INDEX idx_shared_timestamp ON joke_interactions (shared_timestamp)',
  );
  late final Index idxCategoryLastUpdate = Index(
    'idx_category_last_update',
    'CREATE INDEX idx_category_last_update ON category_interactions (last_update_timestamp)',
  );
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [
    jokeInteractions,
    categoryInteractions,
    idxLastUpdateTimestamp,
    idxFeedIndex,
    idxNavigatedTimestamp,
    idxViewedTimestamp,
    idxSavedTimestamp,
    idxSharedTimestamp,
    idxCategoryLastUpdate,
  ];
}

typedef $$JokeInteractionsTableCreateCompanionBuilder =
    JokeInteractionsCompanion Function({
      required String jokeId,
      Value<DateTime?> navigatedTimestamp,
      Value<DateTime?> viewedTimestamp,
      Value<DateTime?> savedTimestamp,
      Value<DateTime?> sharedTimestamp,
      required DateTime lastUpdateTimestamp,
      Value<String?> setupText,
      Value<String?> punchlineText,
      Value<String?> setupImageUrl,
      Value<String?> punchlineImageUrl,
      Value<int?> feedIndex,
      Value<int> rowid,
    });
typedef $$JokeInteractionsTableUpdateCompanionBuilder =
    JokeInteractionsCompanion Function({
      Value<String> jokeId,
      Value<DateTime?> navigatedTimestamp,
      Value<DateTime?> viewedTimestamp,
      Value<DateTime?> savedTimestamp,
      Value<DateTime?> sharedTimestamp,
      Value<DateTime> lastUpdateTimestamp,
      Value<String?> setupText,
      Value<String?> punchlineText,
      Value<String?> setupImageUrl,
      Value<String?> punchlineImageUrl,
      Value<int?> feedIndex,
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

  ColumnFilters<DateTime> get navigatedTimestamp => $composableBuilder(
    column: $table.navigatedTimestamp,
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

  ColumnFilters<String> get setupText => $composableBuilder(
    column: $table.setupText,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get punchlineText => $composableBuilder(
    column: $table.punchlineText,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get setupImageUrl => $composableBuilder(
    column: $table.setupImageUrl,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get punchlineImageUrl => $composableBuilder(
    column: $table.punchlineImageUrl,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get feedIndex => $composableBuilder(
    column: $table.feedIndex,
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

  ColumnOrderings<DateTime> get navigatedTimestamp => $composableBuilder(
    column: $table.navigatedTimestamp,
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

  ColumnOrderings<String> get setupText => $composableBuilder(
    column: $table.setupText,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get punchlineText => $composableBuilder(
    column: $table.punchlineText,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get setupImageUrl => $composableBuilder(
    column: $table.setupImageUrl,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get punchlineImageUrl => $composableBuilder(
    column: $table.punchlineImageUrl,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get feedIndex => $composableBuilder(
    column: $table.feedIndex,
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

  GeneratedColumn<DateTime> get navigatedTimestamp => $composableBuilder(
    column: $table.navigatedTimestamp,
    builder: (column) => column,
  );

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

  GeneratedColumn<String> get setupText =>
      $composableBuilder(column: $table.setupText, builder: (column) => column);

  GeneratedColumn<String> get punchlineText => $composableBuilder(
    column: $table.punchlineText,
    builder: (column) => column,
  );

  GeneratedColumn<String> get setupImageUrl => $composableBuilder(
    column: $table.setupImageUrl,
    builder: (column) => column,
  );

  GeneratedColumn<String> get punchlineImageUrl => $composableBuilder(
    column: $table.punchlineImageUrl,
    builder: (column) => column,
  );

  GeneratedColumn<int> get feedIndex =>
      $composableBuilder(column: $table.feedIndex, builder: (column) => column);
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
                Value<DateTime?> navigatedTimestamp = const Value.absent(),
                Value<DateTime?> viewedTimestamp = const Value.absent(),
                Value<DateTime?> savedTimestamp = const Value.absent(),
                Value<DateTime?> sharedTimestamp = const Value.absent(),
                Value<DateTime> lastUpdateTimestamp = const Value.absent(),
                Value<String?> setupText = const Value.absent(),
                Value<String?> punchlineText = const Value.absent(),
                Value<String?> setupImageUrl = const Value.absent(),
                Value<String?> punchlineImageUrl = const Value.absent(),
                Value<int?> feedIndex = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => JokeInteractionsCompanion(
                jokeId: jokeId,
                navigatedTimestamp: navigatedTimestamp,
                viewedTimestamp: viewedTimestamp,
                savedTimestamp: savedTimestamp,
                sharedTimestamp: sharedTimestamp,
                lastUpdateTimestamp: lastUpdateTimestamp,
                setupText: setupText,
                punchlineText: punchlineText,
                setupImageUrl: setupImageUrl,
                punchlineImageUrl: punchlineImageUrl,
                feedIndex: feedIndex,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String jokeId,
                Value<DateTime?> navigatedTimestamp = const Value.absent(),
                Value<DateTime?> viewedTimestamp = const Value.absent(),
                Value<DateTime?> savedTimestamp = const Value.absent(),
                Value<DateTime?> sharedTimestamp = const Value.absent(),
                required DateTime lastUpdateTimestamp,
                Value<String?> setupText = const Value.absent(),
                Value<String?> punchlineText = const Value.absent(),
                Value<String?> setupImageUrl = const Value.absent(),
                Value<String?> punchlineImageUrl = const Value.absent(),
                Value<int?> feedIndex = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => JokeInteractionsCompanion.insert(
                jokeId: jokeId,
                navigatedTimestamp: navigatedTimestamp,
                viewedTimestamp: viewedTimestamp,
                savedTimestamp: savedTimestamp,
                sharedTimestamp: sharedTimestamp,
                lastUpdateTimestamp: lastUpdateTimestamp,
                setupText: setupText,
                punchlineText: punchlineText,
                setupImageUrl: setupImageUrl,
                punchlineImageUrl: punchlineImageUrl,
                feedIndex: feedIndex,
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
typedef $$CategoryInteractionsTableCreateCompanionBuilder =
    CategoryInteractionsCompanion Function({
      required String categoryId,
      Value<DateTime?> viewedTimestamp,
      required DateTime lastUpdateTimestamp,
      Value<int> rowid,
    });
typedef $$CategoryInteractionsTableUpdateCompanionBuilder =
    CategoryInteractionsCompanion Function({
      Value<String> categoryId,
      Value<DateTime?> viewedTimestamp,
      Value<DateTime> lastUpdateTimestamp,
      Value<int> rowid,
    });

class $$CategoryInteractionsTableFilterComposer
    extends Composer<_$AppDatabase, $CategoryInteractionsTable> {
  $$CategoryInteractionsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get categoryId => $composableBuilder(
    column: $table.categoryId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get viewedTimestamp => $composableBuilder(
    column: $table.viewedTimestamp,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get lastUpdateTimestamp => $composableBuilder(
    column: $table.lastUpdateTimestamp,
    builder: (column) => ColumnFilters(column),
  );
}

class $$CategoryInteractionsTableOrderingComposer
    extends Composer<_$AppDatabase, $CategoryInteractionsTable> {
  $$CategoryInteractionsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get categoryId => $composableBuilder(
    column: $table.categoryId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get viewedTimestamp => $composableBuilder(
    column: $table.viewedTimestamp,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get lastUpdateTimestamp => $composableBuilder(
    column: $table.lastUpdateTimestamp,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$CategoryInteractionsTableAnnotationComposer
    extends Composer<_$AppDatabase, $CategoryInteractionsTable> {
  $$CategoryInteractionsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get categoryId => $composableBuilder(
    column: $table.categoryId,
    builder: (column) => column,
  );

  GeneratedColumn<DateTime> get viewedTimestamp => $composableBuilder(
    column: $table.viewedTimestamp,
    builder: (column) => column,
  );

  GeneratedColumn<DateTime> get lastUpdateTimestamp => $composableBuilder(
    column: $table.lastUpdateTimestamp,
    builder: (column) => column,
  );
}

class $$CategoryInteractionsTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $CategoryInteractionsTable,
          CategoryInteraction,
          $$CategoryInteractionsTableFilterComposer,
          $$CategoryInteractionsTableOrderingComposer,
          $$CategoryInteractionsTableAnnotationComposer,
          $$CategoryInteractionsTableCreateCompanionBuilder,
          $$CategoryInteractionsTableUpdateCompanionBuilder,
          (
            CategoryInteraction,
            BaseReferences<
              _$AppDatabase,
              $CategoryInteractionsTable,
              CategoryInteraction
            >,
          ),
          CategoryInteraction,
          PrefetchHooks Function()
        > {
  $$CategoryInteractionsTableTableManager(
    _$AppDatabase db,
    $CategoryInteractionsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$CategoryInteractionsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$CategoryInteractionsTableOrderingComposer(
                $db: db,
                $table: table,
              ),
          createComputedFieldComposer: () =>
              $$CategoryInteractionsTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<String> categoryId = const Value.absent(),
                Value<DateTime?> viewedTimestamp = const Value.absent(),
                Value<DateTime> lastUpdateTimestamp = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => CategoryInteractionsCompanion(
                categoryId: categoryId,
                viewedTimestamp: viewedTimestamp,
                lastUpdateTimestamp: lastUpdateTimestamp,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String categoryId,
                Value<DateTime?> viewedTimestamp = const Value.absent(),
                required DateTime lastUpdateTimestamp,
                Value<int> rowid = const Value.absent(),
              }) => CategoryInteractionsCompanion.insert(
                categoryId: categoryId,
                viewedTimestamp: viewedTimestamp,
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

typedef $$CategoryInteractionsTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $CategoryInteractionsTable,
      CategoryInteraction,
      $$CategoryInteractionsTableFilterComposer,
      $$CategoryInteractionsTableOrderingComposer,
      $$CategoryInteractionsTableAnnotationComposer,
      $$CategoryInteractionsTableCreateCompanionBuilder,
      $$CategoryInteractionsTableUpdateCompanionBuilder,
      (
        CategoryInteraction,
        BaseReferences<
          _$AppDatabase,
          $CategoryInteractionsTable,
          CategoryInteraction
        >,
      ),
      CategoryInteraction,
      PrefetchHooks Function()
    >;

class $AppDatabaseManager {
  final _$AppDatabase _db;
  $AppDatabaseManager(this._db);
  $$JokeInteractionsTableTableManager get jokeInteractions =>
      $$JokeInteractionsTableTableManager(_db, _db.jokeInteractions);
  $$CategoryInteractionsTableTableManager get categoryInteractions =>
      $$CategoryInteractionsTableTableManager(_db, _db.categoryInteractions);
}

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$appDatabaseHash() => r'ff3f40c93139c0a434c1f55f3e9f6dcdce4fc2ce';

/// See also [appDatabase].
@ProviderFor(appDatabase)
final appDatabaseProvider = Provider<AppDatabase>.internal(
  appDatabase,
  name: r'appDatabaseProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$appDatabaseHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef AppDatabaseRef = ProviderRef<AppDatabase>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
