import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/data/core/app/app_providers.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/feed_sync_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart'
    show JokeField, JokeFilter, JokeListPageCursor, OrderDirection, dummyDocId;
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/settings/application/random_starting_id_provider.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

/// Signal provider that triggers stale joke checks for daily jokes.
/// Incremented by DailyJokesScreen when it wants to trigger a check.
final dailyJokesCheckNowProvider = StateProvider<int>((ref) => 0);

/// Tracks the last date we performed a reset of the daily jokes list.
/// Used to ensure we only reset once per day to avoid thrashing.
final dailyJokesLastResetDateProvider = StateProvider<DateTime?>((ref) => null);

/// Tracks the date of the most recent daily joke.
final dailyJokesMostRecentDateProvider = StateProvider<DateTime?>(
  (ref) => null,
);

/// Signal used to invalidate saved jokes paging data.
/// Increment the value to trigger a refresh of saved jokes data sources.
final savedJokesRefreshTriggerProvider = StateProvider<int>((ref) => 0);

/// Active category selection for Discover. Changing this resets the unified
/// category data source via its reset trigger.
final activeCategoryProvider = StateProvider<JokeCategory?>((ref) => null);

/// Signal to trigger reset of composite joke feed after initial sync completes.
/// Only incremented once when feed is first populated.
final compositeJokesResetTriggerProvider = StateProvider<int>((ref) => 0);

/// Per-subsource retry backoff schedule.
const List<Duration> _subSourceBackoffSchedule = <Duration>[
  Duration(seconds: 3),
  Duration(seconds: 10),
  Duration(seconds: 30),
  Duration(minutes: 2),
  Duration(minutes: 5),
];

class _SubSourceRetryState {
  const _SubSourceRetryState({
    required this.nextRetryAt,
    required this.attemptIndex,
  });

  final DateTime nextRetryAt;
  final int attemptIndex;
}

/// Tracks retry state per subsource to avoid tight error loops.
final _subSourceRetryStateProvider =
    StateProvider<Map<String, _SubSourceRetryState>>((ref) => {});

/// Data source for daily jokes loaded from monthly schedule batches
class DailyJokesDataSource extends JokeListDataSource {
  DailyJokesDataSource(WidgetRef ref) : super(ref, _dailyJokesPagingProviders);
}

/// Data source for user joke search
class UserJokeSearchDataSource extends JokeListDataSource {
  UserJokeSearchDataSource(WidgetRef ref)
    : super(ref, _userJokeSearchProviders);
}

/// Unified category data source that routes to search vs. popular loaders
/// based on the currently active category.
class CategoryDataSource extends JokeListDataSource {
  CategoryDataSource(WidgetRef ref) : super(ref, _categoryPagingProviders);
}

/// Data source for saved jokes with incremental loading
class SavedJokesDataSource extends JokeListDataSource {
  SavedJokesDataSource(WidgetRef ref) : super(ref, _savedJokesPagingProviders);
}

/// Composite feed that sequences through multiple joke sources.
class CompositeJokeDataSource extends JokeListDataSource {
  CompositeJokeDataSource(WidgetRef ref)
    : super(ref, compositeJokePagingProviders);
}

final _userJokeSearchProviders = createPagingProviders(
  loadPage: _makeLoadSearchPage(SearchScope.userJokeSearch),
  resetTriggers: [
    ResetTrigger(
      provider: searchQueryProvider(SearchScope.userJokeSearch),
      shouldReset: (ref, prev, next) =>
          (prev as SearchQuery?)?.query != (next as SearchQuery).query,
    ),
  ],
  // Scope-specific analytics source label
  dataSourceName: 'search:${SearchScope.userJokeSearch.name}',
  initialPageSize: 2,
  loadPageSize: 5,
  loadMoreThreshold: 5,
);

final PagingProviderBundle _dailyJokesPagingProviders = createPagingProviders(
  loadPage: loadDailyJokesPage,
  resetTriggers: [
    ResetTrigger(
      provider: dailyJokesCheckNowProvider,
      shouldReset: shouldResetDailyJokesForStaleData,
    ),
  ],
  dataSourceName: 'daily_jokes',
  initialPageSize: 5,
  loadPageSize: 10,
  loadMoreThreshold: 10,
);

final _savedJokesPagingProviders = createPagingProviders(
  loadPage: _loadSavedJokesPage,
  resetTriggers: [
    ResetTrigger(
      provider: savedJokesRefreshTriggerProvider,
      shouldReset: (_, prev, next) {
        if (prev == null) return false;
        return prev != next;
      },
    ),
  ],

  dataSourceName: 'saved_jokes',
  initialPageSize: 3,
  loadPageSize: 10,
  loadMoreThreshold: 5,
);

final _categoryPagingProviders = createPagingProviders(
  loadPage: _loadCategoryPage,
  resetTriggers: [
    ResetTrigger(
      provider: activeCategoryProvider,
      shouldReset: (ref, prev, next) =>
          (prev as JokeCategory?)?.id != (next as JokeCategory?)?.id,
    ),
  ],
  dataSourceName: 'category',
  initialPageSize: 2,
  loadPageSize: 5,
  loadMoreThreshold: 5,
);

/// Shared preferences key for persisting the composite feed cursor.
const compositeJokeCursorPrefsKey = JokeConstants.compositeJokeCursorPrefsKey;

/// Sentinel cursor value marking a priority source as permanently exhausted.
const String kDoneSentinel = '__DONE__';

/// Maximum number of local feed jokes required before skipping Firestore fallback.
const int _kFeedFallbackLocalThreshold = 300;

/// Number of jokes stored per Firestore feed document (except possibly the last).
const int _kFeedJokesPerFirestoreDoc = 50;

/// Constants for composite joke source index boundaries and date ranges.
/// These values define when different subsources become active or inactive.
/// Null values indicate no boundary (unlimited range).
class CompositeJokeSourceBoundaries {
  CompositeJokeSourceBoundaries._();

  // Priority sources

  static const int? seasonalMinIndex = null;
  static const int? seasonalMaxIndex = null;

  static const int todayJokeMinIndex = 5;
  static const int? todayJokeMaxIndex = null;

  // Composite sources

  static const int localFeedJokesMinIndex = 0;
  static const int? localFeedJokesMaxIndex = null;

  static const int bestJokesMinIndex = 0;
  static const int bestJokesMaxIndex = 200;

  static const int randomMinIndex = 10;
  static const int randomMaxIndex = 500;

  static const int publicMinIndex = 200;
  static const int? publicMaxIndex = null;
}

enum SeasonalCategoryFeed {
  halloween(
    value: 'Halloween',
    startMonth: 10,
    startDay: 25,
    endMonth: 11,
    endDay: 1,
  );

  const SeasonalCategoryFeed({
    required this.value,
    required this.startMonth,
    required this.startDay,
    required this.endMonth,
    required this.endDay,
  });

  final String value;
  final int startMonth;
  final int startDay;
  final int endMonth;
  final int endDay;

  /// Returns true when [currentDate] falls within this category's start/end
  /// (month/day) window, inclusive on both ends.
  ///
  /// Comparisons are date-only (midnight-normalized).
  bool isActiveOn(DateTime currentDate) {
    final today = DateTime(
      currentDate.year,
      currentDate.month,
      currentDate.day,
    );
    final startDate = DateTime(today.year, startMonth, startDay);
    final endDate = DateTime(today.year, endMonth, endDay);

    if (endDate.isAfter(startDate)) {
      return today.compareTo(startDate) >= 0 && today.compareTo(endDate) <= 0;
    }

    // Range spans year boundary (e.g., Dec -> Jan)
    return today.compareTo(startDate) >= 0 || today.compareTo(endDate) <= 0;
  }
}

final compositeJokePagingProviders = createPagingProviders(
  loadPage: _loadCompositeJokePage,
  resetTriggers: [
    ResetTrigger(
      provider: compositeJokesResetTriggerProvider,
      shouldReset: (_, prev, next) => prev != null && prev != next,
    ),
  ],
  initialCursorProvider: (ref) {
    final settings = ref.read(settingsServiceProvider);
    return settings.getString(compositeJokeCursorPrefsKey);
  },
  onCursorChanged: (ref, cursor) {
    /// Never clear the saved cursor.
    if (cursor == null || cursor.isEmpty) return;
    final settings = ref.read(settingsServiceProvider);
    unawaited(settings.setString(compositeJokeCursorPrefsKey, cursor));
    AppLogger.debug('PAGING_INTERNAL: Saved composite cursor: $cursor');
  },
  dataSourceName: 'composite_jokes',
  initialPageSize: 3,
  loadPageSize: 12,
  loadMoreThreshold: 5,
  unviewedOnly: true,
);

CompositeJokeSubSource _seasonalSubSource(
  String id,
  SeasonalCategoryFeed category,
) {
  return CompositeJokeSubSource(
    id: id,
    minIndex: CompositeJokeSourceBoundaries.seasonalMinIndex,
    maxIndex: CompositeJokeSourceBoundaries.seasonalMaxIndex,
    condition: (ref) => category.isActiveOn(getCurrentDate(ref)),
    load: (Ref ref, int limit, String? cursor) => _loadSeasonalCategoryPage(
      ref,
      limit,
      cursor,
      seasonalValueOverride: category.value,
      orderByFieldOverride: JokeField.savedFraction,
      orderDirectionOverride: OrderDirection.descending,
    ),
  );
}

/// Priority data sources that take precedence over composite sources.
/// Priority sources are checked first; only the first active one is loaded exclusively.
/// When a priority source exhausts (hasMore=false), its cursor is marked "__DONE__"
/// and it will never be loaded again.
final List<CompositeJokeSubSource> _prioritySubSources = [
  // Halloween priority source takes precedence when active
  _seasonalSubSource(
    'priority_halloween_jokes',
    SeasonalCategoryFeed.halloween,
  ),
  // Today's daily joke appears once per day starting at index 5
  CompositeJokeSubSource(
    id: 'priority_today_joke',
    minIndex: CompositeJokeSourceBoundaries.todayJokeMinIndex,
    maxIndex: CompositeJokeSourceBoundaries.todayJokeMaxIndex,
    condition: _shouldShowTodayJoke,
    load: (Ref ref, int limit, String? cursor) => _loadTodayJoke(ref),
  ),
];

/// "Regular" data sources that will intereaved together.
const String localFeedJokesSubSourceId = 'local_feed_jokes';

final List<CompositeJokeSubSource> _compositeSubSources = [
  CompositeJokeSubSource(
    id: localFeedJokesSubSourceId,
    minIndex: CompositeJokeSourceBoundaries.localFeedJokesMinIndex,
    maxIndex: CompositeJokeSourceBoundaries.localFeedJokesMaxIndex,
    load: (Ref ref, int limit, String? cursor) =>
        _loadFeedJokesFromDatabase(ref, limit, cursor),
  ),
  // Temporarily disabled. Keep this code for now.
  // CompositeJokeSubSource(
  //   id: 'best_jokes',
  //   minIndex: CompositeJokeSourceBoundaries.bestJokesMinIndex,
  //   maxIndex: CompositeJokeSourceBoundaries.bestJokesMaxIndex,
  //   load: (Ref ref, int limit, String? cursor) => _loadFirestoreJokes(
  //     ref,
  //     limit,
  //     cursor,
  //     orderByField: JokeField.savedFraction,
  //     orderDirection: OrderDirection.descending,
  //     dataSource: 'best_jokes',
  //   ),
  // ),
  // CompositeJokeSubSource(
  //   id: 'all_jokes_random',
  //   minIndex: CompositeJokeSourceBoundaries.randomMinIndex,
  //   maxIndex: CompositeJokeSourceBoundaries
  //       .randomMaxIndex, // Loops infinitely, so need a max limit.
  //   load: (Ref ref, int limit, String? cursor) =>
  //       loadRandomJokesWithWrapping(ref, limit, cursor),
  // ),
  // CompositeJokeSubSource(
  //   id: 'all_jokes_public_timestamp',
  //   minIndex: CompositeJokeSourceBoundaries.publicMinIndex,
  //   maxIndex: CompositeJokeSourceBoundaries.publicMaxIndex,
  //   load: (Ref ref, int limit, String? cursor) => _loadFirestoreJokes(
  //     ref,
  //     limit,
  //     cursor,
  //     orderByField: JokeField.publicTimestamp,
  //     orderDirection: OrderDirection.ascending,
  //     dataSource: 'all_jokes_public_timestamp',
  //   ),
  // ),
];

// Combined index boundaries across composite and priority subsources, computed once.
final List<int> _allSubSourceIndexBoundaries = <int>{
  ..._compositeSubSources.map((s) => s.minIndex ?? 0),
  ..._compositeSubSources.map((s) => s.maxIndex ?? 0),
  ..._prioritySubSources.map((s) => s.minIndex ?? 0),
  ..._prioritySubSources.map((s) => s.maxIndex ?? 0),
}.where((b) => b > 0).toList()..sort();

class CompositeJokeSubSource {
  const CompositeJokeSubSource({
    required this.id,
    required this.minIndex,
    required this.maxIndex,
    required Future<PageResult> Function(Ref<Object?>, int, String?) load,
    this.condition,
  }) : _load = load;

  final String id;
  final int? minIndex;
  final int? maxIndex;
  final bool Function(Ref)? condition;
  final Future<PageResult> Function(Ref ref, int limit, String? cursor) _load;

  /// Check if this subsource is active based on condition, cursor state, and index range.
  ///
  /// [totalJokesLoaded] is used to determine if the subsource is within its active range.
  /// [cursor] is checked for the done sentinel value.
  bool isActive(Ref ref, int totalJokesLoaded, String? cursor) {
    // Check if marked as done
    if (cursor == kDoneSentinel) {
      return false;
    }

    // Check condition if present
    if (condition != null && !condition!(ref)) {
      return false;
    }

    // Check index range
    final isInRange = minIndex == null || minIndex! <= totalJokesLoaded;
    final isNotExceeded = maxIndex == null || maxIndex! > totalJokesLoaded;
    return isInRange && isNotExceeded;
  }

  Future<PageResult> load(Ref ref, int limit, String? cursor) async {
    if (limit <= 0) {
      return PageResult.noOpPage(cursor);
    }
    final page = await _load(ref, limit, cursor);
    AppLogger.debug(
      'PAGING_INTERNAL: Composite: Loaded ${page.jokes.length} jokes from $id (hasMore=${page.hasMore})',
    );
    return page;
  }
}

const String kTotalJokesLoadedKey = 'totalJokesLoaded';
const String kSubSourceCursorsKey = 'subSourceCursors';
const String kPrioritySourceCursorsKey = 'prioritySourceCursors';

class CompositeCursor {
  const CompositeCursor({
    this.totalJokesLoaded = 0,
    this.subSourceCursors = const {},
    this.prioritySourceCursors = const {},
  });

  final int totalJokesLoaded;
  final Map<String, String> subSourceCursors;
  final Map<String, String> prioritySourceCursors;

  String encode() {
    return jsonEncode({
      kTotalJokesLoadedKey: totalJokesLoaded,
      kSubSourceCursorsKey: subSourceCursors,
      kPrioritySourceCursorsKey: prioritySourceCursors,
    });
  }

  static CompositeCursor? decode(String? encoded) {
    if (encoded == null || encoded.isEmpty) return null;
    try {
      final Map<String, dynamic> data =
          jsonDecode(encoded) as Map<String, dynamic>;
      final totalJokesLoaded =
          (data[kTotalJokesLoadedKey] as num?)?.toInt() ?? 0;
      final cursorsData =
          data[kSubSourceCursorsKey] as Map<String, dynamic>? ?? {};
      final cursors = cursorsData.map(
        (key, value) => MapEntry(key, value as String),
      );
      final priorityCursorsData =
          data[kPrioritySourceCursorsKey] as Map<String, dynamic>? ?? {};
      final priorityCursors = priorityCursorsData.map(
        (key, value) => MapEntry(key, value as String),
      );
      return CompositeCursor(
        totalJokesLoaded: totalJokesLoaded,
        subSourceCursors: cursors,
        prioritySourceCursors: priorityCursors,
      );
    } catch (_) {
      return null;
    }
  }
}

bool _isSubSourceCoolingDown(Ref ref, String id) {
  final state = ref.read(_subSourceRetryStateProvider);
  final retryState = state[id];
  if (retryState == null) return false;
  final now = ref.read(clockProvider)();
  final coolingDown = retryState.nextRetryAt.isAfter(now);
  if (coolingDown) {
    AppLogger.debug(
      'PAGING_INTERNAL: Subsource $id cooling down until '
      '${retryState.nextRetryAt.toIso8601String()}',
    );
  }
  return coolingDown;
}

void _recordSubSourceFailure(Ref ref, String id) {
  final notifier = ref.read(_subSourceRetryStateProvider.notifier);
  final state = Map<String, _SubSourceRetryState>.from(notifier.state);
  final currentIndex = state[id]?.attemptIndex ?? 0;
  final backoffIndex = currentIndex.clamp(
    0,
    _subSourceBackoffSchedule.length - 1,
  );
  final backoff = _subSourceBackoffSchedule[backoffIndex.toInt()];
  final nextRetryAt = ref.read(clockProvider)().add(backoff);
  final nextAttemptIndex = (backoffIndex + 1)
      .clamp(0, _subSourceBackoffSchedule.length - 1)
      .toInt();

  state[id] = _SubSourceRetryState(
    nextRetryAt: nextRetryAt,
    attemptIndex: nextAttemptIndex,
  );
  notifier.state = state;

  AppLogger.warn(
    'PAGING_INTERNAL: Subsource $id entering cooldown for '
    '${backoff.inSeconds}s (until ${nextRetryAt.toIso8601String()})',
  );
}

void _clearSubSourceFailure(Ref ref, String id) {
  final notifier = ref.read(_subSourceRetryStateProvider.notifier);
  final state = Map<String, _SubSourceRetryState>.from(notifier.state);
  if (state.remove(id) != null) {
    notifier.state = state;
  }
}

Future<PageResult> _loadCompositeJokePage(
  Ref ref,
  int limit,
  String? cursor,
) async {
  CompositeCursor? currentCursor = CompositeCursor.decode(cursor);
  final totalJokesLoaded = currentCursor?.totalJokesLoaded ?? 0;

  /// Adjust the limit to stop at the next subsource index boundary.
  final effectiveLimit = calculateEffectiveLimit(totalJokesLoaded, limit);

  // Check priority sources first
  final prioritySourceCursors = currentCursor?.prioritySourceCursors ?? {};
  final Map<String, PageResult> priorityPages = {};
  bool subSourceAttempted = false;
  bool subSourceFailedOrSkipped = false;
  bool anyPageAdded = false;
  for (final prioritySource in _prioritySubSources) {
    final priorityCursor = prioritySourceCursors[prioritySource.id];

    // Check if this priority source is active
    if (prioritySource.isActive(ref, totalJokesLoaded, priorityCursor)) {
      subSourceAttempted = true;
      if (_isSubSourceCoolingDown(ref, prioritySource.id)) {
        subSourceFailedOrSkipped = true;
        continue;
      }

      // Load from this priority source exclusively
      AppLogger.debug(
        'PAGING_INTERNAL: Loading from priority source: ${prioritySource.id}',
      );

      try {
        final priorityPage = await prioritySource.load(
          ref,
          effectiveLimit,
          priorityCursor,
        );
        // Record success (even if empty) and stop checking other priority sources.
        _clearSubSourceFailure(ref, prioritySource.id);
        priorityPages[prioritySource.id] = priorityPage;
        if (priorityPage.jokes.isNotEmpty) {
          anyPageAdded = true;
        }
        if (priorityPage.hasMore == false && priorityPage.jokes.isEmpty) {
          AppLogger.debug(
            'PAGING_INTERNAL: Priority source ${prioritySource.id} returned empty and is exhausted.',
          );
        }
        break; // Current flow loads only the first active priority source
      } catch (e) {
        subSourceFailedOrSkipped = true;
        AppLogger.warn(
          'PAGING_INTERNAL: Error loading priority source ${prioritySource.id}: $e',
        );
        _recordSubSourceFailure(ref, prioritySource.id);
      }
    }
  }

  // Load composite sources if needed
  final compositePages = <String, PageResult>{};
  if (priorityPages.isEmpty) {
    // Determine active subsources based on current totalJokesLoaded and conditions
    final activeSubsources = _compositeSubSources.where((subsource) {
      final subsourceCursor = currentCursor?.subSourceCursors[subsource.id];
      return subsource.isActive(ref, totalJokesLoaded, subsourceCursor);
    }).toList();

    if (activeSubsources.isEmpty) {
      // No more active subsources
      return PageResult(
        jokes: const <JokeWithDate>[],
        cursor: null,
        hasMore: false,
      );
    }

    // Calculate how many jokes to request from each active subsource
    int remaining = effectiveLimit;
    final jokesPerSource = (effectiveLimit / activeSubsources.length).round();

    final subSourceCursors = currentCursor?.subSourceCursors ?? {};
    for (final subsource in activeSubsources) {
      subSourceAttempted = true;
      if (_isSubSourceCoolingDown(ref, subsource.id)) {
        subSourceFailedOrSkipped = true;
        continue;
      }

      final subsourceCursor = subSourceCursors[subsource.id];
      final subsourceLimit = math.min(remaining, jokesPerSource);
      if (subsourceLimit <= 0) continue;
      try {
        final page = await subsource.load(ref, subsourceLimit, subsourceCursor);
        _clearSubSourceFailure(ref, subsource.id);
        compositePages[subsource.id] = page;
        if (page.jokes.isNotEmpty) {
          anyPageAdded = true;
        }
      } catch (e) {
        subSourceFailedOrSkipped = true;
        AppLogger.warn(
          'PAGING_INTERNAL: Error loading composite source ${subsource.id}: $e',
        );
        _recordSubSourceFailure(ref, subsource.id);
      }
      remaining -= subsourceLimit;
    }
  }

  if (!anyPageAdded && subSourceAttempted && subSourceFailedOrSkipped) {
    // Throw so GenericPagingNotifier applies backoff
    throw Exception(
      'All attempted composite sources failed or are in cooldown.',
    );
  }

  if (!anyPageAdded) {
    // All sources reported no data without errors; mark as exhausted.
    final encodedCursor = currentCursor?.encode();
    return PageResult.empty(encodedCursor);
  }

  return await createNextPage(
    ref: ref,
    prevCursor: currentCursor,
    priorityPagesBySubSourceId: priorityPages,
    compositePagesBySubSourceId: compositePages,
  );
}

/// Calculate the effective limit to stop at the next subsource index boundary.
int calculateEffectiveLimit(int totalJokesLoaded, int limit) {
  final boundary = _allSubSourceIndexBoundaries.firstWhere(
    (b) => b > totalJokesLoaded && b <= totalJokesLoaded + limit,
    orElse: () => totalJokesLoaded + limit,
  );
  return boundary - totalJokesLoaded;
}

/// Interleave composite subsource pages in round-robin order up to [limit].
List<JokeWithDate> interleaveCompositePages(
  Map<String, PageResult> pagesBySubSourceId,
  List<String> orderedCompositeSourceIds,
) {
  if (pagesBySubSourceId.isEmpty) {
    return const <JokeWithDate>[];
  }

  final interleaved = <JokeWithDate>[];
  int maxLen = pagesBySubSourceId.entries
      .map((e) => e.value.jokes.length)
      .reduce((a, b) => math.max(a, b));

  for (int i = 0; i < maxLen; i++) {
    for (final sourceId in orderedCompositeSourceIds) {
      final page = pagesBySubSourceId[sourceId];
      if (page == null) continue;
      if (i < page.jokes.length) {
        final jokeWithDate = page.jokes[i];
        interleaved.add(
          JokeWithDate(
            joke: jokeWithDate.joke,
            date: jokeWithDate.date,
            dataSource: sourceId,
          ),
        );
      }
    }
  }
  return interleaved;
}

/// Assemble a next page from priority and composite pages, update cursor, and return PageResult.
Future<PageResult> createNextPage({
  required Ref ref,
  CompositeCursor? prevCursor,
  Map<String, PageResult>? priorityPagesBySubSourceId,
  Map<String, PageResult>? compositePagesBySubSourceId,
  List<CompositeJokeSubSource>? prioritySubSourcesOverride,
}) async {
  final priorityPages = priorityPagesBySubSourceId ?? const {};
  final compositePages = compositePagesBySubSourceId ?? const {};

  // Build ordered priority jokes per declared or provided priority source order
  final priorityOrder = (prioritySubSourcesOverride ?? _prioritySubSources)
      .map((s) => s.id)
      .toList();
  final concatenatedPriorityJokes = <JokeWithDate>[];
  for (final sourceId in priorityOrder) {
    final page = priorityPages[sourceId];
    if (page == null) continue;
    concatenatedPriorityJokes.addAll(page.jokes);
  }

  // Determine composite source order from declared composite subsources
  final compositeOrder = _compositeSubSources
      .map((s) => s.id)
      .where((id) => compositePages.containsKey(id))
      .toList();

  final interleavedComposite = interleaveCompositePages(
    compositePages,
    compositeOrder,
  );

  // Combine jokes (priority first, then composite)
  final combinedJokes = <JokeWithDate>[
    ...concatenatedPriorityJokes,
    ...interleavedComposite,
  ];

  // Update cursor
  final current = prevCursor ?? const CompositeCursor();
  // Update priority cursors
  final updatedPriorityCursors = Map<String, String>.from(
    current.prioritySourceCursors,
  );
  for (final sourceId in priorityOrder) {
    final page = priorityPages[sourceId];
    if (page == null) continue;
    if (page.hasMore) {
      if (page.cursor != null) {
        updatedPriorityCursors[sourceId] = page.cursor!;
      }
    } else {
      updatedPriorityCursors[sourceId] = kDoneSentinel;
    }
  }
  // Update composite cursors
  final updatedCompositeCursor = Map<String, String>.from(
    current.subSourceCursors,
  );
  for (final sourceId in compositeOrder) {
    final page = compositePages[sourceId];
    if (page?.cursor != null) {
      updatedCompositeCursor[sourceId] = page!.cursor!;
    }
  }

  final nextCursor = CompositeCursor(
    // Priority sources are not counted towards total jokes loaded.
    totalJokesLoaded: current.totalJokesLoaded + interleavedComposite.length,
    subSourceCursors: updatedCompositeCursor,
    prioritySourceCursors: updatedPriorityCursors,
  ).encode();

  // Always hasMore=true because the composite source is intended to be infinite
  return PageResult(jokes: combinedJokes, cursor: nextCursor, hasMore: true);
}

Future<PageResult> _loadFirestoreJokes(
  Ref ref,
  int limit,
  String? cursor, {
  required JokeField orderByField,
  required OrderDirection orderDirection,
  String? dataSource,
}) async {
  final repository = ref.read(jokeRepositoryProvider);
  final pageCursor = cursor != null
      ? JokeListPageCursor.deserialize(cursor)
      : null;

  final filters = JokeFilter.basePublicFilters();
  final page = await repository.getFilteredJokePage(
    filters: filters,
    orderByField: orderByField,
    orderDirection: orderDirection,
    limit: limit,
    cursor: pageCursor,
  );

  if (page.jokes == null || page.ids.isEmpty) {
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  final jokesWithDate = page.jokes!
      .map((j) => JokeWithDate(joke: j, dataSource: dataSource))
      .toList();

  final nextCursor = page.cursor?.serialize();

  return PageResult(
    jokes: jokesWithDate,
    cursor: nextCursor,
    hasMore: page.hasMore,
  );
}

/// Load random jokes with wrapping logic for infinite traversal.
/// On first load ever (no composite cursor), starts at user's random starting ID.
/// When reaching the end (hasMore=false), wraps around to start from 0.
Future<PageResult> loadRandomJokesWithWrapping(
  Ref ref,
  int limit,
  String? cursor,
) async {
  String? effectiveCursor = await getRandomJokeEffectiveCursor(ref, cursor);

  // Load the page
  final result = await _loadFirestoreJokes(
    ref,
    limit,
    effectiveCursor,
    orderByField: JokeField.randomId,
    orderDirection: OrderDirection.ascending,
    dataSource: 'all_jokes_random',
  );

  // If we've reached the end, wrap around by returning cursor=null
  if (!result.hasMore) {
    AppLogger.debug(
      'PAGING_INTERNAL: Reached end of random jokes, wrapping around to start from 0',
    );
    return PageResult(
      jokes: result.jokes,
      cursor: JokeListPageCursor(
        orderValue: 0,
        docId: dummyDocId,
      ).serialize(), // This will start from 0 on next load
      hasMore: true, // Keep hasMore=true to continue pagination
    );
  }

  return result;
}

Future<String?> getRandomJokeEffectiveCursor(Ref ref, String? cursor) async {
  if (cursor != null) {
    return cursor;
  }

  final settings = ref.read(settingsServiceProvider);
  final hasCompositeCursor = settings.containsKey(compositeJokeCursorPrefsKey);

  // If this is the first load ever (no composite cursor exists) and no cursor provided,
  // start at the user's random starting ID
  if (!hasCompositeCursor) {
    final randomStartingId = await ref.read(randomStartingIdProvider.future);
    final initialCursor = JokeListPageCursor(
      orderValue: randomStartingId,
      docId: dummyDocId,
    );
    AppLogger.debug(
      "PAGING_INTERNAL: Starting random jokes at user's random ID: $randomStartingId",
    );
    return initialCursor.serialize();
  }

  return cursor;
}

Future<PageResult> _loadCategoryPage(Ref ref, int limit, String? cursor) async {
  final category = ref.read(activeCategoryProvider);
  if (category == null) {
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }
  switch (category.type) {
    case CategoryType.firestore:
      return _loadCategoryPageFromCache(ref, category, limit, cursor);
    case CategoryType.popular:
      return _loadFirestoreJokes(
        ref,
        limit,
        cursor,
        orderByField: JokeField.popularityScore,
        orderDirection: OrderDirection.descending,
        dataSource: 'category:popular',
      );
    case CategoryType.daily:
      return loadDailyJokesPage(ref, limit, cursor);
  }
}

Future<PageResult> _loadCategoryPageFromCache(
  Ref ref,
  JokeCategory category,
  int limit,
  String? cursor,
) async {
  AppLogger.debug(
    'PAGING_INTERNAL: Loading Firestore category from cache: ${category.id}, limit: $limit, cursor: $cursor',
  );

  final categoryRepo = ref.read(jokeCategoryRepositoryProvider);
  final cachedJokes = await categoryRepo.getCachedCategoryJokes(
    category.firestoreDocumentId,
  );

  if (cachedJokes.isEmpty) {
    return const PageResult(
      jokes: [],
      cursor: null,
      hasMore: false,
      totalCount: 0,
    );
  }

  // Offset-based pagination
  final offset = cursor != null ? int.parse(cursor) : 0;
  final pageCachedJokes = cachedJokes.skip(offset).take(limit).toList();

  // Construct Joke objects directly from cache data
  final jokes = pageCachedJokes
      .map(
        (cachedJoke) => Joke(
          id: cachedJoke.jokeId,
          setupText: cachedJoke.setupText,
          punchlineText: cachedJoke.punchlineText,
          setupImageUrl: cachedJoke.setupImageUrl,
          punchlineImageUrl: cachedJoke.punchlineImageUrl,
        ),
      )
      .toList();

  final jokesWithDate = jokes
      .map(
        (j) => JokeWithDate(
          joke: j,
          dataSource: 'category:firestore:${category.id}',
        ),
      )
      .toList();

  final nextOffset = offset + limit;
  final hasMore = nextOffset < cachedJokes.length;

  AppLogger.debug(
    'PAGING_INTERNAL: Loaded cached category page at offset $offset, fetched ${jokesWithDate.length} jokes, total cached: ${cachedJokes.length}, hasMore: $hasMore',
  );

  return PageResult(
    jokes: jokesWithDate,
    cursor: hasMore ? nextOffset.toString() : null,
    hasMore: hasMore,
    totalCount: cachedJokes.length,
  );
}

Future<PageResult> _loadSeasonalCategoryPage(
  Ref ref,
  int limit,
  String? cursor, {
  String? seasonalValueOverride,
  JokeField? orderByFieldOverride,
  OrderDirection? orderDirectionOverride,
}) async {
  AppLogger.debug(
    'PAGING_INTERNAL: Loading seasonal category page with limit: $limit, cursor: $cursor',
  );

  final category = ref.read(activeCategoryProvider);
  final seasonalValue = (seasonalValueOverride ?? category?.seasonalValue)
      ?.trim();
  if (seasonalValue == null || seasonalValue.isEmpty) {
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  final repository = ref.read(jokeRepositoryProvider);

  final pageCursor = cursor != null
      ? JokeListPageCursor.deserialize(cursor)
      : null;

  final page = await repository.getFilteredJokePage(
    filters: [
      ...JokeFilter.basePublicFilters(),
      JokeFilter.equals(JokeField.seasonal, seasonalValue),
    ],
    orderByField: orderByFieldOverride ?? JokeField.publicTimestamp,
    orderDirection: orderDirectionOverride ?? OrderDirection.descending,
    limit: limit,
    cursor: pageCursor,
  );

  if (page.ids.isEmpty) {
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  // Fetch full joke documents for the page
  final jokes = await repository.getJokesByIds(page.ids);

  final jokesWithDate = jokes
      .map(
        (j) => JokeWithDate(
          joke: j,
          dataSource: 'category:seasonal:$seasonalValue',
        ),
      )
      .toList();

  final nextCursor = page.cursor?.serialize();

  return PageResult(
    jokes: jokesWithDate,
    cursor: nextCursor,
    hasMore: page.hasMore,
  );
}

// Settings key for tracking last delivered today joke
const String kTodayJokeLastDateKey = 'today_joke_last_date';

/// Load exactly today's daily joke and mark today in settings when returned.
Future<PageResult> _loadTodayJoke(Ref ref) async {
  // Reuse daily jokes loader with limit 1 and no cursor
  final page = await loadDailyJokesPage(ref, 1, null);
  // Always return at most 1 joke
  final jokes = page.jokes.isEmpty ? <JokeWithDate>[] : [page.jokes[0]];

  // Regardless of whether the page has jokes, don't load again today
  final now = ref.read(clockProvider)();
  final todayStr =
      '${now.year.toString().padLeft(4, '0')}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
  final settings = ref.read(settingsServiceProvider);
  // Fire and forget; no need to await persistence for paging
  unawaited(settings.setString(kTodayJokeLastDateKey, todayStr));

  // Always hasMore=true to allow the priority mechanism to continue future days.
  // The cursor isn't actually used, but use todayStr as cursor so the
  // composite cursor is updated.
  return PageResult(jokes: jokes, cursor: todayStr, hasMore: true);
}

bool _shouldShowTodayJoke(Ref ref) {
  final settings = ref.read(settingsServiceProvider);
  final storedDateStr = settings.getString(kTodayJokeLastDateKey);
  if (storedDateStr == null || storedDateStr.isEmpty) {
    AppLogger.debug(
      "PAGING_INTERNAL: Today's joke: No stored date, showing today's joke",
    );
    return true;
  }

  final today = getCurrentDate(ref);

  try {
    final parts = storedDateStr.split('-');
    if (parts.length != 3) return true; // invalid format -> show
    final y = int.parse(parts[0]);
    final m = int.parse(parts[1]);
    final d = int.parse(parts[2]);
    final storedDate = DateTime(y, m, d);
    // Return true only if today > stored
    final isAfter = today.isAfter(storedDate);
    AppLogger.debug(
      "PAGING_INTERNAL: Today's joke: Stored date: $storedDate, today: $today, isAfter: $isAfter",
    );
    return isAfter;
  } catch (e) {
    AppLogger.error(
      "PAGING_INTERNAL: Today's joke: Parse failure, showing today's joke",
    );
    return true; // parse failure -> show
  }
}

/// Factory that returns a page loader bound to a specific SearchScope
Future<PageResult> Function(Ref ref, int limit, String? cursor)
_makeLoadSearchPage(SearchScope scope) {
  return (Ref ref, int limit, String? cursor) async {
    AppLogger.debug(
      'PAGING_INTERNAL: Loading search page with limit: $limit, cursor: $cursor, scope: ${scope.name}',
    );

    // Get all search result IDs from the cached provider for this scope
    final allResults = await ref.read(searchResultIdsProvider(scope).future);

    if (allResults.isEmpty) {
      return const PageResult(
        jokes: [],
        cursor: null,
        hasMore: false,
        totalCount: 0,
      );
    }

    // Parse cursor as offset (0-based index into the full result set)
    final offset = cursor != null ? int.parse(cursor) : 0;

    // Slice the IDs for this page
    final pageResults = allResults.skip(offset).take(limit).toList();
    final jokeIds = pageResults.map((r) => r.id).toList();

    // Fetch joke data only for this page
    final repository = ref.read(jokeRepositoryProvider);
    final jokes = await repository.getJokesByIds(jokeIds);
    final jokesWithDate = jokes
        .map((j) => JokeWithDate(joke: j, dataSource: 'search:${scope.name}'))
        .toList();

    // Calculate next cursor and hasMore
    final nextOffset = offset + limit;
    final hasMore = nextOffset < allResults.length;

    AppLogger.debug(
      'PAGING_INTERNAL: Loaded search page at offset $offset, fetched ${jokesWithDate.length} jokes, total results: ${allResults.length}, hasMore: $hasMore',
    );

    return PageResult(
      jokes: jokesWithDate,
      cursor: hasMore ? nextOffset.toString() : null,
      hasMore: hasMore,
      totalCount: allResults.length,
    );
  };
}

Future<PageResult> loadDailyJokesPage(
  Ref ref,
  int limit,
  String? cursor,
) async {
  AppLogger.debug(
    'PAGING_INTERNAL: Loading daily jokes page with limit: $limit, cursor: $cursor',
  );

  final repository = ref.read(jokeScheduleRepositoryProvider);

  final now = ref.read(clockProvider)();
  final today = DateTime(now.year, now.month, now.day);

  // Determine target month to load
  final DateTime targetMonth;
  if (cursor == null) {
    targetMonth = DateTime(now.year, now.month);
  } else {
    final parts = cursor.split('_');
    final int year = int.parse(parts[0]);
    final int month = int.parse(parts[1]);
    targetMonth = DateTime(year, month);
  }

  // Fetch the batch for the target month
  final batch = await repository.getBatchForMonth(
    JokeConstants.defaultJokeScheduleId,
    targetMonth.year,
    targetMonth.month,
  );

  if (batch == null) {
    AppLogger.debug('PAGING_INTERNAL: No batch for this month: $targetMonth');
    // No batch for this month: stop pagination
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  // Extract jokes from batch; sort by day descending (newest first)
  final jokesWithDate = <JokeWithDate>[];
  final sortedDays = batch.jokes.keys.toList()..sort((a, b) => b.compareTo(a));

  for (final dayKey in sortedDays) {
    final joke = batch.jokes[dayKey];
    if (joke == null) continue;

    final int? day = int.tryParse(dayKey);
    if (day == null) continue;

    final jokeDate = DateTime(batch.year, batch.month, day);
    if (!jokeDate.isAfter(today)) {
      jokesWithDate.add(
        JokeWithDate(joke: joke, date: jokeDate, dataSource: 'daily'),
      );
    }
  }

  // Compute next cursor as previous month; keep paginating until no batch exists
  final previousMonth = DateTime(targetMonth.year, targetMonth.month - 1);
  final nextCursor = '${previousMonth.year}_${previousMonth.month.toString()}';

  // Update the most recent daily joke date
  if (jokesWithDate.isNotEmpty) {
    final mostRecentJokeDate = ref.read(dailyJokesMostRecentDateProvider);
    final firstJokeDate = jokesWithDate.first.date;
    if (firstJokeDate != null &&
        (mostRecentJokeDate == null ||
            firstJokeDate.isAfter(mostRecentJokeDate))) {
      ref.read(dailyJokesMostRecentDateProvider.notifier).state = firstJokeDate;
    }
  }

  AppLogger.debug(
    'PAGING_INTERNAL: Loaded daily jokes page with cursor "$cursor", fetched ${jokesWithDate.length} jokes, next cursor: "$nextCursor"',
  );
  return PageResult(jokes: jokesWithDate, cursor: nextCursor, hasMore: true);
}

/// Determines if daily jokes should be reset due to stale data.
///
/// This function is called whenever the check signal is incremented.
/// It checks if the first loaded joke is stale (date < today) and
/// we haven't already reset today (to avoid thrashing).
bool shouldResetDailyJokesForStaleData(Ref ref, dynamic prev, dynamic next) {
  AppLogger.debug('PAGING_INTERNAL: Checking if daily jokes should be reset');

  final today = getCurrentDate(ref);
  final lastResetDate = ref.read(dailyJokesLastResetDateProvider);

  if (lastResetDate != null && !lastResetDate.isBefore(today)) {
    // Already reset today, don't reset
    return false;
  }

  final firstJokeDate = ref.read(dailyJokesMostRecentDateProvider);
  if (firstJokeDate == null) {
    // First joke has no date, don't reset
    return false;
  }

  final isStale = firstJokeDate.isBefore(today);
  if (!isStale) {
    // Not stale, don't reset
    return false;
  }

  AppLogger.debug(
    'PAGING_INTERNAL: Resetting stale jokes. First joke date: $firstJokeDate, today: $today',
  );
  // Mark that we're resetting today to prevent multiple resets
  ref.read(dailyJokesLastResetDateProvider.notifier).state = today;
  return true;
}

Future<PageResult> _loadSavedJokesPage(
  Ref ref,
  int limit,
  String? cursor,
) async {
  AppLogger.debug(
    'PAGING_INTERNAL: Loading saved jokes page with limit: $limit, cursor: $cursor',
  );

  final appUsageService = ref.read(appUsageServiceProvider);
  final savedJokeIds = await appUsageService.getSavedJokeIds();

  if (savedJokeIds.isEmpty) {
    return const PageResult(
      jokes: [],
      cursor: null,
      hasMore: false,
      totalCount: 0,
    );
  }

  // Offset-based pagination (like search)
  final offset = cursor != null ? int.parse(cursor) : 0;
  final pageIds = savedJokeIds.skip(offset).take(limit).toList();

  // Fetch jokes for this page
  final repository = ref.read(jokeRepositoryProvider);
  final jokes = await repository.getJokesByIds(pageIds);

  // Create map for order preservation
  final jokeMap = <String, Joke>{};
  for (final joke in jokes) {
    jokeMap[joke.id] = joke;
  }

  // Build results in original order
  final jokesWithDate = <JokeWithDate>[];
  for (final id in pageIds) {
    final joke = jokeMap[id];
    if (joke != null) {
      jokesWithDate.add(JokeWithDate(joke: joke, dataSource: 'saved'));
    }
  }

  final nextOffset = offset + limit;
  final hasMore = nextOffset < savedJokeIds.length;

  AppLogger.debug(
    'PAGING_INTERNAL: Loaded saved jokes page at offset $offset, fetched ${jokesWithDate.length} jokes, total saved: ${savedJokeIds.length}, hasMore: $hasMore',
  );

  return PageResult(
    jokes: jokesWithDate,
    cursor: hasMore ? nextOffset.toString() : null,
    hasMore: hasMore,
    totalCount: savedJokeIds.length,
  );
}

Future<PageResult> _loadFeedJokesFromDatabase(
  Ref ref,
  int limit,
  String? cursor,
) async {
  AppLogger.debug(
    'PAGING_INTERNAL: Loading feed jokes from database with limit: $limit, cursor: $cursor',
  );

  final interactionsRepository = ref.read(jokeInteractionsRepositoryProvider);

  final cursorFeedIndex = _parseFeedCursor(cursor);

  final localPage = await _loadFeedJokesFromLocalDatabase(
    ref: ref,
    interactionsRepository: interactionsRepository,
    limit: limit,
    cursorFeedIndex: cursorFeedIndex,
  );

  if (localPage.jokes.isNotEmpty) {
    return localPage;
  }

  final feedCount = await interactionsRepository.countFeedJokes();
  if (feedCount >= _kFeedFallbackLocalThreshold) {
    AppLogger.debug(
      'PAGING_INTERNAL: Local DB returned empty but has $feedCount feed entries; skipping Firestore fallback.',
    );
    return localPage;
  }

  AppLogger.info(
    'PAGING_INTERNAL: Local DB returned empty and has $feedCount feed entries; falling back to Firestore.',
  );
  final syncService = ref.read(feedSyncServiceProvider);
  unawaited(syncService.triggerSync(forceSync: false));

  final fallbackPage = await _loadFeedJokesFromFirestore(
    ref: ref,
    interactionsRepository: interactionsRepository,
    limit: limit,
    cursorFeedIndex: cursorFeedIndex,
  );

  return fallbackPage;
}

Future<PageResult> _loadFeedJokesFromLocalDatabase({
  required Ref ref,
  required JokeInteractionsRepository interactionsRepository,
  required int limit,
  required int? cursorFeedIndex,
}) async {
  final interactions = await interactionsRepository.getFeedJokes(
    cursorFeedIndex: cursorFeedIndex,
    limit: limit,
  );

  if (interactions.isEmpty) {
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  final jokesWithDate = interactions
      .map(
        (interaction) => JokeWithDate(
          joke: Joke(
            id: interaction.jokeId,
            setupText: interaction.setupText ?? '',
            punchlineText: interaction.punchlineText ?? '',
            setupImageUrl: interaction.setupImageUrl,
            punchlineImageUrl: interaction.punchlineImageUrl,
          ),
          dataSource: 'local_feed_jokes',
        ),
      )
      .toList();

  final hasMore = interactions.length == limit;
  final lastFeedIndex = interactions.last.feedIndex;
  final nextCursor = hasMore && lastFeedIndex != null
      ? lastFeedIndex.toString()
      : kDoneSentinel;

  AppLogger.debug(
    'PAGING_INTERNAL: Loaded feed jokes from database: ${jokesWithDate.length} jokes, hasMore: $hasMore, nextCursor: $nextCursor',
  );

  return PageResult(jokes: jokesWithDate, cursor: nextCursor, hasMore: hasMore);
}

Future<PageResult> _loadFeedJokesFromFirestore({
  required Ref ref,
  required JokeInteractionsRepository interactionsRepository,
  required int limit,
  required int? cursorFeedIndex,
}) async {
  if (limit <= 0) {
    return const PageResult(jokes: [], cursor: kDoneSentinel, hasMore: false);
  }

  final repository = ref.read(jokeRepositoryProvider);
  final startFeedIndex = (cursorFeedIndex ?? -1) + 1;
  final targetDocIndex = startFeedIndex ~/ _kFeedJokesPerFirestoreDoc;
  final offsetInDoc = startFeedIndex % _kFeedJokesPerFirestoreDoc;

  // Jump directly to the target doc by constructing a cursor just before it.
  final JokeListPageCursor? repoCursor = targetDocIndex == 0
      ? null
      : JokeListPageCursor(
          orderValue: _zeroPad10(targetDocIndex - 1),
          docId: _zeroPad10(targetDocIndex - 1),
        );

  final page = await repository.readFeedJokes(cursor: repoCursor);
  final jokes = page.jokes ?? const <Joke>[];
  if (jokes.isEmpty) {
    return const PageResult(jokes: [], cursor: kDoneSentinel, hasMore: false);
  }

  final baseFeedIndex = targetDocIndex * _kFeedJokesPerFirestoreDoc;
  final rawCandidates = <({Joke joke, int feedIndex})>[];
  for (var j = offsetInDoc; j < jokes.length; j++) {
    final feedIndex = baseFeedIndex + j;
    if (feedIndex < startFeedIndex) continue;
    rawCandidates.add((joke: jokes[j], feedIndex: feedIndex));
  }

  if (rawCandidates.isEmpty) {
    return const PageResult(jokes: [], cursor: kDoneSentinel, hasMore: false);
  }

  // Return raw slice; viewed filtering happens in GenericPagingNotifier.filterJokes.
  final visible = rawCandidates.take(limit).toList();
  final hasMore = visible.length == limit || page.hasMore;
  final lastFeedIndex = visible.last.feedIndex;

  final jokesWithDate = visible
      .map(
        (entry) =>
            JokeWithDate(joke: entry.joke, dataSource: 'firestore_feed_jokes'),
      )
      .toList();

  final nextCursor = hasMore ? lastFeedIndex.toString() : kDoneSentinel;

  AppLogger.debug(
    'PAGING_INTERNAL: Firestore fallback loaded ${jokesWithDate.length} jokes (hasMore=$hasMore, nextCursor=$nextCursor).',
  );

  return PageResult(jokes: jokesWithDate, cursor: nextCursor, hasMore: hasMore);
}

String _zeroPad10(int value) => value.toString().padLeft(10, '0');
int? _parseFeedCursor(String? cursor) {
  if (cursor == null || cursor.isEmpty) {
    return null;
  }
  try {
    return int.parse(cursor);
  } catch (e) {
    AppLogger.debug(
      'PAGING_INTERNAL: Invalid feed cursor "$cursor", defaulting to null',
    );
    return null;
  }
}

/// Get current date (midnight-normalized) for comparison
DateTime getCurrentDate(Ref ref) {
  final now = ref.read(clockProvider)();
  return DateTime(now.year, now.month, now.day);
}
