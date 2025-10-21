import 'package:flutter_test/flutter_test.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

void main() {
  group('Joke Model', () {
    // A complete Joke object with all fields populated for thorough testing.
    final tFullJoke = Joke(
      id: '1',
      setupText: 'Why did the scarecrow win an award?',
      punchlineText: 'Because he was outstanding in his field!',
      setupImageUrl: 'http://example.com/setup.png',
      punchlineImageUrl: 'http://example.com/punchline.png',
      setupImageDescription: 'a scarecrow',
      punchlineImageDescription: 'a happy scarecrow',
      allSetupImageUrls: const ['http://example.com/setup.png'],
      allPunchlineImageUrls: const ['http://example.com/punchline.png'],
      generationMetadata: const {'source': 'test'},
      numSaves: 5,
      numShares: 3,
      numSavedUsersFraction: 0.2,
      adminRating: JokeAdminRating.approved,
      state: JokeState.published,
      publicTimestamp: DateTime.utc(2023),
      tags: const ['puns', 'awards'],
      seasonal: 'fall',
    );

    // A minimal Joke object with only required fields.
    const tMinimalJoke = Joke(
      id: '2',
      setupText: 'What do you call a fake noodle?',
      punchlineText: 'An Impasta!',
    );

    group('Serialization (fromMap/toMap)', () {
      test('should perform a round trip (toMap -> fromMap) successfully', () {
        // Arrange
        final map = tFullJoke.toMap();

        // Act
        final result = Joke.fromMap(map, tFullJoke.id);

        // Assert
        expect(result, tFullJoke);
      });

      test(
        'should handle minimal data, setting defaults for missing fields',
        () {
          // Arrange
          final map = {
            'setup_text': tMinimalJoke.setupText,
            'punchline_text': tMinimalJoke.punchlineText,
          };

          // Act
          final result = Joke.fromMap(map, tMinimalJoke.id);

          // Assert
          expect(result, tMinimalJoke);
          expect(result.tags, isEmpty);
          expect(result.setupImageUrl, isNull);
        },
      );

      group('_parsePublicTimestamp', () {
        test('should parse Timestamp object', () {
          final timestamp = Timestamp.fromDate(DateTime.utc(2023));
          final map = {...tMinimalJoke.toMap(), 'public_timestamp': timestamp};
          final result = Joke.fromMap(map, tMinimalJoke.id);
          expect(result.publicTimestamp, DateTime.utc(2023));
        });

        test('should parse String object', () {
          const dateString = '2023-01-01T12:00:00.000Z';
          final map = {...tMinimalJoke.toMap(), 'public_timestamp': dateString};
          final result = Joke.fromMap(map, tMinimalJoke.id);
          expect(result.publicTimestamp, DateTime.parse(dateString).toUtc());
        });

        test('should parse int (milliseconds)', () {
          final milliseconds = DateTime.utc(2023).millisecondsSinceEpoch;
          final map = {
            ...tMinimalJoke.toMap(),
            'public_timestamp': milliseconds,
          };
          final result = Joke.fromMap(map, tMinimalJoke.id);
          expect(
            result.publicTimestamp,
            DateTime.fromMillisecondsSinceEpoch(milliseconds, isUtc: true),
          );
        });

        test('should parse int (seconds)', () {
          final seconds = DateTime.utc(2023).millisecondsSinceEpoch ~/ 1000;
          final map = {...tMinimalJoke.toMap(), 'public_timestamp': seconds};
          final result = Joke.fromMap(map, tMinimalJoke.id);
          expect(
            result.publicTimestamp,
            DateTime.fromMillisecondsSinceEpoch(seconds * 1000, isUtc: true),
          );
        });

        test('should return null for invalid data', () {
          final map = {
            ...tMinimalJoke.toMap(),
            'public_timestamp': 'not-a-date',
          };
          final result = Joke.fromMap(map, tMinimalJoke.id);
          expect(result.publicTimestamp, isNull);
        });
      });
    });

    group('copyWith', () {
      test(
        'should return an identical object when no parameters are provided',
        () {
          // Act
          final result = tFullJoke.copyWith();
          // Assert
          expect(result, tFullJoke);
        },
      );

      test('should update only the specified fields', () {
        // Act
        final result = tMinimalJoke.copyWith(
          setupText: 'new setup',
          numSaves: 100,
        );
        // Assert
        expect(result.setupText, 'new setup');
        expect(result.numSaves, 100);
        expect(result.punchlineText, tMinimalJoke.punchlineText); // Unchanged
        expect(result.id, tMinimalJoke.id); // Unchanged
      });

      test('should create a new object with all fields updated', () {
        // Act
        final result = tMinimalJoke.copyWith(
          id: '3',
          setupText: 'new setup',
          punchlineText: 'new punchline',
          setupImageUrl: 'new_url',
          numSaves: 1,
          tags: ['new_tag'],
        );

        // Assert
        expect(result.id, '3');
        expect(result.setupText, 'new setup');
        expect(result.punchlineText, 'new punchline');
        expect(result.setupImageUrl, 'new_url');
        expect(result.numSaves, 1);
        expect(result.tags, ['new_tag']);
      });
    });

    group('Equality and hashCode', () {
      test('should be equal if all properties are the same', () {
        // Arrange
        final anotherFullJoke = tFullJoke.copyWith();
        // Assert
        expect(tFullJoke, anotherFullJoke);
        expect(tFullJoke.hashCode, anotherFullJoke.hashCode);
      });

      test('should not be equal if any property is different', () {
        // Assert
        expect(tFullJoke, isNot(tFullJoke.copyWith(id: '_')));
        expect(tFullJoke, isNot(tFullJoke.copyWith(setupText: '_')));
        expect(tFullJoke, isNot(tFullJoke.copyWith(punchlineText: '_')));
        expect(tFullJoke, isNot(tFullJoke.copyWith(numSaves: 999)));
        expect(tFullJoke, isNot(tFullJoke.copyWith(tags: ['_'])));
      });

      test('hashCode should be different if any property is different', () {
        // Assert
        expect(tFullJoke.hashCode, isNot(tFullJoke.copyWith(id: '_').hashCode));
        expect(
          tFullJoke.hashCode,
          isNot(tFullJoke.copyWith(setupText: '_').hashCode),
        );
        expect(
          tFullJoke.hashCode,
          isNot(tFullJoke.copyWith(punchlineText: '_').hashCode),
        );
      });
    });

    test('toString should return a non-empty string', () {
      expect(tFullJoke.toString(), isNotEmpty);
    });
  });
}
