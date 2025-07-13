import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

final jokeReactionsServiceProvider = Provider<JokeReactionsService>((ref) {
  final jokeRepository = ref.watch(jokeRepositoryProvider);
  final analyticsService = ref.watch(analyticsServiceProvider);
  return JokeReactionsService(
    jokeRepository: jokeRepository,
    analyticsService: analyticsService,
  );
});

class JokeReactionsService {
  final JokeRepository? _jokeRepository;
  final AnalyticsService? _analyticsService;

  JokeReactionsService({
    JokeRepository? jokeRepository,
    AnalyticsService? analyticsService,
  }) : _jokeRepository = jokeRepository,
       _analyticsService = analyticsService;

  Future<SharedPreferences> get _prefs => SharedPreferences.getInstance();

  /// Get all user reactions for all jokes
  /// Returns a map: jokeId -> Set of active reaction types
  Future<Map<String, Set<JokeReactionType>>> getAllUserReactions() async {
    final prefs = await _prefs;
    final Map<String, Set<JokeReactionType>> allReactions = {};

    for (final reactionType in JokeReactionType.values) {
      final jokeIds = prefs.getStringList(reactionType.prefsKey) ?? [];
      for (final jokeId in jokeIds) {
        allReactions[jokeId] ??= <JokeReactionType>{};
        allReactions[jokeId]!.add(reactionType);
      }
    }

    return allReactions;
  }

  /// Get saved joke IDs in the order they were saved to SharedPreferences
  Future<List<String>> getSavedJokeIds() async {
    final prefs = await _prefs;
    return prefs.getStringList(JokeReactionType.save.prefsKey) ?? [];
  }

  /// Get user reactions for a specific joke
  Future<Set<JokeReactionType>> getUserReactionsForJoke(String jokeId) async {
    final prefs = await _prefs;
    final Set<JokeReactionType> reactions = {};

    for (final reactionType in JokeReactionType.values) {
      final jokeIds = prefs.getStringList(reactionType.prefsKey) ?? [];
      if (jokeIds.contains(jokeId)) {
        reactions.add(reactionType);
      }
    }

    return reactions;
  }

  /// Check if user has reacted to a joke with a specific reaction type
  Future<bool> hasUserReaction(
    String jokeId,
    JokeReactionType reactionType,
  ) async {
    final prefs = await _prefs;
    final jokeIds = prefs.getStringList(reactionType.prefsKey) ?? [];
    return jokeIds.contains(jokeId);
  }

  /// Add a user reaction
  Future<void> addUserReaction(
    String jokeId,
    JokeReactionType reactionType, {
    required String jokeContext,
  }) async {
    final prefs = await _prefs;
    final jokeIds = prefs.getStringList(reactionType.prefsKey) ?? [];

    if (!jokeIds.contains(jokeId)) {
      jokeIds.add(jokeId);
      await prefs.setStringList(reactionType.prefsKey, jokeIds);

      // Increment reaction count in repository
      if (_jokeRepository != null) {
        await _jokeRepository.incrementReaction(jokeId, reactionType);
      }

      // Track analytics for reaction
      if (_analyticsService != null) {
        if (reactionType == JokeReactionType.save) {
          await _analyticsService.logJokeSaved(
            jokeId,
            true, // Always true for add
            jokeContext: jokeContext,
          );
        } else if (reactionType == JokeReactionType.share) {
          await _analyticsService.logJokeShared(
            jokeId,
            jokeContext: jokeContext,
          );
        }
      }
    }
  }

  /// Remove a user reaction
  Future<void> removeUserReaction(
    String jokeId,
    JokeReactionType reactionType, {
    required String jokeContext,
  }) async {
    final prefs = await _prefs;
    final jokeIds = prefs.getStringList(reactionType.prefsKey) ?? [];

    if (jokeIds.contains(jokeId)) {
      jokeIds.remove(jokeId);
      await prefs.setStringList(reactionType.prefsKey, jokeIds);

      // Decrement reaction count in repository
      if (_jokeRepository != null) {
        await _jokeRepository.decrementReaction(jokeId, reactionType);
      }

      // Track analytics for reaction
      if (_analyticsService != null) {
        if (reactionType == JokeReactionType.save) {
          await _analyticsService.logJokeSaved(
            jokeId,
            false, // Always false for remove
            jokeContext: jokeContext,
          );
        } else if (reactionType == JokeReactionType.share) {
          await _analyticsService.logJokeShared(
            jokeId,
            jokeContext: jokeContext,
          );
        }
      }
    }
  }

  /// Toggle a user reaction (add if not present, remove if present)
  Future<bool> toggleUserReaction(
    String jokeId,
    JokeReactionType reactionType, {
    required String jokeContext,
  }) async {
    final hasReaction = await hasUserReaction(jokeId, reactionType);

    if (hasReaction) {
      await removeUserReaction(jokeId, reactionType, jokeContext: jokeContext);
      return false; // Reaction was removed
    } else {
      await addUserReaction(jokeId, reactionType, jokeContext: jokeContext);
      return true; // Reaction was added
    }
  }
}
