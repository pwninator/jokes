import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/settings_providers.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/startup/startup_tasks.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

class MockJokeInteraction extends Mock implements JokeInteraction {}

void main() {
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

      // Mock the full feed sync to do nothing and complete instantly
      when(() => mockJokeRepository.readFeedJokes(cursor: any(named: 'cursor')))
          .thenAnswer(
        (_) async => const JokeListPage(ids: [], cursor: null, hasMore: false),
      );

      // Mock the feed head watch to return a list that satisfies the initial window
      final mockInteractions = List.generate(100, (i) {
        final mockInteraction = MockJokeInteraction();
        when(() => mockInteraction.feedIndex).thenReturn(i);
        return mockInteraction;
      });
      when(() => mockJokeInteractionsRepository.watchFeedHead(
              limit: any(named: 'limit')))
          .thenAnswer((_) => Stream.value(mockInteractions));
    });

    tearDown(() {
      container.dispose();
    });

    test(
        'resets composite cursor for feed jokes if it is marked as __DONE__',
        () async {
      // Arrange: Set up SharedPreferences with a "done" cursor
      final initialCursor = const CompositeCursor(
        totalJokesLoaded: 100,
        subSourceCursors: {
          localFeedJokesSubSourceId: kDoneSentinel,
          'another_source': 'cursor-123',
        },
        prioritySourceCursors: {},
      ).encode();

      SharedPreferences.setMockInitialValues({
        compositeJokeCursorPrefsKey: initialCursor,
      });
      sharedPreferences = await SharedPreferences.getInstance();

      container = ProviderContainer(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          jokeInteractionsRepositoryProvider
              .overrideWithValue(mockJokeInteractionsRepository),
          sharedPreferencesProvider.overrideWithValue(sharedPreferences),
        ],
      );

      final startupReader = container.read;

      // Act: Run the startup task
      await syncFeedJokesExecute(startupReader);

      // Assert: Check that the cursor was modified correctly
      final updatedRawCursor =
          sharedPreferences.getString(compositeJokeCursorPrefsKey);
      final updatedCursor = CompositeCursor.decode(updatedRawCursor);

      expect(updatedCursor, isNotNull);
      expect(
        updatedCursor!.subSourceCursors.containsKey(localFeedJokesSubSourceId),
        isFalse,
      );
      expect(
        updatedCursor.subSourceCursors['another_source'],
        'cursor-123',
      );
    });

    test('does not modify cursor if feed joke cursor is not __DONE__',
        () async {
      // Arrange: Set up SharedPreferences with a "normal" cursor
      final initialCursor = const CompositeCursor(
        totalJokesLoaded: 50,
        subSourceCursors: {
          localFeedJokesSubSourceId: 'some-feed-cursor',
          'another_source': 'cursor-123',
        },
        prioritySourceCursors: {},
      ).encode();

      SharedPreferences.setMockInitialValues({
        compositeJokeCursorPrefsKey: initialCursor,
      });
      sharedPreferences = await SharedPreferences.getInstance();

      container = ProviderContainer(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          jokeInteractionsRepositoryProvider
              .overrideWithValue(mockJokeInteractionsRepository),
          sharedPreferencesProvider.overrideWithValue(sharedPreferences),
        ],
      );

      final startupReader = container.read;

      // Act: Run the startup task
      await syncFeedJokesExecute(startupReader);

      // Assert: Check that the cursor was not changed
      final updatedRawCursor =
          sharedPreferences.getString(compositeJokeCursorPrefsKey);
      expect(updatedRawCursor, initialCursor);
    });
  });
}
