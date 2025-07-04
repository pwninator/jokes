import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_editor_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';

class JokeManagementScreen extends ConsumerStatefulWidget {
  final bool ratingMode;

  const JokeManagementScreen({super.key, this.ratingMode = false});

  @override
  ConsumerState<JokeManagementScreen> createState() =>
      _JokeManagementScreenState();
}

class _JokeManagementScreenState extends ConsumerState<JokeManagementScreen> {
  @override
  void initState() {
    super.initState();
    // Set the filter state when the component mounts
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (widget.ratingMode) {
        ref.read(jokeFilterProvider.notifier).setUnratedOnly(true);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final jokesAsync =
        widget.ratingMode
            ? ref
                .watch(ratingModeJokesProvider)
                .when(
                  data: (jokes) => AsyncValue.data(jokes),
                  loading: () => const AsyncValue.loading(),
                  error:
                      (error, stackTrace) =>
                          AsyncValue.error(error, stackTrace),
                )
            : ref.watch(filteredJokesProvider);
    final filterState = ref.watch(jokeFilterProvider);

    return AdaptiveAppBarScreen(
      title: widget.ratingMode ? 'Rate Jokes' : 'Joke Management',
      floatingActionButton:
          widget.ratingMode
              ? null
              : FloatingActionButton(
                onPressed: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (context) => const JokeEditorScreen(),
                    ),
                  );
                },
                tooltip: 'Add New Joke',
                child: const Icon(Icons.add),
              ),
      body: Column(
        children: [
          // Filter bar - only show when not in rating mode
          if (!widget.ratingMode)
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: 16.0,
                vertical: 8.0,
              ),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surface,
                border: Border(
                  bottom: BorderSide(
                    color: Theme.of(
                      context,
                    ).colorScheme.outline.withValues(alpha: 0.2),
                    width: 1,
                  ),
                ),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      'Filters',
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        color: Theme.of(
                          context,
                        ).colorScheme.onSurface.withValues(alpha: 0.8),
                      ),
                    ),
                  ),
                  FilterChip(
                    key: const Key('unrated-only-filter-chip'),
                    label: const Text('Unrated only'),
                    selected: filterState.showUnratedOnly,
                    onSelected: (selected) {
                      ref.read(jokeFilterProvider.notifier).toggleUnratedOnly();
                    },
                    showCheckmark: true,
                  ),
                ],
              ),
            ),
          // Jokes list
          Expanded(
            child: jokesAsync.when(
              data:
                  (jokes) =>
                      jokes.isEmpty
                          ? Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  Icons.mood_bad,
                                  size: 64,
                                  color: Theme.of(context).colorScheme.onSurface
                                      .withValues(alpha: 0.4),
                                ),
                                const SizedBox(height: 16),
                                Text(
                                  widget.ratingMode
                                      ? 'No unrated jokes with images found!'
                                      : filterState.showUnratedOnly
                                      ? 'No unrated jokes with images found!'
                                      : 'No jokes yet!',
                                  style: TextStyle(
                                    fontSize: 18,
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurface
                                        .withValues(alpha: 0.6),
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  widget.ratingMode
                                      ? 'All jokes have been rated or don\'t have images'
                                      : filterState.showUnratedOnly
                                      ? 'Try turning off the filter or add some jokes with images'
                                      : 'Tap the + button to add your first joke',
                                  style: TextStyle(
                                    fontSize: 14,
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurface
                                        .withValues(alpha: 0.5),
                                  ),
                                  textAlign: TextAlign.center,
                                ),
                              ],
                            ),
                          )
                          : ListView.builder(
                            padding: const EdgeInsets.all(8.0),
                            itemCount: jokes.length,
                            itemBuilder: (context, index) {
                              final joke = jokes[index];
                              return JokeCard(
                                joke: joke,
                                index: index,
                                isAdminMode: true,
                                showSaveButton: false,
                                showThumbsButtons: true,
                              );
                            },
                          ),
              loading:
                  () => const Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        CircularProgressIndicator(),
                        SizedBox(height: 16),
                        Text('Loading jokes...'),
                      ],
                    ),
                  ),
              error:
                  (error, stackTrace) => Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.error_outline,
                          size: 64,
                          color: Theme.of(context).colorScheme.error,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Error loading jokes',
                          style: TextStyle(
                            fontSize: 18,
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          error.toString(),
                          style: const TextStyle(fontSize: 14),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
            ),
          ),
        ],
      ),
    );
  }
}
