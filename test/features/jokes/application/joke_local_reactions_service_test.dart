import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_local_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

void main() {
  group('JokeLocalReactionsService Tests', () {
    late JokeLocalReactionsService service;
    late MockJokeRepository mockRepository;
    late MockAnalyticsService mockAnalyticsService;

    setUp(() {
      mockRepository = MockJokeRepository();
      mockAnalyticsService = MockAnalyticsService();

      // Register fallbacks for mocktail
      registerFallbackValue(JokeReactionType.save);

      service = JokeLocalReactionsService(
        jokeRepository: mockRepository,
        analyticsService: mockAnalyticsService,
      );

      // Mock analytics service methods
      when(
        () => mockAnalyticsService.logJokeSaved(
          any(),
          any(),
          jokeContext: any(named: 'jokeContext'),
        ),
      ).thenAnswer((_) async {});

      when(
        () => mockRepository.incrementReaction(any(), any()),
      ).thenAnswer((_) async {});

      when(
        () => mockRepository.decrementReaction(any(), any()),
      ).thenAnswer((_) async {});
    });

    tearDown(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('should get empty saved joke IDs initially', () async {
      SharedPreferences.setMockInitialValues({});

      final result = await service.getSavedJokeIds();

      expect(result, isEmpty);
    });

    test('should get saved joke IDs in order', () async {
      SharedPreferences.setMockInitialValues({
        'user_reactions_save': ['joke1', 'joke2', 'joke3'],
      });

      final result = await service.getSavedJokeIds();

      expect(result, equals(['joke1', 'joke2', 'joke3']));
    });

    test('should check if joke is saved correctly', () async {
      SharedPreferences.setMockInitialValues({
        'user_reactions_save': ['joke1', 'joke2'],
      });

      expect(await service.isJokeSaved('joke1'), isTrue);
      expect(await service.isJokeSaved('joke2'), isTrue);
      expect(await service.isJokeSaved('joke3'), isFalse);
    });

    test('should save a joke successfully', () async {
      SharedPreferences.setMockInitialValues({});

      await service.saveJoke('joke1', jokeContext: 'test');

      final result = await service.getSavedJokeIds();
      expect(result, contains('joke1'));

      verify(
        () => mockRepository.incrementReaction('joke1', JokeReactionType.save),
      ).called(1);
      verify(
        () => mockAnalyticsService.logJokeSaved(
          'joke1',
          true,
          jokeContext: 'test',
        ),
      ).called(1);
    });

    test('should not save a joke if already saved', () async {
      SharedPreferences.setMockInitialValues({
        'user_reactions_save': ['joke1'],
      });

      await service.saveJoke('joke1', jokeContext: 'test');

      final result = await service.getSavedJokeIds();
      expect(result, equals(['joke1'])); // Should not be duplicated

      verifyNever(() => mockRepository.incrementReaction(any(), any()));
      verifyNever(
        () => mockAnalyticsService.logJokeSaved(
          any(),
          any(),
          jokeContext: any(named: 'jokeContext'),
        ),
      );
    });

    test('should unsave a joke successfully', () async {
      SharedPreferences.setMockInitialValues({
        'user_reactions_save': ['joke1', 'joke2'],
      });

      await service.unsaveJoke('joke1', jokeContext: 'test');

      final result = await service.getSavedJokeIds();
      expect(result, equals(['joke2']));

      verify(
        () => mockRepository.decrementReaction('joke1', JokeReactionType.save),
      ).called(1);
      verify(
        () => mockAnalyticsService.logJokeSaved(
          'joke1',
          false,
          jokeContext: 'test',
        ),
      ).called(1);
    });

    test('should not unsave a joke if not saved', () async {
      SharedPreferences.setMockInitialValues({
        'user_reactions_save': ['joke1'],
      });

      await service.unsaveJoke('joke2', jokeContext: 'test');

      final result = await service.getSavedJokeIds();
      expect(result, equals(['joke1'])); // Should remain unchanged

      verifyNever(() => mockRepository.decrementReaction(any(), any()));
      verifyNever(
        () => mockAnalyticsService.logJokeSaved(
          any(),
          any(),
          jokeContext: any(named: 'jokeContext'),
        ),
      );
    });

    test('should toggle save joke from unsaved to saved', () async {
      SharedPreferences.setMockInitialValues({});

      final result = await service.toggleSaveJoke('joke1', jokeContext: 'test');

      expect(result, isTrue); // Was saved
      expect(await service.isJokeSaved('joke1'), isTrue);

      verify(
        () => mockRepository.incrementReaction('joke1', JokeReactionType.save),
      ).called(1);
      verify(
        () => mockAnalyticsService.logJokeSaved(
          'joke1',
          true,
          jokeContext: 'test',
        ),
      ).called(1);
    });

    test('should toggle save joke from saved to unsaved', () async {
      SharedPreferences.setMockInitialValues({
        'user_reactions_save': ['joke1'],
      });

      final result = await service.toggleSaveJoke('joke1', jokeContext: 'test');

      expect(result, isFalse); // Was unsaved
      expect(await service.isJokeSaved('joke1'), isFalse);

      verify(
        () => mockRepository.decrementReaction('joke1', JokeReactionType.save),
      ).called(1);
      verify(
        () => mockAnalyticsService.logJokeSaved(
          'joke1',
          false,
          jokeContext: 'test',
        ),
      ).called(1);
    });

    test('should work with null repository', () async {
      SharedPreferences.setMockInitialValues({});

      final serviceWithoutRepo = JokeLocalReactionsService(
        jokeRepository: null,
        analyticsService: mockAnalyticsService,
      );

      await serviceWithoutRepo.saveJoke('joke1', jokeContext: 'test');

      expect(await serviceWithoutRepo.isJokeSaved('joke1'), isTrue);
      verify(
        () => mockAnalyticsService.logJokeSaved(
          'joke1',
          true,
          jokeContext: 'test',
        ),
      ).called(1);
    });

    test('should work with null analytics service', () async {
      SharedPreferences.setMockInitialValues({});

      final serviceWithoutAnalytics = JokeLocalReactionsService(
        jokeRepository: mockRepository,
        analyticsService: null,
      );

      await serviceWithoutAnalytics.saveJoke('joke1', jokeContext: 'test');

      expect(await serviceWithoutAnalytics.isJokeSaved('joke1'), isTrue);
      verify(
        () => mockRepository.incrementReaction('joke1', JokeReactionType.save),
      ).called(1);
    });

    test(
      'should work with both repository and analytics service as null',
      () async {
        SharedPreferences.setMockInitialValues({});

        final serviceWithoutDeps = JokeLocalReactionsService(
          jokeRepository: null,
          analyticsService: null,
        );

        await serviceWithoutDeps.saveJoke('joke1', jokeContext: 'test');

        expect(await serviceWithoutDeps.isJokeSaved('joke1'), isTrue);
      },
    );

    test('should handle analytics failure gracefully', () async {
      SharedPreferences.setMockInitialValues({});

      when(
        () => mockAnalyticsService.logJokeSaved(
          any(),
          any(),
          jokeContext: any(named: 'jokeContext'),
        ),
      ).thenThrow(Exception('Analytics error'));

      // Should not throw
      await service.saveJoke('joke1', jokeContext: 'test');

      expect(await service.isJokeSaved('joke1'), isTrue);
    });

    test('should handle repository failure gracefully', () async {
      SharedPreferences.setMockInitialValues({});

      when(
        () => mockRepository.incrementReaction(any(), any()),
      ).thenThrow(Exception('Repository error'));

      // Should not throw
      await service.saveJoke('joke1', jokeContext: 'test');

      expect(await service.isJokeSaved('joke1'), isTrue);
    });

    test('should maintain order when saving multiple jokes', () async {
      SharedPreferences.setMockInitialValues({});

      await service.saveJoke('joke1', jokeContext: 'test');
      await service.saveJoke('joke2', jokeContext: 'test');
      await service.saveJoke('joke3', jokeContext: 'test');

      final result = await service.getSavedJokeIds();
      expect(result, equals(['joke1', 'joke2', 'joke3']));
    });

    test('should maintain order when unsaving jokes', () async {
      SharedPreferences.setMockInitialValues({
        'user_reactions_save': ['joke1', 'joke2', 'joke3'],
      });

      await service.unsaveJoke('joke2', jokeContext: 'test');

      final result = await service.getSavedJokeIds();
      expect(result, equals(['joke1', 'joke3']));
    });
  });
}
