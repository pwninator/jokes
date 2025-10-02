import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

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
    required BuildContext context,
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
      await _reactionsService.toggleUserReaction(
        jokeId,
        reactionType,
        context: context, // ignore: use_build_context_synchronously
      );

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
