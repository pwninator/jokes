import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_management_screen.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

import '../../../test_helpers/firebase_mocks.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

void main() {
  setUpAll(() {
    registerFallbackValue(
      const JokeListPageCursor(orderValue: 0, docId: 'cursor'),
    );
  });

  testWidgets('Clear icon is always visible and clears search', (tester) async {
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
      overrides: [
        ...FirebaseMocks.getFirebaseProviderOverrides(),
        jokeRepositoryProvider.overrideWithValue(repo),
      ],
    );

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: JokeManagementScreen()),
      ),
    );

    await tester.pumpAndSettle(const Duration(milliseconds: 100));

    // Reveal the search UI via the chip
    final searchChip = find.byKey(const Key('search-toggle-chip'));
    expect(searchChip, findsOneWidget);
    await tester.tap(searchChip);
    await tester.pumpAndSettle();

    // Clear icon should be present even with empty field
    final clearIcon = find.byIcon(Icons.clear);
    expect(clearIcon, findsOneWidget);

    // Enter text, ensure clear remains visible, tap to clear, and search hides
    final searchField = find.byKey(const Key('admin-search-field'));
    expect(searchField, findsOneWidget);
    await tester.enterText(searchField, 'knock knock');
    await tester.pump();
    expect(clearIcon, findsOneWidget);

    await tester.tap(clearIcon);
    await tester.pumpAndSettle();

    // After clearing, the search UI should hide per screen behavior
    expect(find.byKey(const Key('admin-search-field')), findsNothing);

    container.dispose();
  });
}
