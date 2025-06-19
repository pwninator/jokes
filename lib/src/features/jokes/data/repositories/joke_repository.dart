import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class JokeRepository {
  final FirebaseFirestore _firestore;

  JokeRepository(this._firestore);

  Stream<List<Joke>> getJokes() {
    return _firestore.collection('jokes').snapshots().map((snapshot) {
      return snapshot.docs.map((doc) {
        return Joke.fromMap(doc.data(), doc.id);
      }).toList();
    });
  }

  // Example of how you might add a joke - not required by current plan
  // Future<void> addJoke(Joke joke) {
  //   return _firestore.collection('jokes').add(joke.toMap());
  // }
}
