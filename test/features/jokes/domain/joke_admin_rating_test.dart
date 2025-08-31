import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';

void main() {
  group('JokeAdminRating Tests', () {
    test('should have correct enum values', () {
      expect(JokeAdminRating.unreviewed.value, equals('UNREVIEWED'));
      expect(JokeAdminRating.approved.value, equals('APPROVED'));
      expect(JokeAdminRating.rejected.value, equals('REJECTED'));
    });

    test('should parse string values correctly', () {
      expect(
        JokeAdminRating.fromString('APPROVED'),
        equals(JokeAdminRating.approved),
      );
      expect(
        JokeAdminRating.fromString('REJECTED'),
        equals(JokeAdminRating.rejected),
      );
      expect(
        JokeAdminRating.fromString('UNREVIEWED'),
        equals(JokeAdminRating.unreviewed),
      );
      expect(JokeAdminRating.fromString('INVALID'), isNull);
      expect(JokeAdminRating.fromString(null), isNull);
    });

    test('should handle all enum values', () {
      expect(JokeAdminRating.values.length, equals(3));
      expect(JokeAdminRating.values.contains(JokeAdminRating.approved), isTrue);
      expect(JokeAdminRating.values.contains(JokeAdminRating.rejected), isTrue);
      expect(
        JokeAdminRating.values.contains(JokeAdminRating.unreviewed),
        isTrue,
      );
    });

    test('should handle edge cases in fromString', () {
      expect(JokeAdminRating.fromString(''), isNull);
      expect(JokeAdminRating.fromString('approved'), isNull); // case sensitive
      expect(JokeAdminRating.fromString('REJECTED '), isNull); // with spaces
    });
  });
}
