import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_population_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';


// Mock classes using mocktail
class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

void main() {
  group('jokePopulationProvider', () {
    late MockJokeCloudFunctionService mockCloudFunctionService;

    setUpAll(() {
      // Fallbacks for enums used with any(named: ...)
      registerFallbackValue(MatchMode.tight);
      registerFallbackValue(SearchScope.userJokeSearch);
    });

    setUp(() {
      mockCloudFunctionService = MockJokeCloudFunctionService();
    });

    test('populateJoke should update state correctly on success', () async {
      // arrange
      const jokeId = 'test-joke-id';
      final successResponse = {
        'success': true,
        'data': {'message': 'Success'},
      };

      when(
        () => mockCloudFunctionService.populateJoke(
          jokeId,
          imagesOnly: any(named: 'imagesOnly'),
        ),
      ).thenAnswer((_) async => successResponse);

      // act
      final container = ProviderContainer(
        overrides: [
          jokeCloudFunctionServiceProvider.overrideWithValue(
            mockCloudFunctionService,
          ),
        ],
      );

      final notifier = container.read(jokePopulationProvider.notifier);

      // Call populateJoke
      await notifier.populateJoke(jokeId);

      // assert
      final state = container.read(jokePopulationProvider);
      expect(state.populatingJokes, isEmpty);
      expect(state.error, isNull);

      verify(
        () => mockCloudFunctionService.populateJoke(
          jokeId,
          imagesOnly: any(named: 'imagesOnly'),
        ),
      ).called(1);

      container.dispose();
    });

    test('populateJoke should update state correctly on failure', () async {
      // arrange
      const jokeId = 'test-joke-id';
      final failureResponse = {'success': false, 'error': 'Test error message'};

      when(
        () => mockCloudFunctionService.populateJoke(
          jokeId,
          imagesOnly: any(named: 'imagesOnly'),
        ),
      ).thenAnswer((_) async => failureResponse);

      // act
      final container = ProviderContainer(
        overrides: [
          jokeCloudFunctionServiceProvider.overrideWithValue(
            mockCloudFunctionService,
          ),
        ],
      );

      final notifier = container.read(jokePopulationProvider.notifier);

      // Call populateJoke
      await notifier.populateJoke(jokeId);

      // assert
      final state = container.read(jokePopulationProvider);
      expect(state.populatingJokes, isEmpty);
      expect(state.error, 'Test error message');

      verify(
        () => mockCloudFunctionService.populateJoke(
          jokeId,
          imagesOnly: any(named: 'imagesOnly'),
        ),
      ).called(1);

      container.dispose();
    });

    test('populateJoke should handle exceptions', () async {
      // arrange
      const jokeId = 'test-joke-id';

      when(
        () => mockCloudFunctionService.populateJoke(
          jokeId,
          imagesOnly: any(named: 'imagesOnly'),
        ),
      ).thenThrow(Exception('Network error'));

      // act
      final container = ProviderContainer(
        overrides: [
          jokeCloudFunctionServiceProvider.overrideWithValue(
            mockCloudFunctionService,
          ),
        ],
      );

      final notifier = container.read(jokePopulationProvider.notifier);

      // Call populateJoke
      await notifier.populateJoke(jokeId);

      // assert
      final state = container.read(jokePopulationProvider);
      expect(state.populatingJokes, isEmpty);
      expect(state.error, contains('Failed to populate joke'));

      container.dispose();
    });

    test('populateJoke should handle multiple concurrent jokes', () async {
      // arrange
      const jokeId1 = 'test-joke-id-1';
      const jokeId2 = 'test-joke-id-2';
      final successResponse = {
        'success': true,
        'data': {'message': 'Success'},
      };

      when(
        () => mockCloudFunctionService.populateJoke(
          any(),
          imagesOnly: any(named: 'imagesOnly'),
        ),
      ).thenAnswer((_) async => successResponse);

      // act
      final container = ProviderContainer(
        overrides: [
          jokeCloudFunctionServiceProvider.overrideWithValue(
            mockCloudFunctionService,
          ),
        ],
      );

      final notifier = container.read(jokePopulationProvider.notifier);

      // Start both populations
      final future1 = notifier.populateJoke(jokeId1);
      final future2 = notifier.populateJoke(jokeId2);

      // Check that both jokes are in populating set
      expect(notifier.isJokePopulating(jokeId1), true);
      expect(notifier.isJokePopulating(jokeId2), true);

      // Wait for both to complete
      await future1;
      await future2;

      // assert
      final state = container.read(jokePopulationProvider);
      expect(state.populatingJokes, isEmpty);
      expect(state.error, isNull);

      container.dispose();
    });

    test('clearError should clear error state', () async {
      // arrange
      const jokeId = 'test-joke-id';
      final failureResponse = {'success': false, 'error': 'Test error message'};

      when(
        () => mockCloudFunctionService.populateJoke(
          jokeId,
          imagesOnly: any(named: 'imagesOnly'),
        ),
      ).thenAnswer((_) async => failureResponse);

      // act
      final container = ProviderContainer(
        overrides: [
          jokeCloudFunctionServiceProvider.overrideWithValue(
            mockCloudFunctionService,
          ),
        ],
      );

      final notifier = container.read(jokePopulationProvider.notifier);

      // Call populateJoke to set error
      await notifier.populateJoke(jokeId);

      // Verify error is set
      expect(
        container.read(jokePopulationProvider).error,
        'Test error message',
      );

      // Clear error
      notifier.clearError();

      // assert
      final state = container.read(jokePopulationProvider);
      expect(state.error, isNull);

      container.dispose();
    });

    test('populateJoke should pass through additional parameters', () async {
      // arrange
      const jokeId = 'test-joke-id';
      final additionalParams = {'param1': 'value1', 'param2': 42};
      final successResponse = {
        'success': true,
        'data': {'message': 'Success'},
      };

      when(
        () => mockCloudFunctionService.populateJoke(
          jokeId,
          imagesOnly: false,
          additionalParams: additionalParams,
        ),
      ).thenAnswer((_) async => successResponse);

      // act
      final container = ProviderContainer(
        overrides: [
          jokeCloudFunctionServiceProvider.overrideWithValue(
            mockCloudFunctionService,
          ),
        ],
      );

      final notifier = container.read(jokePopulationProvider.notifier);

      // Call populateJoke with additional parameters
      await notifier.populateJoke(
        jokeId,
        imagesOnly: false,
        additionalParams: additionalParams,
      );

      // assert
      verify(
        () => mockCloudFunctionService.populateJoke(
          jokeId,
          imagesOnly: false,
          additionalParams: additionalParams,
        ),
      ).called(1);

      container.dispose();
    });
  });
}
