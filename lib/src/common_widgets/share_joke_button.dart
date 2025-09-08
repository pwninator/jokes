import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/joke_share_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

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
          await shareService.shareJoke(joke, jokeContext: jokeContext);
        } catch (e) {
          debugPrint('ERROR: share_joke_button: Failed to share joke: $e');
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
}
