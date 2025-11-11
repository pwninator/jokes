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

/// Minimum number of feed jokes to wait for during initial sync.
const int kFeedSyncMinInitialJokes = 50;

/// Maximum time to wait for [kFeedSyncMinInitialJokes] to be available locally.
const Duration kFeedSyncInitialWaitTimeout = Duration(seconds: 10);

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
  Timer? _retryTimer;
  int _retryAttemptIndex = 0;

  /// Triggers a feed sync.
  ///
  /// forceSync:
  ///  - true: always run (overwrite via upsert), never clear
  ///  - false: only run if DB has zero feed jokes
  ///
  /// Returns true if a sync was started. This call blocks until at least 50 jokes
  /// are available locally or a 10 second timeout elapses (background sync continues).
  Future<bool> triggerSync({required bool forceSync}) async {
    // If a retry was scheduled, cancel as we're attempting now.
    _cancelRetry();

    if (_isSyncing) {
      AppLogger.debug('FEED_SYNC: Skipping; sync already in progress');
      return false;
    }

    final existingCount = await _interactionsRepository.countFeedJokes();
    if (!forceSync && existingCount > 0) {
      AppLogger.debug(
        'FEED_SYNC: Skipping connectivity/manual sync; DB has $existingCount feed jokes',
      );
      _resetBackoffOnSuccess();
      return false;
    }

    final shouldResetComposite = existingCount == 0;
    _isSyncing = true;

    AppLogger.info(
      'FEED_SYNC: Starting sync (forceSync=$forceSync, initialCount=$existingCount)',
    );

    try {
      // Start waiting for the initial window FIRST to avoid missing early emissions,
      // then kick off the background sync concurrently.
      final waitFuture = _waitForFeedWindow(minJokes: kFeedSyncMinInitialJokes);
      unawaited(
        _runFullFeedSync().whenComplete(() {
          _isSyncing = false;
          AppLogger.info('FEED_SYNC: Background sync completed');
        }),
      );

      // Wait until we have at least threshold jokes or timeout.
      var syncSuccessful = true;
      await waitFuture.timeout(
        kFeedSyncInitialWaitTimeout,
        onTimeout: () {
          AppLogger.warn(
            'FEED_SYNC: Timed out waiting for $kFeedSyncMinInitialJokes jokes',
          );
          syncSuccessful = false;
        },
      );

      if (syncSuccessful) {
        // Only reset composite if DB was empty when we began syncing and we
        // successfully reached the initial threshold (no timeout).
        if (shouldResetComposite) {
          AppLogger.info('FEED_SYNC: Triggering composite reset');
          _ref.read(compositeJokesResetTriggerProvider.notifier).state++;
        }
        _resetBackoffOnSuccess();
      } else {
        _scheduleRetry();
      }

      return true;
    } catch (e, stack) {
      _isSyncing = false;
      AppLogger.fatal('FEED_SYNC: Sync failed: $e', stackTrace: stack);
      _scheduleRetry();
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

  void _scheduleRetry() {
    if (_retryTimer?.isActive ?? false) {
      // A retry is already scheduled.
      return;
    }
    const schedule = <Duration>[
      Duration(seconds: 5),
      Duration(seconds: 30),
      Duration(minutes: 2),
      Duration(minutes: 5),
    ];
    final idx = _retryAttemptIndex.clamp(0, schedule.length - 1);
    final delay = schedule[idx];
    _retryAttemptIndex = (idx + 1).clamp(0, schedule.length - 1);
    AppLogger.info(
      'FEED_SYNC: Scheduling retry in ${delay.inSeconds} seconds (attemptIndex=$_retryAttemptIndex)',
    );
    _retryTimer = Timer(delay, () {
      _retryTimer = null;
      unawaited(triggerSync(forceSync: false));
    });
  }

  void _resetBackoffOnSuccess() {
    _retryAttemptIndex = 0;
    _cancelRetry();
  }

  void _cancelRetry() {
    if (_retryTimer?.isActive ?? false) {
      _retryTimer?.cancel();
    }
    _retryTimer = null;
  }
}
