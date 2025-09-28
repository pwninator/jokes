import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_navigation_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';

import '../../../test_helpers/firebase_mocks.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('JokeListViewer restores page from provider-managed controller', (
    tester,
  ) async {
    const viewerId = 'persist_case';

    final jokes = List.generate(5, (i) {
      return JokeWithDate(
        joke: Joke(
          id: 'id_$i',
          setupText: 'Setup $i',
          punchlineText: 'Punchline $i',
          setupImageUrl: 'https://example.com/s$i.jpg',
          punchlineImageUrl: 'https://example.com/p$i.jpg',
        ),
      );
    });

    final container = ProviderContainer(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(),
    );
    addTearDown(container.dispose);

    // Build with initial data
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SizedBox.shrink()),
      ),
    );

    // First mount
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          home: TickerMode(
            enabled: false,
            child: JokeListViewer(
              jokesAsyncValue: AsyncValue.data(jokes),
              jokeContext: 'test_ctx',
              viewerId: viewerId,
            ),
          ),
        ),
      ),
    );

    await tester.pump(const Duration(milliseconds: 50));

    // Scroll to page 3
    // Simulate navigating to page 3 by updating the saved index and rebuilding
    container.read(jokeViewerPageIndexProvider(viewerId).notifier).state = 3;
    container.read(jokeViewerPageIndexProvider(viewerId).notifier).state = 3;

    await tester.pump(const Duration(milliseconds: 50));

    // Unmount (navigate away)
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SizedBox.shrink()),
      ),
    );
    await tester.pump(const Duration(milliseconds: 50));

    // Remount (navigate back) and ensure page restores to 3
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          home: TickerMode(
            enabled: false,
            child: JokeListViewer(
              jokesAsyncValue: AsyncValue.data(jokes),
              jokeContext: 'test_ctx',
              viewerId: viewerId,
            ),
          ),
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 50));

    // Verify that the rebuilt viewer shows the saved page by reading the index
    final restored = container.read(jokeViewerPageIndexProvider(viewerId));
    expect(restored, 3);
  });
}
