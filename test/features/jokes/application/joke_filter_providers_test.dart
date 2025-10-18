import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_filter_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

void main() {
  group('JokeFilter Tests', () {
    setUpAll(() {
      // Fallbacks for enums used with any(named: ...)
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

    test('JokeFilterNotifier should handle popular only toggle', () {
      final container = ProviderContainer();
      final notifier = container.read(jokeFilterProvider.notifier);

      expect(container.read(jokeFilterProvider).showPopularOnly, false);

      notifier.togglePopularOnly();
      expect(container.read(jokeFilterProvider).showPopularOnly, true);

      notifier.togglePopularOnly();
      expect(container.read(jokeFilterProvider).showPopularOnly, false);

      container.dispose();
    });

    test('JokeFilterNotifier should set popular only value', () {
      final container = ProviderContainer();
      final notifier = container.read(jokeFilterProvider.notifier);

      expect(container.read(jokeFilterProvider).showPopularOnly, false);

      notifier.setPopularOnly(true);
      expect(container.read(jokeFilterProvider).showPopularOnly, true);

      notifier.setPopularOnly(false);
      expect(container.read(jokeFilterProvider).showPopularOnly, false);

      container.dispose();
    });
  });
}
