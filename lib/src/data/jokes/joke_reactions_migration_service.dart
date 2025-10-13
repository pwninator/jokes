import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
// No codegen to avoid build_runner requirement here
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/settings_providers.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

final jokeReactionsMigrationServiceProvider =
    Provider<JokeReactionsMigrationService>((ref) {
      final interactions = ref.read(jokeInteractionsRepositoryProvider);
      final prefsFuture = ref.read(sharedPreferencesProvider.future);
      final perf = ref.read(performanceServiceProvider);
      return JokeReactionsMigrationService(
        interactions: interactions,
        prefsFuture: prefsFuture,
        performanceService: perf,
      );
    });

class JokeReactionsMigrationService {
  JokeReactionsMigrationService({
    required JokeInteractionsRepository interactions,
    required Future<SharedPreferences> prefsFuture,
    required PerformanceService performanceService,
  }) : _interactions = interactions,
       _prefsFuture = prefsFuture,
       _perf = performanceService;

  final JokeInteractionsRepository _interactions;
  final Future<SharedPreferences> _prefsFuture;
  final PerformanceService _perf;

  Future<void> migrateIfNeeded() async {
    _perf.startNamedTrace(name: TraceName.startupTaskMigrateReactions);
    try {
      final prefs = await _prefsFuture;

      // Only migrate if legacy keys exist
      final legacySave = prefs.getStringList(JokeReactionType.save.prefsKey);
      final legacyShare = prefs.getStringList(JokeReactionType.share.prefsKey);
      final hasLegacy =
          (legacySave != null && legacySave.isNotEmpty) ||
          (legacyShare != null && legacyShare.isNotEmpty);
      if (!hasLegacy) {
        return;
      }

      // Preserve order for saved: earliest first
      final uniqueSaved = <String>{};
      final orderedSaved = <String>[];
      for (final id in (legacySave ?? const <String>[])) {
        if (uniqueSaved.add(id)) orderedSaved.add(id);
      }
      final uniqueShared = <String>{};
      final orderedShared = <String>[];
      for (final id in (legacyShare ?? const <String>[])) {
        if (uniqueShared.add(id)) orderedShared.add(id);
      }

      // Use synthetic timestamps to preserve saved order
      final now = DateTime.now();
      for (int i = 0; i < orderedSaved.length; i++) {
        final id = orderedSaved[i];
        // Earlier items should have earlier timestamps
        final at = now.subtract(
          Duration(milliseconds: (orderedSaved.length - i)),
        );
        await _interactions.setSavedAt(id, at);
      }

      // For shares, order is not surfaced, but ensure presence is recorded
      for (final id in orderedShared) {
        await _interactions.setSharedAt(id, now);
      }

      // Mark migrated and delete old keys
      await prefs.remove(JokeReactionType.save.prefsKey);
      await prefs.remove(JokeReactionType.share.prefsKey);

      AppLogger.debug(
        'REACTION_MIGRATION: Migrated ${orderedSaved.length} saved and ${orderedShared.length} shared reactions to Drift',
      );
    } catch (e, stack) {
      AppLogger.error(
        'REACTION_MIGRATION: Migration failed: $e',
        stackTrace: stack,
      );
    } finally {
      _perf.stopNamedTrace(name: TraceName.startupTaskMigrateReactions);
    }
  }
}
