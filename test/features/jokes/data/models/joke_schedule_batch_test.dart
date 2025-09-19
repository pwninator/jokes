import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';

void main() {
  group('JokeScheduleBatch', () {
    group('ID Management', () {
      test('createBatchId should format correctly', () {
        final testCases = {
          'daily_jokes_2024_03': () =>
              JokeScheduleBatch.createBatchId('daily_jokes', 2024, 3),
          'holiday_special_2024_12': () =>
              JokeScheduleBatch.createBatchId('holiday_special', 2024, 12),
        };

        for (final entry in testCases.entries) {
          expect(entry.value(), entry.key);
        }
      });

      test('parseBatchId should extract components correctly', () {
        final testCases = {
          'daily_jokes_2024_03': {
            'scheduleId': 'daily_jokes',
            'year': 2024,
            'month': 3,
          },
          'holiday_special_schedule_2024_12': {
            'scheduleId': 'holiday_special_schedule',
            'year': 2024,
            'month': 12,
          },
        };

        for (final entry in testCases.entries) {
          expect(JokeScheduleBatch.parseBatchId(entry.key), entry.value);
        }
      });

      test('parseBatchId should return null for invalid formats', () {
        final invalidIds = ['invalid', 'too_few_parts', 'invalid_year_month'];
        for (final id in invalidIds) {
          expect(JokeScheduleBatch.parseBatchId(id), isNull);
        }
      });
    });

    group('Model methods', () {
      final testJoke = Joke(
        id: 'joke_1',
        setupText: 'Why did the chicken cross the road?',
        punchlineText: 'To get to the other side!',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      final tBatch = JokeScheduleBatch(
        id: 'daily_jokes_2024_03',
        scheduleId: 'daily_jokes',
        year: 2024,
        month: 3,
        jokes: {'01': testJoke},
      );

      test('should perform a serialization round trip correctly', () {
        // Arrange
        final map = tBatch.toMap();

        // Act
        final fromMap = JokeScheduleBatch.fromMap(map, tBatch.id);

        // Assert
        expect(fromMap, tBatch);
      });

      test('fromMap should handle empty and missing jokes gracefully', () {
        // Empty jokes map
        final batch1 = JokeScheduleBatch.fromMap({
          'jokes': <String, dynamic>{},
        }, 'test_2024_01');
        expect(batch1.jokes, isEmpty);

        // Missing jokes field
        final batch2 = JokeScheduleBatch.fromMap(
          <String, dynamic>{},
          'test_2024_01',
        );
        expect(batch2.jokes, isEmpty);
      });

      test('fromMap should throw ArgumentError on invalid document ID', () {
        expect(
          () => JokeScheduleBatch.fromMap({}, 'invalid_id'),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('copyWith should create a copy with updated values', () {
        // Arrange
        final newJokes = {
          '02': const Joke(id: 'new', setupText: 'New', punchlineText: 'New'),
        };

        // Act
        final copied = tBatch.copyWith(year: 2025, jokes: newJokes);

        // Assert
        expect(copied.id, tBatch.id); // Unchanged
        expect(copied.scheduleId, tBatch.scheduleId); // Unchanged
        expect(copied.year, 2025); // Updated
        expect(copied.jokes, newJokes); // Updated
      });

      test('equality and hashCode should work correctly', () {
        // Arrange
        final sameBatch = tBatch.copyWith();
        final differentBatch = tBatch.copyWith(id: 'diff_id');

        // Assert
        expect(tBatch, sameBatch);
        expect(tBatch.hashCode, sameBatch.hashCode);
        expect(tBatch, isNot(differentBatch));
        expect(tBatch.hashCode, isNot(differentBatch.hashCode));
      });

      test('toString should return a non-empty string', () {
        expect(tBatch.toString(), isNotEmpty);
      });
    });
  });
}
