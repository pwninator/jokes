import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

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

  /// Generic method to increment any reaction count
  Future<void> incrementReaction(
    String jokeId,
    JokeReactionType reactionType,
  ) async {
    await _firestore.collection('jokes').doc(jokeId).update({
      reactionType.firestoreField: FieldValue.increment(1),
    });
  }

  /// Generic method to decrement any reaction count
  Future<void> decrementReaction(
    String jokeId,
    JokeReactionType reactionType,
  ) async {
    await _firestore.collection('jokes').doc(jokeId).update({
      reactionType.firestoreField: FieldValue.increment(-1),
    });
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

  /// Set admin rating for a joke
  /// This updates both the new admin_rating field and the legacy thumbs fields
  Future<void> setAdminRating(String jokeId, JokeAdminRating? rating) async {
    final Map<String, dynamic> updates = {};

    if (rating != null) {
      updates['admin_rating'] = rating.value;

      // Update legacy fields for backward compatibility
      if (rating == JokeAdminRating.approved) {
        updates['num_thumbs_up'] = 1;
        updates['num_thumbs_down'] = 0;
      } else if (rating == JokeAdminRating.rejected) {
        updates['num_thumbs_up'] = 0;
        updates['num_thumbs_down'] = 1;
      }
    } else {
      // Clear rating
      updates['admin_rating'] = null;
      updates['num_thumbs_up'] = 0;
      updates['num_thumbs_down'] = 0;
    }

    await _firestore.collection('jokes').doc(jokeId).update(updates);
  }

  /// Delete a joke from Firestore
  Future<void> deleteJoke(String jokeId) async {
    await _firestore.collection('jokes').doc(jokeId).delete();
  }
}
