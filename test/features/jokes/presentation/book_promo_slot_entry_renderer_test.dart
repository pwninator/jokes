import 'package:cloud_functions/cloud_functions.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/app/app_providers.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/core/providers/settings_providers.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_entries.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_entry_renderers.dart';

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockAppUsageService extends Mock implements AppUsageService {}

class _FakeRemoteConfigValues implements RemoteConfigValues {
  _FakeRemoteConfigValues(this.variant);

  final String variant;

  @override
  bool getBool(RemoteParam param) => false;

  @override
  double getDouble(RemoteParam param) => 0.0;

  @override
  int getInt(RemoteParam param) => 0;

  @override
  String getString(RemoteParam param) {
    if (param == RemoteParam.bookPromoCardVariant) {
      return variant;
    }
    return '';
  }

  @override
  T getEnum<T>(RemoteParam param) {
    final descriptor = remoteParams[param]!;
    return (descriptor.enumDefault ?? '') as T;
  }
}

class MockFirebaseFunctions extends Mock implements FirebaseFunctions {}

class _NoopPerformanceService implements PerformanceService {
  @override
  void dropNamedTrace({required TraceName name, String? key}) {}

  @override
  void putNamedTraceAttributes({
    required TraceName name,
    String? key,
    required Map<String, String> attributes,
  }) {}

  @override
  void startNamedTrace({
    required TraceName name,
    String? key,
    Map<String, String>? attributes,
  }) {}

  @override
  void stopNamedTrace({required TraceName name, String? key}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MockAnalyticsService mockAnalyticsService;
  late MockAppUsageService mockAppUsageService;
  late SharedPreferences sharedPreferences;
  late PerformanceService performanceService;
  late MockFirebaseFunctions mockFirebaseFunctions;
  final fixedNow = DateTime(2025, 2, 1);

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    sharedPreferences = await SharedPreferences.getInstance();
    mockAnalyticsService = MockAnalyticsService();
    mockAppUsageService = MockAppUsageService();
    performanceService = _NoopPerformanceService();
    mockFirebaseFunctions = MockFirebaseFunctions();
  });

  testWidgets('falls back to default fake variant when remote value unknown', (
    tester,
  ) async {
    final remoteValues = _FakeRemoteConfigValues('unknown_variant');
    when(
      () => mockAnalyticsService.logBookPromoCardViewed(
        jokeContext: any(named: 'jokeContext'),
        bookPromoVariant: any(named: 'bookPromoVariant'),
      ),
    ).thenAnswer((_) {});
    when(
      () => mockAppUsageService.setBookPromoCardLastShown(any()),
    ).thenAnswer((_) async {});

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          appUsageServiceProvider.overrideWithValue(mockAppUsageService),
          clockProvider.overrideWithValue(() => fixedNow),
          sharedPreferencesProvider.overrideWithValue(sharedPreferences),
          performanceServiceProvider.overrideWithValue(performanceService),
          remoteConfigValuesProvider.overrideWithValue(remoteValues),
          firebaseFunctionsProvider.overrideWithValue(mockFirebaseFunctions),
        ],
        child: MaterialApp(
          home: Scaffold(
            body: Consumer(
              builder: (context, ref, _) {
                final renderer = const BookPromoSlotEntryRenderer();
                final config = SlotEntryViewConfig(
                  context: context,
                  ref: ref,
                  index: 0,
                  isLandscape: false,
                  jokeContext: 'joke_feed',
                  showSimilarSearchButton: false,
                );
                return renderer.build(
                  entry: const BookPromoSlotEntry(),
                  config: config,
                );
              },
            ),
          ),
        ),
      ),
    );

    await tester.pump();
    await tester.pump();

    expect(find.byKey(const Key('fake-joke-card-fake_joke_1')), findsOneWidget);
    final capturedTestVariant = verify(
      () => mockAnalyticsService.logBookPromoCardViewed(
        jokeContext: captureAny(named: 'jokeContext'),
        bookPromoVariant: captureAny(named: 'bookPromoVariant'),
      ),
    ).captured;
    expect(capturedTestVariant[0], 'joke_feed');
    expect(capturedTestVariant[1], 'fake_joke_1');
    verify(
      () => mockAppUsageService.setBookPromoCardLastShown(fixedNow),
    ).called(1);
  });

  testWidgets(
    'renders configured fake joke variant with analytics + usage logging',
    (tester) async {
      final remoteValues = _FakeRemoteConfigValues('fake_joke_2');
      when(
        () => mockAnalyticsService.logBookPromoCardViewed(
          jokeContext: any(named: 'jokeContext'),
          bookPromoVariant: any(named: 'bookPromoVariant'),
        ),
      ).thenAnswer((_) {});
      when(
        () => mockAppUsageService.setBookPromoCardLastShown(any()),
      ).thenAnswer((_) async {});

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
            appUsageServiceProvider.overrideWithValue(mockAppUsageService),
            clockProvider.overrideWithValue(() => fixedNow),
            sharedPreferencesProvider.overrideWithValue(sharedPreferences),
            performanceServiceProvider.overrideWithValue(performanceService),
            remoteConfigValuesProvider.overrideWithValue(remoteValues),
            firebaseFunctionsProvider.overrideWithValue(mockFirebaseFunctions),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: Consumer(
                builder: (context, ref, _) {
                  final renderer = const BookPromoSlotEntryRenderer();
                  final config = SlotEntryViewConfig(
                    context: context,
                    ref: ref,
                    index: 0,
                    isLandscape: false,
                    jokeContext: 'discover',
                    showSimilarSearchButton: false,
                  );
                  return renderer.build(
                    entry: const BookPromoSlotEntry(),
                    config: config,
                  );
                },
              ),
            ),
          ),
        ),
      );

      await tester.pump();
      await tester.pump();

      expect(
        find.byKey(const Key('fake-joke-card-fake_joke_2')),
        findsOneWidget,
      );
      final cardFinder = find.byType(JokeCard);
      expect(cardFinder, findsOneWidget);
      final JokeCard renderedCard = tester.widget(cardFinder);
      expect(renderedCard.skipJokeTracking, isTrue);
      expect(renderedCard.showSaveButton, isFalse);
      expect(renderedCard.showShareButton, isFalse);
      final capturedFakeVariant = verify(
        () => mockAnalyticsService.logBookPromoCardViewed(
          jokeContext: captureAny(named: 'jokeContext'),
          bookPromoVariant: captureAny(named: 'bookPromoVariant'),
        ),
      ).captured;
      expect(capturedFakeVariant[0], 'discover');
      expect(capturedFakeVariant[1], 'fake_joke_2');
      verify(
        () => mockAppUsageService.setBookPromoCardLastShown(fixedNow),
      ).called(1);
    },
  );
}
