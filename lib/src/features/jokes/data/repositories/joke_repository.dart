import 'dart:async';
import 'dart:convert';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

/// Dummy docId value that comes before any real joke docIDs
const String dummyDocId = ' DUMMY_VALUE ';

@immutable
class JokeListPageCursor {
  // Timestamp when ordering by creation_time, or double when by popularity_score
  final Object orderValue;
  final String docId;

  const JokeListPageCursor({required this.orderValue, required this.docId});

  String serialize() {
    final Object encodedOrderValue;
    final value = orderValue;
    if (value is Timestamp) {
      encodedOrderValue = {
        'ts': {'s': value.seconds, 'n': value.nanoseconds},
      };
    } else {
      encodedOrderValue = value;
    }
    return jsonEncode({'o': encodedOrderValue, 'd': docId});
  }

  factory JokeListPageCursor.deserialize(String serialized) {
    final Map<String, dynamic> data =
        jsonDecode(serialized) as Map<String, dynamic>;
    final dynamic raw = data['o'];
    final Object orderValue;
    if (raw is Map && raw.containsKey('ts')) {
      final dynamic ts = raw['ts'];
      if (ts is! Map) {
        throw FormatException('Invalid timestamp cursor payload: $ts');
      }
      final seconds = (ts['s'] as num).toInt();
      final nanoseconds = (ts['n'] as num).toInt();
      orderValue = Timestamp(seconds, nanoseconds);
    } else {
      orderValue = raw as Object;
    }
    return JokeListPageCursor(
      orderValue: orderValue,
      docId: data['d'] as String,
    );
  }
}

@immutable
class JokeListPage {
  final List<String> ids;
  final JokeListPageCursor? cursor;
  final bool hasMore;

  final List<Joke>? jokes;

  const JokeListPage({
    required this.ids,
    required this.cursor,
    required this.hasMore,
    this.jokes,
  });
}

enum JokeField {
  creationTime('creation_time'),
  isPublic('is_public'),
  popularityScore('popularity_score'),
  popularityScoreRecent('popularity_score_recent'),
  publicTimestamp('public_timestamp'),
  randomId('random_id'),
  savedFraction('num_saved_users_fraction'),
  seasonal('seasonal'),
  state('state');

  const JokeField(this.firestoreName);
  final String firestoreName;

  @override
  String toString() => firestoreName;
}

enum OrderDirection { ascending, descending }

@immutable
class JokeFilter {
  final JokeField field;
  final Object? isEqualTo;
  final Object? isNotEqualTo;
  final Object? isLessThan;
  final Object? isLessThanOrEqualTo;
  final Object? isGreaterThan;
  final Object? isGreaterThanOrEqualTo;
  final Object? arrayContains;
  final Iterable<Object?>? arrayContainsAny;
  final Iterable<Object?>? whereIn;
  final Iterable<Object?>? whereNotIn;
  final bool? isNull;

  const JokeFilter({
    required this.field,
    this.isEqualTo,
    this.isNotEqualTo,
    this.isLessThan,
    this.isLessThanOrEqualTo,
    this.isGreaterThan,
    this.isGreaterThanOrEqualTo,
    this.arrayContains,
    this.arrayContainsAny,
    this.whereIn,
    this.whereNotIn,
    this.isNull,
  }) : assert(
         ((isEqualTo != null ? 1 : 0) +
                 (isNotEqualTo != null ? 1 : 0) +
                 (isLessThan != null ? 1 : 0) +
                 (isLessThanOrEqualTo != null ? 1 : 0) +
                 (isGreaterThan != null ? 1 : 0) +
                 (isGreaterThanOrEqualTo != null ? 1 : 0) +
                 (arrayContains != null ? 1 : 0) +
                 (arrayContainsAny != null ? 1 : 0) +
                 (whereIn != null ? 1 : 0) +
                 (whereNotIn != null ? 1 : 0) +
                 (isNull != null ? 1 : 0)) ==
             1,
         'Exactly one condition must be provided for JokeFilter.',
       );

  static JokeFilter equals(JokeField field, Object? value) =>
      JokeFilter(field: field, isEqualTo: value);

  static JokeFilter notEqualTo(JokeField field, Object value) =>
      JokeFilter(field: field, isNotEqualTo: value);

  static JokeFilter lessThan(JokeField field, Object value) =>
      JokeFilter(field: field, isLessThan: value);

  static JokeFilter lessThanOrEqualTo(JokeField field, Object value) =>
      JokeFilter(field: field, isLessThanOrEqualTo: value);

  static JokeFilter greaterThan(JokeField field, Object value) =>
      JokeFilter(field: field, isGreaterThan: value);

  static JokeFilter greaterThanOrEqualTo(JokeField field, Object value) =>
      JokeFilter(field: field, isGreaterThanOrEqualTo: value);

  static JokeFilter arrayContainsValue(JokeField field, Object value) =>
      JokeFilter(field: field, arrayContains: value);

  static JokeFilter arrayContainsAnyValues(
    JokeField field,
    Iterable<Object?> values,
  ) => JokeFilter(field: field, arrayContainsAny: values);

  static JokeFilter whereInValues(JokeField field, Iterable<Object?> values) =>
      JokeFilter(field: field, whereIn: values);

  static JokeFilter whereNotInValues(
    JokeField field,
    Iterable<Object?> values,
  ) => JokeFilter(field: field, whereNotIn: values);

  static JokeFilter isNullValue(JokeField field, bool value) =>
      JokeFilter(field: field, isNull: value);

  /// Baseline filters that constrain results to jokes visible to end users.
  static List<JokeFilter> basePublicFilters() => [
    whereInValues(JokeField.state, [
      JokeState.published.value,
      JokeState.daily.value,
    ]),
    equals(JokeField.isPublic, true),
  ];

  Query<Map<String, dynamic>> apply(Query<Map<String, dynamic>> query) {
    return query.where(
      field.firestoreName,
      isEqualTo: isEqualTo,
      isNotEqualTo: isNotEqualTo,
      isLessThan: isLessThan,
      isLessThanOrEqualTo: isLessThanOrEqualTo,
      isGreaterThan: isGreaterThan,
      isGreaterThanOrEqualTo: isGreaterThanOrEqualTo,
      arrayContains: arrayContains,
      arrayContainsAny: arrayContainsAny,
      whereIn: whereIn,
      whereNotIn: whereNotIn,
      isNull: isNull,
    );
  }

  @override
  String toString() {
    return 'JokeFilter(field: ${field.firestoreName}, isEqualTo: $isEqualTo, isNotEqualTo: $isNotEqualTo, isLessThan: $isLessThan, isLessThanOrEqualTo: $isLessThanOrEqualTo, isGreaterThan: $isGreaterThan, isGreaterThanOrEqualTo: $isGreaterThanOrEqualTo, arrayContains: $arrayContains, arrayContainsAny: $arrayContainsAny, whereIn: $whereIn, whereNotIn: $whereNotIn, isNull: $isNull)';
  }
}

class JokeRepository {
  final FirebaseFirestore _firestore;
  final PerformanceService _perf;

  JokeRepository({
    required FirebaseFirestore firestore,
    required PerformanceService perf,
  }) : _firestore = firestore,
       _perf = perf;

  /// Wrap a Firestore stream and record a Performance trace from subscription
  /// until the first event is received. If the stream errors or is cancelled
  /// before any event, the trace is dropped.
  Stream<T> _traceFirstSnapshot<T>({
    required Stream<T> source,
    required String key,
    required String op,
    String? collection,
    String? docId,
    Map<String, String>? extra,
    Map<String, String> Function(T firstEvent)? firstAttributes,
  }) {
    final perf = _perf;

    final controller = StreamController<T>();
    StreamSubscription<T>? sub;
    bool firstEvent = true;

    final attrs = <String, String>{'op': op};
    if (collection != null) attrs['collection'] = collection;
    if (docId != null) attrs['docId'] = docId;
    if (extra != null) attrs.addAll(extra);

    perf.startNamedTrace(name: TraceName.fsRead, key: key, attributes: attrs);

    sub = source.listen(
      (event) {
        if (firstEvent) {
          firstEvent = false;
          final fa = firstAttributes?.call(event);
          if (fa != null && fa.isNotEmpty) {
            perf.putNamedTraceAttributes(
              name: TraceName.fsRead,
              key: key,
              attributes: fa,
            );
          }
          perf.stopNamedTrace(name: TraceName.fsRead, key: key);
        }
        controller.add(event);
      },
      onError: (Object error, StackTrace st) {
        if (firstEvent) {
          firstEvent = false;
          perf.dropNamedTrace(name: TraceName.fsRead, key: key);
        }
        controller.addError(error, st);
      },
      onDone: () async {
        if (firstEvent) {
          firstEvent = false;
          perf.dropNamedTrace(name: TraceName.fsRead, key: key);
        }
        await controller.close();
      },
      cancelOnError: false,
    );

    controller.onCancel = () async {
      if (firstEvent) {
        firstEvent = false;
        perf.dropNamedTrace(name: TraceName.fsRead, key: key);
      }
      await sub?.cancel();
    };

    return controller.stream;
  }

  Future<T> _traceFs<T>({
    required TraceName traceName,
    required String op,
    required Future<T> Function() action,
    String? collection,
    String? docId,
    Map<String, String>? extra,
  }) async {
    final key = docId != null && collection != null
        ? '$collection:$docId'
        : (collection ?? 'misc');
    final perf = _perf;
    perf.startNamedTrace(
      name: traceName,
      key: key,
      attributes: {
        'op': op,
        if (collection != null) 'collection': collection,
        if (docId != null) 'docId': docId,
        if (extra != null) ...extra,
      },
    );
    try {
      return await action();
    } finally {
      perf.stopNamedTrace(name: traceName, key: key);
    }
  }

  Stream<List<Joke>> getJokes() {
    final source = _firestore
        .collection('jokes')
        .orderBy('creation_time', descending: true)
        .snapshots();

    final traced = _traceFirstSnapshot<QuerySnapshot<Map<String, dynamic>>>(
      source: source,
      key: 'jokes:list',
      op: 'query_snapshots',
      collection: 'jokes',
      extra: {'order': 'creation_time_desc'},
      firstAttributes: (snap) => {'result_count': snap.docs.length.toString()},
    );

    return traced.map((snapshot) {
      return snapshot.docs.map((doc) {
        return Joke.fromMap(doc.data(), doc.id);
      }).toList();
    });
  }

  /// Fetch a paginated snapshot of joke IDs filtered and sorted in Firestore.
  /// - Applies the same filters with limit and cursor.
  /// - Adds a stable secondary order on document ID to ensure deterministic paging
  ///   when the primary order values are equal.
  Future<JokeListPage> getFilteredJokePage({
    required List<JokeFilter> filters,
    required JokeField orderByField,
    required OrderDirection orderDirection,
    required int limit,
    JokeListPageCursor? cursor,
  }) async {
    Query<Map<String, dynamic>> query = _firestore.collection('jokes');

    for (final filter in filters) {
      query = filter.apply(query);
    }

    final descending = orderDirection == OrderDirection.descending;

    query = query
        .orderBy(orderByField.firestoreName, descending: descending)
        .orderBy(FieldPath.documentId, descending: true);

    if (cursor != null) {
      // Use tuple-based startAfter with primary order value and doc ID
      query = query.startAfter([cursor.orderValue, cursor.docId]);
    }

    query = query.limit(limit);

    final snapshot = await _traceFs(
      traceName: TraceName.fsRead,
      op: 'query_get',
      collection: 'jokes',
      action: () => query.get(),
      extra: {
        'order': orderByField.firestoreName,
        'order_desc': descending.toString(),
        'limit': limit.toString(),
        'filters': filters.length.toString(),
      },
    );

    final ids = snapshot.docs.map((d) => d.id).toList();
    if (ids.isEmpty) {
      return const JokeListPage(ids: <String>[], cursor: null, hasMore: false);
    }

    // The last document determines the next cursor
    final lastDoc = snapshot.docs.last;
    final lastData = lastDoc.data();
    // Ensure the primary ordered field exists on the last document so the
    // subsequent cursor matches the query definition.
    final Object? orderValue = lastData[orderByField.firestoreName];
    if (orderValue == null) {
      throw StateError(
        'Joke ${lastDoc.id} is missing order-by field '
        '${orderByField.firestoreName}',
      );
    }

    final nextCursor = JokeListPageCursor(
      orderValue: orderValue,
      docId: lastDoc.id,
    );

    // We don't know hasMore without an extra count/read; conservatively assume
    // more pages exist if the page is full
    final hasMore = ids.length == limit;

    final jokes = snapshot.docs
        .map((d) => Joke.fromMap(d.data(), d.id))
        .toList();
    return JokeListPage(
      ids: ids,
      cursor: nextCursor,
      hasMore: hasMore,
      jokes: jokes,
    );
  }

  Future<JokeListPage> readFeedJokes({JokeListPageCursor? cursor}) async {
    Query<Map<String, dynamic>> query = _firestore.collection('joke_feed');

    // Order by document ID for stable pagination. Document IDs are chronological.
    query = query.orderBy(FieldPath.documentId);

    if (cursor != null) {
      // For feed jokes, the orderValue is the document ID itself.
      // We use startAfter with the doc ID from the last read document.
      query = query.startAfter([cursor.orderValue]);
    }

    // We only fetch one feed document (which is a batch of jokes) at a time.
    query = query.limit(1);

    final snapshot = await _traceFs(
      traceName: TraceName.fsReadJokeFeed,
      op: 'query_get',
      collection: 'joke_feed',
      action: () => query.get(),
      extra: {'limit': '1', 'cursor': (cursor != null).toString()},
    );

    if (snapshot.docs.isEmpty) {
      AppLogger.info('JOKE_FEED_REPO: No feed jokes found');
      return const JokeListPage(
        ids: [],
        cursor: null,
        hasMore: false,
        jokes: [],
      );
    }

    final doc = snapshot.docs.first;
    final docData = doc.data();
    final List<dynamic> jokesData = docData['jokes'] as List<dynamic>? ?? [];

    final List<Joke> jokes = [];
    final List<String> ids = [];
    for (final jokeData in jokesData) {
      if (jokeData is Map<String, dynamic>) {
        final jokeId = jokeData['key'] as String?;
        if (jokeId != null) {
          // The joke data is nested inside the feed document.
          // The `fromMap` factory expects the joke data map and its ID.
          jokes.add(Joke.fromMap(jokeData, jokeId));
          ids.add(jokeId);
        }
      }
    }

    final nextCursor = JokeListPageCursor(orderValue: doc.id, docId: doc.id);

    // If we reached here, we have a page. We can't know if it's the last one
    // without another read, so we assume there could be more. The next fetch
    // with the returned cursor will return an empty list if this was the end.
    const hasMore = true;

    AppLogger.info(
      'JOKE_FEED_REPO: Found feed jokes: ${jokes.length}, next cursor: ${nextCursor.docId}, hasMore: $hasMore',
    );
    return JokeListPage(
      ids: ids,
      cursor: nextCursor,
      hasMore: hasMore,
      jokes: jokes,
    );
  }

  /// Get a real-time stream of a joke by ID
  Stream<Joke?> getJokeByIdStream(String jokeId) {
    final source = _firestore.collection('jokes').doc(jokeId).snapshots();
    final traced = _traceFirstSnapshot<DocumentSnapshot<Map<String, dynamic>>>(
      source: source,
      key: 'jokes:$jokeId',
      op: 'doc_snapshots',
      collection: 'jokes',
      docId: jokeId,
      firstAttributes: (snap) => {
        'exists': (snap.exists && snap.data() != null).toString(),
      },
    );
    return traced.map((snapshot) {
      if (snapshot.exists && snapshot.data() != null) {
        return Joke.fromMap(snapshot.data()!, snapshot.id);
      }
      return null;
    });
  }

  /// Get multiple jokes by their IDs in a single batch query
  Future<List<Joke>> getJokesByIds(List<String> jokeIds) async {
    if (jokeIds.isEmpty) {
      return [];
    }

    try {
      // Deduplicate while preserving the first occurrence order
      final seen = <String>{};
      final orderedUnique = <String>[];
      for (final id in jokeIds) {
        if (seen.add(id)) orderedUnique.add(id);
      }

      // Use 'in' query to fetch multiple documents in a single request
      // Note: Firestore 'in' queries are limited to 10 items, so we need to batch them
      const batchSize = 10;
      final fetched = <Joke>[];

      // Build all batch futures first, then run in parallel
      final futures = <Future<QuerySnapshot<Map<String, dynamic>>>>[];
      for (int i = 0; i < orderedUnique.length; i += batchSize) {
        final batch = orderedUnique.skip(i).take(batchSize).toList();
        futures.add(
          _traceFs(
            traceName: TraceName.fsRead,
            op: 'where_in_get',
            collection: 'jokes',
            action: () => _firestore
                .collection('jokes')
                .where(FieldPath.documentId, whereIn: batch)
                .get(),
            extra: {'count': batch.length.toString()},
          ),
        );
      }
      final snapshots = await Future.wait(futures);
      for (final querySnapshot in snapshots) {
        fetched.addAll(
          querySnapshot.docs.map((doc) {
            return Joke.fromMap(doc.data(), doc.id);
          }),
        );
      }

      // Reorder to match the original requested order, skipping missing
      final byId = {for (final j in fetched) j.id: j};
      final ordered = <Joke>[];
      for (final id in orderedUnique) {
        final j = byId[id];
        if (j != null) ordered.add(j);
      }

      return ordered;
    } catch (e) {
      throw Exception('Failed to get jokes by IDs: $e');
    }
  }

  Future<void> updateJoke({
    required String jokeId,
    required String setupText,
    required String punchlineText,
    String? setupImageUrl,
    String? punchlineImageUrl,
    String? setupImageDescription,
    String? punchlineImageDescription,
  }) async {
    final updateData = <String, dynamic>{
      'setup_text': setupText,
      'punchline_text': punchlineText,
    };

    if (setupImageUrl != null) {
      updateData['setup_image_url'] = setupImageUrl;
    }
    if (punchlineImageUrl != null) {
      updateData['punchline_image_url'] = punchlineImageUrl;
    }
    if (setupImageDescription != null) {
      updateData['setup_image_description'] = setupImageDescription;
    }
    if (punchlineImageDescription != null) {
      updateData['punchline_image_description'] = punchlineImageDescription;
    }

    await _traceFs(
      traceName: TraceName.fsWrite,
      op: 'update',
      collection: 'jokes',
      docId: jokeId,
      action: () =>
          _firestore.collection('jokes').doc(jokeId).update(updateData),
    );
  }

  /// Set admin rating and state together (state mirrors rating)
  Future<void> setAdminRatingAndState(
    String jokeId,
    JokeAdminRating rating,
  ) async {
    // Validate current state allows changing admin rating
    final docRef = _firestore.collection('jokes').doc(jokeId);
    final snapshot = await _traceFs(
      traceName: TraceName.fsRead,
      op: 'get',
      collection: 'jokes',
      docId: jokeId,
      action: () => docRef.get(),
    );
    final data = snapshot.data();
    final currentState = data == null
        ? null
        : JokeState.fromString(data['state'] as String?);
    if (currentState == null || !currentState.canMutateAdminRating) {
      throw StateError(
        'Admin rating cannot be changed when state is ${currentState?.value ?? 'UNKNOWN'}',
      );
    }

    // Map rating to state (only APPROVED/REJECTED/UNREVIEWED supported)
    JokeState mappedState;
    switch (rating) {
      case JokeAdminRating.approved:
        mappedState = JokeState.approved;
        break;
      case JokeAdminRating.rejected:
        mappedState = JokeState.rejected;
        break;
      case JokeAdminRating.unreviewed:
        mappedState = JokeState.unreviewed;
        break;
    }

    await _traceFs(
      traceName: TraceName.fsWrite,
      op: 'update',
      collection: 'jokes',
      docId: jokeId,
      action: () => docRef.update({
        'admin_rating': rating.value,
        'state': mappedState.value,
      }),
    );
  }

  /// Delete a joke from Firestore
  Future<void> deleteJoke(String jokeId) async {
    await _traceFs(
      traceName: TraceName.fsWrite,
      op: 'delete',
      collection: 'jokes',
      docId: jokeId,
      action: () => _firestore.collection('jokes').doc(jokeId).delete(),
    );
  }

  /// Helper method to atomically increment a field in a joke document
  Future<void> _incrementJokeField(
    String jokeId,
    List<String> fieldNames,
    int amount,
  ) async {
    await _traceFs(
      traceName: TraceName.fsWrite,
      op: 'increment',
      collection: 'jokes',
      docId: jokeId,
      action: () => _firestore.collection('jokes').doc(jokeId).update({
        for (final fieldName in fieldNames)
          fieldName: FieldValue.increment(amount),
      }),
    );
  }

  /// Atomically increment the number of users who viewed this joke
  Future<void> incrementJokeViews(String jokeId) async {
    await _incrementJokeField(jokeId, [
      'num_viewed_users',
      'num_viewed_users_recent',
    ], 1);
  }

  /// Atomically increment the number of users who saved this joke
  Future<void> incrementJokeSaves(String jokeId) async {
    await _incrementJokeField(jokeId, [
      'num_saved_users',
      'num_saved_users_recent',
    ], 1);
  }

  /// Atomically decrement the number of users who saved this joke
  Future<void> decrementJokeSaves(String jokeId) async {
    await _incrementJokeField(jokeId, [
      'num_saved_users',
      'num_saved_users_recent',
    ], -1);
  }

  /// Atomically increment the number of users who shared this joke
  Future<void> incrementJokeShares(String jokeId) async {
    await _incrementJokeField(jokeId, [
      'num_shared_users',
      'num_shared_users_recent',
    ], 1);
  }

  /// Batch publish jokes
  Future<void> setJokesPublished(
    Map<String, DateTime> jokeIdToPublicTimestamp,
    bool isDaily,
  ) async {
    if (jokeIdToPublicTimestamp.isEmpty) return;
    final batch = _firestore.batch();
    for (final entry in jokeIdToPublicTimestamp.entries) {
      final docRef = _firestore.collection('jokes').doc(entry.key);
      batch.update(docRef, {
        'state': isDaily ? JokeState.daily.value : JokeState.published.value,
        'public_timestamp': Timestamp.fromDate(entry.value),
        'is_public': !isDaily,
      });
    }
    await _traceFs(
      traceName: TraceName.fsWriteBatch,
      op: 'batch_commit',
      collection: 'jokes',
      action: () => batch.commit(),
      extra: {'count': jokeIdToPublicTimestamp.length.toString()},
    );
  }

  /// Batch reset jokes: set state=APPROVED and public_timestamp=null
  /// Validates that all jokes have the expected state before updating
  Future<void> resetJokesToApproved(
    Iterable<String> jokeIds, {
    JokeState? expectedState,
  }) async {
    final ids = jokeIds.toList();
    if (ids.isEmpty) return;
    final batch = _firestore.batch();
    for (final jokeId in ids) {
      final docRef = _firestore.collection('jokes').doc(jokeId);
      final snapshot = await _traceFs(
        traceName: TraceName.fsRead,
        op: 'get',
        collection: 'jokes',
        docId: jokeId,
        action: () => docRef.get(),
      );

      if (!snapshot.exists || snapshot.data() == null) {
        // Don't commit the batch since validation failed
        throw Exception('Joke with ID $jokeId not found');
      }

      final data = snapshot.data()!;
      final currentState = JokeState.fromString(data['state'] as String?);

      if (expectedState != null && currentState != expectedState) {
        // Don't commit the batch since validation failed
        throw Exception(
          'Cannot reset joke $jokeId: current state is ${currentState?.value ?? 'unknown'}, expected ${expectedState.value}',
        );
      }

      // Validation passed, add to batch
      batch.update(docRef, {
        'state': JokeState.approved.value,
        'public_timestamp': null,
        'is_public': false,
      });
    }

    // All validations passed, commit the batch
    await _traceFs(
      traceName: TraceName.fsWriteBatch,
      op: 'batch_commit',
      collection: 'jokes',
      action: () => batch.commit(),
      extra: {'count': ids.length.toString()},
    );
  }
}
