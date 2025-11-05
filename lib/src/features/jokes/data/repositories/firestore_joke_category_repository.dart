import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_category_repository.dart';

class FirestoreJokeCategoryRepository implements JokeCategoryRepository {
  final FirebaseFirestore _firestore;
  final PerformanceService _perf;

  static const String _collection = 'joke_categories';

  FirestoreJokeCategoryRepository({
    required FirebaseFirestore firestore,
    required PerformanceService perf,
  }) : _firestore = firestore,
       _perf = perf;

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

    if (category.seasonalValue != null) {
      data['seasonal_name'] = category.seasonalValue;
    }
    if (category.jokeDescriptionQuery != null) {
      data['joke_description_query'] = category.jokeDescriptionQuery;
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
    final key = '$categoryId:cache';
    _perf.startNamedTrace(
      name: TraceName.fsReadCategoryCache,
      key: key,
      attributes: {'collection': _collection, 'docId': categoryId, 'op': 'get'},
    );

    try {
      final snapshot = await _doc(
        categoryId,
      ).collection('category_jokes').doc('cache').get();

      final data = snapshot.data();
      if (!snapshot.exists || data == null) {
        _perf.stopNamedTrace(name: TraceName.fsReadCategoryCache, key: key);
        return <CategoryCachedJoke>[];
      }

      final dynamic jokesField = data['jokes'];
      if (jokesField is! List) {
        _perf.stopNamedTrace(name: TraceName.fsReadCategoryCache, key: key);
        return <CategoryCachedJoke>[];
      }

      final result = jokesField
          .whereType<Map<String, dynamic>>()
          .map(CategoryCachedJoke.fromMap)
          .where((j) => j.jokeId.isNotEmpty)
          .toList();

      _perf.putNamedTraceAttributes(
        name: TraceName.fsReadCategoryCache,
        key: key,
        attributes: {'result_count': result.length.toString()},
      );

      _perf.stopNamedTrace(name: TraceName.fsReadCategoryCache, key: key);

      return result;
    } catch (e) {
      _perf.dropNamedTrace(name: TraceName.fsReadCategoryCache, key: key);
      rethrow;
    }
  }

  DocumentReference<Map<String, dynamic>> _doc(String categoryId) {
    final docId = categoryId.startsWith(JokeCategory.firestorePrefix)
        ? categoryId.substring(JokeCategory.firestorePrefix.length)
        : categoryId;
    return _firestore.collection(_collection).doc(docId);
  }
}
