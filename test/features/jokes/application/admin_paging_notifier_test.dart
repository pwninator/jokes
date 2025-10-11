import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_admin_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

void main() {
  setUpAll(() {
    registerFallbackValue(
      const JokeListPageCursor(orderValue: 0, docId: 'cursor'),
    );
  });

  test('loadFirstPage loads 10 ids and sets cursor/hasMore', () async {
    final repo = MockJokeRepository();
    when(
      () => repo.getFilteredJokePage(
        states: any(named: 'states'),
        popularOnly: any(named: 'popularOnly'),
        publicOnly: any(named: 'publicOnly'),
        limit: any(named: 'limit'),
        cursor: any(named: 'cursor'),
      ),
    ).thenAnswer(
      (_) async => const JokeListPage(
        ids: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j'],
        cursor: JokeListPageCursor(orderValue: 1, docId: 'j'),
        hasMore: true,
      ),
    );

    final container = ProviderContainer(
      overrides: [jokeRepositoryProvider.overrideWithValue(repo)],
    );

    final notifier = container.read(adminPagingProvider.notifier);
    await notifier.loadFirstPage();

    final state = container.read(adminPagingProvider);
    expect(state.loadedIds.length, 10);
    expect(state.cursor?.docId, 'j');
    expect(state.hasMore, true);

    container.dispose();
  });

  test('loadMore appends unique ids and updates cursor/hasMore', () async {
    final repo = MockJokeRepository();
    // First page
    when(
      () => repo.getFilteredJokePage(
        states: any(named: 'states'),
        popularOnly: any(named: 'popularOnly'),
        publicOnly: any(named: 'publicOnly'),
        limit: any(named: 'limit'),
        cursor: null,
      ),
    ).thenAnswer(
      (_) async => const JokeListPage(
        ids: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j'],
        cursor: JokeListPageCursor(orderValue: 1, docId: 'j'),
        hasMore: true,
      ),
    );
    // Second page with one overlap
    when(
      () => repo.getFilteredJokePage(
        states: any(named: 'states'),
        popularOnly: any(named: 'popularOnly'),
        publicOnly: any(named: 'publicOnly'),
        limit: any(named: 'limit'),
        cursor: const JokeListPageCursor(orderValue: 1, docId: 'j'),
      ),
    ).thenAnswer(
      (_) async => const JokeListPage(
        ids: ['j', 'k', 'l'],
        cursor: JokeListPageCursor(orderValue: 2, docId: 'l'),
        hasMore: false,
      ),
    );

    final container = ProviderContainer(
      overrides: [jokeRepositoryProvider.overrideWithValue(repo)],
    );

    final notifier = container.read(adminPagingProvider.notifier);
    await notifier.loadFirstPage();
    await notifier.loadMore();

    final state = container.read(adminPagingProvider);
    expect(state.loadedIds, [
      'a',
      'b',
      'c',
      'd',
      'e',
      'f',
      'g',
      'h',
      'i',
      'j',
      'k',
      'l',
    ]);
    expect(state.cursor?.docId, 'l');
    expect(state.hasMore, false);

    container.dispose();
  });
}
