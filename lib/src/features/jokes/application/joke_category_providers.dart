import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/firestore_joke_category_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_category_repository.dart';

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

final popularTileImageNames = [
  'category_tile_popular_bunny1.png',
  'category_tile_popular_cat1.png',
  'category_tile_popular_hedgehog1.png',
  'category_tile_popular_lamb1.png',
  'category_tile_popular_puppy1.png',
  'category_tile_popular_panda1.png',
];

/// Merged provider for Discover: programmatic tiles first, then Firestore categories.
final discoverCategoriesProvider = Provider<AsyncValue<List<JokeCategory>>>((
  ref,
) {
  // Randomly select an image name each time
  final randomImageName =
      popularTileImageNames[Random().nextInt(popularTileImageNames.length)];

  // Programmatic Popular tile
  final popularTile = JokeCategory(
    id: 'programmatic:popular',
    displayName: 'Most Popular ❤️',
    jokeDescriptionQuery: null,
    imageUrl:
        'https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/joke_assets/$randomImageName',
    imageDescription: 'Popular jokes',
    state: JokeCategoryState.approved,
    type: CategoryType.popular,
  );

  // Programmatic Seasonal (Halloween) tile
  final halloweenTile = JokeCategory(
    id: 'programmatic:seasonal:halloween',
    displayName: 'Halloween 🎃',
    imageUrl:
        "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/pun_agent_image_20251011_091010_529423.png",
    imageDescription: 'Halloween jokes',
    state: JokeCategoryState.approved,
    type: CategoryType.seasonal,
    seasonalValue: 'Halloween',
    borderColor: Colors.orange,
  );

  final categoriesAsync = ref.watch(jokeCategoriesProvider);
  return categoriesAsync.whenData((categories) {
    final approvedCategories = categories
        .where((c) => c.state == JokeCategoryState.approved)
        .toList();
    return [halloweenTile, popularTile, ...approvedCategories];
  });
});
