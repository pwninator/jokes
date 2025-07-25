import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

void main() {
  group('JokeReactionsService', () {
    late JokeReactionsService service;

    setUp(() {
      service = JokeReactionsService();
    });

    tearDown(() async {
      // Clear SharedPreferences after each test
      final prefs = await SharedPreferences.getInstance();
      await prefs.clear();
    });

    group('getAllUserReactions', () {
      test('returns empty map when no reactions exist', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({});

        // Act
        final result = await service.getAllUserReactions();

        // Assert
        expect(result, isEmpty);
      });

      test('returns all user reactions grouped by joke ID', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({
          'user_reactions_save': ['joke1', 'joke2'],
          'user_reactions_share': ['joke1'],
          'user_reactions_thumbsUp': ['joke3'],
        });

        // Act
        final result = await service.getAllUserReactions();

        // Assert
        expect(result, {
          'joke1': {JokeReactionType.save, JokeReactionType.share},
          'joke2': {JokeReactionType.save},
          'joke3': {JokeReactionType.thumbsUp},
        });
      });
    });

    group('getSavedJokeIds', () {
      test('returns empty list when no saved jokes exist', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({});

        // Act
        final result = await service.getSavedJokeIds();

        // Assert
        expect(result, isEmpty);
      });

      test('returns saved joke IDs in order they were saved', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({
          'user_reactions_save': ['joke1', 'joke3', 'joke2'],
        });

        // Act
        final result = await service.getSavedJokeIds();

        // Assert
        expect(result, equals(['joke1', 'joke3', 'joke2']));
      });
    });

    group('getUserReactionsForJoke', () {
      test('returns empty set when joke has no reactions', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({});

        // Act
        final result = await service.getUserReactionsForJoke('joke1');

        // Assert
        expect(result, isEmpty);
      });

      test('returns correct reactions for specific joke', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({
          'user_reactions_save': ['joke1', 'joke2'],
          'user_reactions_share': ['joke1'],
          'user_reactions_thumbsUp': ['joke2', 'joke3'],
        });

        // Act
        final result = await service.getUserReactionsForJoke('joke1');

        // Assert
        expect(result, equals({JokeReactionType.save, JokeReactionType.share}));
      });
    });

    group('hasUserReaction', () {
      test('returns false when reaction does not exist', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({});

        // Act
        final result = await service.hasUserReaction(
          'joke1',
          JokeReactionType.save,
        );

        // Assert
        expect(result, isFalse);
      });

      test('returns true when reaction exists', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({
          'user_reactions_save': ['joke1'],
        });

        // Act
        final result = await service.hasUserReaction(
          'joke1',
          JokeReactionType.save,
        );

        // Assert
        expect(result, isTrue);
      });

      test('returns false for different reaction type', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({
          'user_reactions_save': ['joke1'],
        });

        // Act
        final result = await service.hasUserReaction(
          'joke1',
          JokeReactionType.share,
        );

        // Assert
        expect(result, isFalse);
      });
    });

    group('addUserReaction', () {
      test('adds reaction to empty list', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({});

        // Act
        await service.addUserReaction('joke1', JokeReactionType.save);

        // Assert
        final result = await service.hasUserReaction(
          'joke1',
          JokeReactionType.save,
        );
        expect(result, isTrue);
      });

      test('adds reaction to existing list', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({
          'user_reactions_save': ['joke1'],
        });

        // Act
        await service.addUserReaction('joke2', JokeReactionType.save);

        // Assert
        final result1 = await service.hasUserReaction(
          'joke1',
          JokeReactionType.save,
        );
        final result2 = await service.hasUserReaction(
          'joke2',
          JokeReactionType.save,
        );
        expect(result1, isTrue);
        expect(result2, isTrue);
      });

      test('does not add duplicate reaction', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({
          'user_reactions_save': ['joke1'],
        });

        // Act
        await service.addUserReaction('joke1', JokeReactionType.save);

        // Assert
        final reactions = await service.getUserReactionsForJoke('joke1');
        expect(reactions, equals({JokeReactionType.save}));
      });
    });

    group('removeUserReaction', () {
      test('removes reaction from list', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({
          'user_reactions_save': ['joke1', 'joke2'],
        });

        // Act
        await service.removeUserReaction('joke1', JokeReactionType.save);

        // Assert
        final result1 = await service.hasUserReaction(
          'joke1',
          JokeReactionType.save,
        );
        final result2 = await service.hasUserReaction(
          'joke2',
          JokeReactionType.save,
        );
        expect(result1, isFalse);
        expect(result2, isTrue);
      });

      test('handles removing non-existent reaction gracefully', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({
          'user_reactions_save': ['joke2'],
        });

        // Act
        await service.removeUserReaction('joke1', JokeReactionType.save);

        // Assert
        final result = await service.hasUserReaction(
          'joke2',
          JokeReactionType.save,
        );
        expect(result, isTrue);
      });

      test('handles removing from empty list gracefully', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({});

        // Act
        await service.removeUserReaction('joke1', JokeReactionType.save);

        // Assert
        final result = await service.hasUserReaction(
          'joke1',
          JokeReactionType.save,
        );
        expect(result, isFalse);
      });
    });

    group('toggleUserReaction', () {
      test('adds reaction when not present and returns true', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({});

        // Act
        final wasAdded = await service.toggleUserReaction(
          'joke1',
          JokeReactionType.save,
        );

        // Assert
        expect(wasAdded, isTrue);
        final hasReaction = await service.hasUserReaction(
          'joke1',
          JokeReactionType.save,
        );
        expect(hasReaction, isTrue);
      });

      test('removes reaction when present and returns false', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({
          'user_reactions_save': ['joke1'],
        });

        // Act
        final wasAdded = await service.toggleUserReaction(
          'joke1',
          JokeReactionType.save,
        );

        // Assert
        expect(wasAdded, isFalse);
        final hasReaction = await service.hasUserReaction(
          'joke1',
          JokeReactionType.save,
        );
        expect(hasReaction, isFalse);
      });

      test('supports multiple toggles correctly', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({});

        // Act & Assert - First toggle (add)
        final result1 = await service.toggleUserReaction(
          'joke1',
          JokeReactionType.save,
        );
        expect(result1, isTrue);
        expect(
          await service.hasUserReaction('joke1', JokeReactionType.save),
          isTrue,
        );

        // Act & Assert - Second toggle (remove)
        final result2 = await service.toggleUserReaction(
          'joke1',
          JokeReactionType.save,
        );
        expect(result2, isFalse);
        expect(
          await service.hasUserReaction('joke1', JokeReactionType.save),
          isFalse,
        );

        // Act & Assert - Third toggle (add again)
        final result3 = await service.toggleUserReaction(
          'joke1',
          JokeReactionType.save,
        );
        expect(result3, isTrue);
        expect(
          await service.hasUserReaction('joke1', JokeReactionType.save),
          isTrue,
        );
      });
    });
  });
}
