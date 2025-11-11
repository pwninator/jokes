import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

part 'feed_sync_service.g.dart';

/// Provides a singleton FeedSyncService instance.
@Riverpod(keepAlive: true)
FeedSyncService feedSyncService(Ref ref) {
  final interactionsRepository = ref.read(jokeInteractionsRepositoryProvider);
  final jokeRepository = ref.read(jokeRepositoryProvider);
  return FeedSyncService(
    ref: ref,
    interactionsRepository: interactionsRepository,
    jokeRepository: jokeRepository,
  );
}

/// Service that manages syncing the Firestore joke feed into the local database.
///
/// - Prevents concurrent syncs via a simple mutex
/// - Startup sync always runs and overwrites existing entries (upsert), never clears
/// - Connectivity/manual sync runs only if the DB has zero feed jokes
/// - Blocks until at least 50 jokes are available locally (10s timeout)
/// - Triggers a one-time composite data source reset if DB was empty when sync started
class FeedSyncService {
  FeedSyncService({
    required Ref ref,
    required JokeInteractionsRepository interactionsRepository,
    required JokeRepository jokeRepository,
  }) : _ref = ref,
       _interactionsRepository = interactionsRepository,
       _jokeRepository = jokeRepository {
    // Listen for connectivity restoration -> attempt sync if DB is empty.
    _ref.listen(offlineToOnlineProvider, (prev, next) {
      // Only react on positive transitions; provider increments on offline->online.
      next.whenData((_) {
        AppLogger.debug('FEED_SYNC: Connectivity restored; considering sync');
        unawaited(triggerSync(forceSync: false));
      });
    });
  }

  final Ref _ref;
  final JokeInteractionsRepository _interactionsRepository;
  final JokeRepository _jokeRepository;

  bool _isSyncing = false;

  /// Triggers a feed sync.
  ///
  /// forceSync:
  ///  - true: always run (overwrite via upsert), never clear
  ///  - false: only run if DB has zero feed jokes
  ///
  /// Returns true if a sync was started. This call blocks until at least 50 jokes
  /// are available locally or a 10 second timeout elapses (background sync continues).
  Future<bool> triggerSync({required bool forceSync}) async {
    if (_isSyncing) {
      AppLogger.debug('FEED_SYNC: Skipping; sync already in progress');
      return false;
    }

    final existingCount = await _interactionsRepository.countFeedJokes();
    if (!forceSync && existingCount > 0) {
      AppLogger.debug(
        'FEED_SYNC: Skipping connectivity/manual sync; DB has $existingCount feed jokes',
      );
      return false;
    }

    final shouldResetComposite = existingCount == 0;
    _isSyncing = true;

    AppLogger.info(
      'FEED_SYNC: Starting sync (forceSync=$forceSync, initialCount=$existingCount)',
    );

    try {
      // Start the full sync in the background; this continues beyond the threshold.
      unawaited(
        _runFullFeedSync().whenComplete(() {
          _isSyncing = false;
          AppLogger.info('FEED_SYNC: Background sync completed');
        }),
      );

      // Wait until we have at least 50 jokes or timeout after 10s.
      await _waitForFeedWindow(minJokes: 50).timeout(
        const Duration(seconds: 10),
        onTimeout: () {
          AppLogger.warn('FEED_SYNC: Timed out waiting for 50 jokes');
        },
      );

      // Only reset composite if DB was empty when we began syncing.
      if (shouldResetComposite) {
        AppLogger.info('FEED_SYNC: Triggering composite reset');
        _ref.read(compositeJokesResetTriggerProvider.notifier).state++;
      }

      return true;
    } catch (e, stack) {
      _isSyncing = false;
      AppLogger.fatal('FEED_SYNC: Sync failed: $e', stackTrace: stack);
      return false;
    }
  }

  /// Watches the local DB until at least [minJokes] feed jokes exist.
  Future<void> _waitForFeedWindow({required int minJokes}) async {
    final completer = Completer<void>();
    final subscription = _interactionsRepository
        .watchFeedHead(limit: 100)
        .listen(
          (interactions) {
            if (interactions.length >= minJokes && !completer.isCompleted) {
              AppLogger.info(
                'FEED_SYNC: Reached threshold (${interactions.length} >= $minJokes)',
              );
              completer.complete();
            }
          },
          onError: (error, stack) {
            if (!completer.isCompleted) {
              AppLogger.error(
                'FEED_SYNC: watchFeedHead error: $error',
                stackTrace: stack,
              );
              completer.completeError(error, stack);
            }
          },
        );

    try {
      await completer.future;
    } finally {
      await subscription.cancel();
    }
  }

  /// Synchronizes all feed jokes from Firestore into Drift, overwriting via upsert.
  Future<void> _runFullFeedSync() async {
    try {
      AppLogger.info('FEED_SYNC: Starting full feed sync');
      JokeListPageCursor? cursor;
      int feedIndex = 0;

      while (true) {
        final page = await _jokeRepository.readFeedJokes(cursor: cursor);

        if (page.jokes != null && page.jokes!.isNotEmpty) {
          final jokes = page.jokes!
              .map((joke) => (joke: joke, feedIndex: feedIndex++))
              .toList();

          await _interactionsRepository.syncFeedJokes(jokes: jokes);
        }

        AppLogger.info(
          'FEED_SYNC: Synced page: ${page.jokes?.length ?? 0} jokes, total so far: $feedIndex',
        );

        if (!page.hasMore ||
            page.cursor == null ||
            page.cursor?.docId == cursor?.docId) {
          AppLogger.info('FEED_SYNC: No more feed jokes to sync');
          break;
        }

        cursor = page.cursor;
      }

      AppLogger.info('FEED_SYNC: Full feed sync completed; total=$feedIndex');
    } catch (e, stack) {
      AppLogger.fatal(
        'FEED_SYNC: Background feed sync failed: $e',
        stackTrace: stack,
      );
      rethrow;
    }
  }
}
