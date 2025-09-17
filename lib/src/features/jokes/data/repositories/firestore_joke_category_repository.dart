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

  @override
  Future<void> upsertCategory(JokeCategory category) {
    return _firestore.collection(_collection).doc(category.id).set({
      'display_name': category.displayName,
      'joke_description_query': category.jokeDescriptionQuery,
      'image_url': category.imageUrl,
      'state': category.state.name,
    });
  }

  @override
  Future<void> deleteCategory(String categoryId) {
    return _firestore.collection(_collection).doc(categoryId).delete();
  }

  @override
  Stream<List<String>> watchCategoryImages(String categoryId) {
    return _firestore
        .collection(_collection)
        .doc(categoryId)
        .collection('images')
        .snapshots()
        .map(
          (snap) => snap.docs.map((d) => d.data()['url'] as String).toList(),
        );
  }

  @override
  Future<void> addImageToCategory(String categoryId, String imageUrl) {
    return _firestore
        .collection(_collection)
        .doc(categoryId)
        .collection('images')
        .add({'url': imageUrl});
  }

  @override
  Future<void> deleteImageFromCategory(String categoryId, String imageUrl) {
    return _firestore
        .collection(_collection)
        .doc(categoryId)
        .collection('images')
        .where('url', isEqualTo: imageUrl)
        .get()
        .then((snapshot) {
      for (var doc in snapshot.docs) {
        doc.reference.delete();
      }
    });
  }
}
