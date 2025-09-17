import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/firestore_joke_category_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_category_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

// Repository provider
final jokeCategoryRepositoryProvider = Provider<JokeCategoryRepository>((ref) {
  final firestore = ref.watch(firebaseFirestoreProvider);
  return FirestoreJokeCategoryRepository(firestore: firestore);
});

// Stream of categories
final jokeCategoriesProvider = StreamProvider<List<JokeCategory>>((ref) {
  return ref.watch(jokeCategoryRepositoryProvider).watchCategories();
});

// Stream of approved categories
final approvedJokeCategoriesProvider =
    StreamProvider<List<JokeCategory>>((ref) {
  return ref.watch(jokeCategoriesProvider.stream).map((categories) {
    return categories
        .where((c) => c.state == JokeCategoryState.APPROVED)
        .toList();
  });
});

// Stream of images for a category
final jokeCategoryImagesProvider =
    StreamProvider.autoDispose.family<List<String>, String>((ref, categoryId) {
  return ref.watch(jokeCategoryRepositoryProvider).watchCategoryImages(categoryId);
});
