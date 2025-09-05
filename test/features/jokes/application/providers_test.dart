import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_search_result.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

import '../../../test_helpers/analytics_mocks.dart';
import '../../../test_helpers/firebase_mocks.dart';

// Mock classes using mocktail
class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class MockJokeReactionsService extends Mock implements JokeReactionsService {}

void main() {
  group('Providers Tests', () {
    late MockJokeCloudFunctionService mockCloudFunctionService;

    setUpAll(() {
      registerAnalyticsFallbackValues();
      // Fallbacks for new enums used with any(named: ...)
      registerFallbackValue(MatchMode.tight);
      registerFallbackValue(SearchScope.userJokeSearch);
    });

    setUp(() {
      mockCloudFunctionService = MockJokeCloudFunctionService();
    });

    group('jokePopulationProvider', () {
      test('populateJoke should update state correctly on success', () async {
        // arrange
        const jokeId = 'test-joke-id';
        final successResponse = {
          'success': true,
          'data': {'message': 'Success'},
        };

        when(
          () => mockCloudFunctionService.populateJoke(
            jokeId,
            imagesOnly: any(named: 'imagesOnly'),
          ),
        ).thenAnswer((_) async => successResponse);

        // act
        final container = ProviderContainer(
          overrides: [
            jokeCloudFunctionServiceProvider.overrideWithValue(
              mockCloudFunctionService,
            ),
          ],
        );

        final notifier = container.read(jokePopulationProvider.notifier);

        // Call populateJoke
        await notifier.populateJoke(jokeId);

        // assert
        final state = container.read(jokePopulationProvider);
        expect(state.populatingJokes, isEmpty);
        expect(state.error, isNull);

        verify(
          () => mockCloudFunctionService.populateJoke(
            jokeId,
            imagesOnly: any(named: 'imagesOnly'),
          ),
        ).called(1);

        container.dispose();
      });

      test('populateJoke should update state correctly on failure', () async {
        // arrange
        const jokeId = 'test-joke-id';
        final failureResponse = {
          'success': false,
          'error': 'Test error message',
        };

        when(
          () => mockCloudFunctionService.populateJoke(
            jokeId,
            imagesOnly: any(named: 'imagesOnly'),
          ),
        ).thenAnswer((_) async => failureResponse);

        // act
        final container = ProviderContainer(
          overrides: [
            jokeCloudFunctionServiceProvider.overrideWithValue(
              mockCloudFunctionService,
            ),
          ],
        );

        final notifier = container.read(jokePopulationProvider.notifier);

        // Call populateJoke
        await notifier.populateJoke(jokeId);

        // assert
        final state = container.read(jokePopulationProvider);
        expect(state.populatingJokes, isEmpty);
        expect(state.error, 'Test error message');

        verify(
          () => mockCloudFunctionService.populateJoke(
            jokeId,
            imagesOnly: any(named: 'imagesOnly'),
          ),
        ).called(1);

        container.dispose();
      });
    });

    group('jokeReactionsProvider', () {
      late MockJokeReactionsService mockReactionsService;

      setUp(() {
        mockReactionsService = MockJokeReactionsService();
      });

      group('toggleReaction - thumbs exclusivity', () {
        test('should remove thumbsDown when adding thumbsUp', () async {
          // arrange
          const jokeId = 'test-joke';

          // Mock initial state: user already has thumbsDown
          when(() => mockReactionsService.getAllUserReactions()).thenAnswer(
            (_) async => {
              jokeId: {JokeReactionType.thumbsDown},
            },
          );
          when(
            () => mockReactionsService.getSavedJokeIds(),
          ).thenAnswer((_) async => <String>[]);

          // Mock service calls
          when(
            () => mockReactionsService.removeUserReaction(
              jokeId,
              JokeReactionType.thumbsDown,
            ),
          ).thenAnswer((_) async {});
          when(
            () => mockReactionsService.toggleUserReaction(
              jokeId,
              JokeReactionType.thumbsUp,
            ),
          ).thenAnswer((_) async => true); // returns true when adding

          // act
          final container = ProviderContainer(
            overrides: [
              jokeReactionsServiceProvider.overrideWithValue(
                mockReactionsService,
              ),
            ],
          );

          final notifier = container.read(jokeReactionsProvider.notifier);

          // Wait for initial load to complete
          await Future.delayed(const Duration(milliseconds: 10));

          // Toggle thumbs up
          await notifier.toggleReaction(
            jokeId,
            JokeReactionType.thumbsUp,
            jokeContext: 'test',
          );

          // assert
          verify(
            () => mockReactionsService.removeUserReaction(
              jokeId,
              JokeReactionType.thumbsDown,
            ),
          ).called(1);

          verify(
            () => mockReactionsService.toggleUserReaction(
              jokeId,
              JokeReactionType.thumbsUp,
            ),
          ).called(1);

          container.dispose();
        });

        test('should remove thumbsUp when adding thumbsDown', () async {
          // arrange
          const jokeId = 'test-joke';

          // Mock initial state: user already has thumbsUp
          when(() => mockReactionsService.getAllUserReactions()).thenAnswer(
            (_) async => {
              jokeId: {JokeReactionType.thumbsUp},
            },
          );
          when(
            () => mockReactionsService.getSavedJokeIds(),
          ).thenAnswer((_) async => <String>[]);

          // Mock service calls
          when(
            () => mockReactionsService.removeUserReaction(
              jokeId,
              JokeReactionType.thumbsUp,
            ),
          ).thenAnswer((_) async {});
          when(
            () => mockReactionsService.toggleUserReaction(
              jokeId,
              JokeReactionType.thumbsDown,
            ),
          ).thenAnswer((_) async => true); // returns true when adding

          // act
          final container = ProviderContainer(
            overrides: [
              jokeReactionsServiceProvider.overrideWithValue(
                mockReactionsService,
              ),
            ],
          );

          final notifier = container.read(jokeReactionsProvider.notifier);

          // Wait for initial load to complete
          await Future.delayed(const Duration(milliseconds: 10));

          // Toggle thumbs down
          await notifier.toggleReaction(
            jokeId,
            JokeReactionType.thumbsDown,
            jokeContext: 'test',
          );

          // assert
          verify(
            () => mockReactionsService.removeUserReaction(
              jokeId,
              JokeReactionType.thumbsUp,
            ),
          ).called(1);

          verify(
            () => mockReactionsService.toggleUserReaction(
              jokeId,
              JokeReactionType.thumbsDown,
            ),
          ).called(1);

          container.dispose();
        });

        test(
          'should handle opposite reaction removal when toggling thumbs',
          () async {
            // arrange
            const jokeId = 'test-joke';

            // Mock initial state: user already has thumbsUp
            when(() => mockReactionsService.getAllUserReactions()).thenAnswer(
              (_) async => {
                jokeId: {JokeReactionType.thumbsUp},
              },
            );
            when(
              () => mockReactionsService.getSavedJokeIds(),
            ).thenAnswer((_) async => <String>[]);

            // Mock service calls
            when(
              () => mockReactionsService.removeUserReaction(
                jokeId,
                JokeReactionType.thumbsUp,
              ),
            ).thenAnswer((_) async {});
            when(
              () => mockReactionsService.toggleUserReaction(
                jokeId,
                JokeReactionType.thumbsDown,
              ),
            ).thenAnswer((_) async => true); // returns true when adding

            // act
            final container = ProviderContainer(
              overrides: [
                jokeReactionsServiceProvider.overrideWithValue(
                  mockReactionsService,
                ),
              ],
            );

            final notifier = container.read(jokeReactionsProvider.notifier);

            // Wait for initial load to complete
            await Future.delayed(const Duration(milliseconds: 10));

            // Toggle thumbs down (should remove thumbs up first)
            await notifier.toggleReaction(
              jokeId,
              JokeReactionType.thumbsDown,
              jokeContext: 'test',
            );

            // assert
            verify(
              () => mockReactionsService.removeUserReaction(
                jokeId,
                JokeReactionType.thumbsUp,
              ),
            ).called(1);

            verify(
              () => mockReactionsService.toggleUserReaction(
                jokeId,
                JokeReactionType.thumbsDown,
              ),
            ).called(1);

            container.dispose();
          },
        );
      });

      group('toggleReaction - non-thumbs reactions', () {
        test(
          'should handle save reaction toggle without removing opposite',
          () async {
            // arrange
            const jokeId = 'test-joke';

            // Mock initial state: no reactions
            when(
              () => mockReactionsService.getAllUserReactions(),
            ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});
            when(
              () => mockReactionsService.getSavedJokeIds(),
            ).thenAnswer((_) async => <String>[]);

            // Mock service calls
            when(
              () => mockReactionsService.toggleUserReaction(
                jokeId,
                JokeReactionType.save,
              ),
            ).thenAnswer((_) async => true); // returns true when adding

            // act
            final container = ProviderContainer(
              overrides: [
                jokeReactionsServiceProvider.overrideWithValue(
                  mockReactionsService,
                ),
              ],
            );

            final notifier = container.read(jokeReactionsProvider.notifier);

            // Wait for initial load to complete
            await Future.delayed(const Duration(milliseconds: 10));

            // Toggle save
            await notifier.toggleReaction(
              jokeId,
              JokeReactionType.save,
              jokeContext: 'test',
            );

            // assert
            verify(
              () => mockReactionsService.toggleUserReaction(
                jokeId,
                JokeReactionType.save,
              ),
            ).called(1);

            // Should not call removeUserReaction for any reaction type
            verifyNever(
              () => mockReactionsService.removeUserReaction(any(), any()),
            );

            container.dispose();
          },
        );

        test(
          'should handle share reaction toggle without removing opposite',
          () async {
            // arrange
            const jokeId = 'test-joke';

            // Mock initial state: no reactions
            when(
              () => mockReactionsService.getAllUserReactions(),
            ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});
            when(
              () => mockReactionsService.getSavedJokeIds(),
            ).thenAnswer((_) async => <String>[]);

            // Mock service calls
            when(
              () => mockReactionsService.toggleUserReaction(
                jokeId,
                JokeReactionType.share,
              ),
            ).thenAnswer((_) async => true); // returns true when adding

            // act
            final container = ProviderContainer(
              overrides: [
                jokeReactionsServiceProvider.overrideWithValue(
                  mockReactionsService,
                ),
              ],
            );

            final notifier = container.read(jokeReactionsProvider.notifier);

            // Wait for initial load to complete
            await Future.delayed(const Duration(milliseconds: 10));

            // Toggle share
            await notifier.toggleReaction(
              jokeId,
              JokeReactionType.share,
              jokeContext: 'test',
            );

            // assert
            verify(
              () => mockReactionsService.toggleUserReaction(
                jokeId,
                JokeReactionType.share,
              ),
            ).called(1);

            // Should not call removeUserReaction for any reaction type
            verifyNever(
              () => mockReactionsService.removeUserReaction(any(), any()),
            );

            container.dispose();
          },
        );
      });

      group('toggleReaction - basic functionality', () {
        test(
          'should toggle reaction and update state optimistically',
          () async {
            // arrange
            const jokeId = 'test-joke';

            // Mock initial state: no reactions
            when(
              () => mockReactionsService.getAllUserReactions(),
            ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});
            when(
              () => mockReactionsService.getSavedJokeIds(),
            ).thenAnswer((_) async => <String>[]);

            // Mock service calls
            when(
              () => mockReactionsService.toggleUserReaction(
                jokeId,
                JokeReactionType.thumbsUp,
              ),
            ).thenAnswer((_) async => true); // returns true when adding

            // act
            final container = ProviderContainer(
              overrides: [
                jokeReactionsServiceProvider.overrideWithValue(
                  mockReactionsService,
                ),
              ],
            );

            final notifier = container.read(jokeReactionsProvider.notifier);

            // Wait for initial load to complete
            await Future.delayed(const Duration(milliseconds: 10));

            // Toggle thumbs up
            await notifier.toggleReaction(
              jokeId,
              JokeReactionType.thumbsUp,
              jokeContext: 'test',
            );

            // assert
            verify(
              () => mockReactionsService.toggleUserReaction(
                jokeId,
                JokeReactionType.thumbsUp,
              ),
            ).called(1);

            container.dispose();
          },
        );

        test(
          'should handle errors gracefully and revert optimistic updates',
          () async {
            // arrange
            const jokeId = 'test-joke';

            // Mock initial state: no reactions
            when(
              () => mockReactionsService.getAllUserReactions(),
            ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});
            when(
              () => mockReactionsService.getSavedJokeIds(),
            ).thenAnswer((_) async => <String>[]);

            // Mock service calls to throw error
            when(
              () => mockReactionsService.toggleUserReaction(
                jokeId,
                JokeReactionType.thumbsUp,
              ),
            ).thenThrow(Exception('Test error'));

            // act
            final container = ProviderContainer(
              overrides: [
                jokeReactionsServiceProvider.overrideWithValue(
                  mockReactionsService,
                ),
              ],
            );

            final notifier = container.read(jokeReactionsProvider.notifier);

            // Wait for initial load to complete
            await Future.delayed(const Duration(milliseconds: 10));

            // Toggle thumbs up (should handle error)
            await notifier.toggleReaction(
              jokeId,
              JokeReactionType.thumbsUp,
              jokeContext: 'test',
            );

            // assert
            final state = container.read(jokeReactionsProvider);
            expect(state.error, isNotNull);
            expect(state.error, contains('Failed to add Like'));

            container.dispose();
          },
        );
      });

      group('state management', () {
        test(
          'should initialize with empty reactions and load from service',
          () async {
            // arrange
            when(
              () => mockReactionsService.getAllUserReactions(),
            ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});
            when(
              () => mockReactionsService.getSavedJokeIds(),
            ).thenAnswer((_) async => <String>[]);

            // act
            final container = ProviderContainer(
              overrides: [
                jokeReactionsServiceProvider.overrideWithValue(
                  mockReactionsService,
                ),
              ],
            );

            // Wait for initial load
            await Future.delayed(const Duration(milliseconds: 10));

            final state = container.read(jokeReactionsProvider);

            // assert
            expect(state.userReactions, isEmpty);
            expect(state.isLoading, isTrue); // Still loading since it's async
            expect(state.error, isNull);

            verify(() => mockReactionsService.getAllUserReactions()).called(1);

            container.dispose();
          },
        );

        test('should handle loading state correctly', () async {
          // arrange
          when(
            () => mockReactionsService.getAllUserReactions(),
          ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});
          when(
            () => mockReactionsService.getSavedJokeIds(),
          ).thenAnswer((_) async => <String>[]);

          // act
          final container = ProviderContainer(
            overrides: [
              jokeReactionsServiceProvider.overrideWithValue(
                mockReactionsService,
              ),
            ],
          );

          // Initial state should show loading
          final initialState = container.read(jokeReactionsProvider);
          expect(initialState.isLoading, isTrue);

          container.dispose();
        });
      });
    });
  });

  // Add new test group for joke filter functionality
  group('JokeFilter Tests', () {
    test('JokeFilterState should have correct initial values', () {
      const state = JokeFilterState();
      expect(state.selectedStates, isEmpty);
      expect(state.showPopularOnly, false);
      expect(state.hasStateFilter, false);
    });

    test('JokeFilterState copyWith should work correctly', () {
      const state = JokeFilterState();
      final newState = state.copyWith(selectedStates: {JokeState.approved});

      expect(newState.selectedStates, {JokeState.approved});
      expect(state.selectedStates, isEmpty); // Original unchanged
      expect(newState.hasStateFilter, true);
    });

    test('JokeFilterNotifier should add and remove states', () {
      final container = ProviderContainer();
      final notifier = container.read(jokeFilterProvider.notifier);

      expect(container.read(jokeFilterProvider).selectedStates, isEmpty);

      notifier.addState(JokeState.approved);
      expect(container.read(jokeFilterProvider).selectedStates, {
        JokeState.approved,
      });

      notifier.addState(JokeState.published);
      expect(container.read(jokeFilterProvider).selectedStates, {
        JokeState.approved,
        JokeState.published,
      });

      notifier.removeState(JokeState.approved);
      expect(container.read(jokeFilterProvider).selectedStates, {
        JokeState.published,
      });

      container.dispose();
    });

    test('JokeFilterNotifier should toggle states', () {
      final container = ProviderContainer();
      final notifier = container.read(jokeFilterProvider.notifier);

      expect(container.read(jokeFilterProvider).selectedStates, isEmpty);

      notifier.toggleState(JokeState.approved);
      expect(container.read(jokeFilterProvider).selectedStates, {
        JokeState.approved,
      });

      notifier.toggleState(JokeState.approved);
      expect(container.read(jokeFilterProvider).selectedStates, isEmpty);

      container.dispose();
    });

    test('JokeFilterNotifier should set selected states', () {
      final container = ProviderContainer();
      final notifier = container.read(jokeFilterProvider.notifier);

      expect(container.read(jokeFilterProvider).selectedStates, isEmpty);

      notifier.setSelectedStates({JokeState.approved, JokeState.rejected});
      expect(container.read(jokeFilterProvider).selectedStates, {
        JokeState.approved,
        JokeState.rejected,
      });

      notifier.clearStates();
      expect(container.read(jokeFilterProvider).selectedStates, isEmpty);

      container.dispose();
    });

    // removed tests for filteredJokesProvider (provider deleted)
  });

  group('filteredJokeIdsProvider', () {
    late MockJokeRepository mockJokeRepository;

    setUp(() {
      mockJokeRepository = MockJokeRepository();
    });

    test('returns ids from repository with no filters', () async {
      when(
        () => mockJokeRepository.getFilteredJokeIds(
          states: any(named: 'states'),
          popularOnly: any(named: 'popularOnly'),
        ),
      ).thenAnswer((_) async => ['a', 'b']);

      final container = ProviderContainer(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
        ],
      );

      final result = await container.read(filteredJokeIdsProvider.future);
      expect(result, ['a', 'b']);
      container.dispose();
    });

    test('passes selected states and popularOnly to repository', () async {
      when(
        () => mockJokeRepository.getFilteredJokeIds(
          states: {JokeState.approved, JokeState.published},
          popularOnly: true,
        ),
      ).thenAnswer((_) async => ['x']);

      final container = ProviderContainer(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
        ],
      );

      // Set filter state
      container.read(jokeFilterProvider.notifier).setSelectedStates({
        JokeState.approved,
        JokeState.published,
      });
      container.read(jokeFilterProvider.notifier).setPopularOnly(true);

      final result = await container.read(filteredJokeIdsProvider.future);
      expect(result, ['x']);

      verify(
        () => mockJokeRepository.getFilteredJokeIds(
          states: {JokeState.approved, JokeState.published},
          popularOnly: true,
        ),
      ).called(1);
      container.dispose();
    });
  });

  group('Search Providers', () {
    late MockJokeRepository mockJokeRepository;
    late MockJokeCloudFunctionService mockCloudFunctionService;

    setUpAll(() {
      // Needed for any(named: 'matchMode') with mocktail
      registerFallbackValue(MatchMode.tight);
    });

    setUp(() {
      mockJokeRepository = MockJokeRepository();
      mockCloudFunctionService = MockJokeCloudFunctionService();
    });

    test('searchResultIdsProvider returns empty when query empty', () async {
      final container = ProviderContainer(
        overrides: [
          jokeCloudFunctionServiceProvider.overrideWithValue(
            mockCloudFunctionService,
          ),
        ],
      );

      // default query is ''
      final results = await container.read(
        searchResultIdsProvider(SearchScope.userJokeSearch).future,
      );
      expect(results, isEmpty);
      container.dispose();
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
        ),
      ).thenAnswer(
        (_) async => const [JokeSearchResult(id: 'x', vectorDistance: 0.1)],
      );

      final container = ProviderContainer(
        overrides: [
          jokeCloudFunctionServiceProvider.overrideWithValue(
            mockCloudFunctionService,
          ),
        ],
      );

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
        ),
      ).called(1);

      container.dispose();
    });

    test(
      'search query excludeJokeIds defaults to empty and can be overridden',
      () async {
        final container = ProviderContainer(
          overrides: [
            jokeCloudFunctionServiceProvider.overrideWithValue(
              mockCloudFunctionService,
            ),
          ],
        );
        addTearDown(container.dispose);

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

        final container = ProviderContainer(
          overrides: FirebaseMocks.getFirebaseProviderOverrides(
            additionalOverrides: [
              jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
              jokeCloudFunctionServiceProvider.overrideWithValue(
                mockCloudFunctionService,
              ),
            ],
          ),
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
        ),
      ).thenAnswer(
        (_) async => const [JokeSearchResult(id: 'j1', vectorDistance: 0.42)],
      );

      final stream = StreamController<Joke?>();
      when(
        () => mockJokeRepository.getJokeByIdStream('j1'),
      ).thenAnswer((_) => stream.stream);

      final container = ProviderContainer(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(
          additionalOverrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
            jokeCloudFunctionServiceProvider.overrideWithValue(
              mockCloudFunctionService,
            ),
          ],
        ),
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

  group('savedJokesProvider', () {
    test('provides saved jokes in SharedPreferences order', () async {
      final mockReactionsService = MockJokeReactionsService();
      final mockJokeRepository = MockJokeRepository();

      // Setup mock to return saved joke IDs in specific order
      when(
        () => mockReactionsService.getSavedJokeIds(),
      ).thenAnswer((_) async => ['joke3', 'joke1', 'joke2']);
      when(() => mockReactionsService.getAllUserReactions()).thenAnswer(
        (_) async => {
          'joke3': {JokeReactionType.save},
          'joke1': {JokeReactionType.save},
          'joke2': {JokeReactionType.save},
        },
      );

      // Setup mock repository to return jokes (one without images)
      when(
        () => mockJokeRepository.getJokesByIds(['joke3', 'joke1', 'joke2']),
      ).thenAnswer(
        (_) async => [
          Joke(
            id: 'joke1',
            setupText: 'Setup 1',
            punchlineText: 'Punchline 1',
            setupImageUrl: 'setup1.jpg',
            punchlineImageUrl: 'punchline1.jpg',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
          Joke(
            id: 'joke2',
            setupText: 'Setup 2',
            punchlineText: 'Punchline 2',
            setupImageUrl: 'setup2.jpg',
            punchlineImageUrl: 'punchline2.jpg',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
          Joke(
            id: 'joke3',
            setupText: 'Setup 3',
            punchlineText: 'Punchline 3',
            setupImageUrl: 'setup3.jpg',
            punchlineImageUrl: 'punchline3.jpg',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
        ],
      );

      final container = ProviderContainer(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(
          additionalOverrides: [
            jokeReactionsServiceProvider.overrideWithValue(
              mockReactionsService,
            ),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        ),
      );

      // Wait for jokeReactionsProvider to finish loading
      while (container.read(jokeReactionsProvider).isLoading) {
        await Future.delayed(const Duration(milliseconds: 10));
      }

      final savedJokes = await container.read(savedJokesProvider.future);

      // Verify that jokes are returned in the same order as stored in SharedPreferences
      expect(savedJokes.length, equals(3));
      expect(savedJokes[0].joke.id, equals('joke3'));
      expect(savedJokes[1].joke.id, equals('joke1'));
      expect(savedJokes[2].joke.id, equals('joke2'));

      container.dispose();
    });

    test('filters out jokes without images', () async {
      final mockReactionsService = MockJokeReactionsService();
      final mockJokeRepository = MockJokeRepository();

      // Setup mock to return saved joke IDs
      when(
        () => mockReactionsService.getSavedJokeIds(),
      ).thenAnswer((_) async => ['joke1', 'joke2', 'joke3']);
      when(() => mockReactionsService.getAllUserReactions()).thenAnswer(
        (_) async => {
          'joke1': {JokeReactionType.save},
          'joke2': {JokeReactionType.save},
          'joke3': {JokeReactionType.save},
        },
      );

      // Setup mock repository to return jokes (one without images)
      when(
        () => mockJokeRepository.getJokesByIds(['joke1', 'joke2', 'joke3']),
      ).thenAnswer(
        (_) async => [
          Joke(
            id: 'joke1',
            setupText: 'Setup 1',
            punchlineText: 'Punchline 1',
            setupImageUrl: 'setup1.jpg',
            punchlineImageUrl: 'punchline1.jpg',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
          Joke(
            id: 'joke2',
            setupText: 'Setup 2',
            punchlineText: 'Punchline 2',
            setupImageUrl: null, // No setup image
            punchlineImageUrl: 'punchline2.jpg',
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
          Joke(
            id: 'joke3',
            setupText: 'Setup 3',
            punchlineText: 'Punchline 3',
            setupImageUrl: 'setup3.jpg',
            punchlineImageUrl: null, // No punchline image
            numThumbsUp: 0,
            numThumbsDown: 0,
          ),
        ],
      );

      final container = ProviderContainer(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(
          additionalOverrides: [
            jokeReactionsServiceProvider.overrideWithValue(
              mockReactionsService,
            ),
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        ),
      );

      // Wait for jokeReactionsProvider to finish loading
      while (container.read(jokeReactionsProvider).isLoading) {
        await Future.delayed(const Duration(milliseconds: 10));
      }

      final savedJokes = await container.read(savedJokesProvider.future);

      // Verify that only jokes with both images are included
      expect(savedJokes.length, equals(1));
      expect(savedJokes[0].joke.id, equals('joke1'));

      container.dispose();
    });

    test('handles empty saved jokes list', () async {
      final mockReactionsService = MockJokeReactionsService();

      // Setup mock to return empty list
      when(
        () => mockReactionsService.getSavedJokeIds(),
      ).thenAnswer((_) async => <String>[]);
      when(
        () => mockReactionsService.getAllUserReactions(),
      ).thenAnswer((_) async => <String, Set<JokeReactionType>>{});

      final container = ProviderContainer(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(
          additionalOverrides: [
            jokeReactionsServiceProvider.overrideWithValue(
              mockReactionsService,
            ),
          ],
        ),
      );

      // Wait for jokeReactionsProvider to finish loading
      while (container.read(jokeReactionsProvider).isLoading) {
        await Future.delayed(const Duration(milliseconds: 10));
      }

      final savedJokes = await container.read(savedJokesProvider.future);

      // Verify that empty list is returned
      expect(savedJokes, isEmpty);

      container.dispose();
    });
  });
}
