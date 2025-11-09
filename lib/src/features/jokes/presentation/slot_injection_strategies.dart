import 'slot_entries.dart';

/// Base contract for slot-injection strategies.
///
/// Implementations receive both the committed entries (what the viewer already
/// renders) and the new entries that are about to be appended. Strategies may
/// examine either list, inject additional [SlotEntry] instances, or leave the
/// list unchanged. Implementations **must** ensure that every element of
/// [newEntries] is still present in the returned list to avoid dropping jokes.
abstract class SlotInjectionStrategy {
  const SlotInjectionStrategy();

  List<SlotEntry> apply({
    required List<SlotEntry> existingEntries,
    required List<SlotEntry> newEntries,
    required bool hasMore,
  });
}

/// Inserts a single end-of-feed entry when pagination reports no more items.
class EndOfFeedSlotInjectionStrategy extends SlotInjectionStrategy {
  const EndOfFeedSlotInjectionStrategy({required this.jokeContext});

  final String jokeContext;

  @override
  List<SlotEntry> apply({
    required List<SlotEntry> existingEntries,
    required List<SlotEntry> newEntries,
    required bool hasMore,
  }) {
    if (hasMore) {
      return newEntries;
    }

    final hasNewEntries = newEntries.isNotEmpty;
    if (!hasNewEntries) {
      final SlotEntry? lastExisting = existingEntries.isNotEmpty
          ? existingEntries.last
          : null;
      if (_isEndOfFeedEntry(lastExisting)) {
        // End-of-feed entry already exists, return new entries unchanged.
        return newEntries;
      }
    }

    final totalJokes =
        existingEntries.whereType<JokeSlotEntry>().length +
        newEntries.whereType<JokeSlotEntry>().length;

    return [
      ...newEntries,
      EndOfFeedSlotEntry(jokeContext: jokeContext, totalJokes: totalJokes),
    ];
  }

  bool _isEndOfFeedEntry(SlotEntry? entry) =>
      entry is EndOfFeedSlotEntry && entry.jokeContext == jokeContext;
}
