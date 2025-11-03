import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_slots.dart';

void main() {
  Joke buildJoke(String id) {
    return Joke(
      id: id,
      setupText: 'setup $id',
      punchlineText: 'punchline $id',
      setupImageUrl: 'setup-$id.png',
      punchlineImageUrl: 'punchline-$id.png',
    );
  }

  List<JokeWithDate> buildJokes(int count) {
    return List<JokeWithDate>.generate(
      count,
      (index) => JokeWithDate(joke: buildJoke('j$index')),
    );
  }

  group('JokeListSlotSequence', () {
    test('exposes slot and joke counts', () {
      final jokes = buildJokes(3);
      final sequence = JokeListSlotSequence(jokes: jokes);

      expect(sequence.slotCount, equals(3));
      expect(sequence.totalJokes, equals(3));
      expect(sequence.hasJokes, isTrue);
    });

    test('maps slot index to joke index symmetrically', () {
      final jokes = buildJokes(4);
      final sequence = JokeListSlotSequence(jokes: jokes);

      for (var i = 0; i < jokes.length; i++) {
        expect(sequence.jokeIndexForSlot(i), equals(i));
        expect(sequence.slotIndexForJokeIndex(i), equals(i));
      }

      expect(sequence.jokeIndexForSlot(10), isNull);
      expect(sequence.slotIndexForJokeIndex(10), isNull);
    });

    test('realJokesBefore tracks running count', () {
      final jokes = buildJokes(5);
      final sequence = JokeListSlotSequence(jokes: jokes);

      for (var i = 0; i < jokes.length; i++) {
        expect(sequence.realJokesBefore(i), equals(i));
      }
    });

    test('navigational helpers locate surrounding jokes', () {
      final jokes = buildJokes(3);
      final sequence = JokeListSlotSequence(jokes: jokes);

      expect(sequence.firstJokeSlotAfter(0), equals(1));
      expect(sequence.firstJokeSlotAfter(1), equals(2));
      expect(sequence.firstJokeSlotAfter(2), isNull);

      expect(sequence.lastJokeSlotAtOrBefore(2), equals(2));
      expect(sequence.lastJokeSlotAtOrBefore(1), equals(1));
      expect(sequence.lastJokeSlotAtOrBefore(0), equals(0));
      expect(sequence.lastJokeSlotAtOrBefore(-1), isNull);
    });

    test('hasJokes reflects empty sequence', () {
      final sequence = JokeListSlotSequence(jokes: const []);

      expect(sequence.slotCount, equals(0));
      expect(sequence.totalJokes, equals(0));
      expect(sequence.hasJokes, isFalse);
      expect(sequence.firstJokeSlotAfter(0), isNull);
      expect(sequence.lastJokeSlotAtOrBefore(0), isNull);
    });
  });
}
