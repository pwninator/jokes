import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';

const specialTileIdPrefix = 'special_tile_';

final specialTiles = [
  JokeCategory(
    id: '${specialTileIdPrefix}1',
    displayName: 'Special Tile 1',
    jokeDescriptionQuery: '',
    state: JokeCategoryState.approved,
  ),
  JokeCategory(
    id: '${specialTileIdPrefix}2',
    displayName: 'Special Tile 2',
    jokeDescriptionQuery: '',
    state: JokeCategoryState.approved,
  ),
  JokeCategory(
    id: '${specialTileIdPrefix}3',
    displayName: 'Special Tile 3',
    jokeDescriptionQuery: '',
    state: JokeCategoryState.approved,
  ),
];

final categoriesWithSpecialTilesProvider = StreamProvider<List<JokeCategory>>((ref) {
  final categoriesStream = ref.watch(jokeCategoriesProvider.stream);
  return categoriesStream.map((categories) {
    return [...categories, ...specialTiles];
  });
});
