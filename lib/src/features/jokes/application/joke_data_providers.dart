import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/app_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

// Provider for getting a specific joke by ID
final jokeStreamByIdProvider = StreamProvider.family<Joke?, String>((
  ref,
  jokeId,
) {
  final repository = ref.watch(jokeRepositoryProvider);
  return repository.getJokeByIdStream(jokeId);
});

// Provider for JokeCloudFunctionService
final jokeCloudFunctionServiceProvider = Provider<JokeCloudFunctionService>((
  ref,
) {
  final perf = ref.read(performanceServiceProvider);
  return JokeCloudFunctionService(perf: perf);
});

// Data class to hold a joke with its associated date
class JokeWithDate {
  final Joke joke;
  final DateTime? date;

  const JokeWithDate({required this.joke, this.date});
}

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
    // Keep logs minimal; analytics will handle error event
    yield <JokeWithDate>[];
  }
});
