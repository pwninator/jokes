import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule.dart';

void main() {
  group('JokeSchedule', () {
    group('sanitizeId', () {
      test('converts name to lowercase', () {
        expect(JokeSchedule.sanitizeId('UPPER'), equals('upper'));
        expect(JokeSchedule.sanitizeId('MixedCase'), equals('mixedcase'));
      });

      test('replaces non-alphanumeric characters with underscores', () {
        expect(JokeSchedule.sanitizeId('hello world'), equals('hello_world'));
        expect(
          JokeSchedule.sanitizeId('test@email.com'),
          equals('test_email_com'),
        );
        expect(
          JokeSchedule.sanitizeId('special!chars#'),
          equals('special_chars'),
        );
      });

      test('removes leading and trailing underscores', () {
        expect(JokeSchedule.sanitizeId('_leading'), equals('leading'));
        expect(JokeSchedule.sanitizeId('trailing_'), equals('trailing'));
        expect(JokeSchedule.sanitizeId('_both_'), equals('both'));
      });

      test('deduplicates consecutive underscores', () {
        expect(
          JokeSchedule.sanitizeId('multiple   spaces'),
          equals('multiple_spaces'),
        );
        expect(
          JokeSchedule.sanitizeId('many____underscores'),
          equals('many_underscores'),
        );
        expect(
          JokeSchedule.sanitizeId('__double__leading__'),
          equals('double_leading'),
        );
      });

      test('handles complex cases', () {
        expect(
          JokeSchedule.sanitizeId('  Daily Joke Schedule  '),
          equals('daily_joke_schedule'),
        );
        expect(
          JokeSchedule.sanitizeId('Holiday-Special@2024!'),
          equals('holiday_special_2024'),
        );
        expect(JokeSchedule.sanitizeId('___test123___'), equals('test123'));
      });

      test('handles edge cases', () {
        expect(JokeSchedule.sanitizeId(''), equals(''));
        expect(JokeSchedule.sanitizeId('___'), equals(''));
        expect(JokeSchedule.sanitizeId('a'), equals('a'));
        expect(JokeSchedule.sanitizeId('123'), equals('123'));
      });
    });

    group('serialization', () {
      const testSchedule = JokeSchedule(
        id: 'test_schedule',
        name: 'Test Schedule',
      );

      test('toMap converts to correct format', () {
        final map = testSchedule.toMap();

        expect(map, {'name': 'Test Schedule'});
      });

      test('fromMap creates correct instance', () {
        final map = {'name': 'Test Schedule'};
        final schedule = JokeSchedule.fromMap(map, 'test_schedule');

        expect(schedule.id, equals('test_schedule'));
        expect(schedule.name, equals('Test Schedule'));
      });

      test('fromMap handles missing name', () {
        final map = <String, dynamic>{};
        final schedule = JokeSchedule.fromMap(map, 'test_id');

        expect(schedule.id, equals('test_id'));
        expect(schedule.name, equals(''));
      });
    });

    group('equality and hashing', () {
      test('equal schedules are equal', () {
        const schedule1 = JokeSchedule(id: 'test', name: 'Test');
        const schedule2 = JokeSchedule(id: 'test', name: 'Test');

        expect(schedule1, equals(schedule2));
        expect(schedule1.hashCode, equals(schedule2.hashCode));
      });

      test('different schedules are not equal', () {
        const schedule1 = JokeSchedule(id: 'test1', name: 'Test 1');
        const schedule2 = JokeSchedule(id: 'test2', name: 'Test 2');

        expect(schedule1, isNot(equals(schedule2)));
      });
    });

    group('copyWith', () {
      const originalSchedule = JokeSchedule(
        id: 'original_id',
        name: 'Original Name',
      );

      test('copies with new values', () {
        final copied = originalSchedule.copyWith(
          id: 'new_id',
          name: 'New Name',
        );

        expect(copied.id, equals('new_id'));
        expect(copied.name, equals('New Name'));
      });

      test('preserves original values when not specified', () {
        final copied = originalSchedule.copyWith(name: 'New Name');

        expect(copied.id, equals('original_id'));
        expect(copied.name, equals('New Name'));
      });
    });
  });
}
