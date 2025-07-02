import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

// Mock classes using mocktail
class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class MockJokeReactionsService extends Mock implements JokeReactionsService {}

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

    group('jokeReactionsProvider', () {
      late MockJokeReactionsService mockReactionsService;
      
      setUp(() {
        mockReactionsService = MockJokeReactionsService();
        
        // Set up default mock responses
        when(() => mockReactionsService.getAllUserReactions())
            .thenAnswer((_) async => <String, Set<JokeReactionType>>{});
      });

      test('thumbs up should remove existing thumbs down', () async {
        // arrange
        const jokeId = 'test-joke';
        
        // Mock initial state: user has thumbs down
        when(() => mockReactionsService.getAllUserReactions())
            .thenAnswer((_) async => {
              jokeId: {JokeReactionType.thumbsDown}
            });
        
        // Mock service calls
        when(() => mockReactionsService.removeUserReaction(jokeId, JokeReactionType.thumbsDown))
            .thenAnswer((_) async {});
        when(() => mockReactionsService.toggleUserReaction(jokeId, JokeReactionType.thumbsUp))
            .thenAnswer((_) async => true); // returns true when adding
        
        // Mock repository calls
        when(() => mockJokeRepository.decrementReaction(jokeId, JokeReactionType.thumbsDown))
            .thenAnswer((_) async {});
        when(() => mockJokeRepository.incrementReaction(jokeId, JokeReactionType.thumbsUp))
            .thenAnswer((_) async {});

        // act
        final container = ProviderContainer(
          overrides: [
            jokeReactionsServiceProvider.overrideWithValue(mockReactionsService),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        );

        final notifier = container.read(jokeReactionsProvider.notifier);
        
        // Wait for initial load to complete
        await Future.delayed(const Duration(milliseconds: 10));
        
        // Toggle thumbs up
        await notifier.toggleReaction(jokeId, JokeReactionType.thumbsUp);

        // assert
        verify(() => mockReactionsService.removeUserReaction(jokeId, JokeReactionType.thumbsDown)).called(1);
        verify(() => mockJokeRepository.decrementReaction(jokeId, JokeReactionType.thumbsDown)).called(1);
        verify(() => mockReactionsService.toggleUserReaction(jokeId, JokeReactionType.thumbsUp)).called(1);
        verify(() => mockJokeRepository.incrementReaction(jokeId, JokeReactionType.thumbsUp)).called(1);

        container.dispose();
      });

      test('thumbs down should remove existing thumbs up', () async {
        // arrange
        const jokeId = 'test-joke';
        
        // Mock initial state: user has thumbs up
        when(() => mockReactionsService.getAllUserReactions())
            .thenAnswer((_) async => {
              jokeId: {JokeReactionType.thumbsUp}
            });
        
        // Mock service calls
        when(() => mockReactionsService.removeUserReaction(jokeId, JokeReactionType.thumbsUp))
            .thenAnswer((_) async {});
        when(() => mockReactionsService.toggleUserReaction(jokeId, JokeReactionType.thumbsDown))
            .thenAnswer((_) async => true); // returns true when adding
        
        // Mock repository calls
        when(() => mockJokeRepository.decrementReaction(jokeId, JokeReactionType.thumbsUp))
            .thenAnswer((_) async {});
        when(() => mockJokeRepository.incrementReaction(jokeId, JokeReactionType.thumbsDown))
            .thenAnswer((_) async {});

        // act
        final container = ProviderContainer(
          overrides: [
            jokeReactionsServiceProvider.overrideWithValue(mockReactionsService),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        );

        final notifier = container.read(jokeReactionsProvider.notifier);
        
        // Wait for initial load to complete
        await Future.delayed(const Duration(milliseconds: 10));
        
        // Toggle thumbs down
        await notifier.toggleReaction(jokeId, JokeReactionType.thumbsDown);

        // assert
        verify(() => mockReactionsService.removeUserReaction(jokeId, JokeReactionType.thumbsUp)).called(1);
        verify(() => mockJokeRepository.decrementReaction(jokeId, JokeReactionType.thumbsUp)).called(1);
        verify(() => mockReactionsService.toggleUserReaction(jokeId, JokeReactionType.thumbsDown)).called(1);
        verify(() => mockJokeRepository.incrementReaction(jokeId, JokeReactionType.thumbsDown)).called(1);

        container.dispose();
      });

      test('save reaction should work independently of thumbs reactions', () async {
        // arrange
        const jokeId = 'test-joke';
        
        // Mock initial state: user has thumbs up
        when(() => mockReactionsService.getAllUserReactions())
            .thenAnswer((_) async => {
              jokeId: {JokeReactionType.thumbsUp}
            });
        
        // Mock service calls
        when(() => mockReactionsService.toggleUserReaction(jokeId, JokeReactionType.save))
            .thenAnswer((_) async => true); // returns true when adding
        
        // Mock repository calls
        when(() => mockJokeRepository.incrementReaction(jokeId, JokeReactionType.save))
            .thenAnswer((_) async {});

        // act
        final container = ProviderContainer(
          overrides: [
            jokeReactionsServiceProvider.overrideWithValue(mockReactionsService),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        );

        final notifier = container.read(jokeReactionsProvider.notifier);
        
        // Wait for initial load to complete
        await Future.delayed(const Duration(milliseconds: 10));
        
        // Toggle save (should not affect thumbs up)
        await notifier.toggleReaction(jokeId, JokeReactionType.save);

        // assert - only save should be affected, thumbs up should remain untouched
        verify(() => mockReactionsService.toggleUserReaction(jokeId, JokeReactionType.save)).called(1);
        verify(() => mockJokeRepository.incrementReaction(jokeId, JokeReactionType.save)).called(1);
        
        // Verify thumbs up was NOT affected
        verifyNever(() => mockReactionsService.removeUserReaction(jokeId, JokeReactionType.thumbsUp));
        verifyNever(() => mockJokeRepository.decrementReaction(jokeId, JokeReactionType.thumbsUp));

        container.dispose();
      });

      test('thumbs up with no existing opposite reaction should work normally', () async {
        // arrange
        const jokeId = 'test-joke';
        
        // Mock initial state: no reactions
        when(() => mockReactionsService.getAllUserReactions())
            .thenAnswer((_) async => <String, Set<JokeReactionType>>{});
        
        // Mock service calls
        when(() => mockReactionsService.toggleUserReaction(jokeId, JokeReactionType.thumbsUp))
            .thenAnswer((_) async => true); // returns true when adding
        
        // Mock repository calls
        when(() => mockJokeRepository.incrementReaction(jokeId, JokeReactionType.thumbsUp))
            .thenAnswer((_) async {});

        // act
        final container = ProviderContainer(
          overrides: [
            jokeReactionsServiceProvider.overrideWithValue(mockReactionsService),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        );

        final notifier = container.read(jokeReactionsProvider.notifier);
        
        // Wait for initial load to complete
        await Future.delayed(const Duration(milliseconds: 10));
        
        // Toggle thumbs up
        await notifier.toggleReaction(jokeId, JokeReactionType.thumbsUp);

        // assert - only thumbs up operations should happen
        verify(() => mockReactionsService.toggleUserReaction(jokeId, JokeReactionType.thumbsUp)).called(1);
        verify(() => mockJokeRepository.incrementReaction(jokeId, JokeReactionType.thumbsUp)).called(1);
        
        // Verify no thumbs down operations
        verifyNever(() => mockReactionsService.removeUserReaction(jokeId, JokeReactionType.thumbsDown));
        verifyNever(() => mockJokeRepository.decrementReaction(jokeId, JokeReactionType.thumbsDown));

        container.dispose();
      });

      test('removing thumbs up should not affect thumbs down', () async {
        // arrange
        const jokeId = 'test-joke';
        
        // Mock initial state: user has thumbs up
        when(() => mockReactionsService.getAllUserReactions())
            .thenAnswer((_) async => {
              jokeId: {JokeReactionType.thumbsUp}
            });
        
        // Mock service calls
        when(() => mockReactionsService.toggleUserReaction(jokeId, JokeReactionType.thumbsUp))
            .thenAnswer((_) async => false); // returns false when removing
        
        // Mock repository calls
        when(() => mockJokeRepository.decrementReaction(jokeId, JokeReactionType.thumbsUp))
            .thenAnswer((_) async {});

        // act
        final container = ProviderContainer(
          overrides: [
            jokeReactionsServiceProvider.overrideWithValue(mockReactionsService),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        );

        final notifier = container.read(jokeReactionsProvider.notifier);
        
        // Wait for initial load to complete
        await Future.delayed(const Duration(milliseconds: 10));
        
        // Toggle thumbs up (remove it)
        await notifier.toggleReaction(jokeId, JokeReactionType.thumbsUp);

        // assert - only thumbs up removal should happen
        verify(() => mockReactionsService.toggleUserReaction(jokeId, JokeReactionType.thumbsUp)).called(1);
        verify(() => mockJokeRepository.decrementReaction(jokeId, JokeReactionType.thumbsUp)).called(1);
        
        // Verify no thumbs down operations
        verifyNever(() => mockReactionsService.removeUserReaction(jokeId, JokeReactionType.thumbsDown));
        verifyNever(() => mockJokeRepository.decrementReaction(jokeId, JokeReactionType.thumbsDown));

        container.dispose();
      });
    });
  });
}
