import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';

class JokeCategoryTile extends StatelessWidget {
  const JokeCategoryTile(
      {super.key,
      required this.category,
      this.onTap,
      this.showBorder = false});

  final JokeCategory category;
  final VoidCallback? onTap;
  final bool showBorder;

  Color _borderColor(BuildContext context) {
    if (!showBorder) return Colors.transparent;
    switch (category.state) {
      case JokeCategoryState.APPROVED:
        return Colors.green;
      case JokeCategoryState.REJECTED:
        return Colors.red;
      case JokeCategoryState.PROPOSED:
        return Colors.blue;
      default:
        return Colors.transparent;
    }
  }

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Card(
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        child: Container(
          key: const Key('joke_category_tile_container'),
          decoration: BoxDecoration(
            border: Border.all(
              color: _borderColor(context),
              width: 3,
            ),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Padding(
            padding: const EdgeInsets.all(8.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                AspectRatio(
                  aspectRatio: 1,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: CachedJokeImage(
                      imageUrl: category.imageUrl,
                      fit: BoxFit.cover,
                      showLoadingIndicator: true,
                      showErrorIcon: true,
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  category.displayName,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.center,
                  style: Theme.of(
                    context,
                  ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
