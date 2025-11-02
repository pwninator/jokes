import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/onboarding_tour_state_store.dart';

/// Coordinates whether the onboarding tour should be displayed.
class OnboardingTourController extends AutoDisposeAsyncNotifier<bool> {
  @override
  Future<bool> build() async {
    final store = ref.watch(onboardingTourStateStoreProvider);
    return _shouldShowTour(store);
  }

  Future<void> markTourCompleted() async {
    final store = ref.read(onboardingTourStateStoreProvider);
    await store.markCompleted();
    state = const AsyncData(false);
  }

  Future<void> setShouldShowTour(bool shouldShow) async {
    final store = ref.read(onboardingTourStateStoreProvider);
    await store.setCompleted(!shouldShow);
    state = AsyncData(shouldShow);
  }

  Future<void> refreshStatus() async {
    final store = ref.read(onboardingTourStateStoreProvider);
    state = const AsyncLoading();
    state = AsyncData(await _shouldShowTour(store));
  }

  Future<bool> _shouldShowTour(OnboardingTourStateStore store) async {
    final completed = await store.hasCompleted();
    return !completed;
  }
}

final onboardingTourControllerProvider =
    AutoDisposeAsyncNotifierProvider<OnboardingTourController, bool>(
      OnboardingTourController.new,
    );
