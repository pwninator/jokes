import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_modification_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_population_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

// Public constants
const String transparentImageDataUrl =
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';

// Fallback registrations
void registerCarouselTestFallbacks() {
  registerFallbackValue(JokeViewerMode.reveal);
  registerFallbackValue(_FakeBuildContext());
  registerFallbackValue(TraceName.carouselToVisible);
}

// Fakes / no-ops
class _FakeBuildContext extends Fake implements BuildContext {}

class FakeJoke extends Fake implements Joke {}

class FakeSettingsService implements SettingsService {
  final Map<String, Object?> _store = {};
  @override
  String? getString(String key) => _store[key] as String?;
  @override
  Future<void> setString(String key, String value) async => _store[key] = value;
  @override
  bool? getBool(String key) => _store[key] as bool?;
  @override
  Future<void> setBool(String key, bool value) async => _store[key] = value;
  @override
  int? getInt(String key) => _store[key] as int?;
  @override
  Future<void> setInt(String key, int value) async => _store[key] = value;
  @override
  double? getDouble(String key) => _store[key] as double?;
  @override
  Future<void> setDouble(String key, double value) async => _store[key] = value;
  @override
  List<String>? getStringList(String key) => _store[key] as List<String>?;
  @override
  Future<void> setStringList(String key, List<String> value) async =>
      _store[key] = value;
  @override
  bool containsKey(String key) => _store.containsKey(key);
  @override
  Future<void> remove(String key) async => _store.remove(key);
  @override
  Future<void> clear() async => _store.clear();
}

class FakeRemoteConfigValues implements RemoteConfigValues {
  @override
  bool getBool(RemoteParam param) => false;
  @override
  double getDouble(RemoteParam param) => 0;
  @override
  int getInt(RemoteParam param) => 0;
  @override
  String getString(RemoteParam param) => '';
  @override
  T getEnum<T>(RemoteParam param) {
    final descriptor = remoteParams[param]!;
    return (descriptor.enumDefault ?? '') as T;
  }
}

class FakeNotificationService implements NotificationService {
  @override
  Future<void> initialize() async {}
  @override
  Future<bool> requestNotificationPermissions() async => true;
  @override
  Future<String?> getFCMToken() async => 'token';
}

class FakeDailyJokeSubscriptionService implements DailyJokeSubscriptionService {
  @override
  Future<bool> ensureSubscriptionSync({bool unsubscribeOthers = true}) async =>
      true;
}

class FakeSubscriptionPromptNotifier extends SubscriptionPromptNotifier {
  FakeSubscriptionPromptNotifier()
    : super(
        SubscriptionNotifier(
          FakeSettingsService(),
          FakeDailyJokeSubscriptionService(),
          FakeNotificationService(),
        ),
        remoteConfigValues: FakeRemoteConfigValues(),
      );
  @override
  void considerPromptAfterJokeViewed(int _) {}
}

// Mock classes
class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

// No-op notifier for population provider
class TestJokePopulationNotifier extends JokePopulationNotifier {
  TestJokePopulationNotifier() : super(MockJokeCloudFunctionService());
  @override
  Future<bool> populateJoke(
    String jokeId, {
    bool imagesOnly = false,
    Map<String, dynamic>? additionalParams,
  }) async => true;
  @override
  void clearError() {
    state = state.copyWith(error: null);
  }

  @override
  bool isJokePopulating(String jokeId) => false;
}

// No-op notifier for modification provider (admin controls)
class TestJokeModificationNotifier extends JokeModificationNotifier {
  TestJokeModificationNotifier() : super(MockJokeCloudFunctionService());
  @override
  Future<bool> modifyJoke(
    String jokeId, {
    String? setupInstructions,
    String? punchlineInstructions,
  }) async => true;
  @override
  Future<bool> upscaleJoke(String jokeId) async => true;
  @override
  void clearError() {
    state = state.copyWith(error: null);
  }
}

// Stub helpers
void stubImageServiceHappyPath(ImageService mock, {String? dataUrl}) {
  final url = dataUrl ?? transparentImageDataUrl;
  when(() => mock.isValidImageUrl(any())).thenReturn(true);
  when(() => mock.processImageUrl(any())).thenReturn(url);
  when(
    () => mock.processImageUrl(
      any(),
      width: any(named: 'width'),
      height: any(named: 'height'),
      quality: any(named: 'quality'),
    ),
  ).thenReturn(url);
  when(
    () => mock.getProcessedJokeImageUrl(any(), width: any(named: 'width')),
  ).thenReturn(url);
  when(
    () => mock.precacheJokeImage(any(), width: any(named: 'width')),
  ).thenAnswer((_) async => url);
  when(
    () => mock.precacheJokeImages(any(), width: any(named: 'width')),
  ).thenAnswer((_) async => (setupUrl: url, punchlineUrl: url));
  when(
    () => mock.precacheMultipleJokeImages(any(), width: any(named: 'width')),
  ).thenAnswer((_) async {});
}

void stubPerformanceNoOps(PerformanceService mock) {
  when(
    () => mock.startNamedTrace(
      name: any(named: 'name'),
      key: any(named: 'key'),
      attributes: any(named: 'attributes'),
    ),
  ).thenAnswer((_) {});
  when(
    () => mock.stopNamedTrace(
      name: any(named: 'name'),
      key: any(named: 'key'),
    ),
  ).thenAnswer((_) {});
  when(
    () => mock.dropNamedTrace(
      name: any(named: 'name'),
      key: any(named: 'key'),
    ),
  ).thenAnswer((_) {});
  when(
    () => mock.putNamedTraceAttributes(
      name: any(named: 'name'),
      key: any(named: 'key'),
      attributes: any(named: 'attributes'),
    ),
  ).thenAnswer((_) {});
}

void stubAppUsageViewed(AppUsageService mock, {int viewedCount = 1}) {
  when(
    () => mock.logJokeViewed(any(), context: any(named: 'context')),
  ).thenAnswer((_) async {});
  when(() => mock.getNumJokesViewed()).thenAnswer((_) async => viewedCount);
}

// Wrap helper for minimal overrides
Widget wrapWithCarouselOverrides(
  Widget child, {
  required ImageService imageService,
  required AppUsageService appUsageService,
  required AnalyticsService analyticsService,
  required PerformanceService performanceService,
  JokeCloudFunctionService? jokeFn,
  List<Override> extraOverrides = const [],
}) {
  return ProviderScope(
    overrides: [
      imageServiceProvider.overrideWithValue(imageService),
      appUsageServiceProvider.overrideWithValue(appUsageService),
      analyticsServiceProvider.overrideWithValue(analyticsService),
      performanceServiceProvider.overrideWithValue(performanceService),
      subscriptionPromptProvider.overrideWith(
        (ref) => FakeSubscriptionPromptNotifier(),
      ),
      jokeCloudFunctionServiceProvider.overrideWithValue(
        jokeFn ?? MockJokeCloudFunctionService(),
      ),
      jokePopulationProvider.overrideWith(
        (ref) => TestJokePopulationNotifier(),
      ),
      jokeModificationProvider.overrideWith(
        (ref) => TestJokeModificationNotifier(),
      ),
      ...extraOverrides,
    ],
    child: MaterialApp(
      theme: lightTheme,
      home: Scaffold(body: child),
    ),
  );
}
