import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart'; // Ensure flutter_test is before flutter_riverpod
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:mockito/mockito.dart';
import 'package:mockito/annotations.dart'; // Import GenerateMocks

// Generate mocks for JokeRepository
@GenerateMocks([JokeRepository])
import 'providers_test.mocks.dart'; // Import generated mocks

// We'll keep MockFirebaseFirestore as a simple manual mock for now,
// as it's only used to satisfy the JokeRepositoryProvider dependency.
class MockFirebaseFirestore extends Mock implements FirebaseFirestore {}


void main() {
  group('Jokes Riverpod Providers', () {
    late ProviderContainer container;
    late MockJokeRepository mockJokeRepository; // Will use generated mock
    late MockFirebaseFirestore mockFirebaseFirestore;

    setUp(() {
      // mockJokeRepository will be set up in the group below or per test
      mockFirebaseFirestore = MockFirebaseFirestore();
    });

    // Helper to create a container with overrides
    ProviderContainer createContainer({List<Override> overrides = const []}) {
      return ProviderContainer(overrides: overrides);
    }

    tearDown(() {
      container.dispose();
    });

    // Removed the direct test for firebaseFirestoreProvider as it causes Firebase initialization issues
    // in a pure unit test environment. We'll test its usage by overriding it in dependent providers.

    group('jokeRepositoryProvider', () {
      test('should correctly instantiate JokeRepository using a mock FirebaseFirestore', () {
        // arrange
        container = createContainer(overrides: [
          firebaseFirestoreProvider.overrideWithValue(mockFirebaseFirestore),
        ]);
        // act
        final repository = container.read(jokeRepositoryProvider);
        // assert
        expect(repository, isA<JokeRepository>());
        // We can't easily verify the mockFirestore was passed without deeper changes to JokeRepository
        // or making _firestore public, which is not ideal. Trusting the wiring for now.
      });
    });

    group('jokesProvider', () {
      // Specific setUp for this group to ensure mockJokeRepository is fresh for these tests
      setUp(() {
        mockJokeRepository = MockJokeRepository(); // Use generated mock
      });

      const tJoke1 = Joke(id: '1', setupText: 'Setup 1', punchlineText: 'Punchline 1');
      const tJoke2 = Joke(id: '2', setupText: 'Setup 2', punchlineText: 'Punchline 2');
      final tJokesList = [tJoke1, tJoke2];

      test('should return a stream of jokes from JokeRepository', () async {
        // arrange
        // Ensure a fresh mock for this specific test interaction if needed, though setUp should handle it.
        // Re-stubbing getJokes for this specific test case.
        when(mockJokeRepository.getJokes()).thenAnswer((_) => Stream.value(tJokesList));

        container = createContainer(overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
        ]);

        // act
        final resultStream = container.read(jokesProvider.stream);

        // assert
        await expectLater(resultStream, emits(tJokesList));
        verify(mockJokeRepository.getJokes()).called(1);
      });

      test('should emit an error when JokeRepository stream emits an error', () async {
        // arrange
        final exception = Exception('Test error from repository');
        // Re-stubbing getJokes for this specific test case.
        when(mockJokeRepository.getJokes()).thenAnswer((_) => Stream.error(exception));

        container = createContainer(overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
        ]);

        // act
        final resultStream = container.read(jokesProvider.stream);

        // assert
        await expectLater(resultStream, emitsError(exception));
        verify(mockJokeRepository.getJokes()).called(1);
      });

      test('should emit an empty list when JokeRepository stream emits an empty list', () async {
        // arrange
        // Re-stubbing getJokes for this specific test case.
        when(mockJokeRepository.getJokes()).thenAnswer((_) => Stream.value([]));

        container = createContainer(overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
        ]);

        // act
        final resultStream = container.read(jokesProvider.stream);

        // assert
        await expectLater(resultStream, emits([]));
        verify(mockJokeRepository.getJokes()).called(1);
      });
    });
  });
}
