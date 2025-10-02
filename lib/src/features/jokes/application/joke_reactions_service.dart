import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

final jokeReactionsServiceProvider = Provider<JokeReactionsService>((ref) {
  final jokeRepository = ref.watch(jokeRepositoryProvider);
  final appUsageService = ref.watch(appUsageServiceProvider);
  final reviewCoordinator = ref.watch(reviewPromptCoordinatorProvider);
  return JokeReactionsService(
    jokeRepository: jokeRepository,
    appUsageService: appUsageService,
    reviewPromptCoordinator: reviewCoordinator,
  );
});

class JokeReactionsService {
  final JokeRepository? _jokeRepository;
  final AppUsageService _appUsageService;
  final ReviewPromptCoordinator _reviewPromptCoordinator;

  JokeReactionsService({
    JokeRepository? jokeRepository,
    required AppUsageService appUsageService,
    required ReviewPromptCoordinator reviewPromptCoordinator,
  }) : _jokeRepository = jokeRepository,
       _appUsageService = appUsageService,
       _reviewPromptCoordinator = reviewPromptCoordinator;

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
    required BuildContext context,
  }) async {
    final prefs = await _prefs;
    final jokeIds = prefs.getStringList(reactionType.prefsKey) ?? [];

    if (!jokeIds.contains(jokeId)) {
      jokeIds.add(jokeId);
      await prefs.setStringList(reactionType.prefsKey, jokeIds);

      // Update usage counters for saved reaction
      if (reactionType == JokeReactionType.save) {
        await _appUsageService.incrementSavedJokesCount();
      }

      if (context.mounted &&
          (reactionType == JokeReactionType.save ||
              reactionType == JokeReactionType.share)) {
        // Trigger review check only on successful save addition
        await _reviewPromptCoordinator.maybePromptForReview(
          source: reactionType == JokeReactionType.save
              ? ReviewRequestSource.jokeSaved
              : ReviewRequestSource.jokeShared,
          context: context,
        );
      }

      // Handle Firestore operations asynchronously without blocking UI
      _handleFirestoreUpdateAsync(jokeId, reactionType, 1);
    }
  }

  /// Remove a user reaction
  Future<void> removeUserReaction(
    String jokeId,
    JokeReactionType reactionType,
  ) async {
    final prefs = await _prefs;
    final jokeIds = prefs.getStringList(reactionType.prefsKey) ?? [];

    if (jokeIds.contains(jokeId)) {
      jokeIds.remove(jokeId);
      await prefs.setStringList(reactionType.prefsKey, jokeIds);

      // Update usage counters for saved reaction
      if (reactionType == JokeReactionType.save) {
        await _appUsageService.decrementSavedJokesCount();
      }

      // Handle Firestore operations asynchronously without blocking UI
      _handleFirestoreUpdateAsync(jokeId, reactionType, -1);
    }
  }

  /// Toggle a user reaction (add if not present, remove if present)
  Future<bool> toggleUserReaction(
    String jokeId,
    JokeReactionType reactionType, {
    required BuildContext context,
  }) async {
    final hasReaction = await hasUserReaction(jokeId, reactionType);

    if (hasReaction) {
      await removeUserReaction(jokeId, reactionType);
      return false; // Reaction was removed
    } else {
      await addUserReaction(
        jokeId,
        reactionType,
        context: context, // ignore: use_build_context_synchronously
      );
      return true; // Reaction was added
    }
  }

  /// Handle Firestore reaction update operation asynchronously without blocking UI
  void _handleFirestoreUpdateAsync(
    String jokeId,
    JokeReactionType reactionType,
    int increment,
  ) {
    final repository = _jokeRepository;
    if (repository != null) {
      // Fire and forget - don't await this operation
      repository
          .updateReactionAndPopularity(jokeId, reactionType, increment)
          .catchError((error) {
            // Log error but don't throw - this shouldn't affect UI state
            // since SharedPreferences has already been updated
            final action = increment > 0 ? 'increment' : 'decrement';
            AppLogger.warn(
              'Failed to $action Firestore reaction for joke $jokeId, reaction $reactionType: $error',
            );
          });
    }
  }
}
