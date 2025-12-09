import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

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

  Future<bool> regenerateImagesViaCreationProcess(
    String jokeId, {
    required String imageQuality,
    String? setupSceneIdea,
    String? punchlineSceneIdea,
  }) async {
    state = state.copyWith(
      populatingJokes: {...state.populatingJokes, jokeId},
      error: null,
    );

    try {
      await _cloudFunctionService.generateImagesViaCreationProcess(
        jokeId: jokeId,
        imageQuality: imageQuality,
        setupSceneIdea: setupSceneIdea,
        punchlineSceneIdea: punchlineSceneIdea,
      );
      final updatedSet = Set<String>.from(state.populatingJokes)
        ..remove(jokeId);
      state = state.copyWith(populatingJokes: updatedSet, error: null);
      return true;
    } catch (e) {
      final updatedSet = Set<String>.from(state.populatingJokes)
        ..remove(jokeId);
      state = state.copyWith(
        populatingJokes: updatedSet,
        error: 'Failed to regenerate images: $e',
      );
      return false;
    }
  }

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
