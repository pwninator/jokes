import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:share_plus/share_plus.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/providers/joke_share_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/joke_share_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_service.dart';
import 'package:snickerdoodle/src/data/jokes/category_interactions_repository.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_population_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

class MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

class MockCategoryInteractionsRepository extends Mock
    implements CategoryInteractionsRepository {}

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class TestJokeViewerRevealNotifier extends JokeViewerRevealNotifier {
  TestJokeViewerRevealNotifier(bool initial)
    : super(TestJokeViewerSettingsService()) {
    state = initial;
  }
}

class TestJokeViewerSettingsService extends JokeViewerSettingsService {
  TestJokeViewerSettingsService()
    : super(
        settingsService: InMemorySettingsService(),
        remoteConfigValues: StaticRemoteConfigValues(),
        analyticsService: NoopAnalyticsService(),
      );
}

class InMemorySettingsService implements SettingsService {
  final Map<String, Object> _store = {};

  @override
  bool? getBool(String key) => _store[key] as bool?;

  @override
  Future<void> setBool(String key, bool value) async {
    _store[key] = value;
  }

  @override
  String? getString(String key) => _store[key] as String?;

  @override
  Future<void> setString(String key, String value) async {
    _store[key] = value;
  }

  @override
  int? getInt(String key) => _store[key] as int?;

  @override
  Future<void> setInt(String key, int value) async {
    _store[key] = value;
  }

  @override
  double? getDouble(String key) => _store[key] as double?;

  @override
  Future<void> setDouble(String key, double value) async {
    _store[key] = value;
  }

  @override
  List<String>? getStringList(String key) => _store[key] as List<String>?;

  @override
  Future<void> setStringList(String key, List<String> value) async {
    _store[key] = value;
  }

  @override
  bool containsKey(String key) => _store.containsKey(key);

  @override
  Future<void> remove(String key) async {
    _store.remove(key);
  }

  @override
  Future<void> clear() async {
    _store.clear();
  }
}

class StaticRemoteConfigValues implements RemoteConfigValues {
  @override
  bool getBool(RemoteParam param) => false;

  @override
  double getDouble(RemoteParam param) => 0;

  @override
  int getInt(RemoteParam param) => 0;

  @override
  String getString(RemoteParam param) => '';

  @override
  T getEnum<T>(RemoteParam param) => '' as T;
}

class NoopPerformanceService implements PerformanceService {
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

class NoopImageService extends Mock implements ImageService {}

class NoopPlatformShareService implements PlatformShareService {
  @override
  Future<ShareResult> shareFiles(
    List<XFile> files, {
    String? subject,
    String? text,
  }) async {
    return ShareResult('mock', ShareResultStatus.success);
  }
}

class NoopAppUsageService implements AppUsageService {
  @override
  Future<String?> getFirstUsedDate() async => null;

  @override
  Future<String?> getLastUsedDate() async => null;

  @override
  Future<int> getNumDaysUsed() async => 0;

  @override
  Future<int> getNumJokesNavigated() async => 0;

  @override
  Future<int> getNumJokesViewed() async => 0;

  @override
  Future<int> getNumSavedJokes() async => 0;

  @override
  Future<List<String>> getSavedJokeIds() async => const [];

  @override
  Future<int> getNumSharedJokes() async => 0;

  @override
  Future<void> logAppUsage() async {}

  @override
  Future<void> logCategoryViewed(String categoryId) async {}

  @override
  Future<void> logJokeViewed(
    String jokeId, {
    required BuildContext context,
  }) async {}

  @override
  Future<void> logJokeNavigated(String jokeId) async {}

  @override
  Future<void> setFirstUsedDate(String? date) async {}

  @override
  Future<void> setLastUsedDate(String? date) async {}

  @override
  Future<void> setNumDaysUsed(int value) async {}

  @override
  Future<bool> toggleJokeSave(
    String jokeId, {
    required BuildContext context,
  }) async => false;

  @override
  Future<void> saveJoke(String jokeId, {required BuildContext context}) async {}

  @override
  Future<void> unsaveJoke(String jokeId) async {}

  @override
  Future<void> shareJoke(
    String jokeId, {
    required BuildContext context,
  }) async {}

  @override
  Future<bool> isJokeSaved(String jokeId) async => false;

  @override
  Future<List<String>> getSharedJokeIds() async => const [];

  @override
  Future<List<String>> getNavigatedJokeIds() async => const [];

  @override
  Future<List<String>> getViewedJokeIds() async => const [];
  @override
  Future<List<String>> getUnviewedJokeIds(List<String> jokeIds) async =>
      jokeIds;
}

class NoopReviewPromptCoordinator extends Mock
    implements ReviewPromptCoordinator {}

class NoopJokeRepository extends Mock implements JokeRepository {}

class NoopAnalyticsService extends Mock implements AnalyticsService {}

List<Override> buildJokeViewerOverrides({
  required AnalyticsService analyticsService,
  bool isOnline = true,
}) {
  final mockJokeInteractionsRepository = MockJokeInteractionsRepository();
  when(
    () => mockJokeInteractionsRepository.countFeedJokes(),
  ).thenAnswer((_) async => 500);
  final mockCategoryInteractionsRepository =
      MockCategoryInteractionsRepository();

  final stubJokeRepository = NoopJokeRepository();
  when(
    () => stubJokeRepository.getFilteredJokePage(
      filters: any(named: 'filters'),
      orderByField: any(named: 'orderByField'),
      orderDirection: any(named: 'orderDirection'),
      limit: any(named: 'limit'),
      cursor: any(named: 'cursor'),
    ),
  ).thenAnswer(
    (_) async => const JokeListPage(ids: [], cursor: null, hasMore: false),
  );
  when(
    () => stubJokeRepository.getJokesByIds(any()),
  ).thenAnswer((_) async => <Joke>[]);
  return [
    analyticsServiceProvider.overrideWithValue(analyticsService),
    performanceServiceProvider.overrideWithValue(NoopPerformanceService()),
    jokeViewerRevealProvider.overrideWith(
      (ref) => TestJokeViewerRevealNotifier(false),
    ),
    jokePopulationProvider.overrideWith(
      (ref) => JokePopulationNotifier(MockJokeCloudFunctionService()),
    ),
    imageServiceProvider.overrideWithValue(NoopImageService()),
    platformShareServiceProvider.overrideWithValue(NoopPlatformShareService()),
    remoteConfigValuesProvider.overrideWithValue(StaticRemoteConfigValues()),
    appUsageServiceProvider.overrideWithValue(NoopAppUsageService()),
    reviewPromptCoordinatorProvider.overrideWithValue(
      NoopReviewPromptCoordinator(),
    ),
    jokeRepositoryProvider.overrideWithValue(stubJokeRepository),
    isOnlineNowProvider.overrideWith((ref) => isOnline),
    jokeInteractionsRepositoryProvider.overrideWithValue(
      mockJokeInteractionsRepository,
    ),
    categoryInteractionsRepositoryProvider.overrideWithValue(
      mockCategoryInteractionsRepository,
    ),
  ];
}
