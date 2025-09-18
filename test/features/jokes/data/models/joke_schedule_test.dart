import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule.dart';

void main() {
  group('JokeSchedule', () {
    group('sanitizeId', () {
      test('should correctly sanitize various string formats', () {
        final Map<String, String> testCases = {
          // Lowercasing
          'UPPER': 'upper',
          'MixedCase': 'mixedcase',
          // Non-alphanumeric replacement
          'hello world': 'hello_world',
          'test@email.com': 'test_email_com',
          'special!chars#': 'special_chars',
          // Leading/trailing underscore removal
          '_leading': 'leading',
          'trailing_': 'trailing',
          '_both_': 'both',
          // Consecutive underscore deduplication
          'multiple   spaces': 'multiple_spaces',
          'many____underscores': 'many_underscores',
          '__double__leading__': 'double_leading',
          // Complex cases
          '  Daily Joke Schedule  ': 'daily_joke_schedule',
          'Holiday-Special@2024!': 'holiday_special_2024',
          '___test123___': 'test123',
          // Edge cases
          '': '',
          '___': '',
          'a': 'a',
          '123': '123',
        };

        for (final entry in testCases.entries) {
          expect(
            JokeSchedule.sanitizeId(entry.key),
            equals(entry.value),
            reason: 'Failed for input: "${entry.key}"',
          );
        }
      });
    });

    group('Model methods', () {
      const tSchedule = JokeSchedule(id: 'test_id', name: 'Test Name');

      test('should perform a serialization round trip correctly', () {
        // Arrange
        final map = tSchedule.toMap();

        // Act
        final fromMap = JokeSchedule.fromMap(map, tSchedule.id);

        // Assert
        expect(fromMap, tSchedule);
      });

      test('fromMap should handle missing name gracefully', () {
        // Arrange
        final map = <String, dynamic>{};

        // Act
        final fromMap = JokeSchedule.fromMap(map, 'test_id');

        // Assert
        expect(fromMap.name, '');
      });

      test('copyWith should create a copy with updated values', () {
        // Act
        final copied = tSchedule.copyWith(id: 'new_id', name: 'New Name');

        // Assert
        expect(copied.id, 'new_id');
        expect(copied.name, 'New Name');
      });

      test('copyWith should preserve values if not provided', () {
        // Act
        final copied = tSchedule.copyWith(name: 'New Name');

        // Assert
        expect(copied.id, tSchedule.id); // Preserved
        expect(copied.name, 'New Name'); // Updated
      });

      test('equality and hashCode should work correctly', () {
        // Arrange
        const sameSchedule = JokeSchedule(id: 'test_id', name: 'Test Name');
        const differentSchedule = JokeSchedule(id: 'diff_id', name: 'Diff Name');

        // Assert
        expect(tSchedule, sameSchedule);
        expect(tSchedule.hashCode, sameSchedule.hashCode);
        expect(tSchedule, isNot(differentSchedule));
        expect(tSchedule.hashCode, isNot(differentSchedule.hashCode));
      });

      test('toString should return a non-empty string', () {
        expect(tSchedule.toString(), isNotEmpty);
      });
    });
  });
}
