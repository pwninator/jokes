import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_entries.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_injection_strategies.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_source.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('SlotEntriesNotifier reset behavior', () {
    // Test-controlled providers
    late StateProvider<AsyncValue<List<JokeWithDate>>> itemsStateProvider;
    late StateProvider<bool> hasMoreStateProvider;

    late PagingProviderBundle bundleWithEndOfFeed;
    late PagingProviderBundle bundleNoStrategies;

    setUp(() {
      // State we can control in tests
      itemsStateProvider = StateProvider<AsyncValue<List<JokeWithDate>>>(
        (ref) => const AsyncValue.data(<JokeWithDate>[]),
      );
      hasMoreStateProvider = StateProvider<bool>((ref) => true);

      // Create a paging bundle whose paging provider is never read (lazy).
      final dummyPaging =
          StateNotifierProvider<GenericPagingNotifier, PagingState>(
            (ref) => throw UnimplementedError(
              'paging not used in SlotEntriesNotifier tests',
            ),
          );

      // Items/hasMore providers are derived from test-controlled state providers
      final itemsProvider = Provider<AsyncValue<List<JokeWithDate>>>(
        (ref) => ref.watch(itemsStateProvider),
      );
      final hasMoreProvider = Provider<bool>(
        (ref) => ref.watch(hasMoreStateProvider),
      );
      final isLoadingProvider = Provider<bool>((ref) => false);
      final isDataPendingProvider = Provider<bool>((ref) => false);
      final resultCountProvider = Provider<({int count, bool hasMore})>((ref) {
        final items = ref.watch(itemsStateProvider);
        final count = items.maybeWhen(
          data: (list) => list.length,
          orElse: () => 0,
        );
        final hasMore = ref.watch(hasMoreStateProvider);
        return (count: count, hasMore: hasMore);
      });

      bundleWithEndOfFeed = PagingProviderBundle(
        paging: dummyPaging,
        items: itemsProvider,
        hasMore: hasMoreProvider,
        isLoading: isLoadingProvider,
        isDataPending: isDataPendingProvider,
        resultCount: resultCountProvider,
      );

      bundleNoStrategies = bundleWithEndOfFeed;
    });

    tearDown(() {});

    JokeWithDate makeJ(String id) => JokeWithDate(
      joke: Joke(id: id, setupText: 's', punchlineText: 'p'),
    );

    testWidgets('Initial empty -> no EndOfFeed injection', (tester) async {
      await _withTester(tester, (ref) async {
        // Prepare data source and slot provider with EndOfFeed strategy
        final dataSource = JokeListDataSource(ref, bundleWithEndOfFeed);
        final provider = slotEntriesProvider((
          dataSource,
          (_) => const [EndOfFeedSlotInjectionStrategy(jokeContext: 'feed')],
        ));

        // Initial: empty items, hasMore=false -> do NOT inject EndOfFeed
        ref.read(hasMoreStateProvider.notifier).state = false;
        ref.read(itemsStateProvider.notifier).state = const AsyncValue.data(
          <JokeWithDate>[],
        );

        // First tick
        await tester.pump();
        // Trigger provider creation then allow microtask to process
        ref.read(provider);
        await tester.pump();
        final first = ref.read(provider);
        expect(first.hasValue, true);
        final firstEntries = first.value!;
        expect(firstEntries, isEmpty);

        // Repeat same state; ensure we still do not inject
        ref.read(itemsStateProvider.notifier).state = const AsyncValue.data(
          <JokeWithDate>[],
        );
        await tester.pump();

        ref.read(provider);
        await tester.pump();
        final second = ref.read(provider);
        expect(second.hasValue, true);
        final secondEntries = second.value!;
        expect(secondEntries, isEmpty);
      });
    });

    // End-of-feed injection now only occurs when there are existing entries,
    // and is covered indirectly by integration tests. We keep core behaviors
    // (initial empty, pagination append, resets) asserted here.

    testWidgets('Pagination append: [a,b] -> [a,b,c] should not reset', (
      tester,
    ) async {
      await _withTester(tester, (ref) async {
        final dataSource = JokeListDataSource(ref, bundleWithEndOfFeed);
        final provider = slotEntriesProvider((
          dataSource,
          (_) => const [EndOfFeedSlotInjectionStrategy(jokeContext: 'feed')],
        ));

        ref.read(hasMoreStateProvider.notifier).state = true;
        ref.read(itemsStateProvider.notifier).state = AsyncValue.data([
          makeJ('a'),
          makeJ('b'),
        ]);
        await tester.pump();

        ref.read(itemsStateProvider.notifier).state = AsyncValue.data([
          makeJ('a'),
          makeJ('b'),
          makeJ('c'),
        ]);
        await tester.pump();

        ref.read(provider);
        await tester.pump();
        final result = ref.read(provider);
        final entries = result.value!;
        expect(entries.length, 3);
        expect(entries.first, isA<JokeSlotEntry>());
        expect((entries[2] as JokeSlotEntry).joke.joke.id, 'c');
      });
    });

    testWidgets(
      'Reset to empty: [a,b] -> [] should clear entries (no strategies)',
      (tester) async {
        await _withTester(tester, (ref) async {
          final dataSource = JokeListDataSource(ref, bundleNoStrategies);
          final provider = slotEntriesProvider((dataSource, (_) => const []));

          ref.read(itemsStateProvider.notifier).state = AsyncValue.data([
            makeJ('a'),
            makeJ('b'),
          ]);
          await tester.pump();

          ref.read(itemsStateProvider.notifier).state = const AsyncValue.data(
            <JokeWithDate>[],
          );
          await tester.pump();

          ref.read(provider);
          await tester.pump();
          final result = ref.read(provider);
          final entries = result.value!;
          expect(entries, isEmpty);
        });
      },
    );

    testWidgets(
      'Reload same jokes: [a,b] -> [a,b] should not reset or duplicate',
      (tester) async {
        await _withTester(tester, (ref) async {
          final dataSource = JokeListDataSource(ref, bundleWithEndOfFeed);
          final provider = slotEntriesProvider((
            dataSource,
            (_) => const [EndOfFeedSlotInjectionStrategy(jokeContext: 'feed')],
          ));

          ref.read(itemsStateProvider.notifier).state = AsyncValue.data([
            makeJ('a'),
            makeJ('b'),
          ]);
          await tester.pump();

          ref.read(itemsStateProvider.notifier).state = AsyncValue.data([
            makeJ('a'),
            makeJ('b'),
          ]);
          await tester.pump();

          ref.read(provider);
          await tester.pump();
          final result = ref.read(provider);
          final entries = result.value!;
          expect(entries.length, 2);
          expect((entries[0] as JokeSlotEntry).joke.joke.id, 'a');
          expect((entries[1] as JokeSlotEntry).joke.joke.id, 'b');
        });
      },
    );
  });
}

// Helper: run with WidgetTester, ensuring proper mount/unmount within the test.
Future<void> _withTester(
  WidgetTester tester,
  Future<void> Function(WidgetRef) body,
) async {
  final completer = Completer<void>();
  await tester.pumpWidget(
    ProviderScope(
      child: Consumer(
        builder: (context, ref, _) {
          scheduleMicrotask(() async {
            try {
              await body(ref);
              completer.complete();
            } catch (e) {
              completer.completeError(e);
            }
          });
          return const SizedBox.shrink();
        },
      ),
    ),
  );
  await tester.pump();
  await completer.future;
  await tester.pumpWidget(const SizedBox.shrink());
}
