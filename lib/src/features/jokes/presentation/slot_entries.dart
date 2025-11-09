import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';

/// Base type for entries rendered by the slot source.
sealed class SlotEntry {
  const SlotEntry();
}

/// Slot entry that represents a real joke.
class JokeSlotEntry extends SlotEntry {
  const JokeSlotEntry({required this.joke});

  /// Joke payload being rendered.
  final JokeWithDate joke;
}

/// Slot entry that signals the viewer has reached the end of the feed.
class EndOfFeedSlotEntry extends SlotEntry {
  const EndOfFeedSlotEntry({
    required this.jokeContext,
    required this.totalJokes,
  });

  /// Analytics context in which the viewer is operating.
  final String jokeContext;

  /// Total real jokes displayed once this entry is appended.
  final int totalJokes;
}
