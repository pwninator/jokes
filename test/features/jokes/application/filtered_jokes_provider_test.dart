import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

void main() {
  group('filteredJokesProvider - Popular only filter', () {
    test(
      'returns only jokes with saves+shares > 0 when popular is enabled',
      () async {
        // Arrange jokes
        const jokePopularSaves = Joke(
          id: '1',
          setupText: 'A',
          punchlineText: 'A',
          numSaves: 1,
          numShares: 0,
        );
        const jokePopularShares = Joke(
          id: '2',
          setupText: 'B',
          punchlineText: 'B',
          numSaves: 0,
          numShares: 2,
        );
        const jokeNotPopular = Joke(
          id: '3',
          setupText: 'C',
          punchlineText: 'C',
          numSaves: 0,
          numShares: 0,
        );

        final container = ProviderContainer(
          overrides: [
            jokesProvider.overrideWith(
              (ref) => Stream.value([
                jokePopularSaves,
                jokePopularShares,
                jokeNotPopular,
              ]),
            ),
          ],
        );
        addTearDown(container.dispose);

        // Wait for jokes stream to emit, then read filtered provider
        await container.read(jokesProvider.future);
        final initialAsync = container.read(filteredJokesProvider);
        expect(initialAsync.hasValue, true);
        expect(initialAsync.value!.length, 3);

        // Enable popular filter
        container.read(jokeFilterProvider.notifier).setPopularOnly(true);
        final filteredAsync = container.read(filteredJokesProvider);

        // Assert only popular jokes remain
        expect(filteredAsync.value!.map((j) => j.id).toSet(), {'1', '2'});
      },
    );
  });
}
