import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
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

  Future<bool> populateJoke(String jokeId, {bool imagesOnly = false}) async {
    // Add joke to populating set
    state = state.copyWith(
      populatingJokes: {...state.populatingJokes, jokeId},
      error: null,
    );

    try {
      final result = await _cloudFunctionService.populateJoke(
        jokeId,
        imagesOnly: imagesOnly,
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
  JokeReactionsNotifier(this._reactionsService, this._jokeRepository)
      : super(const JokeReactionsState()) {
    _loadUserReactions();
  }

  final JokeReactionsService _reactionsService;
  final JokeRepository _jokeRepository;

  /// Load user reactions from SharedPreferences on initialization
  Future<void> _loadUserReactions() async {
    state = state.copyWith(isLoading: true, clearError: true);
    
    try {
      final reactions = await _reactionsService.getAllUserReactions();
      state = state.copyWith(
        userReactions: reactions,
        isLoading: false,
      );
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
    JokeReactionType reactionType,
  ) async {
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
    final newUserReactions = Map<String, Set<JokeReactionType>>.from(state.userReactions);
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
      }
      
      // Update SharedPreferences and Firestore for the main reaction
      final wasAdded = await _reactionsService.toggleUserReaction(jokeId, reactionType);
      
      if (wasAdded) {
        await _jokeRepository.incrementReaction(jokeId, reactionType);
      } else {
        await _jokeRepository.decrementReaction(jokeId, reactionType);
      }
    } catch (e) {
      // Revert optimistic update on error
      await _loadUserReactions(); // Reload from source of truth
      state = state.copyWith(
        error: 'Failed to ${hadReaction ? 'remove' : 'add'} ${reactionType.label}: $e',
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
  return JokeReactionsNotifier(reactionsService, jokeRepository);
});

// Family provider to check if a user has reacted to a joke with a specific reaction type
final hasUserReactionProvider = Provider.family<bool, ({String jokeId, JokeReactionType reactionType})>((ref, params) {
  final reactionsState = ref.watch(jokeReactionsProvider);
  return reactionsState.userReactions[params.jokeId]?.contains(params.reactionType) ?? false;
});

// Family provider to get all user reactions for a specific joke
final userReactionsForJokeProvider = Provider.family<Set<JokeReactionType>, String>((ref, jokeId) {
  final reactionsState = ref.watch(jokeReactionsProvider);
  return reactionsState.userReactions[jokeId] ?? <JokeReactionType>{};
});
