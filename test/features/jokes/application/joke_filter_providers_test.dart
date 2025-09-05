import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_filter_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

import '../../../test_helpers/analytics_mocks.dart';

// Mock classes using mocktail
class MockJokeRepository extends Mock implements JokeRepository {}

void main() {
  group('JokeFilter Tests', () {
    setUpAll(() {
      registerAnalyticsFallbackValues();
      // Fallbacks for new enums used with any(named: ...)
      registerFallbackValue(MatchMode.tight);
      registerFallbackValue(SearchScope.userJokeSearch);
    });

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
}
