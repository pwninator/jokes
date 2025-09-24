import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/search/presentation/special_tile_widget.dart';

sealed class SearchGridItem {}

class CategoryGridItem extends SearchGridItem {
  final JokeCategory category;
  CategoryGridItem(this.category);
}

class SpecialTileGridItem extends SearchGridItem {
  final SpecialTile tile;
  SpecialTileGridItem(this.tile);
}
