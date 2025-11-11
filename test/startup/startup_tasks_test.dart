import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/settings_providers.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/application/feed_sync_service.dart';
import 'package:snickerdoodle/src/startup/startup_tasks.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

class MockJokeInteraction extends Mock implements JokeInteraction {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() {
    registerFallbackValue(const JokeListPageCursor(orderValue: '', docId: ''));
  });

  group('_syncFeedJokes startup task', () {
    late MockJokeRepository mockJokeRepository;
    late MockJokeInteractionsRepository mockJokeInteractionsRepository;
    late ProviderContainer container;
    late SharedPreferences sharedPreferences;

    // Get a reference to the private function via the public task list
    final syncFeedJokesExecute = bestEffortBlockingTasks
        .firstWhere((task) => task.id == 'sync_feed_jokes')
        .execute;

    setUp(() async {
      mockJokeRepository = MockJokeRepository();
      mockJokeInteractionsRepository = MockJokeInteractionsRepository();
      when(
        () => mockJokeInteractionsRepository.countFeedJokes(),
      ).thenAnswer((_) async => 0);

      // Mock the full feed sync to do nothing and complete instantly
      when(
        () => mockJokeRepository.readFeedJokes(cursor: any(named: 'cursor')),
      ).thenAnswer(
        (_) async => const JokeListPage(ids: [], cursor: null, hasMore: false),
      );

      // Mock the feed head watch to return a list that satisfies the initial window
      final mockInteractions = List.generate(100, (i) {
        final mockInteraction = MockJokeInteraction();
        when(() => mockInteraction.feedIndex).thenReturn(i);
        return mockInteraction;
      });
      when(
        () => mockJokeInteractionsRepository.watchFeedHead(
          limit: any(named: 'limit'),
        ),
      ).thenAnswer((_) => Stream.value(mockInteractions));
    });

    tearDown(() {
      container.dispose();
    });

    test('triggers composite reset when DB initially empty', () async {
      // Arrange
      when(
        () => mockJokeInteractionsRepository.countFeedJokes(),
      ).thenAnswer((_) async => 0);

      SharedPreferences.setMockInitialValues({});
      sharedPreferences = await SharedPreferences.getInstance();

      container = ProviderContainer(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          jokeInteractionsRepositoryProvider.overrideWithValue(
            mockJokeInteractionsRepository,
          ),
          sharedPreferencesProvider.overrideWithValue(sharedPreferences),
        ],
      );

      final before = container.read(compositeJokesResetTriggerProvider);
      // Act
      await syncFeedJokesExecute(container.read);
      final after = container.read(compositeJokesResetTriggerProvider);
      // Assert
      expect(after, greaterThan(before));
    });

    test(
      'does not trigger composite reset when DB already populated',
      () async {
        // Arrange
        when(
          () => mockJokeInteractionsRepository.countFeedJokes(),
        ).thenAnswer((_) async => 10);

        SharedPreferences.setMockInitialValues({});
        sharedPreferences = await SharedPreferences.getInstance();

        container = ProviderContainer(
          overrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
            jokeInteractionsRepositoryProvider.overrideWithValue(
              mockJokeInteractionsRepository,
            ),
            sharedPreferencesProvider.overrideWithValue(sharedPreferences),
          ],
        );

        final before = container.read(compositeJokesResetTriggerProvider);
        // Act
        await syncFeedJokesExecute(container.read);
        final after = container.read(compositeJokesResetTriggerProvider);
        // Assert
        expect(after, equals(before));
      },
    );
  });

  test('startup sync task completes without error', () async {
    final mockRepo = MockJokeRepository();
    final mockInteractions = MockJokeInteractionsRepository();

    // Stub repository to return at least threshold jokes in one page
    when(() => mockRepo.readFeedJokes(cursor: any(named: 'cursor'))).thenAnswer(
      (_) async => JokeListPage(
        ids: List.generate(kFeedSyncMinInitialJokes, (i) => 'id_$i'),
        cursor: const JokeListPageCursor(orderValue: '1', docId: '1'),
        hasMore: false,
        jokes: List.generate(
          kFeedSyncMinInitialJokes,
          (i) => Joke(id: 'id_$i', setupText: 's', punchlineText: 'p'),
        ),
      ),
    );
    when(
      () => mockInteractions.syncFeedJokes(jokes: any(named: 'jokes')),
    ).thenAnswer((_) async => true);
    when(() => mockInteractions.countFeedJokes()).thenAnswer((_) async => 0);
    when(
      () => mockInteractions.watchFeedHead(limit: any(named: 'limit')),
    ).thenAnswer((_) => Stream.value(const []));

    final container = ProviderContainer(
      overrides: [
        jokeRepositoryProvider.overrideWithValue(mockRepo),
        jokeInteractionsRepositoryProvider.overrideWithValue(mockInteractions),
      ],
    );

    T reader<T>(ProviderListenable<T> provider) {
      return container.read(provider);
    }

    final task = bestEffortBlockingTasks.firstWhere(
      (t) => t.id == 'sync_feed_jokes',
    );
    await task.execute(reader);
  });
}
