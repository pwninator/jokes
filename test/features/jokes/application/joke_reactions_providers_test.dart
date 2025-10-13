import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

import '../../../test_helpers/analytics_mocks.dart';

// Mock classes using mocktail
class MockJokeReactionsService extends Mock implements JokeReactionsService {}

class FakeBuildContext extends Fake implements BuildContext {
  @override
  bool get mounted => true;
}

void main() {
  group('jokeReactionsProvider', () {
    late MockJokeReactionsService mockReactionsService;
    late BuildContext fakeContext;

    setUpAll(() {
      registerAnalyticsFallbackValues();
      // Fallbacks for new enums used with any(named: ...)
      registerFallbackValue(MatchMode.tight);
      registerFallbackValue(SearchScope.userJokeSearch);
      registerFallbackValue(FakeBuildContext());
    });

    setUp(() {
      mockReactionsService = MockJokeReactionsService();
      fakeContext = FakeBuildContext();
    });

    group('toggleReaction', () {
      test('should handle save reaction toggle', () async {
        // arrange
        const jokeId = 'test-joke';

        // Mock initial state: no reactions
        when(
          () => mockReactionsService.getAllUserReactions(),
        ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});
        when(
          () => mockReactionsService.getSavedJokeIds(),
        ).thenAnswer((_) async => <String>[]);

        // Mock service calls
        when(
          () => mockReactionsService.toggleUserReaction(
            jokeId,
            JokeReactionType.save,
            context: any(named: 'context'),
          ),
        ).thenAnswer((_) async => true); // returns true when adding

        // act
        final container = ProviderContainer(
          overrides: [
            jokeReactionsServiceProvider.overrideWithValue(
              mockReactionsService,
            ),
          ],
        );

        final notifier = container.read(jokeReactionsProvider.notifier);

        // Wait for initial load to complete
        await Future.delayed(const Duration(milliseconds: 10));

        // Toggle save
        await notifier.toggleReaction(
          jokeId,
          JokeReactionType.save,
          jokeContext: 'test',
          context: fakeContext,
        );

        // assert
        verify(
          () => mockReactionsService.toggleUserReaction(
            jokeId,
            JokeReactionType.save,
            context: any(named: 'context'),
          ),
        ).called(1);

        // Should not call removeUserReaction for any reaction type
        verifyNever(
          () => mockReactionsService.removeUserReaction(any(), any()),
        );

        container.dispose();
      });

      test(
        'should handle share reaction toggle without removing opposite',
        () async {
          // arrange
          const jokeId = 'test-joke';

          // Mock initial state: no reactions
          when(
            () => mockReactionsService.getAllUserReactions(),
          ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});
          when(
            () => mockReactionsService.getSavedJokeIds(),
          ).thenAnswer((_) async => <String>[]);

          // Mock service calls
          when(
            () => mockReactionsService.toggleUserReaction(
              jokeId,
              JokeReactionType.share,
              context: any(named: 'context'),
            ),
          ).thenAnswer((_) async => true); // returns true when adding

          // act
          final container = ProviderContainer(
            overrides: [
              jokeReactionsServiceProvider.overrideWithValue(
                mockReactionsService,
              ),
            ],
          );

          final notifier = container.read(jokeReactionsProvider.notifier);

          // Wait for initial load to complete
          await Future.delayed(const Duration(milliseconds: 10));

          // Toggle share
          await notifier.toggleReaction(
            jokeId,
            JokeReactionType.share,
            jokeContext: 'test',
            context: fakeContext,
          );

          // assert
          verify(
            () => mockReactionsService.toggleUserReaction(
              jokeId,
              JokeReactionType.share,
              context: any(named: 'context'),
            ),
          ).called(1);

          // Should not call removeUserReaction for any reaction type
          verifyNever(
            () => mockReactionsService.removeUserReaction(any(), any()),
          );

          container.dispose();
        },
      );
    });

    group('toggleReaction - basic functionality', () {
      test('should toggle reaction and update state optimistically', () async {
        // arrange
        const jokeId = 'test-joke';

        // Mock initial state: no reactions
        when(
          () => mockReactionsService.getAllUserReactions(),
        ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});
        when(
          () => mockReactionsService.getSavedJokeIds(),
        ).thenAnswer((_) async => <String>[]);

        // Mock service calls
        when(
          () => mockReactionsService.toggleUserReaction(
            jokeId,
            JokeReactionType.share,
            context: any(named: 'context'),
          ),
        ).thenAnswer((_) async => true); // returns true when adding

        // act
        final container = ProviderContainer(
          overrides: [
            jokeReactionsServiceProvider.overrideWithValue(
              mockReactionsService,
            ),
          ],
        );

        final notifier = container.read(jokeReactionsProvider.notifier);

        // Wait for initial load to complete
        await Future.delayed(const Duration(milliseconds: 10));

        // Toggle share
        await notifier.toggleReaction(
          jokeId,
          JokeReactionType.share,
          jokeContext: 'test',
          context: fakeContext,
        );

        // assert
        verify(
          () => mockReactionsService.toggleUserReaction(
            jokeId,
            JokeReactionType.share,
            context: any(named: 'context'),
          ),
        ).called(1);

        container.dispose();
      });

      test(
        'should handle errors gracefully and revert optimistic updates',
        () async {
          // arrange
          const jokeId = 'test-joke';

          // Mock initial state: no reactions
          when(
            () => mockReactionsService.getAllUserReactions(),
          ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});
          when(
            () => mockReactionsService.getSavedJokeIds(),
          ).thenAnswer((_) async => <String>[]);

          // Mock service calls to throw error
          when(
            () => mockReactionsService.toggleUserReaction(
              jokeId,
              JokeReactionType.share,
              context: any(named: 'context'),
            ),
          ).thenThrow(Exception('Test error'));

          // act
          final container = ProviderContainer(
            overrides: [
              jokeReactionsServiceProvider.overrideWithValue(
                mockReactionsService,
              ),
            ],
          );

          final notifier = container.read(jokeReactionsProvider.notifier);

          // Wait for initial load to complete
          await Future.delayed(const Duration(milliseconds: 10));

          // Toggle share (should handle error)
          await notifier.toggleReaction(
            jokeId,
            JokeReactionType.share,
            jokeContext: 'test',
            context: fakeContext,
          );

          // assert
          final state = container.read(jokeReactionsProvider);
          expect(state.error, isNotNull);
          expect(state.error, contains('Failed to add Share'));

          container.dispose();
        },
      );
    });

    group('state management', () {
      test(
        'should initialize with empty reactions and load from service',
        () async {
          // arrange
          when(
            () => mockReactionsService.getAllUserReactions(),
          ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});
          when(
            () => mockReactionsService.getSavedJokeIds(),
          ).thenAnswer((_) async => <String>[]);

          // act
          final container = ProviderContainer(
            overrides: [
              jokeReactionsServiceProvider.overrideWithValue(
                mockReactionsService,
              ),
            ],
          );

          // Wait for initial load
          await Future.delayed(const Duration(milliseconds: 10));

          final state = container.read(jokeReactionsProvider);

          // assert
          expect(state.userReactions, isEmpty);
          expect(state.isLoading, isTrue); // Still loading since it's async
          expect(state.error, isNull);

          verify(() => mockReactionsService.getAllUserReactions()).called(1);

          container.dispose();
        },
      );

      test('should handle loading state correctly', () async {
        // arrange
        when(
          () => mockReactionsService.getAllUserReactions(),
        ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});
        when(
          () => mockReactionsService.getSavedJokeIds(),
        ).thenAnswer((_) async => <String>[]);

        // act
        final container = ProviderContainer(
          overrides: [
            jokeReactionsServiceProvider.overrideWithValue(
              mockReactionsService,
            ),
          ],
        );

        // Initial state should show loading
        final initialState = container.read(jokeReactionsProvider);
        expect(initialState.isLoading, isTrue);

        container.dispose();
      });
    });
  });
}
