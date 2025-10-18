import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

part 'joke_reactions_service.g.dart';

@Riverpod(keepAlive: true)
JokeReactionsService jokeReactionsService(Ref ref) {
  final appUsageService = ref.watch(appUsageServiceProvider);
  final interactionsRepository = ref.watch(jokeInteractionsRepositoryProvider);
  return JokeReactionsService(
    appUsageService: appUsageService,
    interactionsRepository: interactionsRepository,
  );
}

class JokeReactionsService {
  final AppUsageService _appUsageService;
  final JokeInteractionsRepository _interactionsRepository;

  JokeReactionsService({
    required AppUsageService appUsageService,
    required JokeInteractionsRepository interactionsRepository,
  }) : _appUsageService = appUsageService,
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

  /// Add a user reaction
  Future<void> addUserReaction(
    String jokeId,
    JokeReactionType reactionType, {
    required BuildContext context,
  }) async {
    if (reactionType == JokeReactionType.save) {
      await _appUsageService.saveJoke(jokeId, context: context);
    } else if (reactionType == JokeReactionType.share) {
      await _appUsageService.shareJoke(jokeId, context: context);
    }
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
      await _appUsageService.unsaveJoke(jokeId);
    }
  }
}
