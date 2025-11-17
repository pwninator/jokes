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

class MockAppUsageService extends Mock implements AppUsageService {}

class MockSettingsService extends Mock implements SettingsService {}

class MockImageService extends Mock implements ImageService {}

class MockNotificationService extends Mock implements NotificationService {}

class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

class MockReviewsRepository extends Mock implements ReviewsRepository {}

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class MockPerformanceService extends Mock implements PerformanceService {}

class MockRemoteConfigValues extends Mock implements RemoteConfigValues {}

class MockJokePopulationNotifier extends StateNotifier<JokePopulationState>
    implements JokePopulationNotifier {
  MockJokePopulationNotifier() : super(const JokePopulationState());

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
    state = state.copyWith(clearError: true);
  }

  @override
  bool isJokePopulating(String jokeId) {
    return false;
  }
}

class MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

class MockCategoryInteractionsRepository extends Mock
    implements CategoryInteractionsRepository {}

// Fake Firebase classes for testing (only what's actually needed)
class FakeFirebaseAnalytics extends Fake implements FirebaseAnalytics {}

class _FixedRemoteValues implements RemoteConfigValues {
  @override
  bool getBool(RemoteParam param) => remoteParams[param]?.defaultBool ?? false;

  @override
  double getDouble(RemoteParam param) =>
      remoteParams[param]?.defaultDouble ?? 0.0;

  @override
  int getInt(RemoteParam param) => remoteParams[param]?.defaultInt ?? 0;

  @override
  String getString(RemoteParam param) =>
      remoteParams[param]?.defaultString ?? '';

  @override
  T getEnum<T>(RemoteParam param) {
    if (param == RemoteParam.adDisplayMode) {
      return AdDisplayMode.none as T;
    }
    final descriptor = remoteParams[param];
    final value =
        descriptor?.enumDefault ??
        (descriptor?.enumValues != null && descriptor!.enumValues!.isNotEmpty
            ? descriptor.enumValues!.first
            : null);
    return value as T;
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
    registerFallbackValue(FakeFirebaseAnalytics());
    registerFallbackValue(TraceName.searchToFirstImage);
    registerFallbackValue(RemoteParam.defaultJokeViewerReveal);
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
    final mockJokeInteractionsRepository = MockJokeInteractionsRepository();
    final mockCategoryInteractionsRepository =
        MockCategoryInteractionsRepository();
    final mockJokePopulationNotifier = MockJokePopulationNotifier();
    final mockRemoteConfigValues = _FixedRemoteValues();
    final mockPerformanceService = MockPerformanceService();

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

    // Setup performance service mocks
    when(
      () => mockPerformanceService.startNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
        attributes: any(named: 'attributes'),
      ),
    ).thenAnswer((_) {});
    when(
      () => mockPerformanceService.putNamedTraceAttributes(
        name: any(named: 'name'),
        key: any(named: 'key'),
        attributes: any(named: 'attributes'),
      ),
    ).thenAnswer((_) {});
    when(
      () => mockPerformanceService.stopNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
      ),
    ).thenAnswer((_) {});
    when(
      () => mockPerformanceService.dropNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
      ),
    ).thenAnswer((_) {});

    // Remote config values provided by _FixedRemoteValues

    // MockJokePopulationNotifier is now a real StateNotifier, no setup needed

    // Setup joke interactions repository mocks
    when(
      () => mockJokeInteractionsRepository.setViewed(any()),
    ).thenAnswer((_) async => true);
    when(
      () => mockJokeInteractionsRepository.setSaved(any()),
    ).thenAnswer((_) async => true);
    when(
      () => mockJokeInteractionsRepository.setUnsaved(any()),
    ).thenAnswer((_) async => true);
    when(
      () => mockJokeInteractionsRepository.setShared(any()),
    ).thenAnswer((_) async => true);
    when(
      () => mockJokeInteractionsRepository.getSavedJokeInteractions(),
    ).thenAnswer((_) async => []);
    when(
      () => mockJokeInteractionsRepository.getAllJokeInteractions(),
    ).thenAnswer((_) async => []);
    when(
      () => mockJokeInteractionsRepository.getJokeInteraction(any()),
    ).thenAnswer((_) async => null);
    when(
      () => mockJokeInteractionsRepository.isJokeSaved(any()),
    ).thenAnswer((_) async => false);
    when(
      () => mockJokeInteractionsRepository.isJokeShared(any()),
    ).thenAnswer((_) async => false);
    when(
      () => mockJokeInteractionsRepository.watchJokeInteraction(any()),
    ).thenAnswer((_) => Stream.value(null));
    when(
      () => mockJokeInteractionsRepository.countViewed(),
    ).thenAnswer((_) async => 0);
    when(
      () => mockJokeInteractionsRepository.countSaved(),
    ).thenAnswer((_) async => 0);
    when(
      () => mockJokeInteractionsRepository.countShared(),
    ).thenAnswer((_) async => 0);

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
        performanceServiceProvider.overrideWithValue(mockPerformanceService),
        appVersionProvider.overrideWith((_) async => 'Snickerdoodle v0.0.1+1'),

        // Firebase mocks (only what's actually needed)
        firebaseAnalyticsProvider.overrideWithValue(FakeFirebaseAnalytics()),
        remoteConfigValuesProvider.overrideWithValue(mockRemoteConfigValues),
        jokeCloudFunctionServiceProvider.overrideWithValue(
          mockCloudFunctionService,
        ),
        jokePopulationProvider.overrideWith(
          (ref) => mockJokePopulationNotifier,
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
          return mockJokeInteractionsRepository;
        }),
        // Override categoryInteractionsRepository
        categoryInteractionsRepositoryProvider.overrideWith((ref) {
          return mockCategoryInteractionsRepository;
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
      publicTimestamp: DateTime.utc(2024, 1, 1),
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
    when(() => mockAppUsageService.getUnviewedJokeIds(any())).thenAnswer((
      invocation,
    ) async {
      return invocation.positionalArguments.first as List<String>;
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
