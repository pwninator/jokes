import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';

/// Represents a slot rendered by [JokeListViewer].
sealed class JokeListSlot {
  const JokeListSlot({required this.slotIndex});

  /// Zero-based index within the rendered sequence.
  final int slotIndex;
}

/// Slot that renders an actual joke.
class JokeSlot extends JokeListSlot {
  JokeSlot({
    required super.slotIndex,
    required this.jokeIndex,
    required this.joke,
  }) : super();

  /// Zero-based index of the joke within the original data source list.
  final int jokeIndex;

  /// Joke backing this slot.
  final JokeWithDate joke;
}

/// Immutable sequence of slots derived from a list of jokes.
///
/// Phase 1: only joke slots exist. Future phases will add injected slots while
/// reusing the same sequence helpers.
class JokeListSlotSequence {
  JokeListSlotSequence({required List<JokeWithDate> jokes})
    : _jokes = List<JokeWithDate>.unmodifiable(jokes),
      _slots = List<JokeListSlot>.generate(
        jokes.length,
        (index) =>
            JokeSlot(slotIndex: index, jokeIndex: index, joke: jokes[index]),
        growable: false,
      ),
      _jokeIndexToSlotIndex = List<int>.generate(
        jokes.length,
        (index) => index,
      ),
      _realJokesBefore = List<int>.generate(jokes.length, (index) => index) {
    // Build caches eagerly so lookups stay O(1) even after we introduce
    // injected slots in later phases.
  }

  final List<JokeWithDate> _jokes;
  final List<JokeListSlot> _slots;
  final List<int> _jokeIndexToSlotIndex;
  final List<int> _realJokesBefore;

  /// Source jokes backing the sequence.
  List<JokeWithDate> get jokes => _jokes;

  /// Total number of rendered slots.
  int get slotCount => _slots.length;

  /// Total number of jokes backing the sequence.
  int get totalJokes => _jokes.length;

  /// Convenience check for whether there is at least one joke.
  bool get hasJokes => totalJokes > 0;

  /// Returns the slot at [slotIndex].
  JokeListSlot slotAt(int slotIndex) => _slots[slotIndex];

  /// Returns the slot typed as [JokeSlot]. Caller must ensure the slot is a
  /// joke slot; mainly used in Phase 1 where all slots are jokes.
  JokeSlot jokeSlotAt(int slotIndex) => _slots[slotIndex] as JokeSlot;

  /// Returns the joke index for the given [slotIndex], or `null` if the slot is
  /// not backed by a joke.
  int? jokeIndexForSlot(int slotIndex) {
    if (slotIndex < 0 || slotIndex >= _slots.length) {
      return null;
    }
    final slot = _slots[slotIndex];
    if (slot is JokeSlot) return slot.jokeIndex;
    return null;
  }

  /// Returns the slot index for the given [jokeIndex], or `null` if out of
  /// bounds.
  int? slotIndexForJokeIndex(int jokeIndex) {
    if (jokeIndex < 0 || jokeIndex >= _jokeIndexToSlotIndex.length) {
      return null;
    }
    return _jokeIndexToSlotIndex[jokeIndex];
  }

  /// Number of real jokes before the slot located at [slotIndex].
  int realJokesBefore(int slotIndex) {
    if (slotIndex < 0 || slotIndex >= _realJokesBefore.length) {
      return 0;
    }
    return _realJokesBefore[slotIndex];
  }

  /// Finds the next slot strictly after [slotIndex] that contains a joke.
  int? firstJokeSlotAfter(int slotIndex) {
    for (int i = slotIndex + 1; i < _slots.length; i++) {
      if (_slots[i] is JokeSlot) return i;
    }
    return null;
  }

  /// Finds the closest slot at or before [slotIndex] that contains a joke.
  int? lastJokeSlotAtOrBefore(int slotIndex) {
    if (_slots.isEmpty) return null;
    int start = slotIndex;
    if (start >= _slots.length) {
      start = _slots.length - 1;
    }
    if (start < 0) return null;
    for (int i = start; i >= 0; i--) {
      if (_slots[i] is JokeSlot) return i;
    }
    return null;
  }
}
