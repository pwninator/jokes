import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
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
  errorAnalyticsSource: 'search:${SearchScope.userJokeSearch.name}',
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
  errorAnalyticsSource: 'daily_jokes',
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

  errorAnalyticsSource: 'saved_jokes',
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
  errorAnalyticsSource: 'category',
  initialPageSize: 2,
  loadPageSize: 5,
  loadMoreThreshold: 5,
);

/// Shared preferences key for persisting the composite feed cursor.
const compositeJokeCursorPrefsKey = 'composite_joke_cursor';

/// Sentinel cursor value marking a priority source as permanently exhausted.
const String kPriorityDoneSentinel = '__DONE__';

final compositeJokePagingProviders = createPagingProviders(
  loadPage: _loadCompositeJokePage,
  resetTriggers: const [],
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
  errorAnalyticsSource: 'composite_jokes',
  initialPageSize: 3,
  loadPageSize: 12,
  loadMoreThreshold: 5,
);

/// Priority data sources that take precedence over composite sources.
/// Priority sources are checked first; only the first active one is loaded exclusively.
/// When a priority source exhausts (hasMore=false), its cursor is marked "__DONE__"
/// and it will never be loaded again.
final List<CompositeJokeSubSource> _prioritySubSources = [];

/// "Regular" data sources that will intereaved together.
final List<CompositeJokeSubSource> _compositeSubSources = [
  CompositeJokeSubSource(
    id: 'best_jokes',
    minIndex: 0,
    maxIndex: 200,
    load: (Ref ref, int limit, String? cursor) => _loadOrderedJokesPage(
      ref,
      limit,
      cursor,
      orderByField: JokeField.savedFraction,
      orderDirection: OrderDirection.descending,
      dataSource: 'best_jokes',
    ),
  ),
  CompositeJokeSubSource(
    id: 'all_jokes_random',
    minIndex: 10,
    maxIndex: 500, // Loops infinitely, so need a max limit.
    load: (Ref ref, int limit, String? cursor) =>
        loadRandomJokesWithWrapping(ref, limit, cursor),
  ),
  CompositeJokeSubSource(
    id: 'all_jokes_public_timestamp',
    minIndex: 200,
    maxIndex: null,
    load: (Ref ref, int limit, String? cursor) => _loadOrderedJokesPage(
      ref,
      limit,
      cursor,
      orderByField: JokeField.publicTimestamp,
      orderDirection: OrderDirection.ascending,
      dataSource: 'all_jokes_public_timestamp',
    ),
  ),
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
    if (cursor == kPriorityDoneSentinel) {
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
  for (final prioritySource in _prioritySubSources) {
    final priorityCursor = prioritySourceCursors[prioritySource.id];

    // Check if this priority source is active
    if (prioritySource.isActive(ref, totalJokesLoaded, priorityCursor)) {
      // Load from this priority source exclusively
      AppLogger.debug(
        'PAGING_INTERNAL: Loading from priority source: ${prioritySource.id}',
      );

      final priorityPage = await prioritySource.load(
        ref,
        effectiveLimit,
        priorityCursor,
      );
      priorityPages[prioritySource.id] = priorityPage;
      break; // Current flow loads only the first active priority source
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

    // Load from all active subsources in parallel
    final futuresBySubSourceId = <String, Future<PageResult>>{};
    final subSourceCursors = currentCursor?.subSourceCursors ?? {};
    for (final subsource in activeSubsources) {
      final subsourceCursor = subSourceCursors[subsource.id];
      final subsourceLimit = math.min(remaining, jokesPerSource);
      futuresBySubSourceId[subsource.id] = subsource.load(
        ref,
        subsourceLimit,
        subsourceCursor,
      );
      remaining -= subsourceLimit;
    }

    for (final subsource in activeSubsources) {
      compositePages[subsource.id] = await futuresBySubSourceId[subsource.id]!;
    }
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

/// Filter out jokes that have already been viewed.
Future<List<JokeWithDate>> filteredUnviewedJokes(
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

  // Log the jokes that were filtered out for debugging.
  if (kDebugMode && unviewedJokes.length != jokeIds.length) {
    final viewedJokeIds = jokeIds
        .where((id) => !unviewedJokeIds.contains(id))
        .toList();
    AppLogger.info(
      'PAGING_INTERNAL: Filtering out ${viewedJokeIds.length} viewed jokes: $viewedJokeIds',
    );
  }

  return unviewedJokes;
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
  final filteredPriority = await filteredUnviewedJokes(
    ref,
    concatenatedPriorityJokes,
  );

  // Determine composite source order from declared composite subsources
  final compositeOrder = _compositeSubSources
      .map((s) => s.id)
      .where((id) => compositePages.containsKey(id))
      .toList();

  final interleavedComposite = interleaveCompositePages(
    compositePages,
    compositeOrder,
  );
  final filteredComposite = await filteredUnviewedJokes(
    ref,
    interleavedComposite,
  );

  // Combine jokes (priority first, then composite)
  final combinedJokes = <JokeWithDate>[
    ...filteredPriority,
    ...filteredComposite,
  ];

  // Compute hasMore across any page
  bool anyHasMore = [
    ...priorityPages.values,
    ...compositePages.values,
  ].any((p) => p.hasMore);

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
      updatedPriorityCursors[sourceId] = kPriorityDoneSentinel;
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
    totalJokesLoaded: current.totalJokesLoaded + filteredComposite.length,
    subSourceCursors: updatedCompositeCursor,
    prioritySourceCursors: updatedPriorityCursors,
  ).encode();

  return PageResult(
    jokes: combinedJokes,
    cursor: nextCursor,
    hasMore: anyHasMore,
  );
}

Future<PageResult> _loadOrderedJokesPage(
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

  if (page.ids.isEmpty) {
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  final jokes = page.jokes ?? await repository.getJokesByIds(page.ids);
  final now = DateTime.now();
  final filtered = jokes.where((joke) {
    final timestamp = joke.publicTimestamp;
    if (timestamp == null) return false;
    return !timestamp.isAfter(now);
  }).toList();
  final jokesWithDate = filterJokesWithImages(filtered)
      .map(
        (j) => JokeWithDate(joke: j.joke, date: j.date, dataSource: dataSource),
      )
      .toList();

  final nextCursor = page.cursor?.serialize();

  return PageResult(
    jokes: jokesWithDate,
    cursor: nextCursor,
    hasMore: page.hasMore,
  );
}

List<JokeWithDate> filterJokesWithImages(List<Joke> jokes) {
  return jokes
      .where(
        (j) =>
            (j.setupImageUrl != null && j.setupImageUrl!.isNotEmpty) &&
            (j.punchlineImageUrl != null && j.punchlineImageUrl!.isNotEmpty),
      )
      .map((j) => JokeWithDate(joke: j))
      .toList();
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
  final result = await _loadOrderedJokesPage(
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
    case CategoryType.search:
      return _loadSearchCategoryPageFromCache(ref, category, limit, cursor);
    case CategoryType.popular:
      return _loadOrderedJokesPage(
        ref,
        limit,
        cursor,
        orderByField: JokeField.popularityScore,
        orderDirection: OrderDirection.descending,
        dataSource: 'category:popular',
      );
    case CategoryType.seasonal:
      return _loadSeasonalCategoryPage(ref, limit, cursor);
    case CategoryType.daily:
      return loadDailyJokesPage(ref, limit, cursor);
    default:
      return const PageResult(jokes: [], cursor: null, hasMore: false);
  }
}

Future<PageResult> _loadSearchCategoryPageFromCache(
  Ref ref,
  JokeCategory category,
  int limit,
  String? cursor,
) async {
  AppLogger.debug(
    'PAGING_INTERNAL: Loading search category from cache: ${category.id}, limit: $limit, cursor: $cursor',
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

  // Filter for images (matching existing behavior)
  final jokesWithDate = filterJokesWithImages(jokes)
      .map(
        (j) => JokeWithDate(
          joke: j.joke,
          date: j.date,
          dataSource: 'category:search:${category.id}',
        ),
      )
      .toList();

  final nextOffset = offset + limit;
  final hasMore = nextOffset < cachedJokes.length;

  AppLogger.debug(
    'PAGINATION: Loaded cached category page at offset $offset, fetched ${jokesWithDate.length} jokes, total cached: ${cachedJokes.length}, hasMore: $hasMore',
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
  String? cursor,
) async {
  AppLogger.debug(
    'PAGINATION: Loading seasonal category page with limit: $limit, cursor: $cursor',
  );

  final category = ref.read(activeCategoryProvider);
  final seasonalValue = category?.seasonalValue?.trim();
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
      JokeFilter.lessThan(JokeField.publicTimestamp, DateTime.now()),
    ],
    orderByField: JokeField.publicTimestamp,
    orderDirection: OrderDirection.descending,
    limit: limit,
    cursor: pageCursor,
  );

  if (page.ids.isEmpty) {
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  // Fetch full joke documents for the page
  final jokes = await repository.getJokesByIds(page.ids);

  final jokesWithDate = filterJokesWithImages(jokes)
      .map(
        (j) => JokeWithDate(
          joke: j.joke,
          date: j.date,
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

/// Factory that returns a page loader bound to a specific SearchScope
Future<PageResult> Function(Ref ref, int limit, String? cursor)
_makeLoadSearchPage(SearchScope scope) {
  return (Ref ref, int limit, String? cursor) async {
    AppLogger.debug(
      'PAGINATION: Loading search page with limit: $limit, cursor: $cursor, scope: ${scope.name}',
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
    final pageIds = pageResults.map((r) => r.id).toList();

    // Fetch joke data only for this page
    final repository = ref.read(jokeRepositoryProvider);
    final jokes = await repository.getJokesByIds(pageIds);
    final jokesWithDate = jokes
        .map((j) => JokeWithDate(joke: j, dataSource: 'search:${scope.name}'))
        .toList();

    // Calculate next cursor and hasMore
    final nextOffset = offset + limit;
    final hasMore = nextOffset < allResults.length;

    AppLogger.debug(
      'PAGINATION: Loaded search page at offset $offset, fetched ${pageIds.length} jokes, total results: ${allResults.length}, hasMore: $hasMore',
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
    'PAGINATION: Loading daily jokes page with limit: $limit, cursor: $cursor',
  );

  final repository = ref.read(jokeScheduleRepositoryProvider);

  final now = DateTime.now();
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
    AppLogger.debug('PAGINATION: No batch for this month: $targetMonth');
    // No batch for this month: stop pagination
    return const PageResult(jokes: [], cursor: null, hasMore: false);
  }

  // Extract jokes from batch; sort by day descending (newest first)
  final jokesWithDates = <JokeWithDate>[];
  final sortedDays = batch.jokes.keys.toList()..sort((a, b) => b.compareTo(a));

  for (final dayKey in sortedDays) {
    final joke = batch.jokes[dayKey];
    if (joke == null) continue;

    final int? day = int.tryParse(dayKey);
    if (day == null) continue;

    final jokeDate = DateTime(batch.year, batch.month, day);
    final bool include = !jokeDate.isAfter(today);

    if (include &&
        joke.setupImageUrl != null &&
        joke.setupImageUrl!.isNotEmpty &&
        joke.punchlineImageUrl != null &&
        joke.punchlineImageUrl!.isNotEmpty) {
      jokesWithDates.add(
        JokeWithDate(joke: joke, date: jokeDate, dataSource: 'daily'),
      );
    }
  }

  // Compute next cursor as previous month; keep paginating until no batch exists
  final previousMonth = DateTime(targetMonth.year, targetMonth.month - 1);
  final nextCursor = '${previousMonth.year}_${previousMonth.month.toString()}';

  // Update the most recent daily joke date
  if (jokesWithDates.isNotEmpty) {
    final mostRecentJokeDate = ref.read(dailyJokesMostRecentDateProvider);
    final firstJokeDate = jokesWithDates.first.date;
    if (firstJokeDate != null &&
        (mostRecentJokeDate == null ||
            firstJokeDate.isAfter(mostRecentJokeDate))) {
      ref.read(dailyJokesMostRecentDateProvider.notifier).state = firstJokeDate;
    }
  }

  AppLogger.debug(
    'PAGINATION: Loaded daily jokes page with cursor "$cursor", fetched ${jokesWithDates.length} jokes, next cursor: "$nextCursor"',
  );
  return PageResult(jokes: jokesWithDates, cursor: nextCursor, hasMore: true);
}

/// Determines if daily jokes should be reset due to stale data.
///
/// This function is called whenever the check signal is incremented.
/// It checks if the first loaded joke is stale (date < today) and
/// we haven't already reset today (to avoid thrashing).
bool shouldResetDailyJokesForStaleData(Ref ref, dynamic prev, dynamic next) {
  AppLogger.debug('PAGINATION: Checking if daily jokes should be reset');

  final today = getCurrentDate();
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
    'PAGINATION: Resetting stale jokes. First joke date: $firstJokeDate, today: $today',
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
    'PAGINATION: Loading saved jokes page with limit: $limit, cursor: $cursor',
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

  // Build results in original order, filtering for images
  final jokesWithDate = <JokeWithDate>[];
  for (final id in pageIds) {
    final joke = jokeMap[id];
    if (joke != null &&
        joke.setupImageUrl != null &&
        joke.setupImageUrl!.isNotEmpty &&
        joke.punchlineImageUrl != null &&
        joke.punchlineImageUrl!.isNotEmpty) {
      jokesWithDate.add(JokeWithDate(joke: joke, dataSource: 'saved'));
    }
  }

  final nextOffset = offset + limit;
  final hasMore = nextOffset < savedJokeIds.length;

  AppLogger.debug(
    'PAGINATION: Loaded saved jokes page at offset $offset, fetched ${jokesWithDate.length} jokes, total saved: ${savedJokeIds.length}, hasMore: $hasMore',
  );

  return PageResult(
    jokes: jokesWithDate,
    cursor: hasMore ? nextOffset.toString() : null,
    hasMore: hasMore,
    totalCount: savedJokeIds.length,
  );
}

/// Get current date (midnight-normalized) for comparison
DateTime getCurrentDate() {
  final now = DateTime.now();
  return DateTime(now.year, now.month, now.day);
}
