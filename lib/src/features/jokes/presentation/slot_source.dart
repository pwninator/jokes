import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';

import 'slot_entries.dart';
import 'slot_injection_strategies.dart';

/// Watches jokes from a data source and emits slot entries for rendering.
class SlotEntriesNotifier extends StateNotifier<AsyncValue<List<SlotEntry>>> {
  SlotEntriesNotifier(
    this._ref,
    this._dataSource, {
    required this.strategies,
    required this.hasMoreProvider,
  }) : _entries = <SlotEntry>[],
       _jokeIds = const <String>[],
       super(const AsyncValue.loading()) {
    _subscription = _ref.listen<AsyncValue<List<JokeWithDate>>>(
      _dataSource.items,
      (_, next) => _enqueueUpdate(next),
    );
    _enqueueUpdate(_ref.read(_dataSource.items));
  }

  final Ref _ref;

  /// Data source providing the jokes to render.
  final JokeListDataSource _dataSource;

  /// Mutable list of slot entries that have been materialized.
  final List<SlotEntry> _entries;

  /// Mutable list of joke IDs in [_entries], used to diff against new jokes.
  List<String> _jokeIds;

  /// Subscription to the data source's items provider.
  late final ProviderSubscription<AsyncValue<List<JokeWithDate>>> _subscription;

  final List<SlotInjectionStrategy> strategies;
  final ProviderListenable<bool> hasMoreProvider;
  bool _isDisposed = false;

  @override
  void dispose() {
    _subscription.close();
    _isDisposed = true;
    super.dispose();
  }

  void _enqueueUpdate(AsyncValue<List<JokeWithDate>> value) {
    Future.microtask(() => _handleJokes(value));
  }

  void _handleJokes(AsyncValue<List<JokeWithDate>> value) {
    if (_isDisposed) return;
    value.when(
      data: (jokes) {
        _updateEntries(jokes);
        state = AsyncValue.data(List<SlotEntry>.unmodifiable(_entries));
      },
      loading: () => state = const AsyncValue.loading(),
      error: (error, stack) => state = AsyncValue.error(error, stack),
    );
  }

  void _updateEntries(List<JokeWithDate> jokes) {
    if (_shouldReset(jokes)) {
      _entries.clear();
      _jokeIds = const <String>[];
    }

    final newJokes = <SlotEntry>[];
    for (int i = _jokeIds.length; i < jokes.length; i++) {
      newJokes.add(JokeSlotEntry(joke: jokes[i]));
    }
    final existingEntries = List<SlotEntry>.unmodifiable(_entries);
    final injected = strategies.fold<List<SlotEntry>>(
      newJokes,
      (current, strategy) => strategy.apply(
        existingEntries: existingEntries,
        newEntries: current,
        hasMore: _ref.read(hasMoreProvider),
      ),
    );
    _entries.addAll(injected);
    _jokeIds = jokes.map((j) => j.joke.id).toList(growable: false);
  }

  bool _shouldReset(List<JokeWithDate> jokes) {
    if (_jokeIds.isEmpty) {
      if (_entries.isNotEmpty) {
        // If we have no tracked jokes yet but we do have existing entries (e.g., an injected
        // EndOfFeed entry), and new jokes arrive, clear the injected entries so that real jokes
        // render from a clean slate.
        return jokes.isNotEmpty;
      } else {
        return false;
      }
    }
    if (jokes.length < _jokeIds.length) return true;
    for (int i = 0; i < _jokeIds.length; i++) {
      if (_jokeIds[i] != jokes[i].joke.id) return true;
    }
    return false;
  }
}

/// Provider that emits slot entries for a given data source.
typedef SlotEntryStrategiesBuilder =
    List<SlotInjectionStrategy> Function(JokeListDataSource dataSource);

List<SlotInjectionStrategy> _defaultStrategiesBuilder(
  JokeListDataSource dataSource,
) => const [];

final slotEntriesProvider =
    AutoDisposeStateNotifierProvider.family<
      SlotEntriesNotifier,
      AsyncValue<List<SlotEntry>>,
      (JokeListDataSource, SlotEntryStrategiesBuilder)
    >((ref, args) {
      final dataSource = args.$1;
      final strategies = args.$2(dataSource);
      return SlotEntriesNotifier(
        ref,
        dataSource,
        strategies: strategies,
        hasMoreProvider: dataSource.hasMore,
      );
    });

/// Simple wrapper exposing the providers the viewer needs.
class SlotSource {
  const SlotSource({
    required this.slotsProvider,
    required this.hasMoreProvider,
    required this.isLoadingProvider,
    required this.isDataPendingProvider,
    required this.onViewingIndexUpdated,
    required this.resultCountProvider,
    this.debugLabel,
  });

  factory SlotSource.fromDataSource(
    JokeListDataSource dataSource, {
    SlotEntryStrategiesBuilder strategiesBuilder = _defaultStrategiesBuilder,
  }) => SlotSource(
    slotsProvider: slotEntriesProvider((dataSource, strategiesBuilder)),
    hasMoreProvider: dataSource.hasMore,
    isLoadingProvider: dataSource.isLoading,
    isDataPendingProvider: dataSource.isDataPending,
    onViewingIndexUpdated: dataSource.updateViewingIndex,
    resultCountProvider: dataSource.resultCount,
    debugLabel: dataSource.runtimeType.toString(),
  );

  final ProviderListenable<AsyncValue<List<SlotEntry>>> slotsProvider;
  final ProviderListenable<bool> hasMoreProvider;
  final ProviderListenable<bool> isLoadingProvider;
  final ProviderListenable<bool> isDataPendingProvider;
  final ProviderListenable<({int count, bool hasMore})> resultCountProvider;
  final void Function(int index)? onViewingIndexUpdated;
  final String? debugLabel;
}
