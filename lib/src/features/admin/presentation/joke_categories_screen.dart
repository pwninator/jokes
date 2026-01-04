import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_staggered_grid_view/flutter_staggered_grid_view.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_configured_screen.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_category_tile.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';

// Tile width constraints (in logical pixels)
const double _minCategoryTileWidth = 150.0;
const double _maxCategoryTileWidth = 250.0;
const double _targetCategoryTileWidth = 200.0; // for initial column estimate

class JokeCategoriesScreen extends ConsumerWidget implements TitledScreen {
  const JokeCategoriesScreen({super.key});

  @override
  String get title => 'Joke Categories';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final categoriesAsync = ref.watch(jokeCategoriesProvider);

    return AppBarConfiguredScreen(
      title: title,
      body: categoriesAsync.when(
        data: (categories) {
          if (categories.isEmpty) {
            return const Center(child: Text('No categories found'));
          }
          return LayoutBuilder(
            builder: (context, constraints) {
              const horizontalPadding = 16.0;
              const spacing = 12.0;
              final availableWidth =
                  constraints.maxWidth - (horizontalPadding * 2);

              int columns = (availableWidth / _targetCategoryTileWidth)
                  .round()
                  .clamp(1, 8);

              double tileWidth() =>
                  (availableWidth - (columns - 1) * spacing) / columns;

              // Adjust columns so width stays within 200-400 px
              while (tileWidth() > _maxCategoryTileWidth && columns < 12) {
                columns += 1;
              }
              while (tileWidth() < _minCategoryTileWidth && columns > 1) {
                columns -= 1;
              }

              return Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: horizontalPadding,
                ),
                child: MasonryGridView.count(
                  crossAxisCount: columns,
                  mainAxisSpacing: spacing,
                  crossAxisSpacing: spacing,
                  itemCount: categories.length,
                  itemBuilder: (context, index) {
                    final cat = categories[index];
                    return JokeCategoryTile(
                      category: cat,
                      borderColor: _getBorderColorForState(cat.state),
                      showBorder: true,
                      onTap: () => context.pushNamed(
                        RouteNames.adminCategoryEditor,
                        pathParameters: {'categoryId': cat.id},
                      ),
                    );
                  },
                ),
              );
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, st) => Center(child: Text('Error loading categories: $e')),
      ),
    );
  }
}

Color _getBorderColorForState(JokeCategoryState state) {
  switch (state) {
    case JokeCategoryState.proposed:
      return Colors.orange;
    case JokeCategoryState.approved:
      return Colors.green;
    case JokeCategoryState.seasonal:
      return Colors.purple;
    case JokeCategoryState.rejected:
      return Colors.red;
  }
}
