import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_local_reactions_service.dart';

/// Provider for checking if a joke is saved
final isJokeSavedProvider = FutureProvider.autoDispose.family<bool, String>((
  ref,
  jokeId,
) async {
  final service = ref.watch(jokeLocalReactionsServiceProvider);
  return service.isJokeSaved(jokeId);
});

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
    final isSavedAsync = ref.watch(isJokeSavedProvider(jokeId));

    return GestureDetector(
      onTap: () async {
        final service = ref.read(jokeLocalReactionsServiceProvider);
        await service.toggleSaveJoke(jokeId, jokeContext: jokeContext);

        // Invalidate the provider to refresh the UI
        ref.invalidate(isJokeSavedProvider(jokeId));
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
              color: isSaved ? Colors.red : Colors.grey.shade600,
            ),
            loading: () => SizedBox(
              width: size * 0.7,
              height: size * 0.7,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: Colors.grey.shade600,
              ),
            ),
            error: (error, stack) => Icon(
              Icons.favorite_border,
              size: size,
              color: Colors.grey.shade600,
            ),
          ),
        ),
      ),
    );
  }
}
