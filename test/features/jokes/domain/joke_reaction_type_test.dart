import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

void main() {
  group('JokeReactionType', () {
    test('should have correct values and properties', () {
      // Test all enum values exist
      expect(JokeReactionType.values.length, equals(2));
      expect(JokeReactionType.values, contains(JokeReactionType.save));
      expect(JokeReactionType.values, contains(JokeReactionType.share));
    });

    group('firestoreField', () {
      test('should return correct Firestore field names', () {
        expect(JokeReactionType.save.firestoreField, equals('num_saves'));
        expect(JokeReactionType.share.firestoreField, equals('num_shares'));
      });
    });

    group('prefsKey', () {
      test('should return correct SharedPreferences keys', () {
        expect(JokeReactionType.save.prefsKey, equals('user_reactions_save'));
        expect(JokeReactionType.share.prefsKey, equals('user_reactions_share'));
      });

      test('should have unique keys for each reaction type', () {
        final keys = JokeReactionType.values.map((e) => e.prefsKey).toSet();
        expect(keys.length, equals(JokeReactionType.values.length));
      });
    });

    group('label', () {
      test('should return correct human-readable labels', () {
        expect(JokeReactionType.save.label, equals('Save'));
        expect(JokeReactionType.share.label, equals('Share'));
      });

      test('should have non-empty labels for all reaction types', () {
        for (final reactionType in JokeReactionType.values) {
          expect(reactionType.label, isNotEmpty);
          expect(reactionType.label, isA<String>());
        }
      });
    });

    group('enum properties consistency', () {
      test(
        'should have all required properties defined for each reaction type',
        () {
          for (final reactionType in JokeReactionType.values) {
            // Verify all properties are accessible and non-null
            expect(reactionType.firestoreField, isNotNull);
            expect(reactionType.firestoreField, isNotEmpty);

            expect(reactionType.activeIcon, isNotNull);
            expect(reactionType.inactiveIcon, isNotNull);
            expect(reactionType.activeColor, isNotNull);

            expect(reactionType.prefsKey, isNotNull);
            expect(reactionType.prefsKey, isNotEmpty);

            expect(reactionType.label, isNotNull);
            expect(reactionType.label, isNotEmpty);
          }
        },
      );

      test('should have unique Firestore field names', () {
        final fields = JokeReactionType.values
            .map((e) => e.firestoreField)
            .toSet();
        expect(fields.length, equals(JokeReactionType.values.length));
      });

      test('should have different active and inactive icons for each type', () {
        for (final reactionType in JokeReactionType.values) {
          expect(
            reactionType.activeIcon,
            isNot(equals(reactionType.inactiveIcon)),
          );
        }
      });
    });
  });
}
