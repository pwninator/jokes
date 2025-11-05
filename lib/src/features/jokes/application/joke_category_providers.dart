import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/firestore_joke_category_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_category_repository.dart';
import 'package:snickerdoodle/src/features/settings/application/admin_settings_service.dart';
import 'package:snickerdoodle/src/features/settings/application/feed_screen_status_provider.dart';

part 'joke_category_providers.g.dart';

@Riverpod(keepAlive: true)
JokeCategoryRepository jokeCategoryRepository(Ref ref) {
  final firestore = ref.read(firebaseFirestoreProvider);
  final perf = ref.read(performanceServiceProvider);
  return FirestoreJokeCategoryRepository(firestore: firestore, perf: perf);
}

// Stream of categories
final jokeCategoriesProvider = StreamProvider<List<JokeCategory>>((ref) {
  return ref.read(jokeCategoryRepositoryProvider).watchCategories();
});

// Stream of images for a category
final jokeCategoryImagesProvider = StreamProvider.autoDispose
    .family<List<String>, String>((ref, categoryId) {
      return ref
          .read(jokeCategoryRepositoryProvider)
          .watchCategoryImages(categoryId);
    });

// Stream of a single category by ID (direct document stream)
final jokeCategoryByIdProvider = StreamProvider.autoDispose
    .family<JokeCategory?, String>((ref, categoryId) {
      return ref.read(jokeCategoryRepositoryProvider).watchCategory(categoryId);
    });

@Riverpod(keepAlive: true)
Stream<Set<String>> viewedCategoryIds(Ref ref) {
  final db = ref.read(appDatabaseProvider);
  final query = (db.select(db.categoryInteractions)
    ..where((tbl) => tbl.viewedTimestamp.isNotNull()));
  return query.watch().map((rows) => rows.map((r) => r.categoryId).toSet());
}

/// Whether there exist any approved Discover categories that the user has not viewed yet.
/// Used to show an "unviewed" indicator on the Discover tab icon.
@Riverpod(keepAlive: true)
bool hasUnviewedCategories(Ref ref) {
  final categoriesAsync = ref.watch(discoverCategoriesProvider);
  final viewedIds = ref.watch(viewedCategoryIdsProvider).valueOrNull;

  return categoriesAsync.maybeWhen(
    data: (categories) {
      if (viewedIds == null) return false;
      return categories.any((c) => !viewedIds.contains(c.id));
    },
    orElse: () => false,
  );
}

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

  // Check feed screen status
  final feedScreenEnabled = ref.read(feedScreenStatusProvider);

  final List<JokeCategory> programmaticTiles = [];

  // Add Daily Jokes tile first if feed screen is enabled, because then
  // there is no daily jokes tab.
  if (feedScreenEnabled) {
    final dailyTile = JokeCategory(
      id: 'programmatic:daily',
      displayName: 'Daily Jokes',
      jokeDescriptionQuery: null,
      imageUrl:
          'https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/pun_agent_image_20251027_071950_137704.png',
      imageDescription: 'Daily jokes',
      state: JokeCategoryState.approved,
      type: CategoryType.daily,
      borderColor: Colors.blue,
    );
    programmaticTiles.add(dailyTile);
  }

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
    borderColor: Colors.red,
  );

  // Add remaining programmatic tiles
  programmaticTiles.add(popularTile);

  final categoriesAsync = ref.watch(jokeCategoriesProvider);
  final adminSettings = ref.read(adminSettingsServiceProvider);
  final includeProposed = adminSettings.getAdminShowProposedCategories();
  return categoriesAsync.whenData((categories) {
    final filteredCategories = categories.where((c) {
      if (c.state == JokeCategoryState.approved) return true;
      if (includeProposed && c.state == JokeCategoryState.proposed) {
        return true;
      }
      return false;
    }).toList();
    return [...programmaticTiles, ...filteredCategories];
  });
});
