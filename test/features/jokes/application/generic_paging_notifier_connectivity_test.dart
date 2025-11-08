import 'dart:async';

import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';

Joke _makeJoke(String id) => Joke(
  id: id,
  setupText: 'setup $id',
  punchlineText: 'punchline $id',
  setupImageUrl: 'https://img/$id-a.jpg',
  punchlineImageUrl: 'https://img/$id-b.jpg',
  publicTimestamp: DateTime.utc(2024, 1, 1),
);

Future<void> waitUntil(bool Function() condition) async {
  final deadline = DateTime.now().add(const Duration(seconds: 1));
  while (!condition()) {
    if (DateTime.now().isAfter(deadline)) {
      fail('Timed out waiting for condition');
    }
    await Future<void>.delayed(const Duration(milliseconds: 5));
  }
}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockFirebaseAnalytics extends Mock implements FirebaseAnalytics {}

void main() {
  setUpAll(() {
    // Setup analytics fallback values
    registerFallbackValue(JokeViewerMode.reveal);
    registerFallbackValue(Brightness.light);
  });
  group('GenericPagingNotifier connectivity', () {
    test('initial pending emits AsyncLoading before first data', () async {
      // Build paging providers with a delayed first page to simulate pending
      Future<PageResult> loadPage(Ref ref, int limit, String? cursor) async {
        await Future<void>.delayed(const Duration(milliseconds: 50));
        return PageResult(
          jokes: [JokeWithDate(joke: _makeJoke('x'))],
          cursor: null,
          hasMore: false,
        );
      }

      final bundle = createPagingProviders(
        loadPage: loadPage,
        resetTriggers: const [],
        dataSourceName: 'test',
        initialPageSize: 1,
        loadPageSize: 1,
        loadMoreThreshold: 1,
      );

      final mockAnalyticsService = MockAnalyticsService();
      final mockFirebaseAnalytics = MockFirebaseAnalytics();

      final container = ProviderContainer(
        overrides: [
          // Mock analytics services
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          firebaseAnalyticsProvider.overrideWithValue(mockFirebaseAnalytics),
          // Mock offlineToOnlineProvider to never emit (no transitions in this test)
          offlineToOnlineProvider.overrideWith((ref) => const Stream.empty()),
          // Mock isOnlineNowProvider to ensure loadFirstPage proceeds
          isOnlineNowProvider.overrideWith((ref) => true),
        ],
      );
      addTearDown(container.dispose);

      // Immediately after creation, items should be loading (pending)
      final first = container.read(bundle.items);
      expect(first.isLoading, true);

      // After delay, it should have a value
      await Future<void>.delayed(const Duration(milliseconds: 80));
      final after = container.read(bundle.items);
      expect(after.hasValue, true);
      expect(after.requireValue.length, 1);
    });
    test('offline at start, then online triggers first page load', () async {
      final connectivityController = StreamController<bool>.broadcast();
      final offlineToOnlineController = StreamController<int>.broadcast();

      // Build paging providers with loadPage that reads current online state
      Future<PageResult> loadPage(Ref ref, int limit, String? cursor) async {
        final online = ref
            .read(isOnlineProvider)
            .maybeWhen(data: (v) => v, orElse: () => true);
        if (!online) {
          throw Exception('offline');
        }
        return PageResult(
          jokes: [JokeWithDate(joke: _makeJoke('1'))],
          cursor: null,
          hasMore: false,
        );
      }

      final bundle = createPagingProviders(
        loadPage: loadPage,
        resetTriggers: const [],
        dataSourceName: 'test',
        initialPageSize: 2,
        loadPageSize: 2,
        loadMoreThreshold: 1,
      );

      final mockAnalyticsService = MockAnalyticsService();
      final mockFirebaseAnalytics = MockFirebaseAnalytics();

      final overrides = [
        // Mock analytics + FirebaseAnalytics to avoid real Firebase init
        analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
        firebaseAnalyticsProvider.overrideWithValue(mockFirebaseAnalytics),
        // Start offline, then allow tests to push updates
        isOnlineProvider.overrideWith((ref) async* {
          yield false;
          yield* connectivityController.stream;
        }),
        // Mock offlineToOnlineProvider to emit when test simulates the transition
        offlineToOnlineProvider.overrideWith(
          (ref) => offlineToOnlineController.stream,
        ),
      ];

      final container = ProviderContainer(overrides: overrides);
      addTearDown(container.dispose);

      // Trigger initial load microtask
      await Future<void>.delayed(const Duration(milliseconds: 10));

      // Should be loading while offline (pending)
      final itemsBefore = container.read(bundle.items);
      expect(itemsBefore.isLoading, true);

      // Prepare a completer to wait for data to arrive
      final loaded = Completer<void>();
      final sub = container.listen<AsyncValue<List<JokeWithDate>>>(
        bundle.items,
        (prev, next) {
          if (!loaded.isCompleted &&
              next.hasValue &&
              next.requireValue.isNotEmpty) {
            loaded.complete();
          }
        },
        fireImmediately: true,
      );

      // Flip to online and trigger offline-to-online transition
      connectivityController.add(true);
      offlineToOnlineController.add(1);

      // Wait for load to complete or time out
      await loaded.future.timeout(
        const Duration(seconds: 2),
        onTimeout: () => null,
      );
      sub.close();

      final itemsAfter = container.read(bundle.items);
      expect(itemsAfter.hasValue, true);
      expect(itemsAfter.requireValue.length, 1);

      await connectivityController.close();
      await offlineToOnlineController.close();
    });

    test('continues paging when first page filters out all jokes', () async {
      final requestedCursors = <String?>[];
      int callCount = 0;

      Future<PageResult> loadPage(Ref ref, int limit, String? cursor) async {
        requestedCursors.add(cursor);
        callCount++;

        if (callCount == 1) {
          final filteredJoke = Joke(
            id: 'filtered',
            setupText: 'setup filtered',
            punchlineText: 'punchline filtered',
            setupImageUrl: '', // Will be filtered out (no image URL)
            punchlineImageUrl: '',
            publicTimestamp: DateTime.utc(2024, 1, 1),
          );
          return PageResult(
            jokes: [JokeWithDate(joke: filteredJoke, dataSource: 'test')],
            cursor: 'cursor-1',
            hasMore: true,
          );
        }

        final validJoke = Joke(
          id: 'kept',
          setupText: 'setup kept',
          punchlineText: 'punchline kept',
          setupImageUrl: 'https://img/kept-a.jpg',
          punchlineImageUrl: 'https://img/kept-b.jpg',
          publicTimestamp: DateTime.utc(2024, 1, 1),
        );
        return PageResult(
          jokes: [JokeWithDate(joke: validJoke, dataSource: 'test')],
          cursor: null,
          hasMore: false,
        );
      }

      final bundle = createPagingProviders(
        loadPage: loadPage,
        resetTriggers: const [],
        dataSourceName: 'test',
        initialPageSize: 1,
        loadPageSize: 1,
        loadMoreThreshold: 1,
      );

      final mockAnalyticsService = MockAnalyticsService();
      final mockFirebaseAnalytics = MockFirebaseAnalytics();

      final container = ProviderContainer(
        overrides: [
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          firebaseAnalyticsProvider.overrideWithValue(mockFirebaseAnalytics),
          offlineToOnlineProvider.overrideWith((ref) => const Stream.empty()),
          isOnlineNowProvider.overrideWith((ref) => true),
        ],
      );
      addTearDown(container.dispose);

      container.read(bundle.paging);

      await waitUntil(() => requestedCursors.length >= 2);
      await waitUntil(
        () =>
            container.read(bundle.paging).loadedJokes.length == 1 &&
            !container.read(bundle.paging).isLoading,
      );

      expect(requestedCursors, [null, 'cursor-1']);
      final state = container.read(bundle.paging);
      expect(state.loadedJokes.single.joke.id, 'kept');
      expect(state.cursor, isNull);
      expect(state.hasMore, isFalse);
    });

    test(
      'does not repeat loadFirstPage when first page filtered away',
      () async {
        final requestedCursors = <String?>[];
        int initialCursorCalls = 0;
        var repeatedLoadFirstPage = false;

        Future<PageResult> loadPage(Ref ref, int limit, String? cursor) async {
          requestedCursors.add(cursor);

          if (cursor == null) {
            initialCursorCalls++;
            if (initialCursorCalls > 1) {
              repeatedLoadFirstPage = true;
              return const PageResult(jokes: [], cursor: null, hasMore: false);
            }
            final filteredJoke = Joke(
              id: 'filtered',
              setupText: 'setup filtered',
              punchlineText: 'punchline filtered',
              setupImageUrl: '',
              punchlineImageUrl: '',
              publicTimestamp: DateTime.utc(2024, 1, 1),
            );
            return PageResult(
              jokes: [JokeWithDate(joke: filteredJoke, dataSource: 'test')],
              cursor: 'cursor-1',
              hasMore: true,
            );
          }

          final validJoke = _makeJoke('kept');
          return PageResult(
            jokes: [JokeWithDate(joke: validJoke, dataSource: 'test')],
            cursor: null,
            hasMore: false,
          );
        }

        final bundle = createPagingProviders(
          loadPage: loadPage,
          resetTriggers: const [],
          dataSourceName: 'test',
          initialPageSize: 1,
          loadPageSize: 1,
          loadMoreThreshold: 1,
        );

        final mockAnalyticsService = MockAnalyticsService();
        final mockFirebaseAnalytics = MockFirebaseAnalytics();

        final container = ProviderContainer(
          overrides: [
            analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
            firebaseAnalyticsProvider.overrideWithValue(mockFirebaseAnalytics),
            offlineToOnlineProvider.overrideWith((ref) => const Stream.empty()),
            isOnlineNowProvider.overrideWith((ref) => true),
          ],
        );
        addTearDown(container.dispose);

        container.read(bundle.paging);

        await waitUntil(
          () =>
              repeatedLoadFirstPage ||
              (!container.read(bundle.paging).isLoading &&
                  container.read(bundle.paging).loadedJokes.length == 1),
        );

        expect(
          repeatedLoadFirstPage,
          isFalse,
          reason: 'loadFirstPage was invoked more than once',
        );
        expect(initialCursorCalls, 1);
        expect(
          container.read(bundle.paging).loadedJokes.single.joke.id,
          'kept',
        );
      },
    );

    test('clears cached cursor when page returns null', () async {
      final requestedCursors = <String?>[];
      int callCount = 0;

      Future<PageResult> loadPage(Ref ref, int limit, String? cursor) async {
        requestedCursors.add(cursor);
        callCount++;
        if (callCount == 1) {
          return PageResult(
            jokes: [JokeWithDate(joke: _makeJoke('first'))],
            cursor: 'cursor-1',
            hasMore: true,
          );
        }
        return PageResult(
          jokes: [JokeWithDate(joke: _makeJoke('second'))],
          cursor: null,
          hasMore: false,
        );
      }

      final bundle = createPagingProviders(
        loadPage: loadPage,
        resetTriggers: const [],
        dataSourceName: 'test',
        initialPageSize: 1,
        loadPageSize: 1,
        loadMoreThreshold: -1,
      );

      final mockAnalyticsService = MockAnalyticsService();
      final mockFirebaseAnalytics = MockFirebaseAnalytics();

      final container = ProviderContainer(
        overrides: [
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          firebaseAnalyticsProvider.overrideWithValue(mockFirebaseAnalytics),
          offlineToOnlineProvider.overrideWith((ref) => const Stream.empty()),
          isOnlineNowProvider.overrideWith((ref) => true),
        ],
      );
      addTearDown(container.dispose);

      // Touch the paging provider so it starts loading.
      container.read(bundle.paging);

      await waitUntil(() => requestedCursors.isNotEmpty);
      await waitUntil(
        () => container.read(bundle.paging).loadedJokes.length == 1,
      );

      final firstState = container.read(bundle.paging);
      expect(firstState.cursor, 'cursor-1');
      expect(firstState.hasMore, isTrue);

      await container.read(bundle.paging.notifier).loadMore();
      await waitUntil(() => requestedCursors.length == 2);
      await waitUntil(
        () =>
            !container.read(bundle.paging).isLoading &&
            container.read(bundle.paging).loadedJokes.length == 2,
      );

      final secondState = container.read(bundle.paging);
      expect(secondState.cursor, isNull);
      expect(secondState.hasMore, isFalse);
      expect(secondState.loadedJokes.length, 2);
      expect(requestedCursors, [null, 'cursor-1']);
    });
  });
}
