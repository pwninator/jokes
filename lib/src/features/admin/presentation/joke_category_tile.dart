import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';

class JokeCategoryTile extends StatelessWidget {
  const JokeCategoryTile({
    super.key,
    required this.category,
    this.onTap,
    this.showStateBorder = false,
  });

  final JokeCategory category;
  final VoidCallback? onTap;
  final bool showStateBorder;

  @override
  Widget build(BuildContext context) {
    final borderColor = _getBorderColorForState(context, category.state);

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Card(
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: showStateBorder
              ? BorderSide(color: borderColor, width: 2)
              : BorderSide.none,
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
    );
  }

  Color _getBorderColorForState(BuildContext context, JokeCategoryState state) {
    switch (state) {
      case JokeCategoryState.proposed:
        return Colors.orange;
      case JokeCategoryState.approved:
        return Colors.green;
      case JokeCategoryState.rejected:
        return Colors.red;
    }
  }
}
