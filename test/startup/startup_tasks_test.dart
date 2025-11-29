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
import 'package:snickerdoodle/src/startup/offline_bundle_loader.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/providers/app_version_provider.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

class MockJokeInteraction extends Mock implements JokeInteraction {}

class MockFeedSyncService extends Mock implements FeedSyncService {}

class MockOfflineBundleLoader extends Mock implements OfflineBundleLoader {}

class MockPerformanceService extends Mock implements PerformanceService {}

const appVersionString = 'app-version-1';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() {
    registerFallbackValue(const JokeListPageCursor(orderValue: '', docId: ''));
  });

  group('_syncFeedJokes startup task', () {
    late MockJokeRepository mockJokeRepository;
    late MockJokeInteractionsRepository mockJokeInteractionsRepository;
    late MockOfflineBundleLoader mockOfflineBundleLoader;
    late MockPerformanceService mockPerformanceService;
    late ProviderContainer container;
    late SharedPreferences sharedPreferences;

    // Get a reference to the private function via the public task list
    final syncFeedJokesExecute = bestEffortBlockingTasks
        .firstWhere((task) => task.id == 'sync_feed_jokes')
        .execute;

    setUp(() async {
      mockJokeRepository = MockJokeRepository();
      mockJokeInteractionsRepository = MockJokeInteractionsRepository();
      mockOfflineBundleLoader = MockOfflineBundleLoader();
      mockPerformanceService = MockPerformanceService();
      when(
        () => mockJokeInteractionsRepository.countFeedJokes(),
      ).thenAnswer((_) async => 0);
      when(() => mockOfflineBundleLoader.loadLatestBundle())
          .thenAnswer((_) async => false);

      // Mock the full feed sync to do nothing and complete instantly
      when(
        () => mockJokeRepository.readFeedJokes(cursor: any(named: 'cursor')),
      ).thenAnswer(
        (_) async => const JokeListPage(ids: [], cursor: null, hasMore: false),
      );

      // Mock the feed count watcher to satisfy the initial window
      when(
        () => mockJokeInteractionsRepository.watchFeedJokeCount(),
      ).thenAnswer((_) => Stream<int>.value(100));
    });

    tearDown(() {
      container.dispose();
    });

    test('triggers composite reset when DB initially empty', () async {
      // Arrange
      when(
        () => mockJokeInteractionsRepository.countFeedJokes(),
      ).thenAnswer((_) async => 0);
      when(() => mockOfflineBundleLoader.loadLatestBundle())
          .thenAnswer((_) async => true);

      SharedPreferences.setMockInitialValues({});
      sharedPreferences = await SharedPreferences.getInstance();

      container = ProviderContainer(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          jokeInteractionsRepositoryProvider.overrideWithValue(
            mockJokeInteractionsRepository,
          ),
          offlineBundleLoaderProvider.overrideWithValue(
            mockOfflineBundleLoader,
          ),
          performanceServiceProvider.overrideWithValue(
            mockPerformanceService,
          ),
          appVersionProvider.overrideWith((_) async => appVersionString),
          sharedPreferencesProvider.overrideWithValue(sharedPreferences),
        ],
      );

      final before = container.read(compositeJokesResetTriggerProvider);
      // Act
      await syncFeedJokesExecute(container.read);
      final after = container.read(compositeJokesResetTriggerProvider);
      // Assert
      expect(after, greaterThan(before));
      verify(() => mockOfflineBundleLoader.loadLatestBundle()).called(1);
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
          offlineBundleLoaderProvider.overrideWithValue(
            mockOfflineBundleLoader,
          ),
          performanceServiceProvider.overrideWithValue(
            mockPerformanceService,
          ),
          appVersionProvider.overrideWith((_) async => appVersionString),
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

    test('removes done sentinel feed cursor before sync completes', () async {
      SharedPreferences.setMockInitialValues({
        compositeJokeCursorPrefsKey: const CompositeCursor(
          totalJokesLoaded: 50,
          subSourceCursors: {
            localFeedJokesSubSourceId: kDoneSentinel,
            'another_source': 'cursor-123',
          },
          prioritySourceCursors: {'priority_source': 'cursor-xyz'},
        ).encode(),
      });
      final sharedPreferences = await SharedPreferences.getInstance();

      final mockFeedSyncService = MockFeedSyncService();
      when(
        () => mockFeedSyncService.triggerSync(forceSync: true),
      ).thenAnswer((_) async => true);

      container = ProviderContainer(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(sharedPreferences),
          feedSyncServiceProvider.overrideWithValue(mockFeedSyncService),
          offlineBundleLoaderProvider.overrideWithValue(
            mockOfflineBundleLoader,
          ),
          performanceServiceProvider.overrideWithValue(
            mockPerformanceService,
          ),
          appVersionProvider.overrideWith((_) async => appVersionString),
        ],
      );

      await syncFeedJokesExecute(container.read);

      final updatedRawCursor = sharedPreferences.getString(
        compositeJokeCursorPrefsKey,
      );
      final updatedCursor = CompositeCursor.decode(updatedRawCursor);

      expect(
        updatedCursor?.subSourceCursors.containsKey(localFeedJokesSubSourceId),
        isFalse,
      );
      expect(updatedCursor?.subSourceCursors['another_source'], 'cursor-123');
      expect(
        updatedCursor?.prioritySourceCursors['priority_source'],
        'cursor-xyz',
      );

      verify(() => mockFeedSyncService.triggerSync(forceSync: true)).called(1);
    });

    test(
      'keeps cursor unchanged when feed cursor is not done sentinel',
      () async {
        const initialCursor = CompositeCursor(
          totalJokesLoaded: 25,
          subSourceCursors: {
            localFeedJokesSubSourceId: 'feed-cursor',
            'another_source': 'cursor-123',
          },
          prioritySourceCursors: {},
        );

        SharedPreferences.setMockInitialValues({
          compositeJokeCursorPrefsKey: initialCursor.encode(),
        });
        final sharedPreferences = await SharedPreferences.getInstance();

        final mockFeedSyncService = MockFeedSyncService();
        when(
          () => mockFeedSyncService.triggerSync(forceSync: true),
        ).thenAnswer((_) async => true);

        container = ProviderContainer(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(sharedPreferences),
          feedSyncServiceProvider.overrideWithValue(mockFeedSyncService),
          offlineBundleLoaderProvider.overrideWithValue(
            mockOfflineBundleLoader,
          ),
          performanceServiceProvider.overrideWithValue(
            mockPerformanceService,
          ),
          appVersionProvider.overrideWith((_) async => appVersionString),
        ],
      );

        await syncFeedJokesExecute(container.read);

        final updatedRawCursor = sharedPreferences.getString(
          compositeJokeCursorPrefsKey,
        );
        expect(updatedRawCursor, initialCursor.encode());

        verify(
          () => mockFeedSyncService.triggerSync(forceSync: true),
        ).called(1);
      },
    );
  });

  test('startup sync task completes without error', () async {
    final mockRepo = MockJokeRepository();
    final mockInteractions = MockJokeInteractionsRepository();
    final mockOfflineBundleLoader = MockOfflineBundleLoader();
    when(() => mockOfflineBundleLoader.loadLatestBundle())
        .thenAnswer((_) async => false);
    final mockPerformanceService = MockPerformanceService();

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
    when(() => mockInteractions.watchFeedJokeCount()).thenAnswer(
      (_) => Stream<int>.fromIterable([0, kFeedSyncMinInitialJokes]),
    );

    SharedPreferences.setMockInitialValues({});
    final sharedPrefs = await SharedPreferences.getInstance();

    final container = ProviderContainer(
      overrides: [
        jokeRepositoryProvider.overrideWithValue(mockRepo),
        jokeInteractionsRepositoryProvider.overrideWithValue(mockInteractions),
        offlineBundleLoaderProvider.overrideWithValue(mockOfflineBundleLoader),
        performanceServiceProvider.overrideWithValue(mockPerformanceService),
        appVersionProvider.overrideWith((_) async => appVersionString),
        sharedPreferencesProvider.overrideWithValue(sharedPrefs),
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
