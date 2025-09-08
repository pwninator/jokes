import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

// State class for joke modification
class JokeModificationState {
  final bool isLoading;
  final String? error;
  final Set<String> modifyingJokes;

  const JokeModificationState({
    this.isLoading = false,
    this.error,
    this.modifyingJokes = const {},
  });

  JokeModificationState copyWith({
    bool? isLoading,
    String? error,
    Set<String>? modifyingJokes,
    bool clearError = false,
  }) {
    return JokeModificationState(
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
      modifyingJokes: modifyingJokes ?? this.modifyingJokes,
    );
  }
}

// Notifier for managing joke modification
class JokeModificationNotifier extends StateNotifier<JokeModificationState> {
  JokeModificationNotifier(this._cloudFunctionService)
    : super(const JokeModificationState());

  final JokeCloudFunctionService _cloudFunctionService;

  Future<bool> modifyJoke(
    String jokeId, {
    String? setupInstructions,
    String? punchlineInstructions,
  }) async {
    // Add joke to modifying set
    state = state.copyWith(
      modifyingJokes: {...state.modifyingJokes, jokeId},
      error: null,
    );

    try {
      final result = await _cloudFunctionService.modifyJoke(
        jokeId: jokeId,
        setupInstructions: setupInstructions,
        punchlineInstructions: punchlineInstructions,
      );

      if (result != null && result['success'] == true) {
        // Remove joke from modifying set
        final updatedSet = Set<String>.from(state.modifyingJokes)
          ..remove(jokeId);
        state = state.copyWith(modifyingJokes: updatedSet, error: null);
        return true;
      } else {
        // Remove joke from modifying set and set error
        final updatedSet = Set<String>.from(state.modifyingJokes)
          ..remove(jokeId);
        state = state.copyWith(
          modifyingJokes: updatedSet,
          error: result?['error'] ?? 'Unknown error occurred',
        );
        return false;
      }
    } catch (e) {
      // Remove joke from modifying set and set error
      final updatedSet = Set<String>.from(state.modifyingJokes)..remove(jokeId);
      state = state.copyWith(
        modifyingJokes: updatedSet,
        error: 'Failed to modify joke: $e',
      );
      return false;
    }
  }

  void clearError() {
    state = state.copyWith(clearError: true);
  }

  bool isJokeModifying(String jokeId) {
    return state.modifyingJokes.contains(jokeId);
  }
}

// Provider for joke modification notifier
final jokeModificationProvider =
    StateNotifierProvider<JokeModificationNotifier, JokeModificationState>((
      ref,
    ) {
      final cloudFunctionService = ref.watch(jokeCloudFunctionServiceProvider);
      return JokeModificationNotifier(cloudFunctionService);
    });
