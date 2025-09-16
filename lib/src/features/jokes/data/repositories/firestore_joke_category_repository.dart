import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_category_repository.dart';

class FirestoreJokeCategoryRepository implements JokeCategoryRepository {
  final FirebaseFirestore _firestore;

  static const String _collection = 'joke_categories';

  FirestoreJokeCategoryRepository({FirebaseFirestore? firestore})
    : _firestore = firestore ?? FirebaseFirestore.instance;

  @override
  Stream<List<JokeCategory>> watchCategories() {
    return _firestore
        .collection(_collection)
        .orderBy('display_name')
        .snapshots()
        .map(
          (snap) => snap.docs
              .map((d) => JokeCategory.fromMap(d.data(), d.id))
              .toList(),
        );
  }
}
