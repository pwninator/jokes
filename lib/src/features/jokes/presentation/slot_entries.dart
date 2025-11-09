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
