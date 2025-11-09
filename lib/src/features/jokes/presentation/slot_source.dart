import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';

import 'slot_entries.dart';

/// Watches jokes from a data source and emits slot entries for rendering.
class SlotEntriesNotifier extends StateNotifier<AsyncValue<List<SlotEntry>>> {
  SlotEntriesNotifier(this._ref, this._dataSource)
    : _entries = <SlotEntry>[],
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

    for (int i = _jokeIds.length; i < jokes.length; i++) {
      _entries.add(JokeSlotEntry(joke: jokes[i]));
    }
    _jokeIds = jokes.map((j) => j.joke.id).toList(growable: false);
  }

  bool _shouldReset(List<JokeWithDate> jokes) {
    if (_jokeIds.isEmpty) return false;
    if (jokes.length < _jokeIds.length) return true;
    for (int i = 0; i < _jokeIds.length; i++) {
      if (_jokeIds[i] != jokes[i].joke.id) return true;
    }
    return false;
  }
}

/// Provider that emits slot entries for a given data source.
final slotEntriesProvider =
    AutoDisposeStateNotifierProvider.family<
      SlotEntriesNotifier,
      AsyncValue<List<SlotEntry>>,
      JokeListDataSource
    >((ref, dataSource) => SlotEntriesNotifier(ref, dataSource));

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

  factory SlotSource.fromDataSource(JokeListDataSource dataSource) =>
      SlotSource(
        slotsProvider: slotEntriesProvider(dataSource),
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
