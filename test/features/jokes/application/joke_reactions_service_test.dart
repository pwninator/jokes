import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

class MockReviewPromptCoordinator extends Mock
    implements ReviewPromptCoordinator {}

class FakeBuildContext extends Fake implements BuildContext {
  @override
  bool get mounted => true;
}

void main() {
  setUpAll(() {
    registerFallbackValue(JokeReactionType.save);
    registerFallbackValue(ReviewRequestSource.jokeViewed);
    registerFallbackValue(FakeBuildContext());
  });

  group('JokeReactionsService', () {
    late JokeReactionsService service;
    late AppUsageService appUsageService;
    late MockReviewPromptCoordinator mockCoordinator;
    late BuildContext fakeContext;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final container = ProviderContainer();
      final ref = container.read(Provider<Ref>((ref) => ref));
      appUsageService = AppUsageService(
        settingsService: settingsService,
        ref: ref,
      );
      mockCoordinator = MockReviewPromptCoordinator();
      when(
        () => mockCoordinator.maybePromptForReview(
          source: any(named: 'source'),
          context: any(named: 'context'),
        ),
      ).thenAnswer((_) async {});
      service = JokeReactionsService(
        appUsageService: appUsageService,
        reviewPromptCoordinator: mockCoordinator,
      );
      fakeContext = FakeBuildContext();
    });

    tearDown(() async {
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
        await service.addUserReaction(
          'joke1',
          JokeReactionType.save,
          context: fakeContext,
        );

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
        await service.addUserReaction(
          'joke2',
          JokeReactionType.save,
          context: fakeContext,
        );

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
        await service.addUserReaction(
          'joke1',
          JokeReactionType.save,
          context: fakeContext,
        );

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
          context: fakeContext,
        );

        // Assert
        expect(wasAdded, isTrue);
        final hasReaction = await service.hasUserReaction(
          'joke1',
          JokeReactionType.save,
        );
        expect(hasReaction, isTrue);
        expect(await appUsageService.getNumSavedJokes(), 1);
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
          context: fakeContext,
        );

        // Assert
        expect(wasAdded, isFalse);
        final hasReaction = await service.hasUserReaction(
          'joke1',
          JokeReactionType.save,
        );
        expect(hasReaction, isFalse);
        expect(await appUsageService.getNumSavedJokes(), 0);
      });

      test('supports multiple toggles correctly', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({});

        // Act & Assert - First toggle (add)
        final result1 = await service.toggleUserReaction(
          'joke1',
          JokeReactionType.save,
          context: fakeContext,
        );
        expect(result1, isTrue);
        expect(
          await service.hasUserReaction('joke1', JokeReactionType.save),
          isTrue,
        );
        expect(await appUsageService.getNumSavedJokes(), 1);

        // Act & Assert - Second toggle (remove)
        final result2 = await service.toggleUserReaction(
          'joke1',
          JokeReactionType.save,
          context: fakeContext,
        );
        expect(result2, isFalse);
        expect(
          await service.hasUserReaction('joke1', JokeReactionType.save),
          isFalse,
        );
        expect(await appUsageService.getNumSavedJokes(), 0);

        // Act & Assert - Third toggle (add again)
        final result3 = await service.toggleUserReaction(
          'joke1',
          JokeReactionType.save,
          context: fakeContext,
        );
        expect(result3, isTrue);
        expect(
          await service.hasUserReaction('joke1', JokeReactionType.save),
          isTrue,
        );
        expect(await appUsageService.getNumSavedJokes(), 1);
      });
    });

    group('non-save reactions do not affect saved counter', () {
      test('thumbsUp add/remove does not change num_saved_jokes', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({});
        expect(await appUsageService.getNumSavedJokes(), 0);

        // Act - add thumbsUp
        await service.addUserReaction(
          'j1',
          JokeReactionType.thumbsUp,
          context: fakeContext,
        );
        // Assert
        expect(await appUsageService.getNumSavedJokes(), 0);

        // Act - remove thumbsUp
        await service.removeUserReaction('j1', JokeReactionType.thumbsUp);
        // Assert
        expect(await appUsageService.getNumSavedJokes(), 0);
      });

      test('share reaction does not change num_saved_jokes', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({});
        expect(await appUsageService.getNumSavedJokes(), 0);

        // Act - toggle share (add)
        final added = await service.toggleUserReaction(
          'j2',
          JokeReactionType.share,
          context: fakeContext,
        );
        expect(added, isTrue);
        // Assert
        expect(await appUsageService.getNumSavedJokes(), 0);

        // Act - toggle share (remove)
        final removed = await service.toggleUserReaction(
          'j2',
          JokeReactionType.share,
          context: fakeContext,
        );
        expect(removed, isFalse);
        // Assert
        expect(await appUsageService.getNumSavedJokes(), 0);
      });
    });

    group('async Firestore operations', () {
      late MockJokeRepository mockRepository;
      late JokeReactionsService serviceWithRepository;

      setUp(() {
        mockRepository = MockJokeRepository();
        serviceWithRepository = JokeReactionsService(
          jokeRepository: mockRepository,
          appUsageService: appUsageService,
          reviewPromptCoordinator: mockCoordinator,
        );
      });

      test(
        'addUserReaction completes immediately even with slow Firestore',
        () async {
          // Arrange
          SharedPreferences.setMockInitialValues({});

          // Mock a slow Firestore operation that takes 1 second
          when(
            () =>
                mockRepository.updateReactionAndPopularity(any(), any(), any()),
          ).thenAnswer((_) async {
            await Future.delayed(const Duration(seconds: 1));
          });

          // Act & Assert - The method should complete immediately
          final stopwatch = Stopwatch()..start();
          await serviceWithRepository.addUserReaction(
            'joke1',
            JokeReactionType.thumbsUp,
            context: fakeContext,
          );
          stopwatch.stop();

          // Should complete in much less than 1 second (SharedPreferences is fast)
          expect(stopwatch.elapsedMilliseconds, lessThan(100));

          // Verify SharedPreferences was updated immediately
          final hasReaction = await serviceWithRepository.hasUserReaction(
            'joke1',
            JokeReactionType.thumbsUp,
          );
          expect(hasReaction, isTrue);

          // Verify Firestore was called
          verify(
            () => mockRepository.updateReactionAndPopularity(
              'joke1',
              JokeReactionType.thumbsUp,
              1,
            ),
          ).called(1);
        },
      );

      test(
        'removeUserReaction completes immediately even with slow Firestore',
        () async {
          // Arrange
          SharedPreferences.setMockInitialValues({
            'user_reactions_thumbsUp': ['joke1'],
          });

          // Mock a slow Firestore operation that takes 1 second
          when(
            () =>
                mockRepository.updateReactionAndPopularity(any(), any(), any()),
          ).thenAnswer((_) async {
            await Future.delayed(const Duration(seconds: 1));
          });

          // Act & Assert - The method should complete immediately
          final stopwatch = Stopwatch()..start();
          await serviceWithRepository.removeUserReaction(
            'joke1',
            JokeReactionType.thumbsUp,
          );
          stopwatch.stop();

          // Should complete in much less than 1 second (SharedPreferences is fast)
          expect(stopwatch.elapsedMilliseconds, lessThan(100));

          // Verify SharedPreferences was updated immediately
          final hasReaction = await serviceWithRepository.hasUserReaction(
            'joke1',
            JokeReactionType.thumbsUp,
          );
          expect(hasReaction, isFalse);

          // Verify Firestore was called
          verify(
            () => mockRepository.updateReactionAndPopularity(
              'joke1',
              JokeReactionType.thumbsUp,
              -1,
            ),
          ).called(1);
        },
      );

      test('Firestore failures do not affect SharedPreferences state', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({});

        // Mock Firestore to throw an error asynchronously
        when(
          () => mockRepository.updateReactionAndPopularity(any(), any(), any()),
        ).thenAnswer((_) async {
          throw Exception('Firestore error');
        });

        // Act
        await serviceWithRepository.addUserReaction(
          'joke1',
          JokeReactionType.thumbsUp,
          context: fakeContext,
        );

        // Assert - SharedPreferences should still be updated despite Firestore error
        final hasReaction = await serviceWithRepository.hasUserReaction(
          'joke1',
          JokeReactionType.thumbsUp,
        );
        expect(hasReaction, isTrue);

        // Verify Firestore was called
        verify(
          () => mockRepository.updateReactionAndPopularity(
            'joke1',
            JokeReactionType.thumbsUp,
            1,
          ),
        ).called(1);
      });

      test('works correctly without repository (null repository)', () async {
        // Arrange
        SharedPreferences.setMockInitialValues({});
        final serviceWithoutRepository = JokeReactionsService(
          jokeRepository: null,
          appUsageService: appUsageService,
          reviewPromptCoordinator: mockCoordinator,
        );

        // Act
        await serviceWithoutRepository.addUserReaction(
          'joke1',
          JokeReactionType.thumbsUp,
          context: fakeContext,
        );

        // Assert - Should still work with SharedPreferences
        final hasReaction = await serviceWithoutRepository.hasUserReaction(
          'joke1',
          JokeReactionType.thumbsUp,
        );
        expect(hasReaction, isTrue);
      });
    });
  });
}
