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

import '../../../test_helpers/analytics_mocks.dart';
import '../../../test_helpers/firebase_mocks.dart';

// Mock classes using mocktail
class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class MockJokeReactionsService extends Mock implements JokeReactionsService {}

void main() {
  group('Providers Tests', () {
    late MockJokeRepository mockJokeRepository;
    late MockJokeCloudFunctionService mockCloudFunctionService;

    setUpAll(() {
      registerAnalyticsFallbackValues();
    });

    setUp(() {
      mockJokeRepository = MockJokeRepository();
      mockCloudFunctionService = MockJokeCloudFunctionService();
    });

    group('jokesProvider', () {
      test('should return stream of jokes from repository', () async {
        // arrange
        const joke1 = Joke(
          id: '1',
          setupText: 'Setup 1',
          punchlineText: 'Punchline 1',
        );
        const joke2 = Joke(
          id: '2',
          setupText: 'Setup 2',
          punchlineText: 'Punchline 2',
        );
        final jokesStream = Stream.value([joke1, joke2]);

        when(
          () => mockJokeRepository.getJokes(),
        ).thenAnswer((_) => jokesStream);

        // act
        final container = ProviderContainer(
          overrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        );

        final result = await container.read(jokesProvider.future);

        // assert
        expect(result, [joke1, joke2]);
        verify(() => mockJokeRepository.getJokes()).called(1);

        container.dispose();
      });
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

      group('hasUserReactionProvider', () {
        test('should return correct reaction status', () async {
          // arrange
          const jokeId = 'test-joke';

          when(() => mockReactionsService.getAllUserReactions()).thenAnswer(
            (_) async => {
              jokeId: {JokeReactionType.save, JokeReactionType.thumbsUp},
            },
          );
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

          // Wait for jokeReactionsProvider to finish loading
          while (container.read(jokeReactionsProvider).isLoading) {
            await Future.delayed(const Duration(milliseconds: 10));
          }

          final hasSave = container.read(
            hasUserReactionProvider((
              jokeId: jokeId,
              reactionType: JokeReactionType.save,
            )),
          );
          final hasThumbsUp = container.read(
            hasUserReactionProvider((
              jokeId: jokeId,
              reactionType: JokeReactionType.thumbsUp,
            )),
          );
          final hasThumbsDown = container.read(
            hasUserReactionProvider((
              jokeId: jokeId,
              reactionType: JokeReactionType.thumbsDown,
            )),
          );

          // assert
          expect(hasSave, isTrue);
          expect(hasThumbsUp, isTrue);
          expect(hasThumbsDown, isFalse);

          container.dispose();
        });
      });

      group('userReactionsForJokeProvider', () {
        test('should return correct reactions for joke', () async {
          // arrange
          const jokeId = 'test-joke';
          const expectedReactions = {
            JokeReactionType.save,
            JokeReactionType.thumbsUp,
          };

          when(
            () => mockReactionsService.getAllUserReactions(),
          ).thenAnswer((_) async => {jokeId: expectedReactions});
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

          // Wait for jokeReactionsProvider to finish loading
          while (container.read(jokeReactionsProvider).isLoading) {
            await Future.delayed(const Duration(milliseconds: 10));
          }

          final reactions = container.read(
            userReactionsForJokeProvider(jokeId),
          );

          // assert
          expect(reactions, equals(expectedReactions));

          container.dispose();
        });
      });
    });
  });

  // Add new test group for joke filter functionality
  group('JokeFilter Tests', () {
    test('JokeFilterState should have correct initial values', () {
      const state = JokeFilterState();
      expect(state.showUnratedOnly, false);
    });

    test('JokeFilterState copyWith should work correctly', () {
      const state = JokeFilterState();
      final newState = state.copyWith(showUnratedOnly: true);

      expect(newState.showUnratedOnly, true);
      expect(state.showUnratedOnly, false); // Original unchanged
    });

    test('JokeFilterNotifier should toggle unrated filter', () {
      final container = ProviderContainer();
      final notifier = container.read(jokeFilterProvider.notifier);

      expect(container.read(jokeFilterProvider).showUnratedOnly, false);

      notifier.toggleUnratedOnly();
      expect(container.read(jokeFilterProvider).showUnratedOnly, true);

      notifier.toggleUnratedOnly();
      expect(container.read(jokeFilterProvider).showUnratedOnly, false);

      container.dispose();
    });

    test('JokeFilterNotifier should set unrated filter value', () {
      final container = ProviderContainer();
      final notifier = container.read(jokeFilterProvider.notifier);

      expect(container.read(jokeFilterProvider).showUnratedOnly, false);

      notifier.setUnratedOnly(true);
      expect(container.read(jokeFilterProvider).showUnratedOnly, true);

      notifier.setUnratedOnly(false);
      expect(container.read(jokeFilterProvider).showUnratedOnly, false);

      container.dispose();
    });

    group('filteredJokesProvider', () {
      late MockJokeRepository mockJokeRepository;

      setUp(() {
        mockJokeRepository = MockJokeRepository();
      });

      test('should return all jokes when filter is off', () async {
        // arrange
        final testJokes = [
          const Joke(id: '1', setupText: 'setup1', punchlineText: 'punchline1'),
          const Joke(
            id: '2',
            setupText: 'setup2',
            punchlineText: 'punchline2',
            setupImageUrl: 'url1',
            punchlineImageUrl: 'url2',
            numThumbsUp: 5,
            numThumbsDown: 2,
          ),
        ];

        when(
          () => mockJokeRepository.getJokes(),
        ).thenAnswer((_) => Stream.value(testJokes));

        // act
        final container = ProviderContainer(
          overrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        );

        // Wait for the stream provider to emit data
        await container.read(jokesProvider.future);

        final result = container.read(filteredJokesProvider);

        // assert
        expect(result.hasValue, true);
        expect(result.value, testJokes);

        container.dispose();
      });

      test(
        'should filter to unrated jokes with images when filter is on',
        () async {
          // arrange
          final testJokes = [
            // No images - should be filtered out
            const Joke(
              id: '1',
              setupText: 'setup1',
              punchlineText: 'punchline1',
              numThumbsUp: 0,
              numThumbsDown: 0,
            ),
            // Has images and unrated - should be included
            const Joke(
              id: '2',
              setupText: 'setup2',
              punchlineText: 'punchline2',
              setupImageUrl: 'url1',
              punchlineImageUrl: 'url2',
              numThumbsUp: 0,
              numThumbsDown: 0,
            ),
            // Has images but rated - should be filtered out
            const Joke(
              id: '3',
              setupText: 'setup3',
              punchlineText: 'punchline3',
              setupImageUrl: 'url3',
              punchlineImageUrl: 'url4',
              numThumbsUp: 5,
              numThumbsDown: 0,
            ),
            // Has images but rated (thumbs down) - should be filtered out
            const Joke(
              id: '4',
              setupText: 'setup4',
              punchlineText: 'punchline4',
              setupImageUrl: 'url5',
              punchlineImageUrl: 'url6',
              numThumbsUp: 0,
              numThumbsDown: 3,
            ),
            // Has only one image - should be filtered out
            const Joke(
              id: '5',
              setupText: 'setup5',
              punchlineText: 'punchline5',
              setupImageUrl: 'url7',
              numThumbsUp: 0,
              numThumbsDown: 0,
            ),
            // Empty image URLs - should be filtered out
            const Joke(
              id: '6',
              setupText: 'setup6',
              punchlineText: 'punchline6',
              setupImageUrl: '',
              punchlineImageUrl: '',
              numThumbsUp: 0,
              numThumbsDown: 0,
            ),
          ];

          when(
            () => mockJokeRepository.getJokes(),
          ).thenAnswer((_) => Stream.value(testJokes));

          // act
          final container = ProviderContainer(
            overrides: [
              jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
            ],
          );

          // Wait for the stream provider to emit data
          await container.read(jokesProvider.future);

          // Turn on the filter
          container.read(jokeFilterProvider.notifier).setUnratedOnly(true);

          final result = container.read(filteredJokesProvider);

          // assert
          expect(result.hasValue, true);
          expect(result.value?.length, 1);
          expect(
            result.value?.first.id,
            '2',
          ); // Only joke 2 should pass the filter

          container.dispose();
        },
      );

      test('should handle loading state correctly', () async {
        // arrange
        when(() => mockJokeRepository.getJokes()).thenAnswer(
          (_) => Stream<List<Joke>>.empty(),
        ); // Empty stream simulates loading

        // act
        final container = ProviderContainer(
          overrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        );

        final asyncValue = container.read(jokesProvider);
        final result = container.read(filteredJokesProvider);

        // assert
        expect(asyncValue.isLoading, true);
        expect(result.isLoading, true);

        container.dispose();
      });

      test('should handle error state correctly', () async {
        // arrange
        const error = 'Test error';

        when(
          () => mockJokeRepository.getJokes(),
        ).thenAnswer((_) => Stream<List<Joke>>.error(error));

        // act
        final container = ProviderContainer(
          overrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        );

        // Try to read the jokesProvider to trigger the error
        try {
          await container.read(jokesProvider.future);
        } catch (e) {
          // Expected to fail
        }

        final result = container.read(filteredJokesProvider);

        // assert
        expect(result.hasError, true);
        expect(result.error, error);

        container.dispose();
      });

      test('popular-only sorts by (shares*10 + saves) descending', () async {
        // arrange
        final testJokes = [
          const Joke(
            id: 'a',
            setupText: 'Sa',
            punchlineText: 'Pa',
            numSaves: 0,
            numShares: 1, // score 10
          ),
          const Joke(
            id: 'b',
            setupText: 'Sb',
            punchlineText: 'Pb',
            numSaves: 11,
            numShares: 0, // score 11
          ),
          const Joke(
            id: 'c',
            setupText: 'Sc',
            punchlineText: 'Pc',
            numSaves: 2,
            numShares: 1, // score 12
          ),
        ];

        when(
          () => mockJokeRepository.getJokes(),
        ).thenAnswer((_) => Stream.value(testJokes));

        final container = ProviderContainer(
          overrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        );

        // Wait for jokes to load
        await container.read(jokesProvider.future);

        // Enable popular filter
        container.read(jokeFilterProvider.notifier).setPopularOnly(true);

        final result = container.read(filteredJokesProvider);
        expect(result.hasValue, true);
        final ids = result.value!.map((j) => j.id).toList();
        expect(ids, ['c', 'b', 'a']);

        container.dispose();
      });

      test(
        'unscheduled + popular filters combine and then sort by score',
        () async {
          // arrange
          final a = const Joke(
            id: 'a',
            setupText: 'Sa',
            punchlineText: 'Pa',
            numSaves: 0,
            numShares: 1, // 10
          );
          final b = const Joke(
            id: 'b',
            setupText: 'Sb',
            punchlineText: 'Pb',
            numSaves: 11,
            numShares: 0, // 11 (but scheduled -> excluded)
          );
          final c = const Joke(
            id: 'c',
            setupText: 'Sc',
            punchlineText: 'Pc',
            numSaves: 2,
            numShares: 1, // 12
          );

          when(
            () => mockJokeRepository.getJokes(),
          ).thenAnswer((_) => Stream.value([a, b, c]));

          final container = ProviderContainer(
            overrides: [
              jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
              // Override schedule provider to mark 'b' as scheduled
              monthlyJokesWithDateProvider.overrideWith(
                (ref) => Stream.value([JokeWithDate(joke: b)]),
              ),
            ],
          );

          // Wait for jokes to load
          await container.read(jokesProvider.future);

          // Enable unscheduled and popular filters
          container.read(jokeFilterProvider.notifier).setUnscheduledOnly(true);
          container.read(jokeFilterProvider.notifier).setPopularOnly(true);

          // Ensure schedule data is ready before reading filtered provider
          await container.read(monthlyJokesWithDateProvider.future);

          final result = container.read(filteredJokesProvider);
          expect(result.hasValue, true);
          final ids = result.value!.map((j) => j.id).toList();
          // 'b' excluded due to schedule; 'c' (12) before 'a' (10)
          expect(ids, ['c', 'a']);

          container.dispose();
        },
      );
    });
  });

  group('Search Providers', () {
    late MockJokeRepository mockJokeRepository;
    late MockJokeCloudFunctionService mockCloudFunctionService;

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
      final ids = await container.read(searchResultIdsProvider.future);
      expect(ids, isEmpty);
      container.dispose();
    });

    test('searchResultsProvider preserves order and applies filters', () async {
      // Arrange: search returns ids in a specific order
      when(
        () => mockCloudFunctionService.searchJokes(
          searchQuery: any(named: 'searchQuery'),
        ),
      ).thenAnswer((_) async => ['c', 'a', 'b']);

      // Repository returns all three jokes
      when(() => mockJokeRepository.getJokesByIds(['c', 'a', 'b'])).thenAnswer(
        (_) async => const [
          Joke(
            id: 'a',
            setupText: 'Sa',
            punchlineText: 'Pa',
            numSaves: 0,
            numShares: 1,
          ),
          Joke(
            id: 'b',
            setupText: 'Sb',
            punchlineText: 'Pb',
            numSaves: 11,
            numShares: 0,
          ),
          Joke(
            id: 'c',
            setupText: 'Sc',
            punchlineText: 'Pc',
            numSaves: 2,
            numShares: 1,
          ),
        ],
      );

      final container = ProviderContainer(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(
          additionalOverrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
            jokeCloudFunctionServiceProvider.overrideWithValue(
              mockCloudFunctionService,
            ),
            // No schedule data needed for this test
          ],
        ),
      );

      // Set a non-empty query
      container.read(searchQueryProvider.notifier).state = 'abc';

      // Read results
      final results = await container.read(searchResultsProvider.future);
      // Should preserve order from ids: c, a, b (before popular filter)
      expect(results.map((j) => j.id).toList(), ['c', 'a', 'b']);

      // Now enable popular filter (will sort by score)
      container.read(jokeFilterProvider.notifier).setPopularOnly(true);
      final resultsAfterFilter = await container.read(
        searchResultsProvider.future,
      );
      expect(resultsAfterFilter.map((j) => j.id).toList(), ['c', 'b', 'a']);

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
