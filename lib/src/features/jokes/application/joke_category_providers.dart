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

// Stream of images for a category
final jokeCategoryImagesProvider =
    StreamProvider.autoDispose.family<List<String>, String>((ref, categoryId) {
  return ref.watch(jokeCategoryRepositoryProvider).watchCategoryImages(categoryId);
});

// Stream of a single category by ID (direct document stream)
final jokeCategoryByIdProvider =
    StreamProvider.autoDispose.family<JokeCategory?, String>((ref, categoryId) {
  return ref.watch(jokeCategoryRepositoryProvider).watchCategory(categoryId);
});