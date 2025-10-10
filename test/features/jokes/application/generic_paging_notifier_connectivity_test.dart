import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

import '../../../test_helpers/analytics_mocks.dart';

Joke _makeJoke(String id) => Joke(
  id: id,
  setupText: 'setup $id',
  punchlineText: 'punchline $id',
  setupImageUrl: 'https://img/$id-a.jpg',
  punchlineImageUrl: 'https://img/$id-b.jpg',
);

void main() {
  setUpAll(() {
    registerAnalyticsFallbackValues();
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
        errorAnalyticsSource: 'test',
        initialPageSize: 1,
        loadPageSize: 1,
        loadMoreThreshold: 1,
      );

      final container = ProviderContainer(
        overrides: [
          ...AnalyticsMocks.getAnalyticsProviderOverrides(),
          // Mock offlineToOnlineProvider to never emit (no transitions in this test)
          offlineToOnlineProvider.overrideWith((ref) => const Stream.empty()),
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
        errorAnalyticsSource: 'test',
        initialPageSize: 2,
        loadPageSize: 2,
        loadMoreThreshold: 1,
      );

      final overrides = [
        // Mock analytics + FirebaseAnalytics to avoid real Firebase init
        ...AnalyticsMocks.getAnalyticsProviderOverrides(),
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
  });
}
