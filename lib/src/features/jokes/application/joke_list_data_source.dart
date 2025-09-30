import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart'
    show JokeWithDate;

/// Data source contract for `JokeListViewer` supporting incremental loading.
///
/// - `items` provides the current list of jokes to render.
/// - `hasMore` indicates whether more items can be loaded.
/// - `isLoading` indicates whether a load operation is in flight.
/// - `loadMore` requests loading the next page of items.
/// - `updateViewingIndex` reports the current viewing position for auto-loading.
abstract class JokeListDataSource {
  ProviderListenable<AsyncValue<List<JokeWithDate>>> get items;
  ProviderListenable<bool> get hasMore;
  ProviderListenable<bool> get isLoading;

  Future<void> loadMore();
  
  /// Updates the current viewing index to enable auto-loading when within threshold
  void updateViewingIndex(int index);
}
