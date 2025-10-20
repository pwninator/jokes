import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

/// Button widget for saving/unsaving jokes
/// Shows visual feedback based on save state and handles toggle functionality
class SaveJokeButton extends ConsumerWidget {
  final String jokeId;
  final String jokeContext;
  final double size;

  const SaveJokeButton({
    super.key,
    required this.jokeId,
    required this.jokeContext,
    this.size = 24.0,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final Color baseButtonColor = jokeIconButtonBaseColor(context);
    final Color activeButtonColor = jokeSaveButtonColor(context);
    final isSavedAsync = ref.watch(isJokeSavedProvider(jokeId));
    final appUsageService = ref.read(appUsageServiceProvider);
    final analyticsService = ref.read(analyticsServiceProvider);

    return GestureDetector(
      key: Key('save_joke_button-$jokeId'),
      onTap: () async {
        bool wasAdded;
        try {
          wasAdded = await appUsageService.toggleJokeSave(
            jokeId,
            context: context,
          );
        } catch (e) {
          analyticsService.logErrorJokeSave(
            jokeId: jokeId,
            action: 'toggle',
            errorMessage: e.toString(),
          );
          return;
        }

        // Log analytics for save state change
        final totalSaved = await appUsageService.getNumSavedJokes();
        if (wasAdded) {
          analyticsService.logJokeSaved(
            jokeId,
            jokeContext: jokeContext,
            totalJokesSaved: totalSaved,
          );
        } else {
          analyticsService.logJokeUnsaved(
            jokeId,
            jokeContext: jokeContext,
            totalJokesSaved: totalSaved,
          );
        }
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: size + 16,
        height: size + 16,
        child: Center(
          child: isSavedAsync.when(
            data: (isSaved) => Icon(
              isSaved ? Icons.favorite : Icons.favorite_border,
              size: size,
              color: isSaved ? activeButtonColor : baseButtonColor,
            ),
            loading: () => SizedBox(
              width: size * 0.7,
              height: size * 0.7,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: baseButtonColor,
              ),
            ),
            error: (error, stack) =>
                Icon(Icons.favorite_border, size: size, color: baseButtonColor),
          ),
        ),
      ),
    );
  }
}
