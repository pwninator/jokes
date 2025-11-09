import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_entries.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_injection_strategies.dart';

void main() {
  group('EndOfFeedSlotInjectionStrategy', () {
    const strategy = EndOfFeedSlotInjectionStrategy(jokeContext: 'feed');

    test('returns new entries unchanged when hasMore is true', () {
      final newEntries = [_jokeEntry('a'), _jokeEntry('b')];

      final result = strategy.apply(
        existingEntries: const [],
        newEntries: newEntries,
        hasMore: true,
      );

      expect(result, equals(newEntries));
    });

    test('appends entry when new entries arrive and feed is exhausted', () {
      final existingEntries = [_jokeEntry('a')];
      final newEntries = [_jokeEntry('b')];

      final result = strategy.apply(
        existingEntries: existingEntries,
        newEntries: newEntries,
        hasMore: false,
      );

      expect(result.length, newEntries.length + 1);
      expect(result.last, isA<EndOfFeedSlotEntry>());
      final endEntry = result.last as EndOfFeedSlotEntry;
      expect(endEntry.totalJokes, 2);
    });

    test(
      'does not insert when no new entries and end-of-feed already present',
      () {
        final existingEntries = [
          _jokeEntry('a'),
          const EndOfFeedSlotEntry(jokeContext: 'feed', totalJokes: 1),
        ];

        final result = strategy.apply(
          existingEntries: existingEntries,
          newEntries: const [],
          hasMore: false,
        );

        expect(result, isEmpty);
      },
    );

    test(
      'inserts when no new entries but trailing entry is not end-of-feed',
      () {
        final existingEntries = [_jokeEntry('a')];

        final result = strategy.apply(
          existingEntries: existingEntries,
          newEntries: const [],
          hasMore: false,
        );

        expect(result.length, 1);
        expect(result.single, isA<EndOfFeedSlotEntry>());
        final endEntry = result.single as EndOfFeedSlotEntry;
        expect(endEntry.totalJokes, 1);
      },
    );

    test(
      'still appends when new entries exist even if end already present',
      () {
        final existingEntries = [
          _jokeEntry('a'),
          const EndOfFeedSlotEntry(jokeContext: 'feed', totalJokes: 1),
        ];
        final newEntries = [_jokeEntry('b')];

        final result = strategy.apply(
          existingEntries: existingEntries,
          newEntries: newEntries,
          hasMore: false,
        );

        expect(result.length, newEntries.length + 1);
        expect(result.last, isA<EndOfFeedSlotEntry>());
      },
    );
  });
}

JokeSlotEntry _jokeEntry(String id) =>
    JokeSlotEntry(joke: JokeWithDate(joke: _joke(id)));

Joke _joke(String id) =>
    Joke(id: id, setupText: 'setup $id', punchlineText: 'punchline $id');
