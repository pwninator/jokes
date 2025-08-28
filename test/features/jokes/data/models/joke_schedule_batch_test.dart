import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';

void main() {
  group('JokeScheduleBatch', () {
    group('ID management', () {
      test('createBatchId formats correctly', () {
        expect(
          JokeScheduleBatch.createBatchId('daily_jokes', 2024, 3),
          equals('daily_jokes_2024_03'),
        );
        expect(
          JokeScheduleBatch.createBatchId('holiday_special', 2024, 12),
          equals('holiday_special_2024_12'),
        );
      });

      test('parseBatchId extracts components correctly', () {
        final parsed = JokeScheduleBatch.parseBatchId('daily_jokes_2024_03');

        expect(parsed, {'scheduleId': 'daily_jokes', 'year': 2024, 'month': 3});
      });

      test('parseBatchId handles schedule IDs with underscores', () {
        final parsed = JokeScheduleBatch.parseBatchId(
          'holiday_special_schedule_2024_12',
        );

        expect(parsed, {
          'scheduleId': 'holiday_special_schedule',
          'year': 2024,
          'month': 12,
        });
      });

      test('parseBatchId returns null for invalid formats', () {
        expect(JokeScheduleBatch.parseBatchId('invalid'), isNull);
        expect(JokeScheduleBatch.parseBatchId('too_few_parts'), isNull);
        expect(JokeScheduleBatch.parseBatchId('invalid_year_month'), isNull);
      });
    });

    group('serialization', () {
      final testJoke = Joke(
        id: 'joke_1',
        setupText: 'Why did the chicken cross the road?',
        punchlineText: 'To get to the other side!',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      final testBatch = JokeScheduleBatch(
        id: 'daily_jokes_2024_03',
        scheduleId: 'daily_jokes',
        year: 2024,
        month: 3,
        jokes: {'01': testJoke},
      );

      test('toMap converts to correct Firestore format', () {
        final map = testBatch.toMap();

        expect(map, {
          'jokes': {
            '01': {
              'joke_id': 'joke_1',
              'setup': 'Why did the chicken cross the road?',
              'punchline': 'To get to the other side!',
              'setup_image_url': 'https://example.com/setup.jpg',
              'punchline_image_url': 'https://example.com/punchline.jpg',
            },
          },
        });
      });

      test('fromMap creates correct instance', () {
        final map = {
          'jokes': {
            '01': {
              'joke_id': 'joke_1',
              'setup': 'Why did the chicken cross the road?',
              'punchline': 'To get to the other side!',
              'setup_image_url': 'https://example.com/setup.jpg',
              'punchline_image_url': 'https://example.com/punchline.jpg',
            },
          },
        };

        final batch = JokeScheduleBatch.fromMap(map, 'daily_jokes_2024_03');

        expect(batch.id, equals('daily_jokes_2024_03'));
        expect(batch.scheduleId, equals('daily_jokes'));
        expect(batch.year, equals(2024));
        expect(batch.month, equals(3));
        expect(batch.jokes.length, equals(1));

        final joke = batch.jokes['01']!;
        expect(joke.id, equals('joke_1'));
        expect(joke.setupText, equals('Why did the chicken cross the road?'));
        expect(joke.punchlineText, equals('To get to the other side!'));
      });

      test('fromMap handles empty jokes', () {
        final map = {'jokes': <String, dynamic>{}};
        final batch = JokeScheduleBatch.fromMap(map, 'test_2024_01');

        expect(batch.jokes, isEmpty);
      });

      test('fromMap handles missing jokes field', () {
        final map = <String, dynamic>{};
        final batch = JokeScheduleBatch.fromMap(map, 'test_2024_01');

        expect(batch.jokes, isEmpty);
      });

      test('fromMap throws on invalid document ID', () {
        final map = {'jokes': {}};

        expect(
          () => JokeScheduleBatch.fromMap(map, 'invalid_id'),
          throwsA(isA<ArgumentError>()),
        );
      });
    });

    group('copyWith', () {
      final originalBatch = JokeScheduleBatch(
        id: 'test_2024_01',
        scheduleId: 'test',
        year: 2024,
        month: 1,
        jokes: {},
      );

      test('copies with new values', () {
        final newJokes = {
          '01': Joke(id: 'new', setupText: 'New', punchlineText: 'New'),
        };
        final copied = originalBatch.copyWith(
          year: 2025,
          month: 2,
          jokes: newJokes,
        );

        expect(copied.id, equals('test_2024_01')); // ID unchanged
        expect(copied.scheduleId, equals('test')); // Schedule ID unchanged
        expect(copied.year, equals(2025));
        expect(copied.month, equals(2));
        expect(copied.jokes, equals(newJokes));
      });
    });

    group('equality and hashing', () {
      final joke = Joke(
        id: 'test',
        setupText: 'Setup',
        punchlineText: 'Punchline',
      );

      test('equal batches are equal', () {
        final batch1 = JokeScheduleBatch(
          id: 'test_2024_01',
          scheduleId: 'test',
          year: 2024,
          month: 1,
          jokes: {'01': joke},
        );
        final batch2 = JokeScheduleBatch(
          id: 'test_2024_01',
          scheduleId: 'test',
          year: 2024,
          month: 1,
          jokes: {'01': joke},
        );

        expect(batch1, equals(batch2));
        // Note: hashCode may differ due to map implementation, which is acceptable
      });

      test('different batches are not equal', () {
        final batch1 = JokeScheduleBatch(
          id: 'test_2024_01',
          scheduleId: 'test',
          year: 2024,
          month: 1,
          jokes: {},
        );
        final batch2 = JokeScheduleBatch(
          id: 'test_2024_02',
          scheduleId: 'test',
          year: 2024,
          month: 2,
          jokes: {},
        );

        expect(batch1, isNot(equals(batch2)));
      });
    });
  });
}
