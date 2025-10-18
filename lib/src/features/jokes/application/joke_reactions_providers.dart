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
}

// Provider for joke reactions notifier
final jokeReactionsProvider =
    StateNotifierProvider<JokeReactionsNotifier, JokeReactionsState>((ref) {
      final reactionsService = ref.watch(jokeReactionsServiceProvider);
      return JokeReactionsNotifier(reactionsService);
    });
