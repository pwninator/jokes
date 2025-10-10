import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';

/// Generic page result containing jokes, cursor, and hasMore flag
class PageResult {
  final List<JokeWithDate> jokes;
  final String? cursor;
  final bool hasMore;
  final int? totalCount; // Optional: total number of results if known upfront

  const PageResult({
    required this.jokes,
    required this.cursor,
    required this.hasMore,
    this.totalCount,
  });
}

/// Generic paging state for any data source
class PagingState {
  final List<JokeWithDate> loadedJokes;
  final String? cursor;
  final bool isLoading;
  final bool hasMore;
  final int? totalCount; // Optional: total number of results if known upfront
  final bool isInitialized;

  const PagingState({
    required this.loadedJokes,
    required this.cursor,
    required this.isLoading,
    required this.hasMore,
    this.totalCount,
    required this.isInitialized,
  });

  const PagingState.initial()
    : loadedJokes = const <JokeWithDate>[],
      cursor = null,
      isLoading = false,
      hasMore = true,
      totalCount = null,
      isInitialized = false;

  PagingState copyWith({
    List<JokeWithDate>? loadedJokes,
    String? cursor,
    bool? isLoading,
    bool? hasMore,
    int? totalCount,
    bool? isInitialized,
  }) {
    return PagingState(
      loadedJokes: loadedJokes ?? this.loadedJokes,
      cursor: cursor ?? this.cursor,
      isLoading: isLoading ?? this.isLoading,
      hasMore: hasMore ?? this.hasMore,
      totalCount: totalCount ?? this.totalCount,
      isInitialized: isInitialized ?? this.isInitialized,
    );
  }

  bool get isDataPending => !isInitialized || isLoading;
}

/// Generic notifier that handles paging logic for any data source
class GenericPagingNotifier extends StateNotifier<PagingState> {
  GenericPagingNotifier({
    required this.ref,
    required this.loadPage,
    required this.resetTriggers,
    required this.errorAnalyticsSource,
    required this.initialPageSize,
    required this.loadPageSize,
    required this.loadMoreThreshold,
  }) : super(const PagingState.initial()) {
    // Set up reset triggers
    for (final trigger in resetTriggers) {
      ref.listen(trigger.provider, (prev, next) {
        if (trigger.shouldReset(prev, next)) {
          reset();
        }
      });
    }

    // Trigger initial load if conditions are already met
    // (listener only catches future changes, not current state)
    Future.microtask(() => loadFirstPage());

    // Listen for connectivity restoration and retry without resetting scroll
    ref.listen<AsyncValue<bool>>(isOnlineProvider, (prev, next) {
      final wasOffline = prev?.valueOrNull == false;
      final isNowOnline = next.valueOrNull == true;
      if (wasOffline && isNowOnline) {
        _clearRetryBackoff();
        Future.microtask(_checkAndLoadIfNeeded);
      }
    });
  }

  final Ref ref;
  final Future<PageResult> Function(int limit, String? cursor) loadPage;
  final List<ResetTrigger> resetTriggers;
  final String errorAnalyticsSource;
  final int initialPageSize;
  final int loadPageSize;
  final int loadMoreThreshold;

  /// Current viewing index for auto-loading
  int _currentViewingIndex = 0;

  /// The index of the last failure attempt
  int _failureAttemptIndex = 0;

  /// Retry backoff window end
  DateTime? _blockRetriesLoadsUntil;

  void reset() {
    state = const PagingState.initial();
    _currentViewingIndex = 0;
    _failureAttemptIndex = 0;
    _blockRetriesLoadsUntil = null;
    // Auto-load after reset (will short-circuit if query is empty/invalid)
    Future.microtask(() => loadFirstPage());
  }

  /// Updates the current viewing index and triggers a load if within threshold
  void updateViewingIndex(int index) {
    _currentViewingIndex = index;
    _checkAndLoadIfNeeded();
  }

  /// Checks if we're within the threshold and triggers a load if needed
  void _checkAndLoadIfNeeded() {
    if (state.isLoading || !state.hasMore) return;
    if (_isInRetryBackoff() || !isOnlineNow(ref)) return;

    final remaining = state.loadedJokes.length - 1 - _currentViewingIndex;

    AppLogger.debug(
      'PAGING_THRESHOLD: index=$_currentViewingIndex, '
      'total=${state.loadedJokes.length}, remaining=$remaining, '
      'threshold=$loadMoreThreshold, hasMore=${state.hasMore}',
    );

    if (remaining <= loadMoreThreshold) {
      AppLogger.debug('PAGING_THRESHOLD: Triggering load');
      if (state.loadedJokes.isEmpty) {
        loadFirstPage();
      } else {
        loadMore();
      }
    }
  }

  Future<void> loadFirstPage() async {
    if (!state.isInitialized) {
      state = state.copyWith(isInitialized: true);
    }
    if (state.isLoading) return;
    if (_isInRetryBackoff() || !isOnlineNow(ref)) return;
    state = state.copyWith(
      isLoading: true,
      loadedJokes: const <JokeWithDate>[],
      cursor: null,
      hasMore: true,
    );
    await _loadInternal(limit: initialPageSize, useCursor: null);
  }

  Future<void> loadMore() async {
    if (!state.isInitialized) {
      state = state.copyWith(isInitialized: true);
    }
    if (state.isLoading || !state.hasMore) return;
    if (_isInRetryBackoff() || !isOnlineNow(ref)) return;
    state = state.copyWith(isLoading: true);
    await _loadInternal(limit: loadPageSize, useCursor: state.cursor);
  }

  Future<void> _loadInternal({required int limit, String? useCursor}) async {
    try {
      final page = await loadPage(limit, useCursor);

      AppLogger.debug(
        'PAGING_INTERNAL: Loaded ${page.jokes.length} jokes, '
        'cursor: ${page.cursor}, hasMore: ${page.hasMore}, '
        'current total: ${state.loadedJokes.length}',
      );

      // Deduplicate by joke ID
      final existingIds = Set<String>.from(
        state.loadedJokes.map((j) => j.joke.id),
      );
      final newJokes = page.jokes
          .where((jokeWithDate) => !existingIds.contains(jokeWithDate.joke.id))
          .toList();

      AppLogger.debug(
        'PAGING_INTERNAL: After dedup, ${newJokes.length} new jokes '
        '(${page.jokes.length - newJokes.length} duplicates removed)',
      );

      final appended = <JokeWithDate>[...state.loadedJokes, ...newJokes];

      // If we got no new jokes, assume no more results
      final effectiveHasMore = newJokes.isEmpty ? false : page.hasMore;

      state = state.copyWith(
        loadedJokes: appended,
        cursor: page.cursor,
        hasMore: effectiveHasMore,
        isLoading: false,
        totalCount: page.totalCount,
      );
      _resetBackoffOnSuccess();

      AppLogger.debug(
        'PAGING_INTERNAL: State updated - total: ${appended.length}, '
        'hasMore: $effectiveHasMore',
      );

      // Check if we need to load more based on current viewing position
      _checkAndLoadIfNeeded();
    } catch (e) {
      // On error, stop current load but keep hasMore true to allow retry
      AppLogger.warn('PAGING_INTERNAL: Error loading page: $e');
      state = state.copyWith(isLoading: false);
      _applyBackoff();
      // Log via analytics provider
      final analytics = ref.read(analyticsServiceProvider);
      analytics.logErrorJokesLoad(
        source: errorAnalyticsSource,
        errorMessage: e.toString(),
      );
    }
  }

  bool _isInRetryBackoff() {
    final until = _blockRetriesLoadsUntil;
    if (until == null) return false;
    return DateTime.now().isBefore(until);
  }

  void _applyBackoff() {
    const schedule = <Duration>[
      Duration(seconds: 5),
      Duration(seconds: 30),
      Duration(minutes: 2),
      Duration(minutes: 5),
    ];
    final idx = _failureAttemptIndex.clamp(0, schedule.length - 1);
    _blockRetriesLoadsUntil = DateTime.now().add(schedule[idx]);
    _failureAttemptIndex = (idx + 1).clamp(0, schedule.length - 1);
  }

  void _resetBackoffOnSuccess() {
    _failureAttemptIndex = 0;
    _clearRetryBackoff();
  }

  void _clearRetryBackoff() {
    _blockRetriesLoadsUntil = null;
  }
}

/// Configuration for when to reset paging state
class ResetTrigger {
  final ProviderListenable provider;
  final bool Function(dynamic prev, dynamic next) shouldReset;

  const ResetTrigger({required this.provider, required this.shouldReset});
}

/// Bundle of all providers needed for a paging data source
class PagingProviderBundle {
  final StateNotifierProvider<GenericPagingNotifier, PagingState> paging;
  final Provider<AsyncValue<List<JokeWithDate>>> items;
  final Provider<bool> hasMore;
  final Provider<bool> isLoading;
  final Provider<bool> isDataPending;
  final Provider<({int count, bool hasMore})> resultCount;

  const PagingProviderBundle({
    required this.paging,
    required this.items,
    required this.hasMore,
    required this.isLoading,
    required this.isDataPending,
    required this.resultCount,
  });
}

/// Factory function that creates all the providers for a paging data source
PagingProviderBundle createPagingProviders({
  required Future<PageResult> Function(Ref ref, int limit, String? cursor)
  loadPage,
  required List<ResetTrigger> resetTriggers,
  required String errorAnalyticsSource,
  required int initialPageSize,
  required int loadPageSize,
  required int loadMoreThreshold,
}) {
  // Create the main paging provider
  final pagingProvider =
      StateNotifierProvider<GenericPagingNotifier, PagingState>((ref) {
        return GenericPagingNotifier(
          ref: ref,
          loadPage: (limit, cursor) => loadPage(ref, limit, cursor),
          resetTriggers: resetTriggers,
          errorAnalyticsSource: errorAnalyticsSource,
          initialPageSize: initialPageSize,
          loadPageSize: loadPageSize,
          loadMoreThreshold: loadMoreThreshold,
        );
      });

  // Create derived providers
  final itemsProvider = Provider<AsyncValue<List<JokeWithDate>>>((ref) {
    final state = ref.watch(pagingProvider);
    final bool isPending = state.loadedJokes.isEmpty && state.isDataPending;
    return isPending
        ? const AsyncValue<List<JokeWithDate>>.loading()
        : AsyncValue<List<JokeWithDate>>.data(state.loadedJokes);
  });

  final hasMoreProvider = Provider<bool>((ref) {
    return ref.watch(pagingProvider).hasMore;
  });

  final isLoadingProvider = Provider<bool>((ref) {
    return ref.watch(pagingProvider).isLoading;
  });

  final isDataPendingProvider = Provider<bool>((ref) {
    return ref.watch(pagingProvider).isDataPending;
  });

  final resultCountProvider = Provider<({int count, bool hasMore})>((ref) {
    final state = ref.watch(pagingProvider);
    // Use totalCount if available, otherwise fall back to loaded count
    final count = state.totalCount ?? state.loadedJokes.length;
    final hasMore = state.hasMore && state.totalCount == null;
    return (count: count, hasMore: hasMore);
  });

  return PagingProviderBundle(
    paging: pagingProvider,
    items: itemsProvider,
    hasMore: hasMoreProvider,
    isLoading: isLoadingProvider,
    isDataPending: isDataPendingProvider,
    resultCount: resultCountProvider,
  );
}

/// Data source contract for `JokeListViewer` supporting incremental loading.
///
/// - `items` provides the current list of jokes to render.
/// - `hasMore` indicates whether more items can be loaded.
/// - `isLoading` indicates whether a load operation is in flight.
/// - `loadMore` requests loading the next page of items.
/// - `updateViewingIndex` reports the current viewing position for auto-loading.
class JokeListDataSource {
  final WidgetRef _ref;
  final PagingProviderBundle _bundle;

  JokeListDataSource(this._ref, this._bundle);

  /// Provides the current list of jokes to render.
  ProviderListenable<AsyncValue<List<JokeWithDate>>> get items => _bundle.items;

  /// Indicates whether more items can be loaded.
  ProviderListenable<bool> get hasMore => _bundle.hasMore;

  /// Indicates whether a load operation is in flight.
  ProviderListenable<bool> get isLoading => _bundle.isLoading;

  /// Indicates whether data is pending (initializing or actively loading)
  ProviderListenable<bool> get isDataPending => _bundle.isDataPending;

  /// Exposes total result count and whether more pages are available
  ProviderListenable<({int count, bool hasMore})> get resultCount =>
      _bundle.resultCount;

  /// Loads the next page of items.
  Future<void> loadMore() async {
    await _ref.read(_bundle.paging.notifier).loadMore();
  }

  /// Loads the first page, resetting any existing data
  Future<void> loadFirstPage() async {
    await _ref.read(_bundle.paging.notifier).loadFirstPage();
  }

  /// Updates the current viewing index and triggers auto-load if within threshold
  void updateViewingIndex(int index) {
    _ref.read(_bundle.paging.notifier).updateViewingIndex(index);
  }
}
