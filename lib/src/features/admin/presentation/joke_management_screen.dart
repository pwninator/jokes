import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';

class JokeManagementScreen extends ConsumerStatefulWidget {
  const JokeManagementScreen({super.key});

  @override
  ConsumerState<JokeManagementScreen> createState() =>
      _JokeManagementScreenState();
}

class _JokeManagementScreenState extends ConsumerState<JokeManagementScreen> {
  String _getEmptyStateTitle(JokeFilterState filterState) {
    if (filterState.showUnratedOnly && filterState.showUnscheduledOnly) {
      return 'No unrated and unscheduled jokes found!';
    } else if (filterState.showUnratedOnly) {
      return 'No unrated jokes with images found!';
    } else if (filterState.showUnscheduledOnly) {
      return 'No unscheduled jokes found!';
    } else {
      return 'No jokes yet!';
    }
  }

  String _getEmptyStateSubtitle(JokeFilterState filterState) {
    if (filterState.showUnratedOnly && filterState.showUnscheduledOnly) {
      return 'Try turning off the filters or add some jokes with images';
    } else if (filterState.showUnratedOnly) {
      return 'Try turning off the filter or add some jokes with images';
    } else if (filterState.showUnscheduledOnly) {
      return 'Try turning off the filter or add some jokes';
    } else {
      return 'Tap the + button to add your first joke';
    }
  }

  @override
  Widget build(BuildContext context) {
    final jokesAsync = ref.watch(filteredJokesProvider);
    final filterState = ref.watch(jokeFilterProvider);

    return AdaptiveAppBarScreen(
      title: 'Joke Management',
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          context.push(AppRoutes.adminEditor);
        },
        tooltip: 'Add New Joke',
        child: const Icon(Icons.add),
      ),
      body: Column(
        children: [
          // Filter bar
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
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Text(
                  'Filters',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    color: Theme.of(
                      context,
                    ).colorScheme.onSurface.withValues(alpha: 0.8),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Wrap(
                    spacing: 4,
                    runSpacing: 0,
                    children: [
                      _AdminFilterChip(
                        key: const Key('unrated-only-filter-chip'),
                        label: 'Unrated',
                        selected: filterState.showUnratedOnly,
                        onSelected: (selected) {
                          ref
                              .read(jokeFilterProvider.notifier)
                              .toggleUnratedOnly();
                        },
                      ),
                      _AdminFilterChip(
                        key: const Key('unscheduled-only-filter-chip'),
                        label: 'Unscheduled',
                        selected: filterState.showUnscheduledOnly,
                        onSelected: (selected) {
                          ref
                              .read(jokeFilterProvider.notifier)
                              .toggleUnscheduledOnly();
                        },
                      ),
                      _AdminFilterChip(
                        key: const Key('popular-only-filter-chip'),
                        label: 'Popular',
                        selected: filterState.showPopularOnly,
                        onSelected: (selected) {
                          ref
                              .read(jokeFilterProvider.notifier)
                              .togglePopularOnly();
                        },
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          // Jokes list
          Expanded(
            child: jokesAsync.when(
              data: (jokes) => jokes.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.mood_bad,
                            size: 64,
                            color: Theme.of(
                              context,
                            ).colorScheme.onSurface.withValues(alpha: 0.4),
                          ),
                          const SizedBox(height: 16),
                          Text(
                            _getEmptyStateTitle(filterState),
                            style: TextStyle(
                              fontSize: 18,
                              color: Theme.of(
                                context,
                              ).colorScheme.onSurface.withValues(alpha: 0.6),
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _getEmptyStateSubtitle(filterState),
                            style: TextStyle(
                              fontSize: 14,
                              color: Theme.of(
                                context,
                              ).colorScheme.onSurface.withValues(alpha: 0.5),
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
                          key: Key(joke.id),
                          joke: joke,
                          index: index,
                          isAdminMode: true,
                          showSaveButton: false,
                          showShareButton: false,
                          showThumbsButtons: true,
                          showNumSaves: true,
                          showNumShares: true,
                          jokeContext: 'admin',
                        );
                      },
                    ),
              loading: () => const Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    CircularProgressIndicator(),
                    SizedBox(height: 16),
                    Text('Loading jokes...'),
                  ],
                ),
              ),
              error: (error, stackTrace) => Center(
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

class _AdminFilterChip extends StatelessWidget {
  const _AdminFilterChip({
    super.key,
    required this.label,
    required this.selected,
    required this.onSelected,
  });

  final String label;
  final bool selected;
  final ValueChanged<bool> onSelected;

  @override
  Widget build(BuildContext context) {
    return FilterChip(
      label: Text(
        label,
        style: Theme.of(context).textTheme.bodySmall?.copyWith(fontSize: 12),
      ),
      labelPadding: const EdgeInsets.symmetric(horizontal: 0),
      visualDensity: VisualDensity.compact,
      selected: selected,
      onSelected: onSelected,
      showCheckmark: true,
    );
  }
}
