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

  // Add new test group for joke filter functionality
  group('JokeFilter Tests', () {
    test('JokeFilterState should have correct initial values', () {
      const state = JokeFilterState();
      expect(state.showUnratedOnly, false);
    });

    test('JokeFilterState copyWith should work correctly', () {
      const state = JokeFilterState();
      final newState = state.copyWith(showUnratedOnly: true);
      
      expect(newState.showUnratedOnly, true);
      expect(state.showUnratedOnly, false); // Original unchanged
    });

    test('JokeFilterNotifier should toggle unrated filter', () {
      final container = ProviderContainer();
      final notifier = container.read(jokeFilterProvider.notifier);
      
      expect(container.read(jokeFilterProvider).showUnratedOnly, false);
      
      notifier.toggleUnratedOnly();
      expect(container.read(jokeFilterProvider).showUnratedOnly, true);
      
      notifier.toggleUnratedOnly();
      expect(container.read(jokeFilterProvider).showUnratedOnly, false);
      
      container.dispose();
    });

    test('JokeFilterNotifier should set unrated filter value', () {
      final container = ProviderContainer();
      final notifier = container.read(jokeFilterProvider.notifier);
      
      expect(container.read(jokeFilterProvider).showUnratedOnly, false);
      
      notifier.setUnratedOnly(true);
      expect(container.read(jokeFilterProvider).showUnratedOnly, true);
      
      notifier.setUnratedOnly(false);
      expect(container.read(jokeFilterProvider).showUnratedOnly, false);
      
      container.dispose();
    });

    group('filteredJokesProvider', () {
      late MockJokeRepository mockJokeRepository;
      
      setUp(() {
        mockJokeRepository = MockJokeRepository();
      });

      test('should return all jokes when filter is off', () async {
        // arrange
        final testJokes = [
          const Joke(id: '1', setupText: 'setup1', punchlineText: 'punchline1'),
          const Joke(
            id: '2', 
            setupText: 'setup2', 
            punchlineText: 'punchline2',
            setupImageUrl: 'url1',
            punchlineImageUrl: 'url2',
            numThumbsUp: 5,
            numThumbsDown: 2,
          ),
        ];
        
        when(() => mockJokeRepository.getJokes())
            .thenAnswer((_) => Stream.value(testJokes));

        // act
        final container = ProviderContainer(
          overrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        );

        // Wait for the stream provider to emit data
        await container.read(jokesProvider.future);

        final result = container.read(filteredJokesProvider);
        
        // assert
        expect(result.hasValue, true);
        expect(result.value, testJokes);
        
        container.dispose();
      });

      test('should filter to unrated jokes with images when filter is on', () async {
        // arrange
        final testJokes = [
          // No images - should be filtered out
          const Joke(
            id: '1', 
            setupText: 'setup1', 
            punchlineText: 'punchline1',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
          // Has images and unrated - should be included
          const Joke(
            id: '2', 
            setupText: 'setup2', 
            punchlineText: 'punchline2',
            setupImageUrl: 'url1',
            punchlineImageUrl: 'url2',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
          // Has images but rated - should be filtered out
          const Joke(
            id: '3', 
            setupText: 'setup3', 
            punchlineText: 'punchline3',
            setupImageUrl: 'url3',
            punchlineImageUrl: 'url4',
            numThumbsUp: 5,
            numThumbsDown: 0,
          ),
          // Has images but rated (thumbs down) - should be filtered out
          const Joke(
            id: '4', 
            setupText: 'setup4', 
            punchlineText: 'punchline4',
            setupImageUrl: 'url5',
            punchlineImageUrl: 'url6',
            numThumbsUp: 0,
            numThumbsDown: 3,
          ),
          // Has only one image - should be filtered out
          const Joke(
            id: '5', 
            setupText: 'setup5', 
            punchlineText: 'punchline5',
            setupImageUrl: 'url7',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
          // Empty image URLs - should be filtered out
          const Joke(
            id: '6', 
            setupText: 'setup6', 
            punchlineText: 'punchline6',
            setupImageUrl: '',
            punchlineImageUrl: '',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
        ];
        
        when(() => mockJokeRepository.getJokes())
            .thenAnswer((_) => Stream.value(testJokes));

        // act
        final container = ProviderContainer(
          overrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        );

        // Wait for the stream provider to emit data
        await container.read(jokesProvider.future);

        // Turn on the filter
        container.read(jokeFilterProvider.notifier).setUnratedOnly(true);

        final result = container.read(filteredJokesProvider);
        
        // assert
        expect(result.hasValue, true);
        expect(result.value?.length, 1);
        expect(result.value?.first.id, '2'); // Only joke 2 should pass the filter
        
        container.dispose();
      });

          test('should handle loading state correctly', () async {
      // arrange
      when(() => mockJokeRepository.getJokes())
          .thenAnswer((_) => Stream<List<Joke>>.empty()); // Empty stream simulates loading

      // act
      final container = ProviderContainer(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
        ],
      );

      final asyncValue = container.read(jokesProvider);
      final result = container.read(filteredJokesProvider);
      
      // assert
      expect(asyncValue.isLoading, true);
      expect(result.isLoading, true);
      
      container.dispose();
    });

    test('should handle error state correctly', () async {
      // arrange
      const error = 'Test error';
      
      when(() => mockJokeRepository.getJokes())
          .thenAnswer((_) => Stream<List<Joke>>.error(error));

      // act
      final container = ProviderContainer(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
        ],
      );

      // Try to read the jokesProvider to trigger the error
      try {
        await container.read(jokesProvider.future);
      } catch (e) {
        // Expected to fail
      }

      final result = container.read(filteredJokesProvider);
      
      // assert
      expect(result.hasError, true);
      expect(result.error, error);
      
      container.dispose();
    });
    });
  });
}
