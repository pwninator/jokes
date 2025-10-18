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
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

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
    registerFallbackValue(ReviewRequestSource.jokeViewed);
  });

  group('JokeReactionsService', () {
    late JokeReactionsService service;
    late AppUsageService appUsageService;
    late MockReviewPromptCoordinator mockCoordinator;
    late MockJokeInteractionsService mockInteractions;
    late List<String> savedOrder;
    late Set<String> savedSet;
    late Set<String> sharedSet;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      mockCoordinator = MockReviewPromptCoordinator();
      final container = ProviderContainer(
        overrides: [
          reviewPromptCoordinatorProvider.overrideWithValue(mockCoordinator),
        ],
      );
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
      when(
        () => mockInteractions.countSaved(),
      ).thenAnswer((_) async => savedSet.length);
      when(
        () => mockInteractions.countShared(),
      ).thenAnswer((_) async => sharedSet.length);

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
      service = JokeReactionsService(
        appUsageService: appUsageService,
        interactionsRepository: mockInteractions,
      );
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
  });
}
