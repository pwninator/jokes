import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

import '../../../test_helpers/analytics_mocks.dart';
import '../../../test_helpers/firebase_mocks.dart';

// Mock classes using mocktail
class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeReactionsService extends Mock implements JokeReactionsService {}

void main() {
  group('savedJokesProvider', () {
    setUpAll(() {
      registerAnalyticsFallbackValues();
      // Fallbacks for new enums used with any(named: ...)
      registerFallbackValue(MatchMode.tight);
      registerFallbackValue(SearchScope.userJokeSearch);
    });

    test('provides saved jokes in SharedPreferences order', () async {
      final mockReactionsService = MockJokeReactionsService();
      final mockJokeRepository = MockJokeRepository();

      // Setup mock to return saved joke IDs in specific order
      when(
        () => mockReactionsService.getSavedJokeIds(),
      ).thenAnswer((_) async => ['joke3', 'joke1', 'joke2']);
      when(() => mockReactionsService.getAllUserReactions()).thenAnswer(
        (_) async => {
          'joke3': {JokeReactionType.save},
          'joke1': {JokeReactionType.save},
          'joke2': {JokeReactionType.save},
        },
      );

      // Setup mock repository to return jokes (one without images)
      when(
        () => mockJokeRepository.getJokesByIds(['joke3', 'joke1', 'joke2']),
      ).thenAnswer(
        (_) async => [
          Joke(
            id: 'joke1',
            setupText: 'Setup 1',
            punchlineText: 'Punchline 1',
            setupImageUrl: 'setup1.jpg',
            punchlineImageUrl: 'punchline1.jpg',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
          Joke(
            id: 'joke2',
            setupText: 'Setup 2',
            punchlineText: 'Punchline 2',
            setupImageUrl: 'setup2.jpg',
            punchlineImageUrl: 'punchline2.jpg',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
          Joke(
            id: 'joke3',
            setupText: 'Setup 3',
            punchlineText: 'Punchline 3',
            setupImageUrl: 'setup3.jpg',
            punchlineImageUrl: 'punchline3.jpg',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
        ],
      );

      final container = ProviderContainer(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(
          additionalOverrides: [
            jokeReactionsServiceProvider.overrideWithValue(
              mockReactionsService,
            ),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        ),
      );

      // Wait for jokeReactionsProvider to finish loading
      while (container.read(jokeReactionsProvider).isLoading) {
        await Future.delayed(const Duration(milliseconds: 10));
      }

      final savedJokes = await container.read(savedJokesProvider.future);

      // Verify that jokes are returned in the same order as stored in SharedPreferences
      expect(savedJokes.length, equals(3));
      expect(savedJokes[0].joke.id, equals('joke3'));
      expect(savedJokes[1].joke.id, equals('joke1'));
      expect(savedJokes[2].joke.id, equals('joke2'));

      container.dispose();
    });

    test('filters out jokes without images', () async {
      final mockReactionsService = MockJokeReactionsService();
      final mockJokeRepository = MockJokeRepository();

      // Setup mock to return saved joke IDs
      when(
        () => mockReactionsService.getSavedJokeIds(),
      ).thenAnswer((_) async => ['joke1', 'joke2', 'joke3']);
      when(() => mockReactionsService.getAllUserReactions()).thenAnswer(
        (_) async => {
          'joke1': {JokeReactionType.save},
          'joke2': {JokeReactionType.save},
          'joke3': {JokeReactionType.save},
        },
      );

      // Setup mock repository to return jokes (one without images)
      when(
        () => mockJokeRepository.getJokesByIds(['joke1', 'joke2', 'joke3']),
      ).thenAnswer(
        (_) async => [
          Joke(
            id: 'joke1',
            setupText: 'Setup 1',
            punchlineText: 'Punchline 1',
            setupImageUrl: 'setup1.jpg',
            punchlineImageUrl: 'punchline1.jpg',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
          Joke(
            id: 'joke2',
            setupText: 'Setup 2',
            punchlineText: 'Punchline 2',
            setupImageUrl: null, // No setup image
            punchlineImageUrl: 'punchline2.jpg',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
          Joke(
            id: 'joke3',
            setupText: 'Setup 3',
            punchlineText: 'Punchline 3',
            setupImageUrl: 'setup3.jpg',
            punchlineImageUrl: null, // No punchline image
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
        ],
      );

      final container = ProviderContainer(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(
          additionalOverrides: [
            jokeReactionsServiceProvider.overrideWithValue(
              mockReactionsService,
            ),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        ),
      );

      // Wait for jokeReactionsProvider to finish loading
      while (container.read(jokeReactionsProvider).isLoading) {
        await Future.delayed(const Duration(milliseconds: 10));
      }

      final savedJokes = await container.read(savedJokesProvider.future);

      // Verify that only jokes with both images are included
      expect(savedJokes.length, equals(1));
      expect(savedJokes[0].joke.id, equals('joke1'));

      container.dispose();
    });

    test('handles empty saved jokes list', () async {
      final mockReactionsService = MockJokeReactionsService();

      // Setup mock to return empty list
      when(
        () => mockReactionsService.getSavedJokeIds(),
      ).thenAnswer((_) async => <String>[]);
      when(
        () => mockReactionsService.getAllUserReactions(),
      ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});

      final container = ProviderContainer(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(
          additionalOverrides: [
            jokeReactionsServiceProvider.overrideWithValue(
              mockReactionsService,
            ),
          ],
        ),
      );

      // Wait for jokeReactionsProvider to finish loading
      while (container.read(jokeReactionsProvider).isLoading) {
        await Future.delayed(const Duration(milliseconds: 10));
      }

      final savedJokes = await container.read(savedJokesProvider.future);

      // Verify that empty list is returned
      expect(savedJokes, isEmpty);

      container.dispose();
    });
  });
}
