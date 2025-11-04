import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_category_repository.dart';

class FirestoreJokeCategoryRepository implements JokeCategoryRepository {
  final FirebaseFirestore _firestore;

  static const String _collection = 'joke_categories';

  FirestoreJokeCategoryRepository({required FirebaseFirestore firestore})
    : _firestore = firestore;

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
    return _doc(categoryId).snapshots().map(
      (d) => d.exists ? JokeCategory.fromMap(d.data()!, d.id) : null,
    );
  }

  @override
  Future<void> upsertCategory(JokeCategory category) {
    final data = <String, dynamic>{
      'display_name': category.displayName,
      'image_description': category.imageDescription,
      'image_url': category.imageUrl,
      'state': category.state.value,
    };

    if (category.type == CategoryType.seasonal) {
      data['seasonal_name'] = category.seasonalValue;
      data['joke_description_query'] = FieldValue.delete();
    } else if (category.type == CategoryType.search) {
      data['joke_description_query'] = category.jokeDescriptionQuery;
      data['seasonal_name'] = FieldValue.delete();
    } else {
      data['joke_description_query'] = FieldValue.delete();
      data['seasonal_name'] = FieldValue.delete();
    }

    return _doc(category.id).set(data, SetOptions(merge: true));
  }

  @override
  Future<void> deleteCategory(String categoryId) {
    return _doc(categoryId).delete();
  }

  @override
  Stream<List<String>> watchCategoryImages(String categoryId) {
    return _doc(categoryId).snapshots().map((doc) {
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
    return _doc(categoryId).update({
      'all_image_urls': FieldValue.arrayUnion([imageUrl]),
    });
  }

  @override
  Future<void> deleteImageFromCategory(String categoryId, String imageUrl) {
    return _doc(categoryId).update({
      'all_image_urls': FieldValue.arrayRemove([imageUrl]),
    });
  }

  @override
  Future<List<CategoryCachedJoke>> getCachedCategoryJokes(
    String categoryId,
  ) async {
    final snapshot = await _doc(
      categoryId,
    ).collection('category_jokes').doc('cache').get();

    final data = snapshot.data();
    if (!snapshot.exists || data == null) return <CategoryCachedJoke>[];

    final dynamic jokesField = data['jokes'];
    if (jokesField is! List) return <CategoryCachedJoke>[];

    return jokesField
        .whereType<Map<String, dynamic>>()
        .map(CategoryCachedJoke.fromMap)
        .where((j) => j.jokeId.isNotEmpty)
        .toList();
  }

  DocumentReference<Map<String, dynamic>> _doc(String categoryId) {
    final docId = categoryId.startsWith(JokeCategory.firestorePrefix)
        ? categoryId.substring(JokeCategory.firestorePrefix.length)
        : categoryId;
    return _firestore.collection(_collection).doc(docId);
  }
}
