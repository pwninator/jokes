import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
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

  Future<Joke?> getJokeById(String jokeId) async {
    try {
      final doc = await _firestore.collection('jokes').doc(jokeId).get();
      if (doc.exists && doc.data() != null) {
        return Joke.fromMap(doc.data()!, doc.id);
      }
      return null;
    } catch (e) {
      throw Exception('Failed to get joke by ID: $e');
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

  /// Delete a joke from Firestore
  Future<void> deleteJoke(String jokeId) async {
    await _firestore.collection('jokes').doc(jokeId).delete();
  }
}
