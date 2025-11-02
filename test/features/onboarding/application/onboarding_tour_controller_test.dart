import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/onboarding_tour_state_store.dart';
import 'package:snickerdoodle/src/features/onboarding/application/onboarding_tour_controller.dart';

class _MockOnboardingTourStateStore extends Mock
    implements OnboardingTourStateStore {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late _MockOnboardingTourStateStore mockStore;
  late ProviderContainer container;

  setUp(() {
    mockStore = _MockOnboardingTourStateStore();
    container = ProviderContainer(overrides: [
      onboardingTourStateStoreProvider.overrideWithValue(mockStore),
    ]);
  });

  tearDown(() {
    container.dispose();
  });

  test('build resolves to true when tour not completed', () async {
    when(() => mockStore.hasCompleted()).thenAnswer((_) async => false);

    final shouldShow =
        await container.read(onboardingTourControllerProvider.future);

    expect(shouldShow, isTrue);
  });

  test('build resolves to false when tour completed', () async {
    when(() => mockStore.hasCompleted()).thenAnswer((_) async => true);

    final shouldShow =
        await container.read(onboardingTourControllerProvider.future);

    expect(shouldShow, isFalse);
  });

  test('markTourCompleted updates store and state', () async {
    when(() => mockStore.hasCompleted()).thenAnswer((_) async => false);
    when(() => mockStore.markCompleted()).thenAnswer((_) async {});

    await container.read(onboardingTourControllerProvider.future);

    await container
        .read(onboardingTourControllerProvider.notifier)
        .markTourCompleted();

    verify(() => mockStore.markCompleted()).called(1);

    expect(
      container.read(onboardingTourControllerProvider),
      const AsyncData(false),
    );
  });

  test('setShouldShowTour toggles completion flag and state', () async {
    when(() => mockStore.hasCompleted()).thenAnswer((_) async => false);
    when(() => mockStore.setCompleted(any())).thenAnswer((_) async {});

    await container.read(onboardingTourControllerProvider.future);

    await container
        .read(onboardingTourControllerProvider.notifier)
        .setShouldShowTour(true);

    verify(() => mockStore.setCompleted(false)).called(1);
    expect(
      container.read(onboardingTourControllerProvider),
      const AsyncData(true),
    );
  });
}
