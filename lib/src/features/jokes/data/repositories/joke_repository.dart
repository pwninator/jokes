import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

@immutable
class JokeListPageCursor {
  // Timestamp when ordering by creation_time, or int when by popularity_score
  final Object orderValue;
  final String docId;

  const JokeListPageCursor({required this.orderValue, required this.docId});
}

@immutable
class JokeListPage {
  final List<String> ids;
  final JokeListPageCursor? cursor;
  final bool hasMore;

  const JokeListPage({
    required this.ids,
    required this.cursor,
    required this.hasMore,
  });
}

class JokeRepository {
  final FirebaseFirestore _firestore;
  final bool _isAdmin;
  final bool _debugMode;
  final PerformanceService? _perf;

  JokeRepository(
    this._firestore,
    this._isAdmin,
    this._debugMode, {
    PerformanceService? perf,
  }) : _perf = perf;

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
    perf?.startNamedTrace(
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
      perf?.stopNamedTrace(name: traceName, key: key);
    }
  }

  Stream<List<Joke>> getJokes() {
    // Streaming reads aren't individually traced; trace subscription start
    _perf?.startNamedTrace(
      name: TraceName.fsRead,
      key: 'jokes',
      attributes: {'op': 'stream_snapshots', 'collection': 'jokes'},
    );
    final stream = _firestore
        .collection('jokes')
        .orderBy('creation_time', descending: true)
        .snapshots()
        .map((snapshot) {
          return snapshot.docs.map((doc) {
            return Joke.fromMap(doc.data(), doc.id);
          }).toList();
        });
    // Stop immediately; duration of stream is not meaningful
    _perf?.stopNamedTrace(name: TraceName.fsRead, key: 'jokes');
    return stream;
  }

  /// Fetch a paginated snapshot of joke IDs filtered and sorted in Firestore.
  /// - Applies the same filters with limit and cursor.
  /// - Adds a stable secondary order on document ID to ensure deterministic paging
  ///   when the primary order values are equal.
  Future<JokeListPage> getFilteredJokePage({
    required Set<JokeState> states,
    required bool popularOnly,
    required int limit,
    JokeListPageCursor? cursor,
  }) async {
    Query<Map<String, dynamic>> query = _firestore.collection('jokes');

    if (states.isNotEmpty) {
      final stateValues = states.map((s) => s.value).toList();
      query = query.where('state', whereIn: stateValues);
    }

    // Primary ordering and the field used for cursor.orderValue
    final String primaryOrderField;
    final bool descending;
    if (popularOnly) {
      primaryOrderField = 'popularity_score';
      descending = true;
      query = query
          .where('popularity_score', isGreaterThan: 0)
          .orderBy(primaryOrderField, descending: descending)
          .orderBy(FieldPath.documentId, descending: true);
    } else {
      primaryOrderField = 'creation_time';
      descending = true;
      query = query
          .orderBy(primaryOrderField, descending: descending)
          .orderBy(FieldPath.documentId, descending: true);
    }

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
        'popular_only': popularOnly.toString(),
        'limit': limit.toString(),
      },
    );
    final ids = snapshot.docs.map((d) => d.id).toList();

    if (ids.isEmpty) {
      return const JokeListPage(ids: <String>[], cursor: null, hasMore: false);
    }

    // The last document determines the next cursor
    final lastDoc = snapshot.docs.last;
    final lastData = lastDoc.data();
    final orderValue = lastData[primaryOrderField];

    final nextCursor = JokeListPageCursor(
      orderValue: orderValue,
      docId: lastDoc.id,
    );

    // We don't know hasMore without an extra count/read; conservatively assume
    // more pages exist if the page is full
    final hasMore = ids.length == limit;

    return JokeListPage(ids: ids, cursor: nextCursor, hasMore: hasMore);
  }

  /// Get a real-time stream of a joke by ID
  Stream<Joke?> getJokeByIdStream(String jokeId) {
    // See note on streaming traces above
    return _firestore.collection('jokes').doc(jokeId).snapshots().map((
      snapshot,
    ) {
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
      // Use 'in' query to fetch multiple documents in a single request
      // Note: Firestore 'in' queries are limited to 10 items, so we need to batch them
      const batchSize = 10;
      final allJokes = <Joke>[];

      for (int i = 0; i < jokeIds.length; i += batchSize) {
        final batch = jokeIds.skip(i).take(batchSize).toList();

        final querySnapshot = await _traceFs(
          traceName: TraceName.fsRead,
          op: 'where_in_get',
          collection: 'jokes',
          action: () => _firestore
              .collection('jokes')
              .where(FieldPath.documentId, whereIn: batch)
              .get(),
          extra: {'count': batch.length.toString()},
        );

        final jokes = querySnapshot.docs.map((doc) {
          return Joke.fromMap(doc.data(), doc.id);
        }).toList();

        allJokes.addAll(jokes);
      }

      return allJokes;
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

  /// Helper function to update reaction count and popularity score
  Future<void> updateReactionAndPopularity(
    String jokeId,
    JokeReactionType reactionType,
    int increment,
  ) async {
    // Suppress Firestore writes for admin users or in debug mode
    if (_isAdmin || _debugMode) {
      final action = increment > 0 ? 'increment' : 'decrement';
      debugPrint(
        'JOKE REPO ADMIN/DEBUG reaction suppressed: $action $reactionType for joke $jokeId',
      );
      return;
    }
    // Get current joke data to calculate new popularity score
    final docRef = _firestore.collection('jokes').doc(jokeId);
    final snapshot = await _traceFs(
      traceName: TraceName.fsRead,
      op: 'get',
      collection: 'jokes',
      docId: jokeId,
      action: () => docRef.get(),
    );
    final data = snapshot.data();

    if (data == null || data.isEmpty) {
      throw Exception('Joke not found');
    }

    final currentSaves = data['num_saves'] as int? ?? 0;
    final currentShares = data['num_shares'] as int? ?? 0;

    // Calculate new values
    int newSaves = currentSaves;
    int newShares = currentShares;

    if (reactionType == JokeReactionType.save) {
      newSaves = currentSaves + increment;
    } else if (reactionType == JokeReactionType.share) {
      newShares = currentShares + increment;
    }

    // Ensure values don't go below 0
    newSaves = newSaves < 0 ? 0 : newSaves;
    newShares = newShares < 0 ? 0 : newShares;

    // Calculate new popularity score
    final newPopularityScore = newSaves + (newShares * 5);

    // Update both the reaction count and popularity score
    await _traceFs(
      traceName: TraceName.fsWrite,
      op: 'update',
      collection: 'jokes',
      docId: jokeId,
      action: () => docRef.update({
        reactionType.firestoreField: FieldValue.increment(increment),
        'popularity_score': newPopularityScore,
      }),
      extra: {'reaction': reactionType.firestoreField},
    );

    debugPrint(
      'REPO: JokeRepository updateReactionAndPopularity: $jokeId, $reactionType, $increment, $newSaves, $newShares, $newPopularityScore',
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
