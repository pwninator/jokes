import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

enum JokeAdminScoreFilter { none, popular, recent, best }

// State class for joke filter
class JokeFilterState {
  final Set<JokeState> selectedStates;
  final JokeAdminScoreFilter adminScoreFilter;

  const JokeFilterState({
    this.selectedStates = const {},
    this.adminScoreFilter = JokeAdminScoreFilter.none,
  });

  JokeFilterState copyWith({
    Set<JokeState>? selectedStates,
    JokeAdminScoreFilter? adminScoreFilter,
  }) {
    return JokeFilterState(
      selectedStates: selectedStates ?? this.selectedStates,
      adminScoreFilter: adminScoreFilter ?? this.adminScoreFilter,
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

  void toggleScoreFilter(JokeAdminScoreFilter filter) {
    final nextFilter = state.adminScoreFilter == filter
        ? JokeAdminScoreFilter.none
        : filter;
    state = state.copyWith(adminScoreFilter: nextFilter);
  }

  void setScoreFilter(JokeAdminScoreFilter filter) {
    state = state.copyWith(adminScoreFilter: filter);
  }
}

// Provider for joke filter notifier
final jokeFilterProvider =
    StateNotifierProvider<JokeFilterNotifier, JokeFilterState>((ref) {
      return JokeFilterNotifier();
    });
