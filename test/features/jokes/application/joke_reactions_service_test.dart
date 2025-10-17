import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_service.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/category_interactions_repository.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

class MockReviewPromptCoordinator extends Mock
    implements ReviewPromptCoordinator {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class _MockCategoryInteractionsService extends Mock
    implements CategoryInteractionsRepository {}

class MockJokeInteractionsService extends Mock
    implements JokeInteractionsRepository {}

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
    late MockJokeRepository mockRepository;
    late AppUsageService appUsageService;
    late MockReviewPromptCoordinator mockCoordinator;
    late BuildContext fakeContext;
    late MockJokeInteractionsService mockInteractions;
    late List<String> savedOrder;
    late Set<String> savedSet;
    late Set<String> sharedSet;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final container = ProviderContainer();
      final ref = container.read(Provider<Ref>((ref) => ref));
      final mockAnalytics = MockAnalyticsService();
      final mockJokeCloudFn = MockJokeCloudFunctionService();
      mockInteractions = MockJokeInteractionsService();
      appUsageService = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mockAnalytics,
        jokeCloudFn: mockJokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mockInteractions,
      );
      mockCoordinator = MockReviewPromptCoordinator();
      mockRepository = MockJokeRepository();

      // In-memory state backing the mock interactions
      savedOrder = <String>[];
      savedSet = <String>{};
      sharedSet = <String>{};

      // Reads now use DB interactions API
      when(() => mockInteractions.getJokeInteraction(any())).thenAnswer((
        inv,
      ) async {
        final id = inv.positionalArguments[0] as String;
        if (!savedSet.contains(id) && !sharedSet.contains(id)) return null;
        final now = DateTime.now();
        return JokeInteraction(
          jokeId: id,
          viewedTimestamp: null,
          savedTimestamp: savedSet.contains(id) ? now : null,
          sharedTimestamp: sharedSet.contains(id) ? now : null,
          lastUpdateTimestamp: now,
        );
      });
      when(() => mockInteractions.getAllJokeInteractions()).thenAnswer((
        _,
      ) async {
        final now = DateTime.now();
        final ids = {...savedSet, ...sharedSet};
        return ids
            .map(
              (id) => JokeInteraction(
                jokeId: id,
                viewedTimestamp: null,
                savedTimestamp: savedSet.contains(id) ? now : null,
                sharedTimestamp: sharedSet.contains(id) ? now : null,
                lastUpdateTimestamp: now,
              ),
            )
            .toList();
      });
      when(() => mockInteractions.getSavedJokeInteractions()).thenAnswer((
        _,
      ) async {
        final now = DateTime.now();
        return savedOrder
            .map(
              (id) => JokeInteraction(
                jokeId: id,
                viewedTimestamp: null,
                savedTimestamp: now,
                sharedTimestamp: sharedSet.contains(id) ? now : null,
                lastUpdateTimestamp: now,
              ),
            )
            .toList();
      });

      // New COUNT APIs used by AppUsageService
      when(() => mockInteractions.countSaved())
          .thenAnswer((_) async => savedSet.length);
      when(() => mockInteractions.countShared())
          .thenAnswer((_) async => sharedSet.length);

      // Writes
      when(() => mockInteractions.setSaved(any())).thenAnswer((inv) async {
        final id = inv.positionalArguments[0] as String;
        if (!savedSet.contains(id)) {
          savedSet.add(id);
          savedOrder.add(id);
        }
        return true;
      });
      when(() => mockInteractions.setUnsaved(any())).thenAnswer((inv) async {
        final id = inv.positionalArguments[0] as String;
        savedSet.remove(id);
        savedOrder.removeWhere((e) => e == id);
        return true;
      });
      when(() => mockInteractions.setShared(any())).thenAnswer((inv) async {
        final id = inv.positionalArguments[0] as String;
        sharedSet.add(id);
        return true;
      });
      when(
        () => mockCoordinator.maybePromptForReview(
          source: any(named: 'source'),
          context: any(named: 'context'),
        ),
      ).thenAnswer((_) async {});
      // Default stub for repository - returns completed future
      when(
        () => mockRepository.updateReactionAndPopularity(any(), any(), any()),
      ).thenAnswer((_) async {});
      service = JokeReactionsService(
        appUsageService: appUsageService,
        reviewPromptCoordinator: mockCoordinator,
        interactionsRepository: mockInteractions,
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
        savedSet.clear();
        sharedSet.clear();

        // Act
        final result = await service.getAllUserReactions();

        // Assert
        expect(result, isEmpty);
      });

      test('returns all user reactions grouped by joke ID', () async {
        // Arrange
        savedSet
          ..clear()
          ..addAll(['joke1', 'joke2']);
        sharedSet
          ..clear()
          ..addAll(['joke1', 'joke3']);

        // Act
        final result = await service.getAllUserReactions();

        // Assert
        expect(result, {
          'joke1': {JokeReactionType.save, JokeReactionType.share},
          'joke2': {JokeReactionType.save},
          'joke3': {JokeReactionType.share},
        });
      });
    });

    group('getSavedJokeIds', () {
      test('returns empty list when no saved jokes exist', () async {
        // Arrange
        savedOrder.clear();

        // Act
        final result = await service.getSavedJokeIds();

        // Assert
        expect(result, isEmpty);
      });

      test('returns saved joke IDs in order they were saved', () async {
        // Arrange
        savedOrder
          ..clear()
          ..addAll(['joke1', 'joke3', 'joke2']);
        savedSet
          ..clear()
          ..addAll(savedOrder);

        // Act
        final result = await service.getSavedJokeIds();

        // Assert
        expect(result, equals(['joke1', 'joke3', 'joke2']));
      });
    });

    group('getUserReactionsForJoke', () {
      test('returns empty set when joke has no reactions', () async {
        // Arrange
        savedSet.clear();
        sharedSet.clear();

        // Act
        final result = await service.getUserReactionsForJoke('joke1');

        // Assert
        expect(result, isEmpty);
      });

      test('returns correct reactions for specific joke', () async {
        // Arrange
        savedSet
          ..clear()
          ..addAll(['joke1', 'joke2']);
        sharedSet
          ..clear()
          ..addAll(['joke1', 'joke3']);

        // Act
        final result = await service.getUserReactionsForJoke('joke1');

        // Assert
        expect(result, equals({JokeReactionType.save, JokeReactionType.share}));
      });
    });

    group('hasUserReaction', () {
      test('returns false when reaction does not exist', () async {
        // Arrange
        savedSet.clear();
        sharedSet.clear();

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
        savedSet
          ..clear()
          ..add('joke1');

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
        savedSet
          ..clear()
          ..add('joke1');

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
        savedSet.clear();

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
        savedSet
          ..clear()
          ..add('joke1');

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
        savedSet
          ..clear()
          ..add('joke1');

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
        savedSet
          ..clear()
          ..addAll(['joke1', 'joke2']);
        savedOrder
          ..clear()
          ..addAll(['joke1', 'joke2']);

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
        savedSet
          ..clear()
          ..add('joke2');
        savedOrder
          ..clear()
          ..add('joke2');

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
        savedSet.clear();
        savedOrder.clear();

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
        savedSet.clear();

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
        savedSet
          ..clear()
          ..add('joke1');

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
        savedSet.clear();

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
      test(
        'share add does not change num_saved_jokes and removing share throws',
        () async {
          // Arrange
          savedSet.clear();
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

          // Act & Assert - removing share should throw
          expect(
            () => service.toggleUserReaction(
              'j2',
              JokeReactionType.share,
              context: fakeContext,
            ),
            throwsA(isA<ArgumentError>()),
          );
          expect(await appUsageService.getNumSavedJokes(), 0);
        },
      );
    });

    group('async Firestore operations', () {
      setUp(() {
        // Ensure repository has a default fast behavior; individual tests override
        when(
          () => mockRepository.updateReactionAndPopularity(any(), any(), any()),
        ).thenAnswer((_) async {});
      });

      test(
        'addUserReaction completes immediately even with slow Firestore',
        () async {
          // Arrange
          savedSet.clear();

          // Mock a slow Firestore operation that takes 1 second
          when(
            () =>
                mockRepository.updateReactionAndPopularity(any(), any(), any()),
          ).thenAnswer((_) async {
            await Future.delayed(const Duration(seconds: 1));
          });

          // Act & Assert - The method should complete immediately
          final stopwatch = Stopwatch()..start();
          await service.addUserReaction(
            'joke1',
            JokeReactionType.share,
            context: fakeContext,
          );
          stopwatch.stop();

          // Should complete in much less than 1 second (local DB is fast)
          expect(stopwatch.elapsedMilliseconds, lessThan(100));

          // Verify local state was updated immediately
          final hasReaction = await service.hasUserReaction(
            'joke1',
            JokeReactionType.share,
          );
          expect(hasReaction, isTrue);

          // Verify Firestore was called
          verify(
            () => mockRepository.updateReactionAndPopularity(
              'joke1',
              JokeReactionType.share,
              1,
            ),
          ).called(1);
        },
      );

      test(
        'removeUserReaction throws for share and does not call Firestore',
        () async {
          // Arrange
          savedSet.clear();
          sharedSet
            ..clear()
            ..add('joke1');

          // Act & Assert
          expect(
            () => service.removeUserReaction('joke1', JokeReactionType.share),
            throwsA(isA<ArgumentError>()),
          );

          // Verify Firestore was NOT called
          verifyNever(
            () =>
                mockRepository.updateReactionAndPopularity(any(), any(), any()),
          );
        },
      );

      test('Firestore failures do not affect local reaction state', () async {
        // Arrange
        // Mock Firestore to throw an error asynchronously
        when(
          () => mockRepository.updateReactionAndPopularity(any(), any(), any()),
        ).thenAnswer((_) async {
          throw Exception('Firestore error');
        });

        // Act
        await service.addUserReaction(
          'joke1',
          JokeReactionType.share,
          context: fakeContext,
        );

        // Assert - SharedPreferences should still be updated despite Firestore error
        final hasReaction = await service.hasUserReaction(
          'joke1',
          JokeReactionType.share,
        );
        expect(hasReaction, isTrue);

        // Verify Firestore was called
        verify(
          () => mockRepository.updateReactionAndPopularity(
            'joke1',
            JokeReactionType.share,
            1,
          ),
        ).called(1);
      });

      test('save add/remove call repository with correct increments', () async {
        // Arrange
        savedSet.clear();
        when(
          () => mockRepository.updateReactionAndPopularity(any(), any(), any()),
        ).thenAnswer((_) async {});

        // Act - add save
        await service.addUserReaction(
          'jA',
          JokeReactionType.save,
          context: fakeContext,
        );
        // Act - remove save
        await service.removeUserReaction('jA', JokeReactionType.save);

        // Assert repository calls
        verify(
          () => mockRepository.updateReactionAndPopularity(
            'jA',
            JokeReactionType.save,
            1,
          ),
        ).called(1);
        verify(
          () => mockRepository.updateReactionAndPopularity(
            'jA',
            JokeReactionType.save,
            -1,
          ),
        ).called(1);
      });
    });
  });
}
