import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/joke_share_providers.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/joke_share_service.dart';
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
      key: Key('share_joke_button-${joke.id}'),
      onTap: () async {
        try {
          final shareService = ref.read(jokeShareServiceProvider);

          // Create controller and show modal progress dialog
          final controller = ShareCancellationController();
          VoidCallback? closeDialog;
          bool shareCompleted = false;

          // Barrier dismiss disabled; cancel via button only
          showDialog<void>(
            context: context,
            barrierDismissible: false,
            builder: (ctx) {
              closeDialog = () {
                final nav = Navigator.of(ctx);
                if (nav.mounted) {
                  nav.pop();
                }
              };
              controller.onBeforePlatformShare = () => closeDialog?.call();
              // If share already finished before dialog build, close immediately
              if (shareCompleted) {
                // schedule after build to avoid popping during build
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  closeDialog?.call();
                });
              }
              return AlertDialog(
                key: Key('share_joke_button-progress-dialog-${joke.id}'),
                content: Row(
                  children: const [
                    SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(strokeWidth: 3),
                    ),
                    SizedBox(width: 12),
                    Expanded(child: Text('Preparing images for sharing…')),
                  ],
                ),
                actions: [
                  TextButton(
                    key: Key('share_joke_button-cancel-button-${joke.id}'),
                    onPressed: () {
                      controller.cancel();
                      closeDialog?.call();
                    },
                    child: const Text('Cancel'),
                  ),
                ],
              );
            },
          );

          // Ensure the dialog builder runs before continuing; prevents race when service resolves immediately
          await Future<void>.delayed(Duration.zero);

          try {
            await shareService.shareJoke(
              joke,
              jokeContext: jokeContext,
              controller: controller,
            );
          } finally {
            shareCompleted = true;
            closeDialog?.call();
          }
        } catch (e) {
          AppLogger.warn('ERROR: share_joke_button: Failed to share joke: $e');
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
