import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_population_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

import '../../../test_helpers/analytics_mocks.dart';

// Mock classes using mocktail
class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

void main() {
  group('jokePopulationProvider', () {
    late MockJokeCloudFunctionService mockCloudFunctionService;

    setUpAll(() {
      registerAnalyticsFallbackValues();
      // Fallbacks for new enums used with any(named: ...)
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
  });
}
