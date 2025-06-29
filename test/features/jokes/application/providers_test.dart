import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

// Mock classes using mocktail
class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

void main() {
  group('Providers Tests', () {
    late MockJokeRepository mockJokeRepository;
    late MockJokeCloudFunctionService mockCloudFunctionService;

    setUp(() {
      mockJokeRepository = MockJokeRepository();
      mockCloudFunctionService = MockJokeCloudFunctionService();
    });

    group('jokesProvider', () {
      test('should return stream of jokes from repository', () async {
        // arrange
        const joke1 = Joke(
          id: '1',
          setupText: 'Setup 1',
          punchlineText: 'Punchline 1',
        );
        const joke2 = Joke(
          id: '2',
          setupText: 'Setup 2',
          punchlineText: 'Punchline 2',
        );
        final jokesStream = Stream.value([joke1, joke2]);

        when(
          () => mockJokeRepository.getJokes(),
        ).thenAnswer((_) => jokesStream);

        // act
        final container = ProviderContainer(
          overrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        );

        final result = await container.read(jokesProvider.future);

        // assert
        expect(result, [joke1, joke2]);
        verify(() => mockJokeRepository.getJokes()).called(1);

        container.dispose();
      });
    });

    group('jokePopulationProvider', () {
      test('populateJoke should update state correctly on success', () async {
        // arrange
        const jokeId = 'test-joke-id';
        final successResponse = {
          'success': true,
          'data': {'message': 'Success'},
        };

        when(
          () => mockCloudFunctionService.populateJoke(jokeId, imagesOnly: any(named: 'imagesOnly')),
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

        verify(() => mockCloudFunctionService.populateJoke(jokeId, imagesOnly: any(named: 'imagesOnly'))).called(1);

        container.dispose();
      });

      test('populateJoke should handle error correctly', () async {
        // arrange
        const jokeId = 'test-joke-id';
        final errorResponse = {'success': false, 'error': 'Test error'};

        when(
          () => mockCloudFunctionService.populateJoke(jokeId, imagesOnly: any(named: 'imagesOnly')),
        ).thenAnswer((_) async => errorResponse);

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
        expect(state.error, 'Test error');

        verify(() => mockCloudFunctionService.populateJoke(jokeId, imagesOnly: any(named: 'imagesOnly'))).called(1);

        container.dispose();
      });

      test('populateJoke should handle null response', () async {
        // arrange
        const jokeId = 'test-joke-id';

        when(
          () => mockCloudFunctionService.populateJoke(jokeId, imagesOnly: any(named: 'imagesOnly')),
        ).thenAnswer((_) async => null);

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
        expect(state.error, 'Unknown error occurred');

        verify(() => mockCloudFunctionService.populateJoke(jokeId, imagesOnly: any(named: 'imagesOnly'))).called(1);

        container.dispose();
      });

      test('populateJoke should handle missing success field', () async {
        // arrange
        const jokeId = 'test-joke-id';
        final responseWithoutSuccess = {'data': 'some data'};

        when(
          () => mockCloudFunctionService.populateJoke(jokeId, imagesOnly: any(named: 'imagesOnly')),
        ).thenAnswer((_) async => responseWithoutSuccess);

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
        expect(state.error, 'Unknown error occurred');

        verify(() => mockCloudFunctionService.populateJoke(jokeId, imagesOnly: any(named: 'imagesOnly'))).called(1);

        container.dispose();
      });

      test('populateJoke should handle exception', () async {
        // arrange
        const jokeId = 'test-joke-id';

        when(
          () => mockCloudFunctionService.populateJoke(jokeId, imagesOnly: any(named: 'imagesOnly')),
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
        expect(
          state.error,
          contains('Failed to populate joke: Exception: Network error'),
        );

        verify(() => mockCloudFunctionService.populateJoke(jokeId, imagesOnly: any(named: 'imagesOnly'))).called(1);

        container.dispose();
      });

      test('clearError should remove error from state', () async {
        // arrange
        const jokeId = 'test-joke-id';
        final errorResponse = {'success': false, 'error': 'Test error'};

        when(
          () => mockCloudFunctionService.populateJoke(jokeId, imagesOnly: any(named: 'imagesOnly')),
        ).thenAnswer((_) async => errorResponse);

        final container = ProviderContainer(
          overrides: [
            jokeCloudFunctionServiceProvider.overrideWithValue(
              mockCloudFunctionService,
            ),
          ],
        );

        final notifier = container.read(jokePopulationProvider.notifier);

        // First create an error
        await notifier.populateJoke(jokeId);
        expect(container.read(jokePopulationProvider).error, 'Test error');

        // act - clear the error
        notifier.clearError();

        // assert
        final state = container.read(jokePopulationProvider);
        expect(state.error, isNull);

        container.dispose();
      });
    });
  });
}
