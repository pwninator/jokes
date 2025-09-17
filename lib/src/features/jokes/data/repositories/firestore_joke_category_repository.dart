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
  Stream<JokeCategory?> watchCategory(String categoryId) {
    return _firestore
        .collection(_collection)
        .doc(categoryId)
        .snapshots()
        .map((d) => d.exists ? JokeCategory.fromMap(d.data()!, d.id) : null);
  }

  @override
  Future<void> upsertCategory(JokeCategory category) {
    return _firestore.collection(_collection).doc(category.id).set({
      'display_name': category.displayName,
      'joke_description_query': category.jokeDescriptionQuery,
      'image_description': category.imageDescription,
      'image_url': category.imageUrl,
      'state': category.state.name,
    }, SetOptions(merge: true));
  }

  @override
  Future<void> deleteCategory(String categoryId) {
    return _firestore.collection(_collection).doc(categoryId).delete();
  }

  @override
  Stream<List<String>> watchCategoryImages(String categoryId) {
    return _firestore.collection(_collection).doc(categoryId).snapshots().map((
      doc,
    ) {
      final data = doc.data();
      if (data == null) return <String>[];
      final dynamic list = data['all_image_urls'];
      if (list is List) {
        return list
            .whereType<dynamic>()
            .map((e) => (e as String?)?.trim())
            .whereType<String>()
            .toList();
      }
      return <String>[];
    });
  }

  @override
  Future<void> addImageToCategory(String categoryId, String imageUrl) {
    return _firestore.collection(_collection).doc(categoryId).update({
      'all_image_urls': FieldValue.arrayUnion([imageUrl]),
    });
  }

  @override
  Future<void> deleteImageFromCategory(String categoryId, String imageUrl) {
    return _firestore.collection(_collection).doc(categoryId).update({
      'all_image_urls': FieldValue.arrayRemove([imageUrl]),
    });
  }
}
