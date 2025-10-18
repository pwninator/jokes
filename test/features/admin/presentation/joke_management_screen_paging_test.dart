import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_management_screen.dart';
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

  group('JokeManagementScreen infinite scroll edge cases', () {
    testWidgets('handles empty first page (no loadMore attempts)', (
      tester,
    ) async {
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
        (_) async => const JokeListPage(ids: [], cursor: null, hasMore: false),
      );

      final container = ProviderContainer(
        overrides: [jokeRepositoryProvider.overrideWithValue(repo)],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: JokeManagementScreen()),
        ),
      );

      await tester.pumpAndSettle(const Duration(milliseconds: 100));

      verify(
        () => repo.getFilteredJokePage(
          states: any(named: 'states'),
          popularOnly: any(named: 'popularOnly'),
          publicOnly: any(named: 'publicOnly'),
          limit: any(named: 'limit'),
          cursor: any(named: 'cursor'),
        ),
      ).called(1);

      container.dispose();
    });

    test(
      'AdminPagingNotifier guards loadMore when loading or hasMore=false',
      () async {
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
          (_) async =>
              const JokeListPage(ids: [], cursor: null, hasMore: false),
        );

        final container = ProviderContainer(
          overrides: [jokeRepositoryProvider.overrideWithValue(repo)],
        );

        final notifier = container.read(adminPagingProvider.notifier);

        container.read(adminPagingProvider); // initialize
        notifier.loadFirstPage();
        await notifier.loadMore();
        await Future<void>.delayed(const Duration(milliseconds: 10));
        await notifier.loadMore();

        verify(
          () => repo.getFilteredJokePage(
            states: any(named: 'states'),
            popularOnly: any(named: 'popularOnly'),
            publicOnly: any(named: 'publicOnly'),
            limit: any(named: 'limit'),
            cursor: any(named: 'cursor'),
          ),
        ).called(1);

        container.dispose();
      },
    );
  });
}
