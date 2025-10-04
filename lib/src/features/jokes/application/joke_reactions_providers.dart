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

  /// Refresh user reactions from SharedPreferences
  Future<void> refreshUserReactions() async {
    await _loadUserReactions();
  }

  /// Toggle a reaction with optimistic UI updates and error handling.
  Future<void> toggleReaction(
    String jokeId,
    JokeReactionType reactionType, {
    required String jokeContext,
    required BuildContext context,
  }) async {
    // Clear previous error
    state = state.copyWith(clearError: true);

    final Map<String, Set<JokeReactionType>> currentReactions =
        Map<String, Set<JokeReactionType>>.from(state.userReactions);
    final Set<JokeReactionType> currentForJoke = Set<JokeReactionType>.from(
      currentReactions[jokeId] ?? <JokeReactionType>{},
    );

    final bool currentlyHasReaction = currentForJoke.contains(reactionType);
    final bool willAdd = !currentlyHasReaction;

    final bool isThumbs =
        reactionType == JokeReactionType.thumbsUp ||
        reactionType == JokeReactionType.thumbsDown;
    final JokeReactionType? oppositeReaction =
        reactionType == JokeReactionType.thumbsUp
        ? JokeReactionType.thumbsDown
        : (reactionType == JokeReactionType.thumbsDown
              ? JokeReactionType.thumbsUp
              : null);

    bool removedOpposite = false;

    // If adding a thumbs reaction and the opposite is present, remove it first (optimistically and in service)
    if (willAdd &&
        isThumbs &&
        oppositeReaction != null &&
        currentForJoke.contains(oppositeReaction)) {
      currentForJoke.remove(oppositeReaction);
      removedOpposite = true;
      try {
        await _reactionsService.removeUserReaction(jokeId, oppositeReaction);
      } catch (_) {
        // Ignore best-effort opposite removal failures here; main toggle will still attempt
      }
    }

    // Optimistic toggle for the requested reaction
    if (currentlyHasReaction) {
      currentForJoke.remove(reactionType);
    } else {
      currentForJoke.add(reactionType);
    }
    currentReactions[jokeId] = currentForJoke;
    state = state.copyWith(userReactions: currentReactions);

    try {
      final bool added = await _reactionsService.toggleUserReaction(
        jokeId,
        reactionType,
        context: context,
      );

      // Reconcile optimistic state if service result differs
      if (added != willAdd) {
        final Map<String, Set<JokeReactionType>> reconciled =
            Map<String, Set<JokeReactionType>>.from(state.userReactions);
        final Set<JokeReactionType> reconciledSet = Set<JokeReactionType>.from(
          reconciled[jokeId] ?? <JokeReactionType>{},
        );
        if (added) {
          reconciledSet.add(reactionType);
        } else {
          reconciledSet.remove(reactionType);
        }
        reconciled[jokeId] = reconciledSet;
        state = state.copyWith(userReactions: reconciled);
      }
    } catch (error) {
      // Revert optimistic change
      final Map<String, Set<JokeReactionType>> reverted =
          Map<String, Set<JokeReactionType>>.from(state.userReactions);
      final Set<JokeReactionType> revertedSet = Set<JokeReactionType>.from(
        reverted[jokeId] ?? <JokeReactionType>{},
      );

      if (willAdd) {
        revertedSet.remove(reactionType);
        if (removedOpposite && oppositeReaction != null) {
          revertedSet.add(oppositeReaction);
        }
      } else {
        revertedSet.add(reactionType);
      }

      reverted[jokeId] = revertedSet;
      state = state.copyWith(
        userReactions: reverted,
        error: _buildToggleErrorMessage(reactionType, willAdd),
      );
    }
  }

  String _buildToggleErrorMessage(
    JokeReactionType reactionType,
    bool wasAdding,
  ) {
    final String action = wasAdding ? 'add' : 'remove';
    final String name = _reactionDisplayName(reactionType);
    return 'Failed to $action $name';
  }

  String _reactionDisplayName(JokeReactionType reactionType) {
    switch (reactionType) {
      case JokeReactionType.thumbsUp:
        return 'Like';
      case JokeReactionType.thumbsDown:
        return 'Dislike';
      case JokeReactionType.save:
        return 'Save';
      case JokeReactionType.share:
        return 'Share';
    }
  }
}

// Provider for joke reactions notifier
final jokeReactionsProvider =
    StateNotifierProvider<JokeReactionsNotifier, JokeReactionsState>((ref) {
      final reactionsService = ref.watch(jokeReactionsServiceProvider);
      return JokeReactionsNotifier(reactionsService);
    });
