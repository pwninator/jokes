import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

// StreamProvider for the list of jokes
final jokesProvider = StreamProvider<List<Joke>>((ref) {
  final repository = ref.watch(jokeRepositoryProvider);
  return repository.getJokes();
});

// StreamProvider for jokes that have both image URLs
final jokesWithImagesProvider = StreamProvider<List<Joke>>((ref) {
  final repository = ref.watch(jokeRepositoryProvider);
  return repository.getJokes().map(
    (jokes) => jokes
        .where(
          (joke) =>
              joke.setupImageUrl != null &&
              joke.setupImageUrl!.isNotEmpty &&
              joke.punchlineImageUrl != null &&
              joke.punchlineImageUrl!.isNotEmpty,
        )
        .toList(),
  );
});

// Provider for getting a specific joke by ID
final jokeByIdProvider = StreamProvider.family<Joke?, String>((ref, jokeId) {
  final repository = ref.watch(jokeRepositoryProvider);
  return repository.getJokeByIdStream(jokeId);
});

// Provider for JokeCloudFunctionService
final jokeCloudFunctionServiceProvider = Provider<JokeCloudFunctionService>((
  ref,
) {
  return JokeCloudFunctionService();
});

// State class for joke population
class JokePopulationState {
  final bool isLoading;
  final String? error;
  final Set<String> populatingJokes;

  const JokePopulationState({
    this.isLoading = false,
    this.error,
    this.populatingJokes = const {},
  });

  JokePopulationState copyWith({
    bool? isLoading,
    String? error,
    Set<String>? populatingJokes,
    bool clearError = false,
  }) {
    return JokePopulationState(
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
      populatingJokes: populatingJokes ?? this.populatingJokes,
    );
  }
}

// Notifier for managing joke population
class JokePopulationNotifier extends StateNotifier<JokePopulationState> {
  JokePopulationNotifier(this._cloudFunctionService)
    : super(const JokePopulationState());

  final JokeCloudFunctionService _cloudFunctionService;

  Future<bool> populateJoke(
    String jokeId, {
    bool imagesOnly = false,
    Map<String, dynamic>? additionalParams,
  }) async {
    // Add joke to populating set
    state = state.copyWith(
      populatingJokes: {...state.populatingJokes, jokeId},
      error: null,
    );

    try {
      final result = await _cloudFunctionService.populateJoke(
        jokeId,
        imagesOnly: imagesOnly,
        additionalParams: additionalParams,
      );

      if (result != null && result['success'] == true) {
        // Remove joke from populating set
        final updatedSet = Set<String>.from(state.populatingJokes)
          ..remove(jokeId);
        state = state.copyWith(populatingJokes: updatedSet, error: null);
        return true;
      } else {
        // Remove joke from populating set and set error
        final updatedSet = Set<String>.from(state.populatingJokes)
          ..remove(jokeId);
        state = state.copyWith(
          populatingJokes: updatedSet,
          error: result?['error'] ?? 'Unknown error occurred',
        );
        return false;
      }
    } catch (e) {
      // Remove joke from populating set and set error
      final updatedSet = Set<String>.from(state.populatingJokes)
        ..remove(jokeId);
      state = state.copyWith(
        populatingJokes: updatedSet,
        error: 'Failed to populate joke: $e',
      );
      return false;
    }
  }

  void clearError() {
    state = state.copyWith(clearError: true);
  }

  bool isJokePopulating(String jokeId) {
    return state.populatingJokes.contains(jokeId);
  }
}

// Provider for joke population notifier
final jokePopulationProvider =
    StateNotifierProvider<JokePopulationNotifier, JokePopulationState>((ref) {
      final cloudFunctionService = ref.watch(jokeCloudFunctionServiceProvider);
      return JokePopulationNotifier(cloudFunctionService);
    });

// State class for joke reactions
class JokeReactionsState {
  final Map<String, Set<JokeReactionType>> userReactions;
  final bool isLoading;
  final String? error;

  const JokeReactionsState({
    this.userReactions = const {},
    this.isLoading = false,
    this.error,
  });

  JokeReactionsState copyWith({
    Map<String, Set<JokeReactionType>>? userReactions,
    bool? isLoading,
    String? error,
    bool clearError = false,
  }) {
    return JokeReactionsState(
      userReactions: userReactions ?? this.userReactions,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

// Notifier for managing joke reactions
class JokeReactionsNotifier extends StateNotifier<JokeReactionsState> {
  JokeReactionsNotifier(this._reactionsService)
    : super(const JokeReactionsState()) {
    _loadUserReactions();
  }

  final JokeReactionsService _reactionsService;

  /// Load user reactions from SharedPreferences on initialization
  Future<void> _loadUserReactions() async {
    if (!mounted) return;
    state = state.copyWith(isLoading: true, clearError: true);

    try {
      final reactions = await _reactionsService.getAllUserReactions();
      if (!mounted) return;
      state = state.copyWith(userReactions: reactions, isLoading: false);
    } catch (e) {
      if (!mounted) return;
      state = state.copyWith(
        isLoading: false,
        error: 'Failed to load user reactions: $e',
      );
    }
  }

  /// Toggle a user's reaction to a joke
  Future<void> toggleReaction(
    String jokeId,
    JokeReactionType reactionType, {
    required String jokeContext,
  }) async {
    final hadReaction = hasUserReaction(jokeId, reactionType);

    // Check if this is a thumbs reaction and handle exclusivity
    JokeReactionType? oppositeReaction;
    bool hadOppositeReaction = false;

    if (reactionType == JokeReactionType.thumbsUp) {
      oppositeReaction = JokeReactionType.thumbsDown;
      hadOppositeReaction = hasUserReaction(jokeId, oppositeReaction);
    } else if (reactionType == JokeReactionType.thumbsDown) {
      oppositeReaction = JokeReactionType.thumbsUp;
      hadOppositeReaction = hasUserReaction(jokeId, oppositeReaction);
    }

    // Optimistic update
    final newUserReactions = Map<String, Set<JokeReactionType>>.from(
      state.userReactions,
    );
    newUserReactions[jokeId] ??= <JokeReactionType>{};

    if (hadReaction) {
      // Remove the current reaction
      newUserReactions[jokeId]!.remove(reactionType);
      if (newUserReactions[jokeId]!.isEmpty) {
        newUserReactions.remove(jokeId);
      }
    } else {
      // Add the new reaction
      newUserReactions[jokeId]!.add(reactionType);

      // If this is a thumbs reaction and user had the opposite reaction, remove it
      if (oppositeReaction != null && hadOppositeReaction) {
        newUserReactions[jokeId]!.remove(oppositeReaction);
      }
    }

    state = state.copyWith(userReactions: newUserReactions, clearError: true);

    try {
      // Handle the opposite reaction first (if applicable)
      if (!hadReaction && oppositeReaction != null && hadOppositeReaction) {
        await _reactionsService.removeUserReaction(jokeId, oppositeReaction);
      }

      // Update SharedPreferences and Firestore for the main reaction
      await _reactionsService.toggleUserReaction(jokeId, reactionType);

      // Note: Analytics are handled by individual widgets (SaveJokeButton, etc.)
      // Note: This keeps the provider focused on core state management
    } catch (e) {
      // Revert optimistic update on error
      if (!mounted) return;
      await _loadUserReactions(); // Reload from source of truth
      if (!mounted) return;
      state = state.copyWith(
        error:
            'Failed to ${hadReaction ? 'remove' : 'add'} ${reactionType.label}: $e',
      );
    }
  }

  /// Check if user has reacted to a joke with a specific reaction type
  bool hasUserReaction(String jokeId, JokeReactionType reactionType) {
    return state.userReactions[jokeId]?.contains(reactionType) ?? false;
  }

  /// Get all reactions for a specific joke
  Set<JokeReactionType> getUserReactionsForJoke(String jokeId) {
    return state.userReactions[jokeId] ?? <JokeReactionType>{};
  }

  /// Clear any error state
  void clearError() {
    state = state.copyWith(clearError: true);
  }

  /// Refresh user reactions from SharedPreferences
  Future<void> refreshUserReactions() async {
    await _loadUserReactions();
  }
}

// Provider for joke reactions notifier
final jokeReactionsProvider =
    StateNotifierProvider<JokeReactionsNotifier, JokeReactionsState>((ref) {
      final reactionsService = ref.watch(jokeReactionsServiceProvider);
      return JokeReactionsNotifier(reactionsService);
    });

// Family provider to check if a user has reacted to a joke with a specific reaction type
final hasUserReactionProvider =
    Provider.family<bool, ({String jokeId, JokeReactionType reactionType})>((
      ref,
      params,
    ) {
      final reactionsState = ref.watch(jokeReactionsProvider);
      return reactionsState.userReactions[params.jokeId]?.contains(
            params.reactionType,
          ) ??
          false;
    });

// Family provider to get all user reactions for a specific joke
final userReactionsForJokeProvider =
    Provider.family<Set<JokeReactionType>, String>((ref, jokeId) {
      final reactionsState = ref.watch(jokeReactionsProvider);
      return reactionsState.userReactions[jokeId] ?? <JokeReactionType>{};
    });

// State class for joke filter
class JokeFilterState {
  final bool showUnratedOnly;
  final bool showUnscheduledOnly;
  final bool showPopularOnly; // saves + shares > 0

  const JokeFilterState({
    this.showUnratedOnly = false,
    this.showUnscheduledOnly = false,
    this.showPopularOnly = false,
  });

  JokeFilterState copyWith({
    bool? showUnratedOnly,
    bool? showUnscheduledOnly,
    bool? showPopularOnly,
  }) {
    return JokeFilterState(
      showUnratedOnly: showUnratedOnly ?? this.showUnratedOnly,
      showUnscheduledOnly: showUnscheduledOnly ?? this.showUnscheduledOnly,
      showPopularOnly: showPopularOnly ?? this.showPopularOnly,
    );
  }
}

// Notifier for managing joke filter
class JokeFilterNotifier extends StateNotifier<JokeFilterState> {
  JokeFilterNotifier() : super(const JokeFilterState());

  void toggleUnratedOnly() {
    state = state.copyWith(showUnratedOnly: !state.showUnratedOnly);
  }

  void setUnratedOnly(bool value) {
    state = state.copyWith(showUnratedOnly: value);
  }

  void toggleUnscheduledOnly() {
    state = state.copyWith(showUnscheduledOnly: !state.showUnscheduledOnly);
  }

  void setUnscheduledOnly(bool value) {
    state = state.copyWith(showUnscheduledOnly: value);
  }

  void togglePopularOnly() {
    state = state.copyWith(showPopularOnly: !state.showPopularOnly);
  }

  void setPopularOnly(bool value) {
    state = state.copyWith(showPopularOnly: value);
  }
}

// Provider for joke filter notifier
final jokeFilterProvider =
    StateNotifierProvider<JokeFilterNotifier, JokeFilterState>((ref) {
      return JokeFilterNotifier();
    });

// Provider for filtered jokes (used in joke management screen)
final filteredJokesProvider = Provider<AsyncValue<List<Joke>>>((ref) {
  final jokesAsync = ref.watch(jokesProvider);
  final filterState = ref.watch(jokeFilterProvider);

  return jokesAsync.when(
    data: (jokes) {
      var filteredJokes = jokes;

      // Apply unrated filter if enabled
      if (filterState.showUnratedOnly) {
        filteredJokes = filteredJokes.where((joke) {
          final hasImages =
              joke.setupImageUrl != null &&
              joke.setupImageUrl!.isNotEmpty &&
              joke.punchlineImageUrl != null &&
              joke.punchlineImageUrl!.isNotEmpty;

          final isUnrated = joke.numThumbsUp == 0 && joke.numThumbsDown == 0;

          return hasImages && isUnrated;
        }).toList();
      }

      // Apply unscheduled filter if enabled
      if (filterState.showUnscheduledOnly) {
        final scheduledJokesAsync = ref.watch(monthlyJokesWithDateProvider);
        return scheduledJokesAsync.when(
          data: (scheduledJokes) {
            final scheduledJokeIds = scheduledJokes
                .map((jokeWithDate) => jokeWithDate.joke.id)
                .toSet();
            filteredJokes = filteredJokes
                .where((joke) => !scheduledJokeIds.contains(joke.id))
                .toList();
            return AsyncValue.data(filteredJokes);
          },
          loading: () => const AsyncValue.loading(),
          error: (error, stackTrace) => AsyncValue.error(error, stackTrace),
        );
      }

      // Apply popular filter if enabled (saves + shares > 0)
      if (filterState.showPopularOnly) {
        filteredJokes = filteredJokes
            .where((joke) => (joke.numSaves + joke.numShares) > 0)
            .toList();
      }

      return AsyncValue.data(filteredJokes);
    },
    loading: () => const AsyncValue.loading(),
    error: (error, stackTrace) => AsyncValue.error(error, stackTrace),
  );
});

// Data class to hold a joke with its associated date
class JokeWithDate {
  final Joke joke;
  final DateTime? date;

  const JokeWithDate({required this.joke, this.date});
}

// Monthly jokes provider that loads from joke_schedule_batches with dates
final monthlyJokesWithDateProvider = StreamProvider<List<JokeWithDate>>((ref) {
  final repository = ref.watch(jokeScheduleRepositoryProvider);

  return repository.watchBatchesForSchedule(JokeConstants.defaultJokeScheduleId).map((
    batches,
  ) {
    // Get current date
    final now = DateTime.now();

    // Calculate 6-month window: 3 previous, current, 2 next
    final targetMonths = <DateTime>[];
    for (int i = -3; i <= 2; i++) {
      targetMonths.add(DateTime(now.year, now.month + i));
    }

    // Filter batches for our target months
    final relevantBatches = batches.where((batch) {
      final batchDate = DateTime(batch.year, batch.month);
      return targetMonths.any(
        (target) =>
            target.year == batchDate.year && target.month == batchDate.month,
      );
    }).toList();

    // Convert batches to chronological joke list with dates
    final jokesWithDates = <JokeWithDate>[];

    // Sort batches in reverse chronological order (newest first)
    relevantBatches.sort((a, b) {
      final aDate = DateTime(a.year, a.month);
      final bDate = DateTime(b.year, b.month);
      return bDate.compareTo(aDate); // Reversed for newest first
    });

    // Extract jokes from each batch in reverse chronological order
    for (final batch in relevantBatches) {
      // Get all days in the batch and sort them in descending order
      final sortedDays = batch.jokes.keys.toList()
        ..sort((a, b) => b.compareTo(a)); // Reverse sort for newest day first

      // Add jokes in day order, but only for dates that are not in the future
      for (final day in sortedDays) {
        final joke = batch.jokes[day];
        if (joke != null) {
          // Parse day string to int and create full date
          final dayInt = int.tryParse(day);
          if (dayInt != null) {
            final jokeDate = DateTime(batch.year, batch.month, dayInt);
            final today = DateTime.now();
            final todayDate = DateTime(today.year, today.month, today.day);

            // Only include jokes for today or past dates
            if (!jokeDate.isAfter(todayDate)) {
              // Filter for jokes with images
              if (joke.setupImageUrl != null &&
                  joke.setupImageUrl!.isNotEmpty &&
                  joke.punchlineImageUrl != null &&
                  joke.punchlineImageUrl!.isNotEmpty) {
                jokesWithDates.add(JokeWithDate(joke: joke, date: jokeDate));
              }
            }
          }
        }
      }
    }

    return jokesWithDates;
  });
});

// Saved jokes provider that loads saved jokes from SharedPreferences
final savedJokesProvider = StreamProvider<List<JokeWithDate>>((ref) async* {
  final jokeRepository = ref.watch(jokeRepositoryProvider);
  final reactionsService = ref.watch(jokeReactionsServiceProvider);

  // Watch the reactions state to react to save/unsave changes
  final reactionsState = ref.watch(jokeReactionsProvider);

  // Check if there are any saved jokes in the reactions state
  final hasSavedJokes = reactionsState.userReactions.values.any(
    (reactions) => reactions.contains(JokeReactionType.save),
  );

  if (!hasSavedJokes) {
    yield <JokeWithDate>[];
    return;
  }

  // Get saved joke IDs directly from SharedPreferences in the order they were saved
  final savedJokeIds = await reactionsService.getSavedJokeIds();

  if (savedJokeIds.isEmpty) {
    yield <JokeWithDate>[];
    return;
  }

  try {
    // Fetch all jokes in a single batch query
    final allJokes = await jokeRepository.getJokesByIds(savedJokeIds);

    // Create a map for quick lookup while preserving order
    final jokeMap = <String, Joke>{};
    for (final joke in allJokes) {
      jokeMap[joke.id] = joke;
    }

    // Build the result list in the same order as savedJokeIds
    final savedJokes = <JokeWithDate>[];
    for (final jokeId in savedJokeIds) {
      final joke = jokeMap[jokeId];
      if (joke != null) {
        // Filter for jokes with images
        if (joke.setupImageUrl != null &&
            joke.setupImageUrl!.isNotEmpty &&
            joke.punchlineImageUrl != null &&
            joke.punchlineImageUrl!.isNotEmpty) {
          savedJokes.add(JokeWithDate(joke: joke));
        }
      }
    }

    // Maintain the order from SharedPreferences (no sorting)
    yield savedJokes;
  } catch (e) {
    // Handle errors gracefully
    debugPrint('Error loading saved jokes: $e');
    yield <JokeWithDate>[];
  }
});
