import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';
import 'package:snickerdoodle/src/core/providers/app_providers.dart';

// Provider for getting a specific joke by ID
final jokeByIdProvider = StreamProvider.family<Joke?, String>((ref, jokeId) {
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

// Monthly jokes provider that loads from joke_schedule_batches with dates
final monthlyJokesWithDateProvider = StreamProvider<List<JokeWithDate>>((ref) {
  final repository = ref.watch(jokeScheduleRepositoryProvider);

  return repository
      .watchBatchesForSchedule(JokeConstants.defaultJokeScheduleId)
      .map((batches) {
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
          final sortedDays = batch.jokes.keys.toList()
            ..sort(
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
                    jokesWithDates.add(
                      JokeWithDate(joke: joke, date: jokeDate),
                    );
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
