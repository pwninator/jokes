import 'dart:async';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:cloud_functions/cloud_functions.dart';
import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/core/providers/crash_reporting_provider.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart'
    show AppTab;
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart'
    show ReviewRequestSource;
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/data/jokes/category_interactions_repository.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_population_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/daily_jokes_screen.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

class MockJokeScheduleRepository extends Mock
    implements JokeScheduleRepository {}

class MockAppUsageService extends Mock implements AppUsageService {}

class MockJokeReactionsService extends Mock implements JokeReactionsService {}

class MockReviewPromptCoordinator extends Mock
    implements ReviewPromptCoordinator {}

class MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

class MockCategoryInteractionsRepository extends Mock
    implements CategoryInteractionsRepository {}

class MockImageService extends Mock implements ImageService {}

class MockNotificationService extends Mock implements NotificationService {}

class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockRemoteConfigValues extends Mock implements RemoteConfigValues {}

class MockFirebaseAnalytics extends Mock implements FirebaseAnalytics {}

class MockFirebaseMessaging extends Mock implements FirebaseMessaging {}

class MockFirebaseFirestore extends Mock implements FirebaseFirestore {}

class MockFirebaseFunctions extends Mock implements FirebaseFunctions {}

class _FakePerformanceService implements PerformanceService {
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

class _FakeBuildContext extends Fake implements BuildContext {}

void main() {
  setUpAll(() {
    registerFallbackValue(ReviewRequestSource.jokeSaved);
    registerFallbackValue(JokeReactionType.save);
    registerFallbackValue(_FakeBuildContext());
    registerFallbackValue(AppTab.dailyJokes);
    registerFallbackValue(
      const Joke(
        id: 'fallback',
        setupText: 'setup',
        punchlineText: 'punchline',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      ),
    );
    registerFallbackValue(RemoteParam.feedbackMinJokesViewed);
  });

  late MockJokeScheduleRepository mockScheduleRepository;
  late MockAppUsageService mockAppUsageService;
  late MockJokeReactionsService mockJokeReactionsService;
  late MockReviewPromptCoordinator mockReviewPromptCoordinator;
  late MockJokeInteractionsRepository mockJokeInteractionsRepository;
  late MockCategoryInteractionsRepository mockCategoryInteractionsRepository;
  late MockImageService mockImageService;
  late MockNotificationService mockNotificationService;
  late MockJokeCloudFunctionService mockJokeCloudFunctionService;
  late MockDailyJokeSubscriptionService mockDailyJokeSubscriptionService;
  late MockAnalyticsService mockAnalyticsService;
  late MockRemoteConfigValues mockRemoteConfigValues;
  late PerformanceService performanceService;
  late FirebaseAnalytics mockFirebaseAnalytics;
  late FirebaseMessaging mockFirebaseMessaging;
  late FirebaseFirestore mockFirebaseFirestore;
  late FirebaseFunctions mockFirebaseFunctions;
  late CrashReportingService crashReportingService;
  late SettingsService settingsService;

  setUp(() async {
    SharedPreferences.setMockInitialValues({'joke_viewer_reveal': true});
    final prefs = await SharedPreferences.getInstance();

    settingsService = SettingsService(prefs);
    mockAnalyticsService = MockAnalyticsService();
    mockRemoteConfigValues = MockRemoteConfigValues();
    mockFirebaseAnalytics = MockFirebaseAnalytics();
    mockFirebaseMessaging = MockFirebaseMessaging();
    mockFirebaseFirestore = MockFirebaseFirestore();
    mockFirebaseFunctions = MockFirebaseFunctions();
    crashReportingService = NoopCrashReportingService();

    mockScheduleRepository = MockJokeScheduleRepository();
    mockAppUsageService = MockAppUsageService();
    mockJokeReactionsService = MockJokeReactionsService();
    mockReviewPromptCoordinator = MockReviewPromptCoordinator();
    mockJokeInteractionsRepository = MockJokeInteractionsRepository();
    mockCategoryInteractionsRepository = MockCategoryInteractionsRepository();
    mockImageService = MockImageService();
    mockNotificationService = MockNotificationService();
    mockJokeCloudFunctionService = MockJokeCloudFunctionService();
    mockDailyJokeSubscriptionService = MockDailyJokeSubscriptionService();
    performanceService = _FakePerformanceService();
    when(() => mockRemoteConfigValues.getBool(any())).thenAnswer((invocation) {
      final param = invocation.positionalArguments.first as RemoteParam;
      if (param == RemoteParam.defaultJokeViewerReveal) {
        return true;
      }
      return remoteParams[param]?.defaultBool ?? false;
    });
    when(() => mockRemoteConfigValues.getInt(any())).thenAnswer((invocation) {
      final param = invocation.positionalArguments.first as RemoteParam;
      return remoteParams[param]?.defaultInt ?? 0;
    });
    when(() => mockRemoteConfigValues.getDouble(any())).thenAnswer((
      invocation,
    ) {
      final param = invocation.positionalArguments.first as RemoteParam;
      return remoteParams[param]?.defaultDouble ?? 0.0;
    });
    when(() => mockRemoteConfigValues.getString(any())).thenAnswer((
      invocation,
    ) {
      final param = invocation.positionalArguments.first as RemoteParam;
      return remoteParams[param]?.defaultString ?? '';
    });
    when(() => mockRemoteConfigValues.getEnum(any())).thenAnswer((invocation) {
      final param = invocation.positionalArguments.first as RemoteParam;
      final descriptor = remoteParams[param];
      return descriptor?.enumDefault ?? descriptor?.enumValues?.first ?? '';
    });

    when(() => mockImageService.isValidImageUrl(any())).thenReturn(true);
    when(() => mockImageService.processImageUrl(any())).thenAnswer(
      (invocation) => invocation.positionalArguments.first as String,
    );
    when(
      () => mockImageService.processImageUrl(
        any(),
        width: any(named: 'width'),
        height: any(named: 'height'),
        quality: any(named: 'quality'),
      ),
    ).thenAnswer(
      (invocation) => invocation.positionalArguments.first as String,
    );
    when(
      () => mockImageService.getProcessedJokeImageUrl(
        any(),
        width: any(named: 'width'),
      ),
    ).thenAnswer((invocation) {
      final url = invocation.positionalArguments.first;
      return url as String?;
    });
    when(() => mockImageService.getThumbnailUrl(any())).thenAnswer(
      (invocation) => invocation.positionalArguments.first as String,
    );
    when(
      () => mockImageService.getThumbnailUrl(any(), size: any(named: 'size')),
    ).thenAnswer(
      (invocation) => invocation.positionalArguments.first as String,
    );
    when(
      () => mockImageService.precacheJokeImages(
        any(),
        width: any(named: 'width'),
      ),
    ).thenAnswer((invocation) async {
      final joke = invocation.positionalArguments.first as Joke;
      return (
        setupUrl: joke.setupImageUrl,
        punchlineUrl: joke.punchlineImageUrl,
      );
    });
    when(
      () =>
          mockImageService.precacheJokeImage(any(), width: any(named: 'width')),
    ).thenAnswer(
      (invocation) async => invocation.positionalArguments.first as String?,
    );
    when(
      () => mockImageService.precacheMultipleJokeImages(
        any(),
        width: any(named: 'width'),
      ),
    ).thenAnswer((_) async {});
    when(() => mockImageService.clearCache()).thenAnswer((_) async {});

    when(
      () => mockAppUsageService.logJokeViewed(any<String>()),
    ).thenAnswer((_) async {});
    when(
      () => mockAppUsageService.getNumJokesViewed(),
    ).thenAnswer((_) async => 0);
    when(
      () => mockAppUsageService.getNumSavedJokes(),
    ).thenAnswer((_) async => 0);
    when(
      () => mockAppUsageService.getNumSharedJokes(),
    ).thenAnswer((_) async => 0);
    when(() => mockAppUsageService.getNumDaysUsed()).thenAnswer((_) async => 0);

    when(
      () => mockJokeReactionsService.toggleUserReaction(
        any<String>(),
        any<JokeReactionType>(),
        context: any(named: 'context'),
      ),
    ).thenAnswer((_) async => true);

    when(
      () => mockReviewPromptCoordinator.maybePromptForReview(
        source: any(named: 'source'),
        context: any(named: 'context'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mockJokeInteractionsRepository.watchJokeInteraction(any()),
    ).thenAnswer((_) => Stream.value(null));

    when(
      () => mockCategoryInteractionsRepository.setViewed(any()),
    ).thenAnswer((_) async => true);

    when(
      () => mockDailyJokeSubscriptionService.ensureSubscriptionSync(
        unsubscribeOthers: any(named: 'unsubscribeOthers'),
      ),
    ).thenAnswer((_) async => true);

    when(() => mockNotificationService.initialize()).thenAnswer((_) async {});
    when(
      () => mockNotificationService.requestNotificationPermissions(),
    ).thenAnswer((_) async => true);
    when(
      () => mockNotificationService.getFCMToken(),
    ).thenAnswer((_) async => 'token');

    when(
      () => mockJokeCloudFunctionService.populateJoke(
        any(),
        imagesOnly: any(named: 'imagesOnly'),
        additionalParams: any(named: 'additionalParams'),
      ),
    ).thenAnswer((_) async => {'success': true});
  });

  JokeScheduleBatch createBatch() {
    final now = DateTime.now();
    final month = DateTime(now.year, now.month);
    final joke = Joke(
      id: 'joke-1',
      setupText: 'Setup line',
      punchlineText: 'Punchline line',
      setupImageUrl: 'https://example.com/setup.jpg',
      punchlineImageUrl: 'https://example.com/punchline.jpg',
    );

    return JokeScheduleBatch(
      id: JokeScheduleBatch.createBatchId(
        JokeConstants.defaultJokeScheduleId,
        month.year,
        month.month,
      ),
      scheduleId: JokeConstants.defaultJokeScheduleId,
      year: month.year,
      month: month.month,
      jokes: {'01': joke},
    );
  }

  ProviderContainer createContainer(JokeScheduleBatch batch) {
    final overrides = <Override>[
      firebaseAnalyticsProvider.overrideWithValue(mockFirebaseAnalytics),
      firebaseMessagingProvider.overrideWithValue(mockFirebaseMessaging),
      firebaseFirestoreProvider.overrideWithValue(mockFirebaseFirestore),
      firebaseFunctionsProvider.overrideWithValue(mockFirebaseFunctions),
      crashReportingServiceProvider.overrideWithValue(crashReportingService),
      analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
      imageServiceProvider.overrideWithValue(mockImageService),
      performanceServiceProvider.overrideWithValue(performanceService),
      dailyJokeSubscriptionServiceProvider.overrideWithValue(
        mockDailyJokeSubscriptionService,
      ),
      notificationServiceProvider.overrideWithValue(mockNotificationService),
      remoteConfigValuesProvider.overrideWithValue(mockRemoteConfigValues),
      settingsServiceProvider.overrideWithValue(settingsService),
      appUsageServiceProvider.overrideWithValue(mockAppUsageService),
      jokeScheduleRepositoryProvider.overrideWithValue(mockScheduleRepository),
      jokeReactionsServiceProvider.overrideWithValue(mockJokeReactionsService),
      jokeInteractionsRepositoryProvider.overrideWithValue(
        mockJokeInteractionsRepository,
      ),
      categoryInteractionsRepositoryProvider.overrideWithValue(
        mockCategoryInteractionsRepository,
      ),
      reviewPromptCoordinatorProvider.overrideWithValue(
        mockReviewPromptCoordinator,
      ),
      jokePopulationProvider.overrideWith((ref) {
        return JokePopulationNotifier(mockJokeCloudFunctionService);
      }),
      isOnlineProvider.overrideWith((ref) async* {
        yield true;
      }),
      offlineToOnlineProvider.overrideWith((ref) async* {}),
      scheduleBatchesProvider.overrideWith(
        (ref) => Stream<List<JokeScheduleBatch>>.value(const []),
      ),
    ];

    return ProviderContainer(overrides: overrides);
  }

  GoRouter createRouter() {
    return GoRouter(
      initialLocation: AppRoutes.jokes,
      routes: [
        GoRoute(
          path: AppRoutes.jokes,
          name: RouteNames.jokes,
          builder: (context, _) => const DailyJokesScreen(),
        ),
        GoRoute(
          path: '/other',
          name: 'other',
          builder: (context, _) =>
              const Scaffold(body: Center(child: Text('Other'))),
        ),
      ],
    );
  }

  Widget buildApp(ProviderContainer container, GoRouter router) {
    return UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(routerConfig: router),
    );
  }

  group('DailyJokesScreen', () {
    testWidgets('triggers stale checks while visible and on resume', (
      tester,
    ) async {
      final batch = createBatch();

      when(
        () => mockScheduleRepository.getBatchForMonth(any(), any(), any()),
      ).thenAnswer((invocation) async {
        final int year = invocation.positionalArguments[1] as int;
        final int month = invocation.positionalArguments[2] as int;
        if (year == batch.year && month == batch.month) {
          return batch;
        }
        return null;
      });

      final container = createContainer(batch);
      addTearDown(container.dispose);

      final router = createRouter();
      addTearDown(router.dispose);

      await tester.pumpWidget(buildApp(container, router));

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      container.read(currentRouteProvider.notifier).state = '/initial';
      await tester.pump();
      container.read(currentRouteProvider.notifier).state = AppRoutes.jokes;
      await tester.pump();

      expect(container.read(dailyJokesCheckNowProvider), 1);

      await tester.pump(const Duration(minutes: 1));
      expect(container.read(dailyJokesCheckNowProvider), 2);

      final dynamic state = tester.state(find.byType(DailyJokesScreen));

      (state as dynamic).didChangeAppLifecycleState(AppLifecycleState.paused);
      await tester.pump(const Duration(minutes: 1));
      expect(container.read(dailyJokesCheckNowProvider), 2);

      (state as dynamic).didChangeAppLifecycleState(AppLifecycleState.resumed);
      await tester.pump();
      expect(container.read(dailyJokesCheckNowProvider), 3);

      await tester.pump(const Duration(minutes: 1));
      expect(container.read(dailyJokesCheckNowProvider), 4);
    });

    testWidgets('pauses timer when screen is off the active route', (
      tester,
    ) async {
      final batch = createBatch();

      when(
        () => mockScheduleRepository.getBatchForMonth(any(), any(), any()),
      ).thenAnswer((invocation) async {
        final int year = invocation.positionalArguments[1] as int;
        final int month = invocation.positionalArguments[2] as int;
        if (year == batch.year && month == batch.month) {
          return batch;
        }
        return null;
      });

      final container = createContainer(batch);
      addTearDown(container.dispose);

      final router = createRouter();
      addTearDown(router.dispose);

      await tester.pumpWidget(buildApp(container, router));

      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      container.read(currentRouteProvider.notifier).state = '/initial';
      await tester.pump();
      container.read(currentRouteProvider.notifier).state = AppRoutes.jokes;
      await tester.pump();

      final baseline = container.read(dailyJokesCheckNowProvider);

      container.read(currentRouteProvider.notifier).state = AppRoutes.saved;
      await tester.pump();
      await tester.pump(const Duration(minutes: 2));

      expect(container.read(dailyJokesCheckNowProvider), baseline);

      container.read(currentRouteProvider.notifier).state = AppRoutes.jokes;
      await tester.pump();

      expect(container.read(dailyJokesCheckNowProvider), baseline + 1);
    });
  });
}
