import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_service.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

part 'joke_reactions_service.g.dart';

@Riverpod(keepAlive: true)
JokeReactionsService jokeReactionsService(Ref ref) {
  final jokeRepository = ref.watch(jokeRepositoryProvider);
  final appUsageService = ref.watch(appUsageServiceProvider);
  final reviewCoordinator = ref.watch(reviewPromptCoordinatorProvider);
  final interactionsRepository = ref.watch(jokeInteractionsRepositoryProvider);
  return JokeReactionsService(
    jokeRepository: jokeRepository,
    appUsageService: appUsageService,
    reviewPromptCoordinator: reviewCoordinator,
    interactionsRepository: interactionsRepository,
  );
}

/// Provider for checking if a joke is saved (reactive)
@Riverpod()
Stream<bool> isJokeSaved(Ref ref, String jokeId) {
  final interactions = ref.watch(jokeInteractionsRepositoryProvider);
  return interactions
      .watchJokeInteraction(jokeId)
      .map((ji) => ji?.savedTimestamp != null);
}

/// Provider for checking if a joke is shared (reactive)
@Riverpod()
Stream<bool> isJokeShared(Ref ref, String jokeId) {
  final interactions = ref.watch(jokeInteractionsRepositoryProvider);
  return interactions
      .watchJokeInteraction(jokeId)
      .map((ji) => ji?.sharedTimestamp != null);
}

class JokeReactionsService {
  final JokeRepository _jokeRepository;
  final AppUsageService _appUsageService;
  final ReviewPromptCoordinator _reviewPromptCoordinator;
  final JokeInteractionsRepository _interactionsRepository;

  JokeReactionsService({
    required JokeRepository jokeRepository,
    required AppUsageService appUsageService,
    required ReviewPromptCoordinator reviewPromptCoordinator,
    required JokeInteractionsRepository interactionsRepository,
  }) : _jokeRepository = jokeRepository,
       _appUsageService = appUsageService,
       _reviewPromptCoordinator = reviewPromptCoordinator,
       _interactionsRepository = interactionsRepository;

  /// Get all user reactions for all jokes
  /// Returns a map: jokeId -> Set of active reaction types
  Future<Map<String, Set<JokeReactionType>>> getAllUserReactions() async {
    final interactions = await _interactionsRepository.getAllJokeInteractions();
    final Map<String, Set<JokeReactionType>> result = {};
    for (final ji in interactions) {
      final set = <JokeReactionType>{};
      if (ji.savedTimestamp != null) set.add(JokeReactionType.save);
      if (ji.sharedTimestamp != null) set.add(JokeReactionType.share);
      if (set.isNotEmpty) {
        result[ji.jokeId] = set;
      }
    }
    return result;
  }

  /// Get saved joke IDs in the order they were saved to SharedPreferences
  Future<List<String>> getSavedJokeIds() async {
    final rows = await _interactionsRepository.getSavedJokeInteractions();
    return rows.map((r) => r.jokeId).toList(growable: false);
  }

  /// Get user reactions for a specific joke
  Future<Set<JokeReactionType>> getUserReactionsForJoke(String jokeId) async {
    final jokeInteraction = await _interactionsRepository.getJokeInteraction(
      jokeId,
    );
    if (jokeInteraction == null) return <JokeReactionType>{};

    final reactions = <JokeReactionType>{};
    if (jokeInteraction.savedTimestamp != null) {
      reactions.add(JokeReactionType.save);
    }
    if (jokeInteraction.sharedTimestamp != null) {
      reactions.add(JokeReactionType.share);
    }
    return reactions;
  }

  /// Check if user has reacted to a joke with a specific reaction type
  Future<bool> hasUserReaction(
    String jokeId,
    JokeReactionType reactionType,
  ) async {
    final reactions = await getUserReactionsForJoke(jokeId);
    return reactions.contains(reactionType);
  }

  /// Add a user reaction
  Future<void> addUserReaction(
    String jokeId,
    JokeReactionType reactionType, {
    required BuildContext context,
  }) async {
    if (reactionType == JokeReactionType.save) {
      await _interactionsRepository.setSaved(jokeId);
      await _appUsageService.incrementSavedJokesCount();
    } else if (reactionType == JokeReactionType.share) {
      await _interactionsRepository.setShared(jokeId);
      await _appUsageService.incrementSharedJokesCount();
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

  /// Remove a user reaction
  Future<void> removeUserReaction(
    String jokeId,
    JokeReactionType reactionType,
  ) async {
    if (reactionType == JokeReactionType.share) {
      throw ArgumentError('Share reaction cannot be removed');
    }
    if (reactionType == JokeReactionType.save) {
      await _interactionsRepository.setUnsaved(jokeId);
      await _appUsageService.decrementSavedJokesCount();
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
    _jokeRepository
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
