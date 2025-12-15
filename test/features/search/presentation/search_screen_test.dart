import 'dart:async';

import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
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
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_population_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_search_result.dart';
import 'package:snickerdoodle/src/features/search/presentation/search_screen.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';
import 'package:fake_cloud_firestore/fake_cloud_firestore.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

// Additional mock classes for Firebase and core services
class MockSettingsService extends Mock implements SettingsService {}

class MockImageService extends Mock implements ImageService {}

class MockNotificationService extends Mock implements NotificationService {}

class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

class MockReviewsRepository extends Mock implements ReviewsRepository {}

class MockFirebaseAnalytics extends Mock implements FirebaseAnalytics {}

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class MockAppUsageService extends Mock implements AppUsageService {}

class MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

class MockCategoryInteractionsRepository extends Mock
    implements CategoryInteractionsRepository {}

class _FakeBuildContext extends Fake implements BuildContext {}

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
    Map<String, dynamic>? additionalParams,
    String imageQuality = 'low',
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

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() {
    registerFallbackValue(MatchMode.tight);
    registerFallbackValue(SearchScope.userJokeSearch);
    registerFallbackValue(SearchLabel.none);
    registerFallbackValue('');
    registerFallbackValue(<String>[]);
    registerFallbackValue(_FakeBuildContext());
  });

  ProviderContainer createContainer({List<Override> overrides = const []}) {
    final mockFirebaseAnalytics = MockFirebaseAnalytics();
    final mockSettingsService = MockSettingsService();
    final mockImageService = MockImageService();
    final mockNotificationService = MockNotificationService();
    final mockSubscriptionService = MockDailyJokeSubscriptionService();
    final mockReviewsRepository = MockReviewsRepository();
    final mockCloudFunctionService = MockJokeCloudFunctionService();
    final mockAppUsageService = MockAppUsageService();
    final mockJokeInteractionsRepository = MockJokeInteractionsRepository();
    final mockCategoryInteractionsRepository =
        MockCategoryInteractionsRepository();
    final fakeFirestore = FakeFirebaseFirestore();
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
    ).thenAnswer(
      (_) async => const Joke(
        id: 'test-id',
        setupText: 'setup',
        punchlineText: 'punchline',
      ),
    );

    when(
      () => mockCloudFunctionService.populateJoke(
        any(),
        additionalParams: any(named: 'additionalParams'),
        imageQuality: any(named: 'imageQuality'),
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

    when(
      () => mockAppUsageService.logCategoryViewed(any()),
    ).thenAnswer((_) async {});
    when(
      () => mockAppUsageService.getNumSavedJokes(),
    ).thenAnswer((_) async => 0);
    when(
      () => mockAppUsageService.getNumSharedJokes(),
    ).thenAnswer((_) async => 0);
    when(
      () => mockAppUsageService.getNumJokesViewed(),
    ).thenAnswer((_) async => 0);
    when(
      () => mockAppUsageService.getNumJokesViewed(),
    ).thenAnswer((_) async => 0);
    when(
      () => mockAppUsageService.getNumJokesViewed(),
    ).thenAnswer((_) async => 0);
    when(
      () => mockAppUsageService.getNumJokesViewed(),
    ).thenAnswer((_) async => 0);
    when(
      () => mockAppUsageService.logJokeNavigated(any()),
    ).thenAnswer((_) async {});
    when(
      () => mockAppUsageService.logJokeViewed(
        any(),
        context: any(named: 'context'),
      ),
    ).thenAnswer((_) async {});
    when(() => mockAppUsageService.getUnviewedJokeIds(any())).thenAnswer((
      invocation,
    ) async {
      return invocation.positionalArguments.first as List<String>;
    });

    return ProviderContainer(
      overrides: [
        // Firebase analytics
        firebaseAnalyticsProvider.overrideWithValue(mockFirebaseAnalytics),
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
        appUsageServiceProvider.overrideWithValue(mockAppUsageService),
        imageAssetManifestProvider.overrideWith((ref) async => <String>{}),
        firebaseFirestoreProvider.overrideWithValue(fakeFirestore),

        // Firebase mocks
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
        jokeInteractionsRepositoryProvider.overrideWith((ref) {
          return mockJokeInteractionsRepository;
        }),
        categoryInteractionsRepositoryProvider.overrideWith((ref) {
          return mockCategoryInteractionsRepository;
        }),
        ...overrides,
      ],
    );
  }

  Future<void> pumpSearch(
    WidgetTester tester,
    ProviderContainer container,
  ) async {
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: SearchScreen())),
      ),
    );
    await tester.pump();
  }

  Future<void> pumpUntil(
    WidgetTester tester,
    bool Function() condition, {
    int maxTicks = 20,
    Duration step = const Duration(milliseconds: 50),
  }) async {
    for (var i = 0; i < maxTicks; i++) {
      await tester.pump(step);
      if (condition()) {
        return;
      }
    }
  }

  testWidgets(
    'configures app bar with automatic back button when stack can pop',
    (tester) async {
      final container = createContainer();
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Builder(
              builder: (context) {
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => const Scaffold(body: SearchScreen()),
                    ),
                  );
                });
                return const SizedBox.shrink();
              },
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pumpAndSettle();

      final config = container.read(appBarConfigProvider);
      expect(config, isNotNull);
      expect(config!.automaticallyImplyLeading, isTrue);
      final leading = config.leading;
      expect(leading, isA<IconButton>());
      expect(
        (leading as IconButton).key,
        const Key('app_bar_configured_screen-back-button'),
      );
    },
  );

  testWidgets('focuses the search field on load', (tester) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final fieldFinder = find.byKey(const Key('search_screen-search-field'));
    final textField = tester.widget<TextField>(fieldFinder);
    expect(textField.focusNode?.hasFocus, isTrue);
  });

  testWidgets('opening the screen clears any existing query', (tester) async {
    final container = createContainer();
    addTearDown(container.dispose);

    final notifier = container.read(
      searchQueryProvider(SearchScope.userJokeSearch).notifier,
    );
    notifier.state = notifier.state.copyWith(
      query: '${JokeConstants.searchQueryPrefix}legacy',
      label: SearchLabel.category,
    );

    await pumpSearch(tester, container);

    final cleared = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(cleared.query, '');
    expect(cleared.label, JokeConstants.userSearchLabel);
    expect(find.byKey(const Key('search_screen-empty-state')), findsOneWidget);
  });

  testWidgets('submitting <2 chars shows banner and preserves query', (
    tester,
  ) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'a');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await pumpUntil(
      tester,
      () =>
          find.text('Please enter a longer search query').evaluate().isNotEmpty,
    );

    expect(find.text('Please enter a longer search query'), findsOneWidget);
    final searchQuery = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(searchQuery.query, '');
    expect(searchQuery.label, SearchLabel.none);
  });

  testWidgets('renders single-result count', (tester) async {
    final mockRepo = MockJokeRepository();
    when(() => mockRepo.getJokesByIds(any())).thenAnswer((inv) async {
      final ids = (inv.positionalArguments[0] as List<String>);
      return ids
          .map(
            (id) => Joke(
              id: id,
              setupText: 'setup-$id',
              punchlineText: 'punch-$id',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
              publicTimestamp: DateTime.utc(2024, 1, 1),
            ),
          )
          .toList();
    });

    final container = createContainer(
      overrides: [
        jokeRepositoryProvider.overrideWithValue(mockRepo),
        searchResultIdsProvider(SearchScope.userJokeSearch).overrideWith(
          (ref) async => const [JokeSearchResult(id: '1', vectorDistance: 0.0)],
        ),
        jokeStreamByIdProvider('1').overrideWith(
          (ref) => Stream.value(
            Joke(
              id: '1',
              setupText: 's',
              punchlineText: 'p',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
              publicTimestamp: DateTime.utc(2024, 1, 1),
            ),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'cats');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await pumpUntil(tester, () => find.text('1 result').evaluate().isNotEmpty);

    expect(find.byKey(const Key('search-results-count')), findsOneWidget);
    expect(find.text('1 result'), findsOneWidget);
  });

  testWidgets('renders pluralised result count', (tester) async {
    final mockRepo = MockJokeRepository();
    when(() => mockRepo.getJokesByIds(any())).thenAnswer((inv) async {
      final ids = (inv.positionalArguments[0] as List<String>);
      return ids
          .map(
            (id) => Joke(
              id: id,
              setupText: 'setup-$id',
              punchlineText: 'punch-$id',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
            ),
          )
          .toList();
    });

    final container = createContainer(
      overrides: [
        jokeRepositoryProvider.overrideWithValue(mockRepo),
        searchResultIdsProvider(SearchScope.userJokeSearch).overrideWith(
          (ref) async => [
            const JokeSearchResult(id: '1', vectorDistance: 0.1),
            const JokeSearchResult(id: '2', vectorDistance: 0.2),
          ],
        ),
        jokeStreamByIdProvider('1').overrideWith(
          (ref) => Stream.value(
            const Joke(
              id: '1',
              setupText: 'a',
              punchlineText: 'b',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
            ),
          ),
        ),
        jokeStreamByIdProvider('2').overrideWith(
          (ref) => Stream.value(
            const Joke(
              id: '2',
              setupText: 'c',
              punchlineText: 'd',
              setupImageUrl: 'c',
              punchlineImageUrl: 'd',
            ),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'robots');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await pumpUntil(tester, () => find.text('2 results').evaluate().isNotEmpty);

    expect(find.text('2 results'), findsOneWidget);
  });

  testWidgets('shows placeholder when no query has been submitted', (
    tester,
  ) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    expect(find.byKey(const Key('search_screen-empty-state')), findsOneWidget);
    expect(find.byKey(const Key('search-results-count')), findsNothing);
  });

  testWidgets('clear button resets provider and restores placeholder', (
    tester,
  ) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'space cows');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    expect(
      container.read(searchQueryProvider(SearchScope.userJokeSearch)).query,
      '${JokeConstants.searchQueryPrefix}space cows',
    );

    final clearBtn = find.byKey(const Key('search_screen-clear-button'));
    expect(clearBtn, findsOneWidget);

    await tester.tap(clearBtn);
    await tester.pump();

    expect(
      container.read(searchQueryProvider(SearchScope.userJokeSearch)).query,
      '',
    );
    expect(find.byKey(const Key('search_screen-empty-state')), findsOneWidget);
  });

  testWidgets('manual typing sets search label to none', (tester) async {
    final container = createContainer();
    addTearDown(container.dispose);

    await pumpSearch(tester, container);

    final field = find.byKey(const Key('search_screen-search-field'));
    await tester.enterText(field, 'manual search');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    final searchQuery = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(
      searchQuery.query,
      '${JokeConstants.searchQueryPrefix}manual search',
    );
    expect(searchQuery.label, SearchLabel.none);
  });

  testWidgets('prefilled similar search preserves query and shows count', (
    tester,
  ) async {
    final mockRepo = MockJokeRepository();
    when(() => mockRepo.getJokesByIds(any())).thenAnswer((inv) async {
      final ids = (inv.positionalArguments[0] as List<String>);
      return ids
          .map(
            (id) => Joke(
              id: id,
              setupText: 'setup-$id',
              punchlineText: 'punch-$id',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
            ),
          )
          .toList();
    });

    final container = createContainer(
      overrides: [
        jokeRepositoryProvider.overrideWithValue(mockRepo),
        searchResultIdsProvider(SearchScope.userJokeSearch).overrideWith(
          (ref) async => const [JokeSearchResult(id: '1', vectorDistance: 0.0)],
        ),
        jokeStreamByIdProvider('1').overrideWith(
          (ref) => Stream.value(
            const Joke(
              id: '1',
              setupText: 'setup',
              punchlineText: 'punch',
              setupImageUrl: 'a',
              punchlineImageUrl: 'b',
            ),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    // Programmatically set a Similar Search before opening screen
    final notifier = container.read(
      searchQueryProvider(SearchScope.userJokeSearch).notifier,
    );
    notifier.state = notifier.state.copyWith(
      query: '${JokeConstants.searchQueryPrefix}cats and dogs',
      label: SearchLabel.similarJokes,
    );

    await pumpSearch(tester, container);
    await pumpUntil(
      tester,
      () => find.byKey(const Key('search-results-count')).evaluate().isNotEmpty,
    );

    // Text field shows the effective query (without prefix)
    final fieldFinder = find.byKey(const Key('search_screen-search-field'));
    final textField = tester.widget<TextField>(fieldFinder);
    expect(textField.controller?.text, 'cats and dogs');

    // Results count appears (since query preserved and provider returns 1)
    expect(find.byKey(const Key('search-results-count')), findsOneWidget);
    expect(find.text('1 result'), findsOneWidget);

    // Label remains similarJokes
    final searchQuery = container.read(
      searchQueryProvider(SearchScope.userJokeSearch),
    );
    expect(searchQuery.label, SearchLabel.similarJokes);
  });
}
