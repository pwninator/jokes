import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

final jokeLocalReactionsServiceProvider = Provider<JokeLocalReactionsService>((
  ref,
) {
  final jokeRepository = ref.watch(jokeRepositoryProvider);
  final analyticsService = ref.watch(analyticsServiceProvider);
  return JokeLocalReactionsService(
    jokeRepository: jokeRepository,
    analyticsService: analyticsService,
  );
});

/// Service for managing local joke reactions (save functionality)
/// Uses SharedPreferences for state storage and provides save/unsave functionality
class JokeLocalReactionsService {
  final JokeRepository? _jokeRepository;
  final AnalyticsService? _analyticsService;

  // SharedPreferences key for saved jokes
  static const String _savedJokesKey = 'user_reactions_save';

  JokeLocalReactionsService({
    JokeRepository? jokeRepository,
    AnalyticsService? analyticsService,
  }) : _jokeRepository = jokeRepository,
       _analyticsService = analyticsService;

  Future<SharedPreferences> get _prefs => SharedPreferences.getInstance();

  /// Get saved joke IDs in the order they were saved
  Future<List<String>> getSavedJokeIds() async {
    final prefs = await _prefs;
    return prefs.getStringList(_savedJokesKey) ?? [];
  }

  /// Check if a joke is saved
  Future<bool> isJokeSaved(String jokeId) async {
    final prefs = await _prefs;
    final savedJokeIds = prefs.getStringList(_savedJokesKey) ?? [];
    return savedJokeIds.contains(jokeId);
  }

  /// Save a joke
  Future<void> saveJoke(String jokeId, {required String jokeContext}) async {
    final prefs = await _prefs;
    final savedJokeIds = prefs.getStringList(_savedJokesKey) ?? [];

    if (!savedJokeIds.contains(jokeId)) {
      savedJokeIds.add(jokeId);
      await prefs.setStringList(_savedJokesKey, savedJokeIds);

      // Increment save count in Firestore
      if (_jokeRepository != null) {
        try {
          await _jokeRepository.incrementReaction(
            jokeId,
            JokeReactionType.save,
          );
        } catch (e) {
          // Gracefully handle repository failures
          debugPrint('Repository error in saveJoke: $e');
        }
      }

      // Log analytics event
      if (_analyticsService != null) {
        try {
          await _analyticsService.logJokeSaved(
            jokeId,
            true, // isAdded = true
            jokeContext: jokeContext,
          );
        } catch (e) {
          // Gracefully handle analytics failures
          debugPrint('Analytics error in saveJoke: $e');
        }
      }
    }
  }

  /// Unsave a joke
  Future<void> unsaveJoke(String jokeId, {required String jokeContext}) async {
    final prefs = await _prefs;
    final savedJokeIds = prefs.getStringList(_savedJokesKey) ?? [];

    if (savedJokeIds.contains(jokeId)) {
      savedJokeIds.remove(jokeId);
      await prefs.setStringList(_savedJokesKey, savedJokeIds);

      // Decrement save count in Firestore
      if (_jokeRepository != null) {
        try {
          await _jokeRepository.decrementReaction(
            jokeId,
            JokeReactionType.save,
          );
        } catch (e) {
          // Gracefully handle repository failures
          debugPrint('Repository error in unsaveJoke: $e');
        }
      }

      // Log analytics event
      if (_analyticsService != null) {
        try {
          await _analyticsService.logJokeSaved(
            jokeId,
            false, // isAdded = false
            jokeContext: jokeContext,
          );
        } catch (e) {
          // Gracefully handle analytics failures
          debugPrint('Analytics error in unsaveJoke: $e');
        }
      }
    }
  }

  /// Toggle save state (save if not saved, unsave if saved)
  /// Returns true if joke was saved, false if it was unsaved
  Future<bool> toggleSaveJoke(
    String jokeId, {
    required String jokeContext,
  }) async {
    final isSaved = await isJokeSaved(jokeId);

    if (isSaved) {
      await unsaveJoke(jokeId, jokeContext: jokeContext);
      return false; // Joke was unsaved
    } else {
      await saveJoke(jokeId, jokeContext: jokeContext);
      return true; // Joke was saved
    }
  }
}
