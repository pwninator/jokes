import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/data/core/app/app_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

class MockAppUsageService extends Mock implements AppUsageService {}

Joke _buildJoke(String id, {DateTime? publicTimestamp, bool hasImages = true}) {
  return Joke(
    id: id,
    setupText: 'setup $id',
    punchlineText: 'punchline $id',
    setupImageUrl: hasImages ? 'setup_$id.png' : null,
    punchlineImageUrl: hasImages ? 'punch_$id.png' : null,
    state: JokeState.published,
    publicTimestamp: publicTimestamp ?? DateTime.utc(2024, 1, 1),
  );
}

List<String> _ids(List<JokeWithDate> jokes) =>
    jokes.map((joke) => joke.joke.id).toList();

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('dedupeJokes', () {
    test('removes duplicate ids while keeping first occurrences in order', () {
      final jokes = [
        JokeWithDate(joke: _buildJoke('first')),
        JokeWithDate(joke: _buildJoke('second')),
        JokeWithDate(joke: _buildJoke('first'), dataSource: 'duplicate'),
        JokeWithDate(joke: _buildJoke('third')),
      ];

      final result = dedupeJokes(jokes, const {});

      expect(_ids(result), equals(['first', 'second', 'third']));
    });

    test(
      'omits ids already present in existingIds without mutating the set',
      () {
        final existingIds = {'seen'};
        final snapshot = Set<String>.from(existingIds);
        final jokes = [
          JokeWithDate(joke: _buildJoke('seen')),
          JokeWithDate(joke: _buildJoke('fresh')),
          JokeWithDate(joke: _buildJoke('fresh'), dataSource: 'dup'),
          JokeWithDate(joke: _buildJoke('another')),
        ];

        final result = dedupeJokes(jokes, existingIds);

        expect(_ids(result), equals(['fresh', 'another']));
        expect(existingIds, equals(snapshot));
      },
    );
  });

  group('filterJokesWithImages', () {
    test('keeps only jokes with both image urls populated', () {
      final jokes = [
        JokeWithDate(joke: _buildJoke('valid')),
        JokeWithDate(joke: _buildJoke('missing', hasImages: false)),
        JokeWithDate(
          joke: _buildJoke(
            'blank',
          ).copyWith(setupImageUrl: '', punchlineImageUrl: ''),
        ),
      ];

      final result = filterJokesWithImages(jokes);

      expect(_ids(result), equals(['valid']));
    });
  });

  group('filterJokesByPublicTimestamp', () {
    test('keeps jokes at or before now and any with null timestamps', () {
      final now = DateTime.utc(2025, 1, 10, 12);
      final container = ProviderContainer(
        overrides: [clockProvider.overrideWithValue(() => now)],
      );
      addTearDown(container.dispose);

      final jokes = [
        JokeWithDate(
          joke: _buildJoke(
            'past',
            publicTimestamp: now.subtract(const Duration(days: 1)),
          ),
        ),
        JokeWithDate(joke: _buildJoke('at_now', publicTimestamp: now)),
        JokeWithDate(
          joke: _buildJoke(
            'future',
            publicTimestamp: now.add(const Duration(minutes: 1)),
          ),
        ),
        JokeWithDate(
          joke: _buildJoke('null_ts').copyWith(publicTimestamp: null),
        ),
      ];

      final provider = Provider(
        (ref) => filterJokesByPublicTimestamp(ref, jokes),
      );

      final result = container.read(provider);

      expect(_ids(result), equals(['past', 'at_now', 'null_ts']));
    });
  });

  group('filterViewedJokes', () {
    test('returns only unviewed ids in original order', () async {
      final jokes = [
        JokeWithDate(joke: _buildJoke('a')),
        JokeWithDate(joke: _buildJoke('b')),
        JokeWithDate(joke: _buildJoke('c')),
      ];
      final mockUsage = MockAppUsageService();
      when(() => mockUsage.getUnviewedJokeIds(any())).thenAnswer((
        invocation,
      ) async {
        final ids = invocation.positionalArguments.first as List<String>;
        expect(ids, equals(['a', 'b', 'c']));
        return ['c', 'a'];
      });

      final container = ProviderContainer(
        overrides: [appUsageServiceProvider.overrideWithValue(mockUsage)],
      );
      addTearDown(container.dispose);

      final provider = FutureProvider((ref) => filterViewedJokes(ref, jokes));

      final result = await container.read(provider.future);

      expect(_ids(result), equals(['a', 'c']));
      verify(() => mockUsage.getUnviewedJokeIds(any())).called(1);
    });

    test('returns empty when every id is already viewed', () async {
      final jokes = [
        JokeWithDate(joke: _buildJoke('x')),
        JokeWithDate(joke: _buildJoke('y')),
      ];
      final mockUsage = MockAppUsageService();
      when(
        () => mockUsage.getUnviewedJokeIds(any()),
      ).thenAnswer((_) async => <String>[]);

      final container = ProviderContainer(
        overrides: [appUsageServiceProvider.overrideWithValue(mockUsage)],
      );
      addTearDown(container.dispose);

      final provider = FutureProvider((ref) => filterViewedJokes(ref, jokes));

      final result = await container.read(provider.future);

      expect(result, isEmpty);
      verify(() => mockUsage.getUnviewedJokeIds(['x', 'y'])).called(1);
    });
  });

  group('filterJokes', () {
    test(
      'applies dedupe/image/timestamp filters and skips viewed lookup when disabled',
      () async {
        final now = DateTime.utc(2025, 2, 1);
        final mockUsage = MockAppUsageService();
        final container = ProviderContainer(
          overrides: [
            clockProvider.overrideWithValue(() => now),
            appUsageServiceProvider.overrideWithValue(mockUsage),
          ],
        );
        addTearDown(container.dispose);

        final existingIds = {'existing'};
        final jokes = [
          JokeWithDate(
            joke: _buildJoke(
              'existing',
              publicTimestamp: now.subtract(const Duration(days: 1)),
            ),
          ),
          JokeWithDate(
            joke: _buildJoke(
              'keep',
              publicTimestamp: now.subtract(const Duration(days: 2)),
            ),
          ),
          JokeWithDate(
            joke: _buildJoke(
              'keep',
              publicTimestamp: now.subtract(const Duration(days: 2)),
            ),
            dataSource: 'duplicate',
          ),
          JokeWithDate(
            joke: _buildJoke(
              'missing_images',
              publicTimestamp: now.subtract(const Duration(days: 3)),
              hasImages: false,
            ),
          ),
          JokeWithDate(
            joke: _buildJoke(
              'blank_images',
              publicTimestamp: now.subtract(const Duration(days: 4)),
            ).copyWith(setupImageUrl: '', punchlineImageUrl: ''),
          ),
          JokeWithDate(
            joke: _buildJoke(
              'future',
              publicTimestamp: now.add(const Duration(days: 1)),
            ),
          ),
          JokeWithDate(
            joke: _buildJoke('null_ts').copyWith(publicTimestamp: null),
          ),
        ];

        final provider = FutureProvider(
          (ref) => filterJokes(
            ref,
            jokes,
            existingIds: existingIds,
            filterViewed: false,
          ),
        );

        final result = await container.read(provider.future);

        expect(_ids(result), equals(['keep', 'null_ts']));
        verifyNever(() => mockUsage.getUnviewedJokeIds(any()));
      },
    );

    test(
      'performs viewed filtering after other filters and can yield empty results',
      () async {
        final now = DateTime.utc(2025, 3, 1);
        final mockUsage = MockAppUsageService();
        when(() => mockUsage.getUnviewedJokeIds(any())).thenAnswer((
          invocation,
        ) async {
          final ids = invocation.positionalArguments.first as List<String>;
          expect(ids, equals(['keep', 'also_keep', 'null_ts']));
          return <String>[];
        });

        final container = ProviderContainer(
          overrides: [
            clockProvider.overrideWithValue(() => now),
            appUsageServiceProvider.overrideWithValue(mockUsage),
          ],
        );
        addTearDown(container.dispose);

        final jokes = [
          JokeWithDate(
            joke: _buildJoke(
              'missing',
              publicTimestamp: now.subtract(const Duration(days: 1)),
              hasImages: false,
            ),
          ),
          JokeWithDate(
            joke: _buildJoke(
              'future',
              publicTimestamp: now.add(const Duration(days: 2)),
            ),
          ),
          JokeWithDate(
            joke: _buildJoke(
              'keep',
              publicTimestamp: now.subtract(const Duration(days: 2)),
            ),
          ),
          JokeWithDate(
            joke: _buildJoke(
              'also_keep',
              publicTimestamp: now.subtract(const Duration(hours: 12)),
            ),
          ),
          JokeWithDate(
            joke: _buildJoke('null_ts').copyWith(publicTimestamp: null),
          ),
        ];

        final provider = FutureProvider(
          (ref) => filterJokes(ref, jokes, filterViewed: true),
        );

        final result = await container.read(provider.future);

        expect(result, isEmpty);
        verify(() => mockUsage.getUnviewedJokeIds(any())).called(1);
      },
    );
  });
}
