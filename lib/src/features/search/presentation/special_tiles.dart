import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/search/presentation/search_grid_item.dart';
import 'package:snickerdoodle/src/features/search/presentation/special_tile_widget.dart';

final specialTilesProvider = Provider<List<SpecialTile>>((ref) {
  return [
    SpecialTile(
      title: '1',
      onTap: (context) =>
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('1'),
      )),
    ),
    SpecialTile(
      title: '2',
      onTap: (context) =>
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('2'),
      )),
    ),
    SpecialTile(
      title: '3',
      onTap: (context) =>
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('3'),
      )),
    ),
  ];
});

final searchGridItemsProvider = StreamProvider<List<SearchGridItem>>((ref) {
  final categoriesStream = ref.watch(jokeCategoriesProvider.stream);
  final specialTiles = ref.watch(specialTilesProvider);

  return categoriesStream.map((categories) {
    final categoryItems = categories.map((c) => CategoryGridItem(c));
    final specialTileItems = specialTiles.map((t) => SpecialTileGridItem(t));
    return [...specialTileItems, ...categoryItems];
  });
});
