import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';

/// Represents the loading status for one direction of a paginated list.
@immutable
class JokeListDirectionStatus {
  /// Creates a status for one direction of a paginated list.
  const JokeListDirectionStatus({this.isLoading = false, this.hasMore = false});

  /// Whether a load is currently in progress for this direction.
  final bool isLoading;

  /// Whether more items can be loaded in this direction.
  final bool hasMore;

  JokeListDirectionStatus copyWith({bool? isLoading, bool? hasMore}) {
    return JokeListDirectionStatus(
      isLoading: isLoading ?? this.isLoading,
      hasMore: hasMore ?? this.hasMore,
    );
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is JokeListDirectionStatus &&
        other.isLoading == isLoading &&
        other.hasMore == hasMore;
  }

  @override
  int get hashCode => Object.hash(isLoading, hasMore);
}

/// Represents the complete state of a paginated list of jokes.
///
/// This class holds the current list of items, loading states for both
/// forward and backward pagination, and an anchor index for lists that support
/// prepending items.
@immutable
class JokeListPaginationState {
  /// Creates a pagination state for a list of jokes.
  const JokeListPaginationState({
    required this.items,
    this.anchorIndex = 0,
    this.forwardStatus = const JokeListDirectionStatus(),
    this.backwardStatus = const JokeListDirectionStatus(),
  }) : assert(anchorIndex >= 0, 'anchorIndex must be non-negative');

  /// The current list of jokes, wrapped in an [AsyncValue] to represent
  /// loading and error states.
  final AsyncValue<List<JokeWithDate>> items;

  /// The index in [items] that marks the boundary between items loaded
  /// backward (prepended) and items loaded forward (appended).
  /// For forward-only lists, this is always 0.
  final int anchorIndex;

  /// The loading status for the forward direction (appending items).
  final JokeListDirectionStatus forwardStatus;

  /// The loading status for the backward direction (prepending items).
  final JokeListDirectionStatus backwardStatus;

  /// Creates a [JokeListPaginationState] from a simple [AsyncValue].
  ///
  /// This is useful for adapting non-paginated providers to the pagination system.
  static JokeListPaginationState fromAsyncValue(
    AsyncValue<List<JokeWithDate>> value, {
    int anchorIndex = 0,
    JokeListDirectionStatus forwardStatus = const JokeListDirectionStatus(),
    JokeListDirectionStatus backwardStatus = const JokeListDirectionStatus(),
  }) {
    return JokeListPaginationState(
      items: value,
      anchorIndex: anchorIndex,
      forwardStatus: forwardStatus,
      backwardStatus: backwardStatus,
    );
  }

  JokeListPaginationState copyWith({
    AsyncValue<List<JokeWithDate>>? items,
    int? anchorIndex,
    JokeListDirectionStatus? forwardStatus,
    JokeListDirectionStatus? backwardStatus,
  }) {
    return JokeListPaginationState(
      items: items ?? this.items,
      anchorIndex: anchorIndex ?? this.anchorIndex,
      forwardStatus: forwardStatus ?? this.forwardStatus,
      backwardStatus: backwardStatus ?? this.backwardStatus,
    );
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is JokeListPaginationState &&
        other.items == items &&
        other.anchorIndex == anchorIndex &&
        other.forwardStatus == forwardStatus &&
        other.backwardStatus == backwardStatus;
  }

  @override
  int get hashCode =>
      Object.hash(items, anchorIndex, forwardStatus, backwardStatus);
}

/// A callback that triggers loading more items for a paginated list.
typedef JokeListLoadCallback = Future<void> Function(WidgetRef ref);

/// Defines the condition for triggering a [JokeListLoadCallback].
@immutable
class JokeListLoadTrigger {
  /// Creates a trigger for loading more jokes.
  const JokeListLoadTrigger({
    required this.threshold,
    required this.onThresholdReached,
  }) : assert(threshold >= 0, 'threshold must be non-negative');

  /// The number of items from the end of the list at which to trigger loading.
  final int threshold;

  /// The callback to invoke when the threshold is reached.
  final JokeListLoadCallback onThresholdReached;
}

/// Configuration for incremental loading in a [JokeListViewer].
///
/// Provides optional triggers for both forward and backward directions.
@immutable
class JokeListLoadMoreConfig {
  /// Creates a configuration for incremental loading.
  const JokeListLoadMoreConfig({this.forward, this.backward});

  /// The trigger for loading more items in the forward direction (appending).
  final JokeListLoadTrigger? forward;

  /// The trigger for loading more items in the backward direction (prepending).
  final JokeListLoadTrigger? backward;
}
