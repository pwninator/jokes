import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

class MockJokeReactionsService extends Mock implements JokeReactionsService {}

class MockBuildContext extends Mock implements BuildContext {
  @override
  bool get mounted => true;
}

void main() {
  group('JokeReactionsProvider', () {
    late MockJokeReactionsService mockService;
    late ProviderContainer container;

    setUpAll(() {
      registerFallbackValue(JokeReactionType.save);
      registerFallbackValue(MockBuildContext());
    });

    setUp(() {
      mockService = MockJokeReactionsService();
      // Set up default mock behavior before creating container
      when(
        () => mockService.getAllUserReactions(),
      ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});

      container = ProviderContainer(
        overrides: [
          jokeReactionsServiceProvider.overrideWithValue(mockService),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    test('initializes and loads user reactions', () async {
      // Check initial state (should be loading)
      final initialState = container.read(jokeReactionsProvider);
      expect(initialState.isLoading, isTrue);

      // Wait for loading to complete
      await Future.delayed(const Duration(milliseconds: 100));

      // Check final state (should be loaded)
      final finalState = container.read(jokeReactionsProvider);
      expect(finalState.isLoading, isFalse);
      expect(finalState.userReactions, isEmpty);
      expect(finalState.error, isNull);
    });

    test('loads user reactions successfully', () async {
      // Arrange
      final expectedReactions = {
        'joke1': {JokeReactionType.save},
        'joke2': {JokeReactionType.share, JokeReactionType.save},
      };
      when(
        () => mockService.getAllUserReactions(),
      ).thenAnswer((_) async => expectedReactions);

      // Act - wait for the notifier to load
      await container
          .read(jokeReactionsProvider.notifier)
          .refreshUserReactions();

      // Assert
      final state = container.read(jokeReactionsProvider);
      expect(state.isLoading, isFalse);
      expect(state.userReactions, equals(expectedReactions));
      expect(state.error, isNull);
    });

    test('handles loading errors gracefully', () async {
      // Arrange
      when(
        () => mockService.getAllUserReactions(),
      ).thenThrow(Exception('Database error'));

      // Act
      await container
          .read(jokeReactionsProvider.notifier)
          .refreshUserReactions();

      // Assert
      final state = container.read(jokeReactionsProvider);
      expect(state.isLoading, isFalse);
      expect(state.error, contains('Failed to load user reactions'));
      expect(state.userReactions, isEmpty);
    });
  });
}
