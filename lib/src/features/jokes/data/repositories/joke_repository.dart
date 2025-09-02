import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

class JokeRepository {
  final FirebaseFirestore _firestore;

  JokeRepository(this._firestore);

  Stream<List<Joke>> getJokes() {
    return _firestore
        .collection('jokes')
        .orderBy('creation_time', descending: true)
        .snapshots()
        .map((snapshot) {
          return snapshot.docs.map((doc) {
            return Joke.fromMap(doc.data(), doc.id);
          }).toList();
        });
  }

  /// Get a real-time stream of a joke by ID
  Stream<Joke?> getJokeByIdStream(String jokeId) {
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

        final querySnapshot = await _firestore
            .collection('jokes')
            .where(FieldPath.documentId, whereIn: batch)
            .get();

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

    await _firestore.collection('jokes').doc(jokeId).update(updateData);
  }

  /// Helper function to update reaction count and popularity score
  Future<void> _updateReactionAndPopularity(
    String jokeId,
    JokeReactionType reactionType,
    int increment,
  ) async {
    // Get current joke data to calculate new popularity score
    final docRef = _firestore.collection('jokes').doc(jokeId);
    final snapshot = await docRef.get();
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
    await docRef.update({
      reactionType.firestoreField: FieldValue.increment(increment),
      'popularity_score': newPopularityScore,
    });
  }

  /// Generic method to increment any reaction count
  Future<void> incrementReaction(
    String jokeId,
    JokeReactionType reactionType,
  ) async {
    await _updateReactionAndPopularity(jokeId, reactionType, 1);
  }

  /// Generic method to decrement any reaction count
  Future<void> decrementReaction(
    String jokeId,
    JokeReactionType reactionType,
  ) async {
    await _updateReactionAndPopularity(jokeId, reactionType, -1);
  }

  // Legacy methods for backward compatibility (can be removed later)
  @Deprecated('Use incrementReaction(jokeId, JokeReactionType.save) instead')
  Future<void> incrementSaves(String jokeId) async {
    await incrementReaction(jokeId, JokeReactionType.save);
  }

  @Deprecated('Use decrementReaction(jokeId, JokeReactionType.save) instead')
  Future<void> decrementSaves(String jokeId) async {
    await decrementReaction(jokeId, JokeReactionType.save);
  }

  /// Set admin rating and state together (state mirrors rating)
  Future<void> setAdminRatingAndState(
    String jokeId,
    JokeAdminRating rating,
  ) async {
    // Validate current state allows changing admin rating
    final docRef = _firestore.collection('jokes').doc(jokeId);
    final snapshot = await docRef.get();
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

    await docRef.update({
      'admin_rating': rating.value,
      'state': mappedState.value,
    });
  }

  /// Delete a joke from Firestore
  Future<void> deleteJoke(String jokeId) async {
    await _firestore.collection('jokes').doc(jokeId).delete();
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
    await batch.commit();
  }

  /// Batch reset jokes: set state=APPROVED and public_timestamp=null
  /// Validates that all jokes have the expected state before updating
  Future<void> resetJokesToApproved(
    Iterable<String> jokeIds,
    JokeState expectedState,
  ) async {
    final ids = jokeIds.toList();
    if (ids.isEmpty) return;
    final batch = _firestore.batch();
    for (final jokeId in ids) {
      final docRef = _firestore.collection('jokes').doc(jokeId);
      final snapshot = await docRef.get();

      if (!snapshot.exists || snapshot.data() == null) {
        // Don't commit the batch since validation failed
        throw Exception('Joke with ID $jokeId not found');
      }

      final data = snapshot.data()!;
      final currentState = JokeState.fromString(data['state'] as String?);

      if (currentState != expectedState) {
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
    await batch.commit();
  }
}
