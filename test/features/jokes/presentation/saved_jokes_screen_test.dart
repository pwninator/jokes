import 'dart:async';

import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/providers/app_version_provider.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/category_interactions_repository.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/data/reviews/reviews_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_population_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_search_result.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/saved_jokes_screen.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

// Additional mock classes for Firebase and core services
class MockAppUsageService extends Mock implements AppUsageService {}

class MockSettingsService extends Mock implements SettingsService {}

class MockImageService extends Mock implements ImageService {}

class MockNotificationService extends Mock implements NotificationService {}

class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

class MockReviewsRepository extends Mock implements ReviewsRepository {}

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

// Fake Firebase classes for testing (only what's actually needed)
class FakeFirebaseAnalytics extends Fake implements FirebaseAnalytics {}

// Test implementations
class _TestRemoteConfigValues implements RemoteConfigValues {
  @override
  bool getBool(RemoteParam param) {
    if (param == RemoteParam.defaultJokeViewerReveal) {
      return true;
    }
    return false;
  }

  @override
  double getDouble(RemoteParam param) => 0;

  @override
  int getInt(RemoteParam param) {
    final descriptor = remoteParams[param]!;
    return descriptor.defaultInt ?? 0;
  }

  @override
  String getString(RemoteParam param) => '';

  @override
  T getEnum<T>(RemoteParam param) {
    final descriptor = remoteParams[param]!;
    return (descriptor.enumDefault ?? '') as T;
  }
}

class _TestNoopPerformanceService implements PerformanceService {
  @override
  void startNamedTrace({
    required TraceName name,
    String? key,
    Map<String, String>? attributes,
  }) {}

  @override
  void putNamedTraceAttributes({
    required TraceName name,
    String? key,
    required Map<String, String> attributes,
  }) {}

  @override
  void stopNamedTrace({required TraceName name, String? key}) {}

  @override
  void dropNamedTrace({required TraceName name, String? key}) {}
}

/// Test joke population notifier that doesn't require Firebase
class TestJokePopulationNotifier extends JokePopulationNotifier {
  TestJokePopulationNotifier() : super(MockJokeCloudFunctionService());

  @override
  Future<bool> populateJoke(
    String jokeId, {
    bool imagesOnly = false,
    Map<String, dynamic>? additionalParams,
  }) async {
    return true;
  }

  @override
  void clearError() {
    state = state.copyWith(error: null);
  }

  @override
  bool isJokePopulating(String jokeId) {
    return false;
  }
}

// Test repository that properly handles streams
class _TestInteractionsRepo extends JokeInteractionsRepository {
  _TestInteractionsRepo({required super.db, required PerformanceService perf})
    : super(performanceService: perf);

  final _controllers = <String, StreamController<JokeInteraction?>>{};

  @override
  Stream<JokeInteraction?> watchJokeInteraction(String jokeId) {
    // Reuse existing controller for this jokeId or create a new one
    if (!_controllers.containsKey(jokeId)) {
      final controller = StreamController<JokeInteraction?>.broadcast();
      _controllers[jokeId] = controller;
      // Add initial value
      controller.add(null);
    }
    return _controllers[jokeId]!.stream;
  }

  void dispose() {
    for (final controller in _controllers.values) {
      controller.close();
    }
    _controllers.clear();
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MockJokeRepository mockRepository;
  late MockAppUsageService mockAppUsageService;

  setUpAll(() {
    registerFallbackValue(MatchMode.tight);
    registerFallbackValue(SearchScope.userJokeSearch);
    registerFallbackValue(SearchLabel.none);
  });

  setUp(() {
    mockRepository = MockJokeRepository();
    mockAppUsageService = MockAppUsageService();

    when(
      () => mockAppUsageService.getSavedJokeIds(),
    ).thenAnswer((_) async => <String>[]);
  });

  ProviderContainer createContainer({List<Override> overrides = const []}) {
    final mockSettingsService = MockSettingsService();
    final mockImageService = MockImageService();
    final mockNotificationService = MockNotificationService();
    final mockSubscriptionService = MockDailyJokeSubscriptionService();
    final mockReviewsRepository = MockReviewsRepository();
    final mockCloudFunctionService = MockJokeCloudFunctionService();

    // Setup default behaviors for mocks
    when(() => mockSettingsService.getBool(any())).thenReturn(null);
    when(
      () => mockSettingsService.setBool(any(), any()),
    ).thenAnswer((_) async {});
    when(() => mockSettingsService.getString(any())).thenReturn(null);
    when(
      () => mockSettingsService.setString(any(), any()),
    ).thenAnswer((_) async {});
    when(() => mockSettingsService.getInt(any())).thenReturn(null);
    when(
      () => mockSettingsService.setInt(any(), any()),
    ).thenAnswer((_) async {});
    when(() => mockSettingsService.getDouble(any())).thenReturn(null);
    when(
      () => mockSettingsService.setDouble(any(), any()),
    ).thenAnswer((_) async {});
    when(() => mockSettingsService.getStringList(any())).thenReturn(null);
    when(
      () => mockSettingsService.setStringList(any(), any()),
    ).thenAnswer((_) async {});
    when(() => mockSettingsService.containsKey(any())).thenReturn(false);
    when(() => mockSettingsService.remove(any())).thenAnswer((_) async {});
    when(() => mockSettingsService.clear()).thenAnswer((_) async {});

    when(() => mockImageService.isValidImageUrl(any())).thenReturn(true);
    when(
      () => mockImageService.processImageUrl(any()),
    ).thenReturn('data:image/png;base64,test');
    when(
      () => mockImageService.getThumbnailUrl(any()),
    ).thenReturn('data:image/png;base64,test');
    when(
      () => mockImageService.getFullSizeUrl(any()),
    ).thenReturn('data:image/png;base64,test');
    when(() => mockImageService.clearCache()).thenAnswer((_) async {});

    when(() => mockNotificationService.initialize()).thenAnswer((_) async {});
    when(
      () => mockNotificationService.requestNotificationPermissions(),
    ).thenAnswer((_) async => true);
    when(
      () => mockNotificationService.getFCMToken(),
    ).thenAnswer((_) async => 'mock_fcm_token');

    when(
      () => mockSubscriptionService.ensureSubscriptionSync(
        unsubscribeOthers: any(named: 'unsubscribeOthers'),
      ),
    ).thenAnswer((_) async => true);

    when(
      () => mockReviewsRepository.recordAppReview(),
    ).thenAnswer((_) async {});

    when(
      () => mockCloudFunctionService.createJokeWithResponse(
        setupText: any(named: 'setupText'),
        punchlineText: any(named: 'punchlineText'),
        adminOwned: any(named: 'adminOwned'),
        setupImageUrl: any(named: 'setupImageUrl'),
        punchlineImageUrl: any(named: 'punchlineImageUrl'),
      ),
    ).thenAnswer((_) async => {'success': true, 'joke_id': 'test-id'});

    when(
      () => mockCloudFunctionService.populateJoke(
        any(),
        imagesOnly: any(named: 'imagesOnly'),
        additionalParams: any(named: 'additionalParams'),
      ),
    ).thenAnswer((_) async => {'success': true, 'data': 'populated'});

    when(
      () => mockCloudFunctionService.searchJokes(
        searchQuery: any(named: 'searchQuery'),
        maxResults: any(named: 'maxResults'),
        publicOnly: any(named: 'publicOnly'),
        matchMode: any(named: 'matchMode'),
        scope: any(named: 'scope'),
        label: any(named: 'label'),
      ),
    ).thenAnswer((_) async => <JokeSearchResult>[]);

    return ProviderContainer(
      overrides: [
        // Core service mocks
        settingsServiceProvider.overrideWithValue(mockSettingsService),
        imageServiceProvider.overrideWithValue(mockImageService),
        notificationServiceProvider.overrideWithValue(mockNotificationService),
        dailyJokeSubscriptionServiceProvider.overrideWithValue(
          mockSubscriptionService,
        ),
        reviewsRepositoryProvider.overrideWithValue(mockReviewsRepository),
        performanceServiceProvider.overrideWithValue(
          _TestNoopPerformanceService(),
        ),
        appVersionProvider.overrideWith((_) async => 'Snickerdoodle v0.0.1+1'),
        appDatabaseProvider.overrideWithValue(AppDatabase.inMemory()),

        // Firebase mocks (only what's actually needed)
        firebaseAnalyticsProvider.overrideWithValue(FakeFirebaseAnalytics()),
        remoteConfigValuesProvider.overrideWithValue(_TestRemoteConfigValues()),
        jokeCloudFunctionServiceProvider.overrideWithValue(
          mockCloudFunctionService,
        ),
        jokePopulationProvider.overrideWith(
          (ref) => TestJokePopulationNotifier(),
        ),

        // Connectivity
        isOnlineProvider.overrideWith((ref) async* {
          yield true;
        }),

        // Test-specific overrides
        jokeRepositoryProvider.overrideWithValue(mockRepository),
        appUsageServiceProvider.overrideWithValue(mockAppUsageService),
        // Override jokeInteractionsRepository to return working streams
        jokeInteractionsRepositoryProvider.overrideWith((ref) {
          return _TestInteractionsRepo(
            db: AppDatabase.inMemory(),
            perf: _TestNoopPerformanceService(),
          );
        }),
        // Override categoryInteractionsRepository
        categoryInteractionsRepositoryProvider.overrideWith((ref) {
          return CategoryInteractionsRepository(
            db: AppDatabase.inMemory(),
            performanceService: _TestNoopPerformanceService(),
          );
        }),
        ...overrides,
      ],
    );
  }

  Joke buildTestJoke(String id) {
    return Joke(
      id: id,
      setupText: 'Setup $id',
      punchlineText: 'Punchline $id',
      setupImageUrl: 'https://example.com/setup_$id.jpg',
      punchlineImageUrl: 'https://example.com/punch_$id.jpg',
    );
  }

  Future<void> pumpSavedJokesScreen(
    WidgetTester tester,
    ProviderContainer container,
  ) async {
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SavedJokesScreen()),
      ),
    );
    await tester.pump();
  }

  Future<void> pumpUntil(
    WidgetTester tester,
    bool Function() condition, {
    int maxTicks = 30,
    Duration step = const Duration(milliseconds: 50),
  }) async {
    for (var i = 0; i < maxTicks; i++) {
      await tester.pump(step);
      if (condition()) {
        return;
      }
    }
  }

  testWidgets('renders saved joke count when jokes exist', (tester) async {
    when(
      () => mockAppUsageService.getSavedJokeIds(),
    ).thenAnswer((_) async => ['1', '2']);
    when(() => mockRepository.getJokesByIds(any())).thenAnswer((
      invocation,
    ) async {
      final ids = invocation.positionalArguments.first as List<String>;
      return ids.map(buildTestJoke).toList();
    });

    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSavedJokesScreen(tester, container);
    await pumpUntil(
      tester,
      () => find
          .byKey(const Key('saved_jokes_screen-results-count'))
          .evaluate()
          .isNotEmpty,
    );

    expect(
      find.byKey(const Key('saved_jokes_screen-results-count')),
      findsOneWidget,
    );
    expect(find.text('2 saved jokes'), findsOneWidget);
  });

  testWidgets('does not render count when no jokes are saved', (tester) async {
    when(
      () => mockAppUsageService.getSavedJokeIds(),
    ).thenAnswer((_) async => <String>[]);
    when(
      () => mockRepository.getJokesByIds(any()),
    ).thenAnswer((_) async => <Joke>[]);

    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSavedJokesScreen(tester, container);
    await pumpUntil(tester, () => tester.binding.hasScheduledFrame == false);

    expect(
      find.byKey(const Key('saved_jokes_screen-results-count')),
      findsNothing,
    );
  });
}
