import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_admin_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_filter_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

void main() {
  setUpAll(() {
    registerFallbackValue(
      const JokeListPageCursor(orderValue: 0, docId: 'cursor'),
    );
    registerFallbackValue(const JokeFilterState());
    registerFallbackValue(
      const SearchQuery(
        query: '',
        maxResults: 50,
        publicOnly: true,
        matchMode: MatchMode.tight,
      ),
    );
  });

  late MockJokeRepository mockJokeRepository;
  late ProviderContainer container;

  setUp(() {
    mockJokeRepository = MockJokeRepository();

    // Default stub for repository calls
    when(
      () => mockJokeRepository.getFilteredJokePage(
        states: any(named: 'states'),
        popularOnly: any(named: 'popularOnly'),
        publicOnly: any(named: 'publicOnly'),
        limit: any(named: 'limit'),
        cursor: any(named: 'cursor'),
      ),
    ).thenAnswer(
      (_) async => const JokeListPage(
        ids: ['a', 'b', 'c'],
        cursor: JokeListPageCursor(orderValue: 1, docId: 'c'),
        hasMore: true,
      ),
    );

    container = ProviderContainer(
      overrides: [jokeRepositoryProvider.overrideWithValue(mockJokeRepository)],
    );
  });

  tearDown(() {
    container.dispose();
  });

  group('AdminPagingNotifier', () {
    test('initial state is correct', () {
      final state = container.read(adminPagingProvider);
      expect(state.loadedIds, isEmpty);
      expect(state.cursor, isNull);
      expect(state.isLoading, isFalse);
      expect(state.hasMore, isTrue);
    });

    group('loadFirstPage', () {
      test('loads first page successfully', () async {
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: null,
          ),
        ).thenAnswer(
          (_) async => const JokeListPage(
            ids: ['a', 'b', 'c', 'd', 'e'],
            cursor: JokeListPageCursor(orderValue: 1, docId: 'e'),
            hasMore: true,
          ),
        );

        final notifier = container.read(adminPagingProvider.notifier);
        await notifier.loadFirstPage();

        final state = container.read(adminPagingProvider);
        expect(state.loadedIds, ['a', 'b', 'c', 'd', 'e']);
        expect(state.cursor?.docId, 'e');
        expect(state.hasMore, isTrue);
        expect(state.isLoading, isFalse);
      });

      test('handles empty results', () async {
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: null,
          ),
        ).thenAnswer(
          (_) async =>
              const JokeListPage(ids: [], cursor: null, hasMore: false),
        );

        final notifier = container.read(adminPagingProvider.notifier);
        await notifier.loadFirstPage();

        final state = container.read(adminPagingProvider);
        expect(state.loadedIds, isEmpty);
        expect(state.cursor, isNull);
        expect(state.hasMore, isFalse);
        expect(state.isLoading, isFalse);
      });

      test('handles repository errors', () async {
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: null,
          ),
        ).thenThrow(Exception('Repository error'));

        final notifier = container.read(adminPagingProvider.notifier);
        await notifier.loadFirstPage();

        final state = container.read(adminPagingProvider);
        expect(state.loadedIds, isEmpty);
        expect(state.cursor, isNull);
        expect(state.hasMore, isFalse);
        expect(state.isLoading, isFalse);
      });

      test('prevents loading when already loading', () async {
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: null,
          ),
        ).thenAnswer((_) async {
          // Simulate slow response
          await Future.delayed(const Duration(milliseconds: 100));
          return const JokeListPage(
            ids: ['a', 'b'],
            cursor: JokeListPageCursor(orderValue: 1, docId: 'b'),
            hasMore: true,
          );
        });

        final notifier = container.read(adminPagingProvider.notifier);

        // Start first load
        final firstLoad = notifier.loadFirstPage();

        // Try to start second load while first is in progress
        await notifier.loadFirstPage();

        // Wait for first load to complete
        await firstLoad;

        // Should only have been called once
        verify(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: null,
          ),
        ).called(1);
      });
    });

    group('loadMore', () {
      test('appends new results successfully', () async {
        // First page
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: null,
          ),
        ).thenAnswer(
          (_) async => const JokeListPage(
            ids: ['a', 'b', 'c'],
            cursor: JokeListPageCursor(orderValue: 1, docId: 'c'),
            hasMore: true,
          ),
        );

        // Second page
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: const JokeListPageCursor(orderValue: 1, docId: 'c'),
          ),
        ).thenAnswer(
          (_) async => const JokeListPage(
            ids: ['d', 'e', 'f'],
            cursor: JokeListPageCursor(orderValue: 2, docId: 'f'),
            hasMore: true,
          ),
        );

        final notifier = container.read(adminPagingProvider.notifier);
        await notifier.loadFirstPage();
        await notifier.loadMore();

        final state = container.read(adminPagingProvider);
        expect(state.loadedIds, ['a', 'b', 'c', 'd', 'e', 'f']);
        expect(state.cursor?.docId, 'f');
        expect(state.hasMore, isTrue);
        expect(state.isLoading, isFalse);
      });

      test('deduplicates overlapping results', () async {
        // First page
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: null,
          ),
        ).thenAnswer(
          (_) async => const JokeListPage(
            ids: ['a', 'b', 'c'],
            cursor: JokeListPageCursor(orderValue: 1, docId: 'c'),
            hasMore: true,
          ),
        );

        // Second page with overlap
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: const JokeListPageCursor(orderValue: 1, docId: 'c'),
          ),
        ).thenAnswer(
          (_) async => const JokeListPage(
            ids: ['c', 'd', 'e'], // 'c' overlaps
            cursor: JokeListPageCursor(orderValue: 2, docId: 'e'),
            hasMore: true,
          ),
        );

        final notifier = container.read(adminPagingProvider.notifier);
        await notifier.loadFirstPage();
        await notifier.loadMore();

        final state = container.read(adminPagingProvider);
        expect(state.loadedIds, ['a', 'b', 'c', 'd', 'e']); // No duplicate 'c'
        expect(state.cursor?.docId, 'e');
        expect(state.hasMore, isTrue);
      });

      test('handles no more results', () async {
        // First page
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: null,
          ),
        ).thenAnswer(
          (_) async => const JokeListPage(
            ids: ['a', 'b'],
            cursor: JokeListPageCursor(orderValue: 1, docId: 'b'),
            hasMore: true,
          ),
        );

        // Second page - no more results
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: const JokeListPageCursor(orderValue: 1, docId: 'b'),
          ),
        ).thenAnswer(
          (_) async => const JokeListPage(
            ids: [],
            cursor: null, // No cursor when no more results
            hasMore: false,
          ),
        );

        final notifier = container.read(adminPagingProvider.notifier);
        await notifier.loadFirstPage();
        await notifier.loadMore();

        final state = container.read(adminPagingProvider);
        expect(state.loadedIds, ['a', 'b']);
        // The implementation preserves the previous cursor even when hasMore is false
        expect(state.cursor?.docId, 'b'); // Previous cursor is preserved
        expect(state.hasMore, isFalse);
        expect(state.isLoading, isFalse);
      });

      test('handles repository errors', () async {
        // First page
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: null,
          ),
        ).thenAnswer(
          (_) async => const JokeListPage(
            ids: ['a', 'b'],
            cursor: JokeListPageCursor(orderValue: 1, docId: 'b'),
            hasMore: true,
          ),
        );

        // Second page - error
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: const JokeListPageCursor(orderValue: 1, docId: 'b'),
          ),
        ).thenThrow(Exception('Repository error'));

        final notifier = container.read(adminPagingProvider.notifier);
        await notifier.loadFirstPage();
        await notifier.loadMore();

        final state = container.read(adminPagingProvider);
        expect(state.loadedIds, ['a', 'b']); // Preserves existing data
        expect(state.cursor?.docId, 'b'); // Preserves existing cursor
        expect(state.hasMore, isTrue); // Preserves existing hasMore
        expect(state.isLoading, isFalse);
      });

      test('prevents loading when already loading', () async {
        // First page
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: null,
          ),
        ).thenAnswer(
          (_) async => const JokeListPage(
            ids: ['a', 'b'],
            cursor: JokeListPageCursor(orderValue: 1, docId: 'b'),
            hasMore: true,
          ),
        );

        // Second page - slow response
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: const JokeListPageCursor(orderValue: 1, docId: 'b'),
          ),
        ).thenAnswer((_) async {
          await Future.delayed(const Duration(milliseconds: 100));
          return const JokeListPage(
            ids: ['c', 'd'],
            cursor: JokeListPageCursor(orderValue: 2, docId: 'd'),
            hasMore: true,
          );
        });

        final notifier = container.read(adminPagingProvider.notifier);
        await notifier.loadFirstPage();

        // Start first loadMore
        final firstLoadMore = notifier.loadMore();

        // Try to start second loadMore while first is in progress
        await notifier.loadMore();

        // Wait for first loadMore to complete
        await firstLoadMore;

        // Should only have been called once for loadMore
        verify(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: const JokeListPageCursor(orderValue: 1, docId: 'b'),
          ),
        ).called(1);
      });

      test('prevents loading when no more results', () async {
        // First page with no more results
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: null,
          ),
        ).thenAnswer(
          (_) async =>
              const JokeListPage(ids: ['a', 'b'], cursor: null, hasMore: false),
        );

        final notifier = container.read(adminPagingProvider.notifier);
        await notifier.loadFirstPage();
        await notifier.loadMore(); // Should not call repository

        // Should only have been called once (for loadFirstPage)
        verify(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: null,
          ),
        ).called(1);
      });
    });

    group('reset', () {
      test('resets state to initial', () async {
        // Load some data first
        when(
          () => mockJokeRepository.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: null,
          ),
        ).thenAnswer(
          (_) async => const JokeListPage(
            ids: ['a', 'b', 'c'],
            cursor: JokeListPageCursor(orderValue: 1, docId: 'c'),
            hasMore: true,
          ),
        );

        final notifier = container.read(adminPagingProvider.notifier);
        await notifier.loadFirstPage();

        // Verify data is loaded
        var state = container.read(adminPagingProvider);
        expect(state.loadedIds, ['a', 'b', 'c']);
        expect(state.cursor?.docId, 'c');
        expect(state.hasMore, isTrue);

        // Reset
        notifier.reset();

        // Verify state is reset
        state = container.read(adminPagingProvider);
        expect(state.loadedIds, isEmpty);
        expect(state.cursor, isNull);
        expect(state.isLoading, isFalse);
        expect(state.hasMore, isTrue);
      });
    });
  });
}
