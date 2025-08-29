import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class JokeTextCard extends ConsumerWidget {
  final Joke joke;
  final int? index;
  final VoidCallback? onTap;
  final String? overlayBadgeText;

  const JokeTextCard({
    super.key,
    required this.joke,
    this.index,
    this.onTap,
    this.overlayBadgeText,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final populationState = ref.watch(jokePopulationProvider);
    final isPopulating = populationState.populatingJokes.contains(joke.id);

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4.0),
      child: Stack(
        children: [
          Column(
            children: [
              Padding(
                padding: const EdgeInsets.all(16.0),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Index indicator
                    if (index != null)
                      Padding(
                        padding: const EdgeInsets.only(right: 12.0),
                        child: CircleAvatar(
                          backgroundColor: Theme.of(
                            context,
                          ).colorScheme.primary,
                          radius: 16,
                          child: Text(
                            '${index! + 1}',
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.onPrimary,
                              fontWeight: FontWeight.bold,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ),

                    // Joke content
                    Expanded(
                      child: GestureDetector(
                        onTap: onTap,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Setup text
                            Text(
                              joke.setupText,
                              style: TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                                color: Theme.of(context).colorScheme.onSurface,
                                height: 1.3,
                              ),
                              maxLines: 3,
                              overflow: TextOverflow.ellipsis,
                            ),

                            const SizedBox(height: 12),

                            // Punchline text
                            Text(
                              joke.punchlineText,
                              style: TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                                color: Theme.of(context).colorScheme.onSurface,
                                height: 1.3,
                                fontStyle: FontStyle.italic,
                              ),
                              maxLines: 3,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(
                  left: 16.0,
                  right: 16.0,
                  bottom: 16.0,
                ),
                child: SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: isPopulating
                        ? null
                        : () async {
                            final notifier = ref.read(
                              jokePopulationProvider.notifier,
                            );
                            await notifier.populateJoke(
                              joke.id,
                              imagesOnly: false,
                            );
                          },
                    icon: isPopulating
                        ? SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation<Color>(
                                Theme.of(
                                  context,
                                ).colorScheme.onSurface.withValues(alpha: 0.6),
                              ),
                            ),
                          )
                        : const Icon(Icons.auto_awesome),
                    label: Text(
                      isPopulating ? 'Generating Images...' : 'Generate Images',
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Theme.of(
                        context,
                      ).colorScheme.primaryContainer,
                      foregroundColor: Theme.of(
                        context,
                      ).colorScheme.onPrimaryContainer,
                    ),
                  ),
                ),
              ),
              if (populationState.error != null)
                Padding(
                  padding: const EdgeInsets.only(
                    left: 16.0,
                    right: 16.0,
                    bottom: 8.0,
                  ),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12.0),
                    decoration: BoxDecoration(
                      color: Theme.of(
                        context,
                      ).appColors.authError.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8.0),
                      border: Border.all(
                        color: Theme.of(
                          context,
                        ).appColors.authError.withValues(alpha: 0.3),
                      ),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          Icons.error_outline,
                          size: 16,
                          color: Theme.of(context).appColors.authError,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            populationState.error!,
                            style: TextStyle(
                              color: Theme.of(context).appColors.authError,
                              fontSize: 12,
                            ),
                          ),
                        ),
                        IconButton(
                          onPressed: () {
                            ref
                                .read(jokePopulationProvider.notifier)
                                .clearError();
                          },
                          icon: Icon(
                            Icons.close,
                            size: 16,
                            color: Theme.of(context).appColors.authError,
                          ),
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
          if (overlayBadgeText != null && overlayBadgeText!.isNotEmpty)
            Positioned(
              top: 8,
              right: 8,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(
                    color: Theme.of(
                      context,
                    ).colorScheme.outline.withValues(alpha: 0.3),
                  ),
                ),
                child: Text(
                  overlayBadgeText!,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: Theme.of(context).colorScheme.onSurface,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
