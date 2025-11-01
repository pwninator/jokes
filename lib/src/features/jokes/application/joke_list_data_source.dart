import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/data/core/app/app_providers.dart';
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

  /// Returns a page where loading was skipped so it's empty, but has more.
  static PageResult noOpPage(String? cursor) {
    return PageResult(jokes: [], cursor: cursor, hasMore: true);
  }

  /// Returns a page where there are no more results.
  static PageResult empty(String? cursor) {
    return PageResult(jokes: [], cursor: cursor, hasMore: false);
  }
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

  /// Returns a new PagingState with the given properties updated.
  /// Set cursor to empty string to unset it.
  PagingState copyWith({
    List<JokeWithDate>? loadedJokes,
    String? cursor,
    bool? isLoading,
    bool? hasMore,
    int? totalCount,
    bool? isInitialized,
  }) {
    final newCursor = cursor == "" ? null : (cursor ?? this.cursor);
    return PagingState(
      loadedJokes: loadedJokes ?? this.loadedJokes,
      cursor: newCursor,
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
    this.initialCursorProvider,
    this.onCursorChanged,
    this.unviewedOnly = false,
  }) : super(const PagingState.initial()) {
    // Set up reset triggers
    for (final trigger in resetTriggers) {
      ref.listen(trigger.provider, (prev, next) {
        if (trigger.shouldReset(ref, prev, next)) {
          reset();
        }
      });
    }

    // Trigger initial load if conditions are already met
    // (listener only catches future changes, not current state)
    Future.microtask(() => {if (mounted) loadFirstPage()});

    // Listen for connectivity restoration and retry without resetting scroll
    ref.listen(offlineToOnlineProvider, (prev, next) {
      _clearRetryBackoff();
      Future.microtask(() => {if (mounted) _checkAndLoadIfNeeded()});
    });
  }

  final Ref ref;
  final Future<PageResult> Function(int limit, String? cursor) loadPage;
  final List<ResetTrigger> resetTriggers;
  final String errorAnalyticsSource;
  final int initialPageSize;
  final int loadPageSize;
  final int loadMoreThreshold;
  final String? Function(Ref ref)? initialCursorProvider;
  final void Function(Ref ref, String?)? onCursorChanged;
  final bool unviewedOnly;

  /// Current viewing index for auto-loading
  int _currentViewingIndex = 0;

  /// The index of the last failure attempt
  int _failureAttemptIndex = 0;

  /// Retry backoff window end
  DateTime? _blockRetriesLoadsUntil;
  String? _initialCursorCache;

  void reset() {
    AppLogger.debug('PAGING_INTERNAL: Resetting GenericPagingNotifier');
    state = const PagingState.initial();
    _currentViewingIndex = 0;
    _failureAttemptIndex = 0;
    _blockRetriesLoadsUntil = null;
    _initialCursorCache = null;
    onCursorChanged?.call(ref, null);
    // Auto-load after reset (will short-circuit if query is empty/invalid)
    Future.microtask(() => {if (mounted) loadFirstPage()});
  }

  /// Updates the current viewing index and triggers a load if within threshold
  void updateViewingIndex(int index) {
    _currentViewingIndex = index;
    _checkAndLoadIfNeeded();
  }

  /// Checks if we're within the threshold and triggers a load if needed
  void _checkAndLoadIfNeeded() {
    if (!mounted) return;
    if (state.isLoading || !state.hasMore) return;
    if (_isInRetryBackoff() || !isOnlineNow(ref)) return;

    final remaining = state.loadedJokes.length - 1 - _currentViewingIndex;

    AppLogger.debug(
      'PAGING_INTERNAL: index=$_currentViewingIndex, '
      'total=${state.loadedJokes.length}, remaining=$remaining, '
      'threshold=$loadMoreThreshold, hasMore=${state.hasMore}',
    );

    if (remaining <= loadMoreThreshold) {
      AppLogger.debug(
        'PAGING_INTERNAL: Triggering load (remaining=$remaining, threshold=$loadMoreThreshold)',
      );
      if (state.loadedJokes.isEmpty) {
        loadFirstPage();
      } else {
        loadMore();
      }
    }
  }

  Future<void> loadFirstPage() async {
    if (!mounted) return;
    if (!state.isInitialized) {
      state = state.copyWith(isInitialized: true);
    }
    if (state.isLoading) return;
    if (_isInRetryBackoff() || !isOnlineNow(ref)) return;
    final String? startCursor = _initialCursorCache ??= initialCursorProvider
        ?.call(ref);
    state = state.copyWith(
      isLoading: true,
      loadedJokes: const <JokeWithDate>[],
      cursor: startCursor,
      hasMore: true,
    );
    await _loadInternal(limit: initialPageSize, useCursor: startCursor);
  }

  Future<void> loadMore() async {
    if (!mounted) return;
    if (!state.isInitialized) {
      state = state.copyWith(isInitialized: true);
    }
    if (state.isLoading || !state.hasMore) return;
    if (_isInRetryBackoff() || !isOnlineNow(ref)) return;
    state = state.copyWith(isLoading: true);
    await _loadInternal(limit: loadPageSize, useCursor: state.cursor);
  }

  Future<void> _loadInternal({required int limit, String? useCursor}) async {
    if (!mounted) return;
    try {
      final previousCursor = state.cursor;
      final page = await loadPage(limit, useCursor);
      if (!mounted) return;

      AppLogger.debug(
        'PAGING_INTERNAL: Loaded ${page.jokes.length} jokes, prev cursor: $previousCursor, '
        'new cursor: ${page.cursor}, hasMore: ${page.hasMore}, '
        'previous total: ${state.loadedJokes.length}',
      );

      // Deduplicate by joke ID
      final existingIds = Set<String>.from(
        state.loadedJokes.map((j) => j.joke.id),
      );
      final newJokes = await filterJokes(
        ref,
        page.jokes,
        filterViewed: unviewedOnly,
        existingIds: existingIds,
      );

      AppLogger.debug(
        'PAGING_INTERNAL: After filters, ${newJokes.length} new jokes '
        '(${page.jokes.length - newJokes.length} removed)',
      );

      final appended = <JokeWithDate>[...state.loadedJokes, ...newJokes];

      // Continue loading only if the source indicated it has more jokes AND
      // it either returned jokes or changed the cursor.
      // This prevents infinite loops when composite sources return the same cursor
      // but with no jokes (all deduped or exhausted).
      final newCursor = page.cursor;
      final effectiveHasMore =
          page.hasMore &&
          (page.jokes.isNotEmpty || newCursor != previousCursor);

      if (!mounted) return;
      state = state.copyWith(
        loadedJokes: appended,
        cursor: newCursor ?? "",
        hasMore: effectiveHasMore,
        isLoading: false,
        totalCount: page.totalCount,
      );
      if (newCursor != previousCursor &&
          appended.length > initialPageSize + loadPageSize) {
        if (previousCursor != null && previousCursor.isNotEmpty) {
          onCursorChanged?.call(ref, previousCursor);
        }
      }
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
      if (!mounted) return;
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
  final bool Function(Ref ref, dynamic prev, dynamic next) shouldReset;

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
  String? Function(Ref ref)? initialCursorProvider,
  void Function(Ref ref, String?)? onCursorChanged,
  bool unviewedOnly = false,
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
          initialCursorProvider: initialCursorProvider,
          onCursorChanged: onCursorChanged,
          unviewedOnly: unviewedOnly,
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

/// Comprehensive filtering for jokes that applies deduplication, image,
/// public timestamp, and unviewed filters.
///
/// - Deduplicates jokes by ID (keeps first occurrence)
/// - Filters for jokes with both setup and punchline images
/// - Filters for jokes with public timestamp before or equal to [now]
/// - Filters out jokes that have already been viewed by the user
///
/// Returns a list of [JokeWithDate] objects that pass all filters.
Future<List<JokeWithDate>> filterJokes(
  Ref ref,
  List<JokeWithDate> jokes, {
  Set<String> existingIds = const {},
  bool filterViewed = false,
}) async {
  List<JokeWithDate> filtered = dedupeJokes(jokes, existingIds);
  filtered = filterJokesWithImages(filtered);
  filtered = filterJokesByPublicTimestamp(ref, filtered);
  filtered = filterViewed ? await filterViewedJokes(ref, filtered) : filtered;
  return filtered;
}

/// Remove duplicate jokes by ID, keeping the first occurrence.
List<JokeWithDate> dedupeJokes(
  List<JokeWithDate> jokes,
  Set<String> existingIds,
) {
  final seen = Set<String>.from(existingIds);
  final deduped = jokes
      .where((jokeWithDate) => seen.add(jokeWithDate.joke.id))
      .toList();
  _logJokesFiltered('deduped', jokes, deduped);
  return deduped;
}

/// Filter for jokes with both setup and punchline images.
List<JokeWithDate> filterJokesWithImages(List<JokeWithDate> jokes) {
  final jokesWithImages = jokes.where((jokeWithDate) {
    final joke = jokeWithDate.joke;
    return (joke.setupImageUrl != null && joke.setupImageUrl!.isNotEmpty) &&
        (joke.punchlineImageUrl != null && joke.punchlineImageUrl!.isNotEmpty);
  }).toList();
  _logJokesFiltered('has images', jokes, jokesWithImages);
  return jokesWithImages;
}

/// Filter for jokes with public timestamp before or equal to now.
List<JokeWithDate> filterJokesByPublicTimestamp(
  Ref ref,
  List<JokeWithDate> jokes,
) {
  final now = ref.read(clockProvider)();
  final jokesWithTimestamp = jokes.where((jokeWithDate) {
    final timestamp = jokeWithDate.joke.publicTimestamp;
    if (timestamp == null) {
      // Cached jokes don't have public timestamp, so include them.
      return true;
    }
    return !timestamp.isAfter(now);
  }).toList();
  _logJokesFiltered('public timestamp', jokes, jokesWithTimestamp);
  return jokesWithTimestamp;
}

/// Filter out jokes that have already been viewed by the user.
Future<List<JokeWithDate>> filterViewedJokes(
  Ref ref,
  List<JokeWithDate> jokes,
) async {
  final jokeIds = jokes.map((jokeWithDate) => jokeWithDate.joke.id).toList();
  final unviewedJokeIds = await ref
      .read(appUsageServiceProvider)
      .getUnviewedJokeIds(jokeIds);
  final unviewedJokes = jokes
      .where((jokeWithDate) => unviewedJokeIds.contains(jokeWithDate.joke.id))
      .toList();

  _logJokesFiltered('unviewed', jokes, unviewedJokes);
  return unviewedJokes;
}

/// Log the diff if in debug mode.
void _logJokesFiltered(
  String filterName,
  List<JokeWithDate> original,
  List<JokeWithDate> filtered,
) {
  final numFiltered = original.length - filtered.length;
  if (!kDebugMode || numFiltered == 0) {
    return;
  }

  final originalIds = original
      .map((jokeWithDate) => jokeWithDate.joke.id)
      .toList();
  final filteredIds = filtered
      .map((jokeWithDate) => jokeWithDate.joke.id)
      .toSet();

  // Original and filtered may differ by duplicates, so iterate over the
  // original and remove from filtered at each step to find the diff.
  final removedIds = <String>[];
  for (final id in originalIds) {
    if (!filteredIds.contains(id)) {
      removedIds.add(id);
    } else {
      filteredIds.remove(id);
    }
  }
  AppLogger.debug(
    'PAGING_INTERNAL: FILTER: $filterName: Filtered out $numFiltered jokes: $removedIds',
  );
}
