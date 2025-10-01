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
final jokeCategoryImagesProvider = StreamProvider.autoDispose
    .family<List<String>, String>((ref, categoryId) {
      return ref
          .watch(jokeCategoryRepositoryProvider)
          .watchCategoryImages(categoryId);
    });

// Stream of a single category by ID (direct document stream)
final jokeCategoryByIdProvider = StreamProvider.autoDispose
    .family<JokeCategory?, String>((ref, categoryId) {
      return ref
          .watch(jokeCategoryRepositoryProvider)
          .watchCategory(categoryId);
    });

/// Merged provider for Discover: programmatic tiles first, then Firestore categories.
final discoverCategoriesProvider = Provider<AsyncValue<List<JokeCategory>>>((
  ref,
) {
  // Programmatic Popular tile
  final popularTile = JokeCategory(
    id: 'programmatic:popular',
    displayName: 'Popular',
    jokeDescriptionQuery: null,
    imageUrl:
        'https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/pun_agent_image_20250903_051129_509211.png',
    imageDescription: 'Popular jokes',
    state: JokeCategoryState.approved,
    type: CategoryType.popular,
  );

  final categoriesAsync = ref.watch(jokeCategoriesProvider);
  return categoriesAsync.whenData((categories) {
    final approved = categories
        .where((c) => c.state == JokeCategoryState.approved)
        .toList();
    return [popularTile, ...approved];
  });
});
