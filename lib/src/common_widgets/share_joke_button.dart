import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/joke_share_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

/// Button that shares a joke using the share functionality
class ShareJokeButton extends ConsumerWidget {
  final Joke joke;
  final String jokeContext;
  final double size;

  const ShareJokeButton({
    super.key,
    required this.joke,
    required this.jokeContext,
    this.size = 24.0,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);

    return GestureDetector(
      onTap: () async {
        try {
          final shareService = ref.read(jokeShareServiceProvider);

          // Show loading state briefly
          _showLoadingIndicator(context);

          // Perform the share
          final shareSuccessful = await shareService.shareJoke(
            joke,
            jokeContext: jokeContext,
          );

          // Only perform follow-up actions if user actually shared
          if (shareSuccessful) {
            // Increment the share count in Firestore (sharing is not toggleable)
            final jokeRepository = ref.read(jokeRepositoryProvider);
            final reactionsService = ref.read(jokeReactionsServiceProvider);

            await jokeRepository.incrementReaction(
              joke.id,
              JokeReactionType.share,
            );
            await reactionsService.addUserReaction(
              joke.id,
              JokeReactionType.share,
            );

            // Track analytics for share reaction
            final analyticsService = ref.read(analyticsServiceProvider);
            await analyticsService.logJokeReaction(
              joke.id,
              JokeReactionType.share,
              true, // Always true since sharing is additive
              jokeContext: jokeContext,
            );
          }

          // Hide loading indicator
          if (context.mounted) {
            Navigator.of(context).pop();
          }
        } catch (e) {
          // Hide loading indicator if it's showing
          if (context.mounted) {
            Navigator.of(context).pop();
          }

          // Show error message
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Failed to share joke: ${e.toString()}'),
                backgroundColor: theme.colorScheme.error,
              ),
            );
          }
        }
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: size + 16,
        height: size + 16,
        child: Center(
          child: Icon(
            Icons.share,
            size: size,
            color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
          ),
        ),
      ),
    );
  }

  void _showLoadingIndicator(BuildContext context) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => const Center(child: CircularProgressIndicator()),
    );
  }
}
