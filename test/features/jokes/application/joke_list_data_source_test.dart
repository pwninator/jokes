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

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('filter helper functions', () {
    test('dedupeJokes keeps first occurrence of duplicate ids', () {
      final original = JokeWithDate(joke: _buildJoke('keep'), dataSource: 'a');
      final duplicate = JokeWithDate(joke: _buildJoke('keep'), dataSource: 'b');
      final other = JokeWithDate(joke: _buildJoke('other'), dataSource: 'c');

      final result = dedupeJokes([original, duplicate, other], {});

      expect(result, [original, other]);
    });

    test(
      'filterJokesWithImages keeps jokes that have both images populated',
      () {
        final hasImages = JokeWithDate(joke: _buildJoke('with-images'));
        final missingImages = JokeWithDate(
          joke: _buildJoke('without-images', hasImages: false),
        );
        final blankImages = JokeWithDate(
          joke: _buildJoke(
            'blank-images',
          ).copyWith(setupImageUrl: '', punchlineImageUrl: ''),
        );

        final result = filterJokesWithImages([
          hasImages,
          missingImages,
          blankImages,
        ]);

        expect(result, [hasImages]);
      },
    );

    test(
      'filterJokesByPublicTimestamp keeps only jokes at or before current time',
      () {
        final now = DateTime.utc(2025, 1, 10, 12);
        final timestampContainer = ProviderContainer(
          overrides: [clockProvider.overrideWithValue(() => now)],
        );
        addTearDown(timestampContainer.dispose);

        final past = JokeWithDate(
          joke: _buildJoke(
            'past',
            publicTimestamp: now.subtract(const Duration(days: 1)),
          ),
        );
        final atNow = JokeWithDate(
          joke: _buildJoke('at-now', publicTimestamp: now),
        );
        final future = JokeWithDate(
          joke: _buildJoke(
            'future',
            publicTimestamp: now.add(const Duration(minutes: 5)),
          ),
        );
        final noTimestamp = JokeWithDate(
          joke: Joke(
            id: 'no-ts',
            setupText: 'setup no-ts',
            punchlineText: 'punchline no-ts',
            setupImageUrl: 'setup_no-ts.png',
            punchlineImageUrl: 'punch_no-ts.png',
            state: JokeState.published,
            publicTimestamp: null,
          ),
        );

        final provider = Provider(
          (ref) => filterJokesByPublicTimestamp(ref, [
            past,
            atNow,
            future,
            noTimestamp,
          ]),
        );

        final result = timestampContainer.read(provider);

        expect(result, [past, atNow, noTimestamp]);
      },
    );

    test('filterViewedJokes returns only unviewed jokes', () async {
      final jokes = [
        JokeWithDate(joke: _buildJoke('a')),
        JokeWithDate(joke: _buildJoke('b')),
        JokeWithDate(joke: _buildJoke('c')),
      ];
      final mockUsageService = MockAppUsageService();
      when(() => mockUsageService.getUnviewedJokeIds(any())).thenAnswer((
        invocation,
      ) async {
        final ids = invocation.positionalArguments.first as List<String>;
        expect(ids, ['a', 'b', 'c']);
        return ['a', 'c'];
      });

      final viewedContainer = ProviderContainer(
        overrides: [
          appUsageServiceProvider.overrideWithValue(mockUsageService),
        ],
      );
      addTearDown(viewedContainer.dispose);

      final provider = FutureProvider((ref) => filterViewedJokes(ref, jokes));

      final result = await viewedContainer.read(provider.future);

      expect(result, [jokes.first, jokes.last]);
      verify(() => mockUsageService.getUnviewedJokeIds(any())).called(1);
    });

    test(
      'filterJokes applies dedupe, image, timestamp, and viewed filters together',
      () async {
        final now = DateTime.utc(2025, 1, 10);
        final keep = JokeWithDate(
          joke: _buildJoke(
            'keep',
            publicTimestamp: now.subtract(const Duration(days: 1)),
          ),
        );
        final duplicate = JokeWithDate(
          joke: _buildJoke(
            'keep',
            publicTimestamp: now.subtract(const Duration(hours: 2)),
          ),
          dataSource: 'duplicate',
        );
        final missingImages = JokeWithDate(
          joke: _buildJoke(
            'missing',
            publicTimestamp: now.subtract(const Duration(days: 2)),
            hasImages: false,
          ),
        );
        final future = JokeWithDate(
          joke: _buildJoke(
            'future',
            publicTimestamp: now.add(const Duration(days: 1)),
          ),
        );
        final viewed = JokeWithDate(
          joke: _buildJoke(
            'viewed',
            publicTimestamp: now.subtract(const Duration(hours: 3)),
          ),
        );

        final mockUsageService = MockAppUsageService();
        when(() => mockUsageService.getUnviewedJokeIds(any())).thenAnswer((
          invocation,
        ) async {
          final ids = invocation.positionalArguments.first as List<String>;
          expect(ids, ['keep', 'viewed']);
          return ['keep'];
        });

        final container = ProviderContainer(
          overrides: [
            appUsageServiceProvider.overrideWithValue(mockUsageService),
            clockProvider.overrideWithValue(() => now),
          ],
        );
        addTearDown(container.dispose);

        final provider = FutureProvider(
          (ref) => filterJokes(ref, [
            keep,
            duplicate,
            missingImages,
            future,
            viewed,
          ], filterViewed: true),
        );

        final result = await container.read(provider.future);

        expect(result, [keep]);
        verify(() => mockUsageService.getUnviewedJokeIds(any())).called(1);
      },
    );
  });
}
