import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mockito/mockito.dart';
import 'package:mockito/annotations.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

import '../../../test_helpers/firebase_mocks.dart';

// Generate mocks for JokeRepository
@GenerateMocks([JokeRepository, JokeCloudFunctionService])
import 'providers_test.mocks.dart';

void main() {
  group('Joke Providers', () {
    late MockJokeRepository mockJokeRepository;
    late ProviderContainer container;

    setUp(() {
      mockJokeRepository = MockJokeRepository();
      container = ProviderContainer(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(
          additionalOverrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        ),
      );
    });

    tearDown(() {
      container.dispose();
    });

    test('jokeRepositoryProvider should provide JokeRepository instance', () {
      final repository = container.read(jokeRepositoryProvider);
      expect(repository, isNotNull);
    });

    test('jokesProvider should return stream of jokes', () async {
      // arrange
      const mockJokes = [
        Joke(
          id: '1',
          setupText: 'Setup 1',
          punchlineText: 'Punchline 1',
        ),
        Joke(
          id: '2',
          setupText: 'Setup 2',
          punchlineText: 'Punchline 2',
        ),
      ];

      // Override with specific test data
      final testContainer = ProviderContainer(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(
          additionalOverrides: [
            jokesProvider.overrideWith((ref) => Stream.value(mockJokes)),
          ],
        ),
      );

      // act
      final asyncValue = await testContainer.read(jokesProvider.future);

      // assert
      expect(asyncValue, equals(mockJokes));
      
      testContainer.dispose();
    });

    test('jokesWithImagesProvider should filter jokes with both image URLs', () async {
      // arrange
      const mockJokes = [
        Joke(
          id: '1',
          setupText: 'Setup 1',
          punchlineText: 'Punchline 1',
          setupImageUrl: 'https://example.com/setup1.jpg',
          punchlineImageUrl: 'https://example.com/punchline1.jpg',
        ),
        Joke(
          id: '2',
          setupText: 'Setup 2',
          punchlineText: 'Punchline 2',
          setupImageUrl: 'https://example.com/setup2.jpg',
          // Missing punchlineImageUrl
        ),
        Joke(
          id: '3',
          setupText: 'Setup 3',
          punchlineText: 'Punchline 3',
          // Missing setupImageUrl
          punchlineImageUrl: 'https://example.com/punchline3.jpg',
        ),
        Joke(
          id: '4',
          setupText: 'Setup 4',
          punchlineText: 'Punchline 4',
          setupImageUrl: '',  // Empty string should be filtered out
          punchlineImageUrl: 'https://example.com/punchline4.jpg',
        ),
        Joke(
          id: '5',
          setupText: 'Setup 5',
          punchlineText: 'Punchline 5',
          setupImageUrl: 'https://example.com/setup5.jpg',
          punchlineImageUrl: 'https://example.com/punchline5.jpg',
        ),
      ];

      when(mockJokeRepository.getJokes())
          .thenAnswer((_) => Stream.value(mockJokes));

      // act
      final asyncValue = await container.read(jokesWithImagesProvider.future);

      // assert - should only contain jokes with both image URLs
      expect(asyncValue.length, equals(2));
      expect(asyncValue[0].id, equals('1'));
      expect(asyncValue[1].id, equals('5'));
      verify(mockJokeRepository.getJokes()).called(1);
    });
  });

  group('JokePopulationNotifier', () {
    late MockJokeCloudFunctionService mockCloudFunctionService;
    late ProviderContainer container;
    late JokePopulationNotifier notifier;

    setUp(() {
      mockCloudFunctionService = MockJokeCloudFunctionService();
      container = ProviderContainer(
        overrides: [
          jokeCloudFunctionServiceProvider.overrideWithValue(mockCloudFunctionService),
        ],
      );
      notifier = container.read(jokePopulationProvider.notifier);
    });

    tearDown(() {
      container.dispose();
    });

    group('populateJoke', () {
      test('should add joke to populating set and remove on success', () async {
        // arrange
        const jokeId = 'test-joke-id';
        when(mockCloudFunctionService.populateJoke(jokeId))
            .thenAnswer((_) async => {'success': true, 'data': 'some-data'});

        // assert initial state
        expect(notifier.state.populatingJokes, isEmpty);
        expect(notifier.state.error, isNull);

        // act
        final result = notifier.populateJoke(jokeId);

        // assert joke is in populating set during operation
        expect(notifier.state.populatingJokes, contains(jokeId));
        expect(notifier.state.error, isNull);

        // wait for completion
        final success = await result;

        // assert final state
        expect(success, isTrue);
        expect(notifier.state.populatingJokes, isEmpty);
        expect(notifier.state.error, isNull);
        verify(mockCloudFunctionService.populateJoke(jokeId)).called(1);
      });

      test('should handle service error and remove joke from populating set', () async {
        // arrange
        const jokeId = 'test-joke-id';
        const errorMessage = 'Service error';
        when(mockCloudFunctionService.populateJoke(jokeId))
            .thenAnswer((_) async => {'success': false, 'error': errorMessage});

        // act
        final success = await notifier.populateJoke(jokeId);

        // assert
        expect(success, isFalse);
        expect(notifier.state.populatingJokes, isEmpty);
        expect(notifier.state.error, equals(errorMessage));
        verify(mockCloudFunctionService.populateJoke(jokeId)).called(1);
      });

      test('should handle service returning null and set generic error', () async {
        // arrange
        const jokeId = 'test-joke-id';
        when(mockCloudFunctionService.populateJoke(jokeId))
            .thenAnswer((_) async => null);

        // act
        final success = await notifier.populateJoke(jokeId);

        // assert
        expect(success, isFalse);
        expect(notifier.state.populatingJokes, isEmpty);
        expect(notifier.state.error, equals('Unknown error occurred'));
        verify(mockCloudFunctionService.populateJoke(jokeId)).called(1);
      });

      test('should handle exception and set error message', () async {
        // arrange
        const jokeId = 'test-joke-id';
        const exceptionMessage = 'Network error';
        when(mockCloudFunctionService.populateJoke(jokeId))
            .thenThrow(Exception(exceptionMessage));

        // act
        final success = await notifier.populateJoke(jokeId);

        // assert
        expect(success, isFalse);
        expect(notifier.state.populatingJokes, isEmpty);
        expect(notifier.state.error, contains('Failed to populate joke'));
        expect(notifier.state.error, contains(exceptionMessage));
        verify(mockCloudFunctionService.populateJoke(jokeId)).called(1);
      });
    });

    group('clearError', () {
      test('should clear error state', () async {
        // arrange - set error state first
        const jokeId = 'test-joke-id';
        when(mockCloudFunctionService.populateJoke(jokeId))
            .thenAnswer((_) async => {'success': false, 'error': 'Some error'});
        
        await notifier.populateJoke(jokeId);
        expect(notifier.state.error, isNotNull);

        // act
        notifier.clearError();

        // assert
        expect(notifier.state.error, isNull);
      });
    });

    group('isJokePopulating', () {
      test('should return true when joke is being populated', () async {
        // arrange
        const jokeId = 'test-joke-id';
        when(mockCloudFunctionService.populateJoke(jokeId))
            .thenAnswer((_) async {
          await Future.delayed(const Duration(milliseconds: 100));
          return {'success': true, 'data': 'data'};
        });

        // act
        final future = notifier.populateJoke(jokeId);

        // assert
        expect(notifier.isJokePopulating(jokeId), isTrue);
        expect(notifier.isJokePopulating('other-joke'), isFalse);

        // wait for completion
        await future;

        // assert
        expect(notifier.isJokePopulating(jokeId), isFalse);
      });
    });
  });

  group('JokePopulationState', () {
    test('should create state with default values', () {
      const state = JokePopulationState();
      
      expect(state.isLoading, isFalse);
      expect(state.error, isNull);
      expect(state.populatingJokes, isEmpty);
    });

    test('should copy state with new values', () {
      const originalState = JokePopulationState(
        isLoading: false,
        error: 'old error',
        populatingJokes: {'joke1'},
      );

      final newState = originalState.copyWith(
        isLoading: true,
        error: 'new error',
        populatingJokes: {'joke2'},
      );

      expect(newState.isLoading, isTrue);
      expect(newState.error, equals('new error'));
      expect(newState.populatingJokes, equals({'joke2'}));
      
      // Original should be unchanged
      expect(originalState.isLoading, isFalse);
      expect(originalState.error, equals('old error'));
      expect(originalState.populatingJokes, equals({'joke1'}));
    });

    test('should copy state preserving existing values when not specified', () {
      const originalState = JokePopulationState(
        isLoading: true,
        error: 'some error',
        populatingJokes: {'joke1'},
      );

      final newState = originalState.copyWith(isLoading: false);

      expect(newState.isLoading, isFalse);
      expect(newState.error, equals('some error')); // preserved
      expect(newState.populatingJokes, equals({'joke1'})); // preserved
    });
  });
}

// Mock FirebaseFirestore is needed for container initialization
// as it's only used to satisfy the JokeRepositoryProvider dependency.
class MockFirebaseFirestore extends Mock implements FirebaseFirestore {}
