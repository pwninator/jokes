import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_search_result.dart';

import '../../../test_helpers/analytics_mocks.dart';
import '../../../test_helpers/firebase_mocks.dart';

// Mock classes using mocktail
class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

void main() {
  group('Search Providers', () {
    late MockJokeRepository mockJokeRepository;
    late MockJokeCloudFunctionService mockCloudFunctionService;
    late MockAnalyticsService mockAnalyticsService;
    late ProviderContainer Function({List<Override> extra}) createContainer;

    setUpAll(() {
      registerAnalyticsFallbackValues();
      // Needed for any(named: 'matchMode') with mocktail
      registerFallbackValue(MatchMode.tight);
      registerFallbackValue(SearchScope.userJokeSearch);
      registerFallbackValue(SearchLabel.none);
    });

    setUp(() {
      mockJokeRepository = MockJokeRepository();
      mockCloudFunctionService = MockJokeCloudFunctionService();
      mockAnalyticsService = MockAnalyticsService();

      // Default: analytics logs resolve immediately
      when(
        () => mockAnalyticsService.logJokeSearch(
          queryLength: any(named: 'queryLength'),
          scope: any(named: 'scope'),
          resultsCount: any(named: 'resultsCount'),
        ),
      ).thenAnswer((_) async {});

      createContainer = ({List<Override> extra = const []}) {
        final container = ProviderContainer(
          overrides: FirebaseMocks.getFirebaseProviderOverrides(
            additionalOverrides: [
              // Ensure these test-specific mocks override defaults
              jokeCloudFunctionServiceProvider.overrideWithValue(
                mockCloudFunctionService,
              ),
              analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
              ...extra,
            ],
          ),
        );
        addTearDown(container.dispose);
        return container;
      };
    });

    test('searchResultIdsProvider returns empty when query empty', () async {
      final container = createContainer();

      // default query is ''
      final results = await container.read(
        searchResultIdsProvider(SearchScope.userJokeSearch).future,
      );
      expect(results, isEmpty);
    });

    test('searchResultIdsProvider passes through search params', () async {
      when(
        () => mockCloudFunctionService.searchJokes(
          searchQuery: any(named: 'searchQuery'),
          maxResults: any(named: 'maxResults'),
          publicOnly: any(named: 'publicOnly'),
          matchMode: any(named: 'matchMode'),
          scope: any(named: 'scope'),
          excludeJokeIds: any(named: 'excludeJokeIds'),
          label: any(named: 'label'),
        ),
      ).thenAnswer(
        (_) async => const [JokeSearchResult(id: 'x', vectorDistance: 0.1)],
      );

      final container = createContainer();

      const q = 'hello';
      const max = 25;
      const pub = false;
      const mode = MatchMode.loose;
      container
          .read(searchQueryProvider(SearchScope.userJokeSearch).notifier)
          .state = const SearchQuery(
        query: q,
        maxResults: max,
        publicOnly: pub,
        matchMode: mode,
        excludeJokeIds: ['id_to_exclude'],
      );

      await container.read(
        searchResultIdsProvider(SearchScope.userJokeSearch).future,
      );

      verify(
        () => mockCloudFunctionService.searchJokes(
          searchQuery: q,
          maxResults: max,
          publicOnly: pub,
          matchMode: mode,
          scope: SearchScope.userJokeSearch,
          excludeJokeIds: ['id_to_exclude'],
          label: SearchLabel.none,
        ),
      ).called(1);
    });

    test(
      'search query excludeJokeIds defaults to empty and can be overridden',
      () async {
        final container = createContainer();

        // Default is empty
        final initial = container.read(
          searchQueryProvider(SearchScope.userJokeSearch),
        );
        expect(initial.excludeJokeIds, isEmpty);

        // Override via copyWith
        container
            .read(searchQueryProvider(SearchScope.userJokeSearch).notifier)
            .state = initial.copyWith(
          excludeJokeIds: ['a'],
        );

        final updated = container.read(
          searchQueryProvider(SearchScope.userJokeSearch),
        );
        expect(updated.excludeJokeIds, ['a']);
      },
    );

    test('search query label defaults to none and can be overridden', () async {
      final container = createContainer();

      // Default is none
      final initial = container.read(
        searchQueryProvider(SearchScope.userJokeSearch),
      );
      expect(initial.label, SearchLabel.none);

      // Override via copyWith
      container
          .read(searchQueryProvider(SearchScope.userJokeSearch).notifier)
          .state = initial.copyWith(
        label: SearchLabel.similarJokes,
      );

      final updated = container.read(
        searchQueryProvider(SearchScope.userJokeSearch),
      );
      expect(updated.label, SearchLabel.similarJokes);
    });

    test(
      'searchResultsLiveProvider preserves order and applies filters',
      () async {
        // Arrange ids
        when(
          () => mockCloudFunctionService.searchJokes(
            searchQuery: any(named: 'searchQuery'),
            maxResults: any(named: 'maxResults'),
            publicOnly: any(named: 'publicOnly'),
            matchMode: any(named: 'matchMode'),
            scope: any(named: 'scope'),
            label: any(named: 'label'),
          ),
        ).thenAnswer(
          (_) async => const [
            JokeSearchResult(id: 'c', vectorDistance: 0.2),
            JokeSearchResult(id: 'a', vectorDistance: 0.3),
            JokeSearchResult(id: 'b', vectorDistance: 0.4),
          ],
        );

        // Per-joke streams
        final streamA = StreamController<Joke?>();
        final streamB = StreamController<Joke?>();
        final streamC = StreamController<Joke?>();

        when(
          () => mockJokeRepository.getJokeByIdStream('a'),
        ).thenAnswer((_) => streamA.stream);
        when(
          () => mockJokeRepository.getJokeByIdStream('b'),
        ).thenAnswer((_) => streamB.stream);
        when(
          () => mockJokeRepository.getJokeByIdStream('c'),
        ).thenAnswer((_) => streamC.stream);

        final container = createContainer(
          extra: [jokeRepositoryProvider.overrideWithValue(mockJokeRepository)],
        );

        // Set a non-empty query to trigger ids fetch and await completion
        container
            .read(searchQueryProvider(SearchScope.userJokeSearch).notifier)
            .state = const SearchQuery(
          query: 'abc',
          maxResults: 50,
          publicOnly: true,
          matchMode: MatchMode.tight,
        );
        await container.read(
          searchResultIdsProvider(SearchScope.userJokeSearch).future,
        );

        // Push initial values
        streamC.add(
          const Joke(
            id: 'c',
            setupText: 'Sc',
            punchlineText: 'Pc',
            numSaves: 2,
            numShares: 1,
          ),
        );
        streamA.add(
          const Joke(
            id: 'a',
            setupText: 'Sa',
            punchlineText: 'Pa',
            numSaves: 0,
            numShares: 1,
          ),
        );
        streamB.add(
          const Joke(
            id: 'b',
            setupText: 'Sb',
            punchlineText: 'Pb',
            numSaves: 11,
            numShares: 0,
          ),
        );

        // Read results (should preserve ids order: c, a, b)
        var value1 = container.read(
          searchResultsLiveProvider(SearchScope.userJokeSearch),
        );
        if (value1.isLoading) {
          await Future.delayed(const Duration(milliseconds: 1));
          value1 = container.read(
            searchResultsLiveProvider(SearchScope.userJokeSearch),
          );
        }
        expect(value1.hasValue, isTrue);
        expect(value1.value!.map((jvd) => jvd.joke.id).toList(), [
          'c',
          'a',
          'b',
        ]);

        await streamA.close();
        await streamB.close();
        await streamC.close();
        container.dispose();
      },
    );

    test('searchResultsLiveProvider updates when a joke changes', () async {
      when(
        () => mockCloudFunctionService.searchJokes(
          searchQuery: any(named: 'searchQuery'),
          maxResults: any(named: 'maxResults'),
          publicOnly: any(named: 'publicOnly'),
          matchMode: any(named: 'matchMode'),
          scope: any(named: 'scope'),
          label: any(named: 'label'),
        ),
      ).thenAnswer(
        (_) async => const [JokeSearchResult(id: 'j1', vectorDistance: 0.42)],
      );

      final stream = StreamController<Joke?>();
      when(
        () => mockJokeRepository.getJokeByIdStream('j1'),
      ).thenAnswer((_) => stream.stream);

      final container = createContainer(
        extra: [jokeRepositoryProvider.overrideWithValue(mockJokeRepository)],
      );

      container
          .read(searchQueryProvider(SearchScope.userJokeSearch).notifier)
          .state = const SearchQuery(
        query: 'xx',
        maxResults: 50,
        publicOnly: true,
        matchMode: MatchMode.tight,
      );
      await container.read(
        searchResultIdsProvider(SearchScope.userJokeSearch).future,
      );

      // Initial emit without images
      stream.add(
        const Joke(
          id: 'j1',
          setupText: 'S',
          punchlineText: 'P',
          setupImageUrl: null,
          punchlineImageUrl: null,
        ),
      );
      var value = container.read(
        searchResultsLiveProvider(SearchScope.userJokeSearch),
      );
      if (value.isLoading) {
        await Future.delayed(const Duration(milliseconds: 1));
        value = container.read(
          searchResultsLiveProvider(SearchScope.userJokeSearch),
        );
      }
      expect(value.hasValue, isTrue);
      expect(value.value!.first.joke.id, 'j1');
      expect(value.value!.first.joke.setupImageUrl, isNull);

      // Update with images -> provider should now reflect images
      stream.add(
        const Joke(
          id: 'j1',
          setupText: 'S',
          punchlineText: 'P',
          setupImageUrl: 's.jpg',
          punchlineImageUrl: 'p.jpg',
        ),
      );
      // Poll briefly until update propagates
      for (int i = 0; i < 20; i++) {
        value = container.read(
          searchResultsLiveProvider(SearchScope.userJokeSearch),
        );
        if (!value.isLoading &&
            value.hasValue &&
            value.value!.isNotEmpty &&
            value.value!.first.joke.setupImageUrl != null &&
            value.value!.first.joke.punchlineImageUrl != null) {
          break;
        }
        await Future.delayed(const Duration(milliseconds: 5));
      }
      expect(value.hasValue, isTrue);
      expect(value.value!.first.joke.setupImageUrl, isNotNull);
      expect(value.value!.first.joke.punchlineImageUrl, isNotNull);

      await stream.close();
      container.dispose();
    });
  });
}
