import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:share_plus/share_plus.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
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
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_navigation_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_population_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

// Mock classes
class MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

class MockCategoryInteractionsRepository extends Mock
    implements CategoryInteractionsRepository {}

class MockPerformanceService extends Mock implements PerformanceService {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class _TestJokeViewerRevealNotifier extends JokeViewerRevealNotifier {
  _TestJokeViewerRevealNotifier(bool initial)
    : super(_TestJokeViewerSettingsService()) {
    state = initial;
  }
}

class _TestJokeViewerSettingsService extends JokeViewerSettingsService {
  _TestJokeViewerSettingsService()
    : super(
        settingsService: _InMemorySettingsService(),
        remoteConfigValues: _StaticRemoteConfigValues(),
        analyticsService: _NoopAnalyticsService(),
      );
}

class _InMemorySettingsService implements SettingsService {
  final Map<String, Object> _store = {};
  @override
  bool? getBool(String key) => _store[key] as bool?;
  @override
  Future<void> setBool(String key, bool value) async => _store[key] = value;
  @override
  String? getString(String key) => _store[key] as String?;
  @override
  Future<void> setString(String key, String value) async => _store[key] = value;
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

class _StaticRemoteConfigValues implements RemoteConfigValues {
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

class _NoopAnalyticsService extends Mock implements AnalyticsService {}

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

class _MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class _NoopImageService extends Mock implements ImageService {}

class _NoopPlatformShareService implements PlatformShareService {
  @override
  Future<ShareResult> shareFiles(
    List<XFile> files, {
    String? subject,
    String? text,
  }) async {
    return ShareResult('mock', ShareResultStatus.success);
  }
}

class _NoopAppUsageService implements AppUsageService {
  @override
  Future<String?> getFirstUsedDate() async => null;
  @override
  Future<String?> getLastUsedDate() async => null;
  @override
  Future<int> getNumDaysUsed() async => 0;
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
  Future<List<String>> getSharedJokeIds() async => [];
  @override
  Future<List<String>> getViewedJokeIds() async => [];
}

class _NoopReviewPromptCoordinator extends Mock
    implements ReviewPromptCoordinator {}

class _NoopJokeRepository extends Mock implements JokeRepository {}

void main() {
  setUpAll(() {
    registerFallbackValue(MockJokeInteractionsRepository());
    registerFallbackValue(MockCategoryInteractionsRepository());
    registerFallbackValue(MockPerformanceService());
  });

  late MockJokeInteractionsRepository mockJokeInteractionsRepository;
  late MockCategoryInteractionsRepository mockCategoryInteractionsRepository;
  late MockAnalyticsService mockAnalyticsService;

  setUp(() {
    mockJokeInteractionsRepository = MockJokeInteractionsRepository();
    mockCategoryInteractionsRepository = MockCategoryInteractionsRepository();
    mockAnalyticsService = MockAnalyticsService();

    // Stub default behavior
    when(
      () => mockJokeInteractionsRepository.watchJokeInteraction(any()),
    ).thenAnswer((_) => Stream.value(null));
    when(
      () => mockCategoryInteractionsRepository.setViewed(any()),
    ).thenAnswer((_) async => true);
  });

  group('JokeListViewer State Persistence', () {
    testWidgets('restores page index after unmount and remount', (
      tester,
    ) async {
      // Arrange: Create test data
      const viewerId = 'persist_test';
      final jokes = List.generate(5, (i) {
        return JokeWithDate(
          joke: Joke(
            id: 'id_$i',
            setupText: 'Setup $i',
            punchlineText: 'Punchline $i',
            setupImageUrl: 'https://example.com/s$i.jpg',
            punchlineImageUrl: 'https://example.com/p$i.jpg',
          ),
        );
      });

      final overrides = [
        analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
        performanceServiceProvider.overrideWithValue(_NoopPerformanceService()),
        jokeViewerRevealProvider.overrideWith(
          (ref) => _TestJokeViewerRevealNotifier(false),
        ),
        jokePopulationProvider.overrideWith(
          (ref) => JokePopulationNotifier(_MockJokeCloudFunctionService()),
        ),
        // Share button dependencies to avoid touching Firebase/RC/etc.
        imageServiceProvider.overrideWithValue(_NoopImageService()),
        platformShareServiceProvider.overrideWithValue(
          _NoopPlatformShareService(),
        ),
        remoteConfigValuesProvider.overrideWithValue(
          _StaticRemoteConfigValues(),
        ),
        appUsageServiceProvider.overrideWithValue(_NoopAppUsageService()),
        reviewPromptCoordinatorProvider.overrideWithValue(
          _NoopReviewPromptCoordinator(),
        ),
        jokeRepositoryProvider.overrideWithValue(_NoopJokeRepository()),
        isOnlineNowProvider.overrideWith((ref) => true),
        jokeInteractionsRepositoryProvider.overrideWithValue(
          mockJokeInteractionsRepository,
        ),
        categoryInteractionsRepositoryProvider.overrideWithValue(
          mockCategoryInteractionsRepository,
        ),
      ];

      // Act: Build widget with ProviderScope
      await tester.pumpWidget(
        ProviderScope(
          overrides: overrides,
          child: MaterialApp(
            home: TickerMode(
              enabled: false,
              child: JokeListViewer(
                key: const Key(
                  'joke_list_viewer_state_persistence_test-initial',
                ),
                jokesAsyncValue: AsyncValue.data(jokes),
                jokeContext: 'test_ctx',
                viewerId: viewerId,
              ),
            ),
          ),
        ),
      );

      await tester.pump(const Duration(milliseconds: 50));

      // Act: Update page index to 3
      final container = ProviderScope.containerOf(
        tester.element(find.byType(JokeListViewer)),
      );
      container.read(jokeViewerPageIndexProvider(viewerId).notifier).state = 3;
      await tester.pump(const Duration(milliseconds: 50));

      // Act: Unmount widget
      await tester.pumpWidget(
        ProviderScope(
          overrides: overrides,
          child: const MaterialApp(home: SizedBox.shrink()),
        ),
      );
      await tester.pump(const Duration(milliseconds: 50));

      // Act: Remount widget
      await tester.pumpWidget(
        ProviderScope(
          overrides: overrides,
          child: MaterialApp(
            home: TickerMode(
              enabled: false,
              child: JokeListViewer(
                key: const Key(
                  'joke_list_viewer_state_persistence_test-remount',
                ),
                jokesAsyncValue: AsyncValue.data(jokes),
                jokeContext: 'test_ctx',
                viewerId: viewerId,
              ),
            ),
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 50));

      // Assert: Page index should be restored to 3
      final restoredIndex = container.read(
        jokeViewerPageIndexProvider(viewerId),
      );
      expect(restoredIndex, 3);
    });

    testWidgets('maintains separate page indices for different viewer IDs', (
      tester,
    ) async {
      // Arrange: Create test data
      const viewerId1 = 'viewer_1';
      const viewerId2 = 'viewer_2';
      final jokes = List.generate(3, (i) {
        return JokeWithDate(
          joke: Joke(
            id: 'id_$i',
            setupText: 'Setup $i',
            punchlineText: 'Punchline $i',
            setupImageUrl: 'https://example.com/s$i.jpg',
            punchlineImageUrl: 'https://example.com/p$i.jpg',
          ),
        );
      });

      final overrides = [
        analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
        performanceServiceProvider.overrideWithValue(_NoopPerformanceService()),
        jokeViewerRevealProvider.overrideWith(
          (ref) => _TestJokeViewerRevealNotifier(false),
        ),
        jokePopulationProvider.overrideWith(
          (ref) => JokePopulationNotifier(_MockJokeCloudFunctionService()),
        ),
        imageServiceProvider.overrideWithValue(_NoopImageService()),
        platformShareServiceProvider.overrideWithValue(
          _NoopPlatformShareService(),
        ),
        remoteConfigValuesProvider.overrideWithValue(
          _StaticRemoteConfigValues(),
        ),
        appUsageServiceProvider.overrideWithValue(_NoopAppUsageService()),
        reviewPromptCoordinatorProvider.overrideWithValue(
          _NoopReviewPromptCoordinator(),
        ),
        jokeRepositoryProvider.overrideWithValue(_NoopJokeRepository()),
        isOnlineNowProvider.overrideWith((ref) => true),
        jokeInteractionsRepositoryProvider.overrideWithValue(
          mockJokeInteractionsRepository,
        ),
        categoryInteractionsRepositoryProvider.overrideWithValue(
          mockCategoryInteractionsRepository,
        ),
      ];

      // Act: Build first viewer
      await tester.pumpWidget(
        ProviderScope(
          overrides: overrides,
          child: MaterialApp(
            home: TickerMode(
              enabled: false,
              child: JokeListViewer(
                key: const Key(
                  'joke_list_viewer_state_persistence_test-viewer1',
                ),
                jokesAsyncValue: AsyncValue.data(jokes),
                jokeContext: 'test_ctx',
                viewerId: viewerId1,
              ),
            ),
          ),
        ),
      );

      await tester.pump(const Duration(milliseconds: 50));

      // Act: Set page index for viewer 1
      final container = ProviderScope.containerOf(
        tester.element(find.byType(JokeListViewer)),
      );
      container.read(jokeViewerPageIndexProvider(viewerId1).notifier).state = 2;
      await tester.pump(const Duration(milliseconds: 50));

      // Act: Build second viewer
      await tester.pumpWidget(
        ProviderScope(
          overrides: overrides,
          child: MaterialApp(
            home: TickerMode(
              enabled: false,
              child: JokeListViewer(
                key: const Key(
                  'joke_list_viewer_state_persistence_test-viewer2',
                ),
                jokesAsyncValue: AsyncValue.data(jokes),
                jokeContext: 'test_ctx',
                viewerId: viewerId2,
              ),
            ),
          ),
        ),
      );

      await tester.pump(const Duration(milliseconds: 50));

      // Act: Set page index for viewer 2
      container.read(jokeViewerPageIndexProvider(viewerId2).notifier).state = 1;
      await tester.pump(const Duration(milliseconds: 50));

      // Assert: Each viewer should have its own page index
      expect(container.read(jokeViewerPageIndexProvider(viewerId1)), 2);
      expect(container.read(jokeViewerPageIndexProvider(viewerId2)), 1);
    });

    testWidgets('handles empty joke list gracefully', (tester) async {
      // Arrange: Create test data with empty list
      const viewerId = 'empty_test';
      final emptyJokes = <JokeWithDate>[];

      final overrides = [
        analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
        performanceServiceProvider.overrideWithValue(_NoopPerformanceService()),
        jokeViewerRevealProvider.overrideWith(
          (ref) => _TestJokeViewerRevealNotifier(false),
        ),
        jokePopulationProvider.overrideWith(
          (ref) => JokePopulationNotifier(_MockJokeCloudFunctionService()),
        ),
        imageServiceProvider.overrideWithValue(_NoopImageService()),
        platformShareServiceProvider.overrideWithValue(
          _NoopPlatformShareService(),
        ),
        remoteConfigValuesProvider.overrideWithValue(
          _StaticRemoteConfigValues(),
        ),
        appUsageServiceProvider.overrideWithValue(_NoopAppUsageService()),
        reviewPromptCoordinatorProvider.overrideWithValue(
          _NoopReviewPromptCoordinator(),
        ),
        jokeRepositoryProvider.overrideWithValue(_NoopJokeRepository()),
        isOnlineNowProvider.overrideWith((ref) => true),
        jokeInteractionsRepositoryProvider.overrideWithValue(
          mockJokeInteractionsRepository,
        ),
        categoryInteractionsRepositoryProvider.overrideWithValue(
          mockCategoryInteractionsRepository,
        ),
      ];

      // Act: Build widget with empty list
      await tester.pumpWidget(
        ProviderScope(
          overrides: overrides,
          child: MaterialApp(
            home: TickerMode(
              enabled: false,
              child: JokeListViewer(
                key: const Key('joke_list_viewer_state_persistence_test-empty'),
                jokesAsyncValue: AsyncValue.data(emptyJokes),
                jokeContext: 'test_ctx',
                viewerId: viewerId,
              ),
            ),
          ),
        ),
      );

      await tester.pump(const Duration(milliseconds: 50));

      // Act: Try to set page index
      final container = ProviderScope.containerOf(
        tester.element(find.byType(JokeListViewer)),
      );
      container.read(jokeViewerPageIndexProvider(viewerId).notifier).state = 5;
      await tester.pump(const Duration(milliseconds: 50));

      // Assert: Should not crash and should maintain the page index
      expect(container.read(jokeViewerPageIndexProvider(viewerId)), 5);
    });

    testWidgets('resets to page 0 when viewer ID changes', (tester) async {
      // Arrange: Create test data
      const initialViewerId = 'initial_viewer';
      const newViewerId = 'new_viewer';
      final jokes = List.generate(3, (i) {
        return JokeWithDate(
          joke: Joke(
            id: 'id_$i',
            setupText: 'Setup $i',
            punchlineText: 'Punchline $i',
            setupImageUrl: 'https://example.com/s$i.jpg',
            punchlineImageUrl: 'https://example.com/p$i.jpg',
          ),
        );
      });

      final overrides = [
        analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
        performanceServiceProvider.overrideWithValue(_NoopPerformanceService()),
        jokeViewerRevealProvider.overrideWith(
          (ref) => _TestJokeViewerRevealNotifier(false),
        ),
        jokePopulationProvider.overrideWith(
          (ref) => JokePopulationNotifier(_MockJokeCloudFunctionService()),
        ),
        imageServiceProvider.overrideWithValue(_NoopImageService()),
        platformShareServiceProvider.overrideWithValue(
          _NoopPlatformShareService(),
        ),
        remoteConfigValuesProvider.overrideWithValue(
          _StaticRemoteConfigValues(),
        ),
        appUsageServiceProvider.overrideWithValue(_NoopAppUsageService()),
        reviewPromptCoordinatorProvider.overrideWithValue(
          _NoopReviewPromptCoordinator(),
        ),
        jokeRepositoryProvider.overrideWithValue(_NoopJokeRepository()),
        isOnlineNowProvider.overrideWith((ref) => true),
        jokeInteractionsRepositoryProvider.overrideWithValue(
          mockJokeInteractionsRepository,
        ),
        categoryInteractionsRepositoryProvider.overrideWithValue(
          mockCategoryInteractionsRepository,
        ),
      ];

      // Act: Build widget with initial viewer ID
      await tester.pumpWidget(
        ProviderScope(
          overrides: overrides,
          child: MaterialApp(
            home: TickerMode(
              enabled: false,
              child: JokeListViewer(
                key: const Key(
                  'joke_list_viewer_state_persistence_test-initial_id',
                ),
                jokesAsyncValue: AsyncValue.data(jokes),
                jokeContext: 'test_ctx',
                viewerId: initialViewerId,
              ),
            ),
          ),
        ),
      );

      await tester.pump(const Duration(milliseconds: 50));

      // Act: Set page index for initial viewer
      final container = ProviderScope.containerOf(
        tester.element(find.byType(JokeListViewer)),
      );
      container
              .read(jokeViewerPageIndexProvider(initialViewerId).notifier)
              .state =
          2;
      await tester.pump(const Duration(milliseconds: 50));

      // Act: Change to new viewer ID
      await tester.pumpWidget(
        ProviderScope(
          overrides: overrides,
          child: MaterialApp(
            home: TickerMode(
              enabled: false,
              child: JokeListViewer(
                key: const Key(
                  'joke_list_viewer_state_persistence_test-new_id',
                ),
                jokesAsyncValue: AsyncValue.data(jokes),
                jokeContext: 'test_ctx',
                viewerId: newViewerId,
              ),
            ),
          ),
        ),
      );

      await tester.pump(const Duration(milliseconds: 50));

      // Assert: New viewer should start at page 0, old viewer should maintain its index
      expect(container.read(jokeViewerPageIndexProvider(initialViewerId)), 2);
      expect(container.read(jokeViewerPageIndexProvider(newViewerId)), 0);
    });
  });
}
