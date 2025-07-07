import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

// Provider for FirebaseFirestore instance (local to jokes feature)
final firebaseFirestoreProvider = Provider<FirebaseFirestore>((ref) {
  return FirebaseFirestore.instance;
});

// Provider for JokeRepository
final jokeRepositoryProvider = Provider<JokeRepository>((ref) {
  final firestore = ref.watch(firebaseFirestoreProvider);
  return JokeRepository(firestore);
});

// StreamProvider for the list of jokes
final jokesProvider = StreamProvider<List<Joke>>((ref) {
  final repository = ref.watch(jokeRepositoryProvider);
  return repository.getJokes();
});

// StreamProvider for jokes that have both image URLs
final jokesWithImagesProvider = StreamProvider<List<Joke>>((ref) {
  final repository = ref.watch(jokeRepositoryProvider);
  return repository.getJokes().map(
    (jokes) =>
        jokes
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
  JokeReactionsNotifier(
    this._reactionsService,
    this._jokeRepository,
    this._analyticsService,
  ) : super(const JokeReactionsState()) {
    _loadUserReactions();
  }

  final JokeReactionsService _reactionsService;
  final JokeRepository _jokeRepository;
  final AnalyticsService _analyticsService;

  /// Load user reactions from SharedPreferences on initialization
  Future<void> _loadUserReactions() async {
    state = state.copyWith(isLoading: true, clearError: true);

    try {
      final reactions = await _reactionsService.getAllUserReactions();
      state = state.copyWith(userReactions: reactions, isLoading: false);
    } catch (e) {
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
        await _jokeRepository.decrementReaction(jokeId, oppositeReaction);

        // Track analytics for opposite reaction removal
        await _analyticsService.logJokeReaction(
          jokeId,
          oppositeReaction,
          false,
          jokeContext: jokeContext,
        );
      }

      // Update SharedPreferences and Firestore for the main reaction
      final wasAdded = await _reactionsService.toggleUserReaction(
        jokeId,
        reactionType,
      );

      if (wasAdded) {
        await _jokeRepository.incrementReaction(jokeId, reactionType);
      } else {
        await _jokeRepository.decrementReaction(jokeId, reactionType);
      }

      // Track analytics for reaction toggle
      await _analyticsService.logJokeReaction(
        jokeId,
        reactionType,
        wasAdded,
        jokeContext: jokeContext,
      );
    } catch (e) {
      // Revert optimistic update on error
      await _loadUserReactions(); // Reload from source of truth
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

  /// Clear all user reactions
  Future<void> clearAllUserReactions() async {
    state = state.copyWith(isLoading: true);

    try {
      await _reactionsService.clearAllUserReactions();
      state = state.copyWith(
        userReactions: <String, Set<JokeReactionType>>{},
        isLoading: false,
        clearError: true,
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Failed to clear user reactions: $e',
      );
    }
  }
}

// Provider for joke reactions notifier
final jokeReactionsProvider =
    StateNotifierProvider<JokeReactionsNotifier, JokeReactionsState>((ref) {
      final reactionsService = ref.watch(jokeReactionsServiceProvider);
      final jokeRepository = ref.watch(jokeRepositoryProvider);
      final analyticsService = ref.watch(analyticsServiceProvider);
      return JokeReactionsNotifier(
        reactionsService,
        jokeRepository,
        analyticsService,
      );
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

  const JokeFilterState({this.showUnratedOnly = false});

  JokeFilterState copyWith({bool? showUnratedOnly}) {
    return JokeFilterState(
      showUnratedOnly: showUnratedOnly ?? this.showUnratedOnly,
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
      if (!filterState.showUnratedOnly) {
        return AsyncValue.data(jokes);
      }

      // Filter for unrated jokes: have images AND num_thumbs_up == 0 AND num_thumbs_down == 0
      final filteredJokes =
          jokes.where((joke) {
            final hasImages =
                joke.setupImageUrl != null &&
                joke.setupImageUrl!.isNotEmpty &&
                joke.punchlineImageUrl != null &&
                joke.punchlineImageUrl!.isNotEmpty;

            final isUnrated = joke.numThumbsUp == 0 && joke.numThumbsDown == 0;

            return hasImages && isUnrated;
          }).toList();

      return AsyncValue.data(filteredJokes);
    },
    loading: () => const AsyncValue.loading(),
    error: (error, stackTrace) => AsyncValue.error(error, stackTrace),
  );
});

// Provider for rating mode that loads jokes once and doesn't listen for changes
final ratingModeJokesProvider = FutureProvider<List<Joke>>((ref) async {
  // Use read instead of watch to avoid listening for changes
  final repository = ref.read(jokeRepositoryProvider);
  final jokes = await repository.getJokes().first;

  // Filter for unrated jokes: have images AND num_thumbs_up == 0 AND num_thumbs_down == 0
  final filteredJokes =
      jokes.where((joke) {
        final hasImages =
            joke.setupImageUrl != null &&
            joke.setupImageUrl!.isNotEmpty &&
            joke.punchlineImageUrl != null &&
            joke.punchlineImageUrl!.isNotEmpty;

        final isUnrated = joke.numThumbsUp == 0 && joke.numThumbsDown == 0;

        return hasImages && isUnrated;
      }).toList();

  return filteredJokes;
});

// Data class to hold a joke with its associated date
class JokeWithDate {
  final Joke joke;
  final DateTime date;

  const JokeWithDate({required this.joke, required this.date});
}

// NEW: Monthly jokes provider that loads from joke_schedule_batches with dates
final monthlyJokesWithDateProvider = StreamProvider<List<JokeWithDate>>((ref) {
  final repository = ref.watch(jokeScheduleRepositoryProvider);

  return repository.watchBatchesForSchedule('tester_jokes').map((batches) {
    // Get current date
    final now = DateTime.now();

    // Calculate 6-month window: 3 previous, current, 2 next
    final targetMonths = <DateTime>[];
    for (int i = -3; i <= 2; i++) {
      targetMonths.add(DateTime(now.year, now.month + i));
    }

    // Filter batches for our target months
    final relevantBatches =
        batches.where((batch) {
          final batchDate = DateTime(batch.year, batch.month);
          return targetMonths.any(
            (target) =>
                target.year == batchDate.year &&
                target.month == batchDate.month,
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
      final sortedDays =
          batch.jokes.keys.toList()..sort(
            (a, b) => b.compareTo(a),
          ); // Reverse sort for newest day first

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

// NEW: Saved jokes provider that loads saved jokes from SharedPreferences
final savedJokesProvider = StreamProvider<List<JokeWithDate>>((ref) async* {
  final reactionsState = ref.watch(jokeReactionsProvider);
  final jokeRepository = ref.watch(jokeRepositoryProvider);

  // Get saved joke IDs (those with save reaction)
  final savedJokeIds = <String>[];
  for (final entry in reactionsState.userReactions.entries) {
    if (entry.value.contains(JokeReactionType.save)) {
      savedJokeIds.add(entry.key);
    }
  }

  if (savedJokeIds.isEmpty) {
    yield <JokeWithDate>[];
    return;
  }

  try {
    // Fetch full joke data for saved IDs
    final savedJokes = <JokeWithDate>[];

    for (final jokeId in savedJokeIds) {
      try {
        final joke = await jokeRepository.getJokeById(jokeId);
        if (joke != null) {
          // Filter for jokes with images
          if (joke.setupImageUrl != null &&
              joke.setupImageUrl!.isNotEmpty &&
              joke.punchlineImageUrl != null &&
              joke.punchlineImageUrl!.isNotEmpty) {
            // Use current date as placeholder since saved jokes don't have associated dates
            savedJokes.add(JokeWithDate(joke: joke, date: DateTime.now()));
          }
        }
      } catch (e) {
        // Skip individual jokes that fail to load
        debugPrint('Failed to load saved joke $jokeId: $e');
      }
    }

    // Sort by joke ID (newest first, assuming IDs are chronological)
    savedJokes.sort((a, b) => b.joke.id.compareTo(a.joke.id));

    yield savedJokes;
  } catch (e) {
    // Handle errors gracefully
    debugPrint('Error loading saved jokes: $e');
    yield <JokeWithDate>[];
  }
});
