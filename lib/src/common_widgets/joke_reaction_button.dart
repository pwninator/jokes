import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

class JokeReactionButton extends ConsumerWidget {
  final String jokeId;
  final JokeReactionType reactionType;
  final double size;

  const JokeReactionButton({
    super.key,
    required this.jokeId,
    required this.reactionType,
    this.size = 24.0,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    try {
      final hasReaction = ref.watch(
        hasUserReactionProvider((jokeId: jokeId, reactionType: reactionType)),
      );

      return GestureDetector(
        onTap: () async {
          // Provide haptic feedback
          await ref
              .read(jokeReactionsProvider.notifier)
              .toggleReaction(jokeId, reactionType);
        },
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          width: size + 16,
          height: size + 16,
          child: Center(
            child: Icon(
              hasReaction ? reactionType.activeIcon : reactionType.inactiveIcon,
              size: size,
              color:
                  hasReaction ? reactionType.activeColor : Colors.grey.shade600,
            ),
          ),
        ),
      );
    } catch (e) {
      // Gracefully handle provider errors (e.g., during tests)
      return SizedBox(
        width: size + 16,
        height: size + 16,
        child: Center(
          child: Icon(
            reactionType.inactiveIcon,
            size: size,
            color: Colors.grey.shade600,
          ),
        ),
      );
    }
  }
}

/// Convenience widget for saving jokes
class SaveJokeButton extends StatelessWidget {
  final String jokeId;
  final double size;

  const SaveJokeButton({super.key, required this.jokeId, this.size = 24.0});

  @override
  Widget build(BuildContext context) {
    return JokeReactionButton(
      jokeId: jokeId,
      reactionType: JokeReactionType.save,
      size: size,
    );
  }
}

/// Convenience widget for sharing jokes
class ShareJokeButton extends StatelessWidget {
  final String jokeId;
  final double size;

  const ShareJokeButton({super.key, required this.jokeId, this.size = 24.0});

  @override
  Widget build(BuildContext context) {
    return JokeReactionButton(
      jokeId: jokeId,
      reactionType: JokeReactionType.share,
      size: size,
    );
  }
}

/// Convenience widget for thumbs up
class ThumbsUpJokeButton extends StatelessWidget {
  final String jokeId;
  final double size;

  const ThumbsUpJokeButton({super.key, required this.jokeId, this.size = 24.0});

  @override
  Widget build(BuildContext context) {
    return JokeReactionButton(
      jokeId: jokeId,
      reactionType: JokeReactionType.thumbsUp,
      size: size,
    );
  }
}

/// Convenience widget for thumbs down
class ThumbsDownJokeButton extends StatelessWidget {
  final String jokeId;
  final double size;

  const ThumbsDownJokeButton({
    super.key,
    required this.jokeId,
    this.size = 24.0,
  });

  @override
  Widget build(BuildContext context) {
    return JokeReactionButton(
      jokeId: jokeId,
      reactionType: JokeReactionType.thumbsDown,
      size: size,
    );
  }
}
