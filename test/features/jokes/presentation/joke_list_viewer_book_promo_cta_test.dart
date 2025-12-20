import 'package:cloud_functions/cloud_functions.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/providers/settings_providers.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_entries.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_source.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockAppUsageService extends Mock implements AppUsageService {}

class MockJokeViewerSettingsService extends Mock
    implements JokeViewerSettingsService {}

class MockFirebaseFunctions extends Mock implements FirebaseFunctions {}

class _FakeRemoteConfigValues implements RemoteConfigValues {
  _FakeRemoteConfigValues();

  @override
  bool getBool(RemoteParam param) => true;

  @override
  double getDouble(RemoteParam param) => 0.0;

  @override
  int getInt(RemoteParam param) => 0;

  @override
  String getString(RemoteParam param) {
    if (param == RemoteParam.bookPromoCardVariant) {
      return 'fake_joke_read';
    }
    return '';
  }

  @override
  T getEnum<T>(RemoteParam param) {
    final descriptor = remoteParams[param]!;
    return (descriptor.enumDefault ?? '') as T;
  }
}

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
  late MockJokeViewerSettingsService mockJokeViewerSettingsService;
  late SharedPreferences sharedPreferences;
  late PerformanceService performanceService;
  late MockFirebaseFunctions mockFirebaseFunctions;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    sharedPreferences = await SharedPreferences.getInstance();
    mockAnalyticsService = MockAnalyticsService();
    mockAppUsageService = MockAppUsageService();
    mockJokeViewerSettingsService = MockJokeViewerSettingsService();
    performanceService = _NoopPerformanceService();
    mockFirebaseFunctions = MockFirebaseFunctions();

    when(
      () => mockJokeViewerSettingsService.getReveal(),
    ).thenAnswer((_) async => true);
    when(
      () => mockJokeViewerSettingsService.setReveal(any()),
    ).thenAnswer((_) async {});

    when(
      () => mockAnalyticsService.logBookPromoCardViewed(
        jokeContext: any(named: 'jokeContext'),
        bookPromoVariant: any(named: 'bookPromoVariant'),
      ),
    ).thenAnswer((_) {});
    when(
      () => mockAppUsageService.setBookPromoCardLastShown(any()),
    ).thenAnswer((_) async {});
  });

  testWidgets('CTA shows Reveal then Next joke for book promo based on image', (
    tester,
  ) async {
    final slotSource = SlotSource(
      slotsProvider: Provider<AsyncValue<List<SlotEntry>>>(
        (ref) => const AsyncValue.data([BookPromoSlotEntry()]),
      ),
      hasMoreProvider: Provider<bool>((ref) => false),
      isLoadingProvider: Provider<bool>((ref) => false),
      isDataPendingProvider: Provider<bool>((ref) => false),
      resultCountProvider: Provider<({int count, bool hasMore})>(
        (ref) => (count: 1, hasMore: false),
      ),
      onViewingIndexUpdated: (_) {},
      debugLabel: 'test',
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          appUsageServiceProvider.overrideWithValue(mockAppUsageService),
          jokeViewerSettingsServiceProvider.overrideWithValue(
            mockJokeViewerSettingsService,
          ),
          sharedPreferencesProvider.overrideWithValue(sharedPreferences),
          performanceServiceProvider.overrideWithValue(performanceService),
          remoteConfigValuesProvider.overrideWithValue(
            _FakeRemoteConfigValues(),
          ),
          firebaseFunctionsProvider.overrideWithValue(mockFirebaseFunctions),
        ],
        child: MaterialApp(
          home: Scaffold(
            body: JokeListViewer(
              slotSource: slotSource,
              jokeContext: 'joke_feed',
              viewerId: 'test_viewer',
              showSimilarSearchButton: false,
            ),
          ),
        ),
      ),
    );

    await tester.pump();
    await tester.pump();

    // Setup image is index 0 by default, so CTA should be Reveal.
    expect(find.text('Reveal'), findsOneWidget);

    await tester.tap(find.byKey(const Key('joke_list_viewer-cta-button')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 350));

    // After revealing punchline (index 1), CTA should show Next joke.
    expect(find.text('Next joke'), findsOneWidget);
  });
}
