import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

// State class for joke filter
class JokeFilterState {
  final Set<JokeState> selectedStates;
  final bool showPopularOnly; // saves + shares > 0

  const JokeFilterState({
    this.selectedStates = const {},
    this.showPopularOnly = false,
  });

  JokeFilterState copyWith({
    Set<JokeState>? selectedStates,
    bool? showPopularOnly,
  }) {
    return JokeFilterState(
      selectedStates: selectedStates ?? this.selectedStates,
      showPopularOnly: showPopularOnly ?? this.showPopularOnly,
    );
  }

  bool get hasStateFilter => selectedStates.isNotEmpty;
}

// Notifier for managing joke filter
class JokeFilterNotifier extends StateNotifier<JokeFilterState> {
  JokeFilterNotifier() : super(const JokeFilterState());

  void addState(JokeState state) {
    final newStates = Set<JokeState>.from(this.state.selectedStates)
      ..add(state);
    this.state = this.state.copyWith(selectedStates: newStates);
  }

  void removeState(JokeState state) {
    final newStates = Set<JokeState>.from(this.state.selectedStates)
      ..remove(state);
    this.state = this.state.copyWith(selectedStates: newStates);
  }

  void toggleState(JokeState state) {
    if (this.state.selectedStates.contains(state)) {
      removeState(state);
    } else {
      addState(state);
    }
  }

  void setSelectedStates(Set<JokeState> states) {
    state = state.copyWith(selectedStates: states);
  }

  void clearStates() {
    state = state.copyWith(selectedStates: const {});
  }

  void togglePopularOnly() {
    state = state.copyWith(showPopularOnly: !state.showPopularOnly);
  }

  void setPopularOnly(bool value) {
    state = state.copyWith(showPopularOnly: value);
  }
}

// Provider for joke filter notifier
final jokeFilterProvider =
    StateNotifierProvider<JokeFilterNotifier, JokeFilterState>((ref) {
      return JokeFilterNotifier();
    });

// Snapshot-only list of filtered joke IDs for admin management list
final filteredJokeIdsProvider = FutureProvider<List<String>>((ref) async {
  final repository = ref.watch(jokeRepositoryProvider);
  final filterState = ref.watch(jokeFilterProvider);
  return repository.getFilteredJokeIds(
    states: filterState.selectedStates,
    popularOnly: filterState.showPopularOnly,
  );
});
