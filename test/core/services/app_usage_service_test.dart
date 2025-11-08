import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/data/jokes/category_interactions_repository.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/settings/application/brightness_provider.dart';
import 'package:snickerdoodle/src/features/settings/application/feed_screen_status_provider.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

class _MockAnalyticsService extends Mock implements AnalyticsService {}

class _MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class _MockReviewPromptStateStore extends Mock
    implements ReviewPromptStateStore {}

class _MockCategoryInteractionsService extends Mock
    implements CategoryInteractionsRepository {}

class _MockJokeInteractionsRepository extends Mock
    implements JokeInteractionsRepository {}

class _MockJokeRepository extends Mock implements JokeRepository {
  @override
  Future<void> incrementJokeViews(String jokeId) async {}

  @override
  Future<void> incrementJokeSaves(String jokeId) async {}

  @override
  Future<void> decrementJokeSaves(String jokeId) async {}

  @override
  Future<void> incrementJokeShares(String jokeId) async {}
}

class _MockSubscriptionPromptNotifier extends Mock
    implements SubscriptionPromptNotifier {}

class _MockReviewPromptCoordinator extends Mock
    implements ReviewPromptCoordinator {}

class _FakeBuildContext extends Fake implements BuildContext {
  @override
  bool get mounted => true;
}

class _TestRemoteConfigValues implements RemoteConfigValues {
  const _TestRemoteConfigValues({required this.reviewRequestEnabled});

  final bool reviewRequestEnabled;

  @override
  bool getBool(RemoteParam param) {
    if (param == RemoteParam.reviewRequestFromJokeViewed) {
      return reviewRequestEnabled;
    }
    return false;
  }

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

/// Test fixture class that creates fresh mocks for each test
class TestMocks {
  TestMocks() {
    when(() => repo.countNavigated()).thenAnswer((_) async => 0);
  }
  final AnalyticsService analytics = _MockAnalyticsService();
  final JokeCloudFunctionService jokeCloudFn = _MockJokeCloudFunctionService();
  final JokeInteractionsRepository repo = _MockJokeInteractionsRepository();
  final ReviewPromptCoordinator reviewCoordinator =
      _MockReviewPromptCoordinator();
  final ReviewPromptStateStore reviewStore = _MockReviewPromptStateStore();
  final SubscriptionPromptNotifier subscriptionPromptNotifier =
      _MockSubscriptionPromptNotifier();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() {
    // Needed for mocktail named matcher on Brightness
    registerFallbackValue(Brightness.light);
    registerFallbackValue(_FakeBuildContext());
    registerFallbackValue(ReviewRequestSource.jokeViewed);
  });
  String todayString() {
    final now = DateTime.now();
    final year = now.year.toString();
    final month = now.month.toString().padLeft(2, '0');
    final day = now.day.toString().padLeft(2, '0');
    return '$year-$month-$day';
  }

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
  });

  group('AppUsageService.logJokeNavigated', () {
    test('writes to repo when navigation occurs for first time', () async {
      final mocks = TestMocks();
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);

      when(
        () => mocks.repo.getJokeInteraction(any()),
      ).thenAnswer((_) async => null);
      when(() => mocks.repo.setNavigated(any())).thenAnswer((_) async => true);

      final container = ProviderContainer(
        overrides: [
          brightnessProvider.overrideWithValue(Brightness.light),
          subscriptionPromptProvider.overrideWith(
            (ref) => mocks.subscriptionPromptNotifier,
          ),
          reviewPromptCoordinatorProvider.overrideWithValue(
            mocks.reviewCoordinator,
          ),
          remoteConfigValuesProvider.overrideWithValue(
            const _TestRemoteConfigValues(reviewRequestEnabled: false),
          ),
          isAdminProvider.overrideWithValue(false),
          reviewPromptStateStoreProvider.overrideWithValue(mocks.reviewStore),
        ],
      );
      final testRefProvider = Provider<Ref>((ref) => ref);
      final ref = container.read(testRefProvider);

      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mocks.analytics,
        jokeCloudFn: mocks.jokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mocks.repo,
        jokeRepository: _MockJokeRepository(),
        reviewPromptCoordinator: mocks.reviewCoordinator,
        isDebugMode: true,
      );

      await service.logJokeNavigated('nav-1');

      verify(() => mocks.repo.setNavigated('nav-1')).called(1);
      container.dispose();
    });

    test('returns early when joke already navigated', () async {
      final mocks = TestMocks();
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);

      final now = DateTime.now();
      final interaction = JokeInteraction(
        jokeId: 'nav-2',
        navigatedTimestamp: now,
        viewedTimestamp: null,
        savedTimestamp: null,
        sharedTimestamp: null,
        lastUpdateTimestamp: now,
      );

      when(
        () => mocks.repo.getJokeInteraction('nav-2'),
      ).thenAnswer((_) async => interaction);

      final container = ProviderContainer(
        overrides: [
          brightnessProvider.overrideWithValue(Brightness.light),
          subscriptionPromptProvider.overrideWith(
            (ref) => mocks.subscriptionPromptNotifier,
          ),
          reviewPromptCoordinatorProvider.overrideWithValue(
            mocks.reviewCoordinator,
          ),
          remoteConfigValuesProvider.overrideWithValue(
            const _TestRemoteConfigValues(reviewRequestEnabled: false),
          ),
          isAdminProvider.overrideWithValue(false),
          reviewPromptStateStoreProvider.overrideWithValue(mocks.reviewStore),
        ],
      );
      final testRefProvider = Provider<Ref>((ref) => ref);
      final ref = container.read(testRefProvider);

      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mocks.analytics,
        jokeCloudFn: mocks.jokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mocks.repo,
        jokeRepository: _MockJokeRepository(),
        reviewPromptCoordinator: mocks.reviewCoordinator,
        isDebugMode: true,
      );

      await service.logJokeNavigated('nav-2');

      verifyNever(() => mocks.repo.setNavigated(any()));
      container.dispose();
    });
  });

  group('AppUsageService.logAppUsage', () {
    test(
      'first run initializes dates and increments unique day count',
      () async {
        final mocks = TestMocks();
        final prefs = await SharedPreferences.getInstance();
        final settingsService = SettingsService(prefs);
        when(
          () => mocks.analytics.logAppUsageDays(
            numDaysUsed: any<int>(named: 'numDaysUsed'),
            brightness: any<Brightness>(named: 'brightness'),
            homepage: any<String>(named: 'homepage'),
          ),
        ).thenAnswer((_) async {});
        final container = ProviderContainer(
          overrides: [
            brightnessProvider.overrideWithValue(Brightness.light),
            feedScreenStatusProvider.overrideWithValue(false),
          ],
        );
        final ref = container.read(Provider<Ref>((ref) => ref));
        final service = AppUsageService(
          settingsService: settingsService,
          ref: ref,
          analyticsService: mocks.analytics,
          jokeCloudFn: mocks.jokeCloudFn,
          categoryInteractionsService: _MockCategoryInteractionsService(),
          jokeInteractionsRepository: mocks.repo,
          jokeRepository: _MockJokeRepository(),
          reviewPromptCoordinator: mocks.reviewCoordinator,
          isDebugMode: true,
        );

        await service.logAppUsage();

        expect(await service.getFirstUsedDate(), todayString());
        expect(await service.getLastUsedDate(), todayString());
        expect(await service.getNumDaysUsed(), 1);

        verify(
          () => mocks.analytics.logAppUsageDays(
            numDaysUsed: 1,
            brightness: any(named: 'brightness'),
            homepage: any(named: 'homepage'),
          ),
        ).called(1);
      },
    );

    test('same day run does not increment unique day count', () async {
      final mocks = TestMocks();
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      when(
        () => mocks.analytics.logAppUsageDays(
          numDaysUsed: any<int>(named: 'numDaysUsed'),
          brightness: any<Brightness>(named: 'brightness'),
          homepage: any<String>(named: 'homepage'),
        ),
      ).thenAnswer((_) async {});
      final container = ProviderContainer(
        overrides: [
          brightnessProvider.overrideWithValue(Brightness.light),
          feedScreenStatusProvider.overrideWithValue(false),
        ],
      );
      final ref = container.read(Provider<Ref>((ref) => ref));
      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mocks.analytics,
        jokeCloudFn: mocks.jokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mocks.repo,
        jokeRepository: _MockJokeRepository(),
        reviewPromptCoordinator: mocks.reviewCoordinator,
        isDebugMode: true,
      );

      await service.logAppUsage();
      await service.logAppUsage();

      expect(await service.getNumDaysUsed(), 1);
      expect(await service.getLastUsedDate(), todayString());

      verify(
        () => mocks.analytics.logAppUsageDays(
          numDaysUsed: any(named: 'numDaysUsed'),
          brightness: any(named: 'brightness'),
          homepage: any(named: 'homepage'),
        ),
      ).called(1);
    });

    test(
      'new day increments unique day count and updates last_used_date',
      () async {
        final mocks = TestMocks();
        final prefs = await SharedPreferences.getInstance();
        final settingsService = SettingsService(prefs);
        when(
          () => mocks.analytics.logAppUsageDays(
            numDaysUsed: any<int>(named: 'numDaysUsed'),
            brightness: any<Brightness>(named: 'brightness'),
            homepage: any<String>(named: 'homepage'),
          ),
        ).thenAnswer((_) async {});
        final container = ProviderContainer(
          overrides: [
            brightnessProvider.overrideWithValue(Brightness.light),
            feedScreenStatusProvider.overrideWithValue(false),
          ],
        );
        final ref = container.read(Provider<Ref>((ref) => ref));
        final service = AppUsageService(
          settingsService: settingsService,
          ref: ref,
          analyticsService: mocks.analytics,
          jokeCloudFn: mocks.jokeCloudFn,
          categoryInteractionsService: _MockCategoryInteractionsService(),
          jokeInteractionsRepository: mocks.repo,
          jokeRepository: _MockJokeRepository(),
          reviewPromptCoordinator: mocks.reviewCoordinator,
          isDebugMode: true,
        );

        await service.logAppUsage();
        expect(await service.getNumDaysUsed(), 1);

        // Simulate that the last used date was yesterday
        final yesterday = DateTime.now().subtract(const Duration(days: 1));
        final yesterdayStr =
            '${yesterday.year.toString()}-${yesterday.month.toString().padLeft(2, '0')}-${yesterday.day.toString().padLeft(2, '0')}';
        await settingsService.setString('last_used_date', yesterdayStr);

        await service.logAppUsage();

        expect(await service.getNumDaysUsed(), 2);
        expect(await service.getLastUsedDate(), todayString());

        verify(
          () => mocks.analytics.logAppUsageDays(
            numDaysUsed: 2,
            brightness: any(named: 'brightness'),
            homepage: any(named: 'homepage'),
          ),
        ).called(1);
      },
    );
  });

  group('AppUsageService.logJokeViewed', () {
    test(
      'writes to repo, evaluates subscription prompt, and counts from repo',
      () async {
        final mocks = TestMocks();
        final prefs = await SharedPreferences.getInstance();
        final settingsService = SettingsService(prefs);

        var viewedCount = 0;
        when(
          () => mocks.repo.getJokeInteraction(any()),
        ).thenAnswer((_) async => null);
        when(() => mocks.repo.setViewed(any())).thenAnswer((_) async {
          viewedCount += 1;
          return true;
        });
        when(
          () => mocks.repo.countViewed(),
        ).thenAnswer((_) async => viewedCount);
        when(() => mocks.repo.countSaved()).thenAnswer((_) async => 0);
        when(() => mocks.repo.countShared()).thenAnswer((_) async => 0);
        when(
          () => mocks.subscriptionPromptNotifier.maybePromptAfterJokeViewed(
            any(),
          ),
        ).thenReturn(false);
        when(
          () => mocks.subscriptionPromptNotifier.state,
        ).thenReturn(const SubscriptionPromptState());
        when(
          () => mocks.reviewCoordinator.maybePromptForReview(
            numDaysUsed: any(named: 'numDaysUsed'),
            numSavedJokes: any(named: 'numSavedJokes'),
            numSharedJokes: any(named: 'numSharedJokes'),
            numJokesViewed: any(named: 'numJokesViewed'),
            source: any(named: 'source'),
            context: any(named: 'context'),
          ),
        ).thenAnswer((_) async {});
        when(() => mocks.reviewStore.hasRequested()).thenReturn(false);

        final container = ProviderContainer(
          overrides: [
            brightnessProvider.overrideWithValue(Brightness.light),
            subscriptionPromptProvider.overrideWith(
              (ref) => mocks.subscriptionPromptNotifier,
            ),
            reviewPromptCoordinatorProvider.overrideWithValue(
              mocks.reviewCoordinator,
            ),
            remoteConfigValuesProvider.overrideWithValue(
              const _TestRemoteConfigValues(reviewRequestEnabled: false),
            ),
            isAdminProvider.overrideWithValue(false),
            reviewPromptStateStoreProvider.overrideWithValue(mocks.reviewStore),
          ],
        );
        final testRefProvider = Provider<Ref>((ref) => ref);
        final ref = container.read(testRefProvider);

        final service = AppUsageService(
          settingsService: settingsService,
          ref: ref,
          analyticsService: mocks.analytics,
          jokeCloudFn: mocks.jokeCloudFn,
          categoryInteractionsService: _MockCategoryInteractionsService(),
          jokeInteractionsRepository: mocks.repo,
          jokeRepository: _MockJokeRepository(),
          reviewPromptCoordinator: mocks.reviewCoordinator,
          isDebugMode: true,
        );

        expect(await service.getNumJokesViewed(), 0);
        await service.logJokeViewed('j1', context: _FakeBuildContext());
        expect(await service.getNumJokesViewed(), 1);
        await service.logJokeViewed('j2', context: _FakeBuildContext());
        expect(await service.getNumJokesViewed(), 2);

        verify(() => mocks.repo.setViewed('j1')).called(1);
        verify(() => mocks.repo.setViewed('j2')).called(1);
        verify(
          () => mocks.subscriptionPromptNotifier.maybePromptAfterJokeViewed(
            any(),
          ),
        ).called(2);
        verifyNever(
          () => mocks.reviewCoordinator.maybePromptForReview(
            numDaysUsed: any(named: 'numDaysUsed'),
            numSavedJokes: any(named: 'numSavedJokes'),
            numSharedJokes: any(named: 'numSharedJokes'),
            numJokesViewed: any(named: 'numJokesViewed'),
            source: any(named: 'source'),
            context: any(named: 'context'),
          ),
        );
        container.dispose();
      },
    );

    test('returns early when joke already viewed', () async {
      final mocks = TestMocks();
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);

      final now = DateTime.now();
      final existingInteraction = JokeInteraction(
        jokeId: 'j1',
        viewedTimestamp: now,
        savedTimestamp: null,
        sharedTimestamp: null,
        lastUpdateTimestamp: now,
      );

      when(
        () => mocks.repo.getJokeInteraction('j1'),
      ).thenAnswer((_) async => existingInteraction);
      when(() => mocks.reviewStore.hasRequested()).thenReturn(false);
      when(
        () => mocks.subscriptionPromptNotifier.state,
      ).thenReturn(const SubscriptionPromptState());

      final container = ProviderContainer(
        overrides: [
          brightnessProvider.overrideWithValue(Brightness.light),
          subscriptionPromptProvider.overrideWith(
            (ref) => mocks.subscriptionPromptNotifier,
          ),
          reviewPromptCoordinatorProvider.overrideWithValue(
            mocks.reviewCoordinator,
          ),
          remoteConfigValuesProvider.overrideWithValue(
            const _TestRemoteConfigValues(reviewRequestEnabled: true),
          ),
          isAdminProvider.overrideWithValue(false),
          reviewPromptStateStoreProvider.overrideWithValue(mocks.reviewStore),
        ],
      );
      final testRefProvider = Provider<Ref>((ref) => ref);
      final ref = container.read(testRefProvider);

      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mocks.analytics,
        jokeCloudFn: mocks.jokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mocks.repo,
        jokeRepository: _MockJokeRepository(),
        reviewPromptCoordinator: mocks.reviewCoordinator,
        isDebugMode: true,
      );

      await service.logJokeViewed('j1', context: _FakeBuildContext());

      verifyNever(() => mocks.repo.setViewed(any()));
      verifyNever(
        () =>
            mocks.subscriptionPromptNotifier.maybePromptAfterJokeViewed(any()),
      );
      verifyNever(
        () => mocks.reviewCoordinator.maybePromptForReview(
          numDaysUsed: any(named: 'numDaysUsed'),
          numSavedJokes: any(named: 'numSavedJokes'),
          numSharedJokes: any(named: 'numSharedJokes'),
          numJokesViewed: any(named: 'numJokesViewed'),
          source: any(named: 'source'),
          context: any(named: 'context'),
        ),
      );
      container.dispose();
    });

    test(
      'does not prompt for review when subscription prompt was shown',
      () async {
        final mocks = TestMocks();
        final prefs = await SharedPreferences.getInstance();
        final settingsService = SettingsService(prefs);

        when(
          () => mocks.repo.getJokeInteraction(any()),
        ).thenAnswer((_) async => null);
        var viewedCount = 0;
        when(() => mocks.repo.setViewed(any())).thenAnswer((_) async {
          viewedCount += 1;
          return true;
        });
        when(
          () => mocks.repo.countViewed(),
        ).thenAnswer((_) async => viewedCount);
        when(() => mocks.repo.countSaved()).thenAnswer((_) async => 0);
        when(() => mocks.repo.countShared()).thenAnswer((_) async => 0);
        when(
          () => mocks.subscriptionPromptNotifier.maybePromptAfterJokeViewed(
            any(),
          ),
        ).thenReturn(true);
        when(
          () => mocks.subscriptionPromptNotifier.state,
        ).thenReturn(const SubscriptionPromptState());
        when(
          () => mocks.reviewCoordinator.maybePromptForReview(
            numDaysUsed: any(named: 'numDaysUsed'),
            numSavedJokes: any(named: 'numSavedJokes'),
            numSharedJokes: any(named: 'numSharedJokes'),
            numJokesViewed: any(named: 'numJokesViewed'),
            source: any(named: 'source'),
            context: any(named: 'context'),
          ),
        ).thenAnswer((_) async {});
        when(() => mocks.reviewStore.hasRequested()).thenReturn(false);

        final container = ProviderContainer(
          overrides: [
            brightnessProvider.overrideWithValue(Brightness.light),
            subscriptionPromptProvider.overrideWith(
              (ref) => mocks.subscriptionPromptNotifier,
            ),
            reviewPromptCoordinatorProvider.overrideWithValue(
              mocks.reviewCoordinator,
            ),
            remoteConfigValuesProvider.overrideWithValue(
              const _TestRemoteConfigValues(reviewRequestEnabled: true),
            ),
            isAdminProvider.overrideWithValue(false),
            reviewPromptStateStoreProvider.overrideWithValue(mocks.reviewStore),
          ],
        );
        final testRefProvider = Provider<Ref>((ref) => ref);
        final ref = container.read(testRefProvider);

        final service = AppUsageService(
          settingsService: settingsService,
          ref: ref,
          analyticsService: mocks.analytics,
          jokeCloudFn: mocks.jokeCloudFn,
          categoryInteractionsService: _MockCategoryInteractionsService(),
          jokeInteractionsRepository: mocks.repo,
          jokeRepository: _MockJokeRepository(),
          reviewPromptCoordinator: mocks.reviewCoordinator,
          isDebugMode: true,
        );

        await service.logJokeViewed('j1', context: _FakeBuildContext());

        verify(
          () => mocks.subscriptionPromptNotifier.maybePromptAfterJokeViewed(1),
        ).called(1);
        verifyNever(
          () => mocks.reviewCoordinator.maybePromptForReview(
            numDaysUsed: any(named: 'numDaysUsed'),
            numSavedJokes: any(named: 'numSavedJokes'),
            numSharedJokes: any(named: 'numSharedJokes'),
            numJokesViewed: any(named: 'numJokesViewed'),
            source: any(named: 'source'),
            context: any(named: 'context'),
          ),
        );
        container.dispose();
      },
    );

    test(
      'prompts for review when enabled and subscription prompt not shown',
      () async {
        final mocks = TestMocks();
        final prefs = await SharedPreferences.getInstance();
        final settingsService = SettingsService(prefs);

        when(
          () => mocks.repo.getJokeInteraction(any()),
        ).thenAnswer((_) async => null);
        var viewedCount = 0;
        when(() => mocks.repo.setViewed(any())).thenAnswer((_) async {
          viewedCount += 1;
          return true;
        });
        when(
          () => mocks.repo.countViewed(),
        ).thenAnswer((_) async => viewedCount);
        when(() => mocks.repo.countSaved()).thenAnswer((_) async => 0);
        when(() => mocks.repo.countShared()).thenAnswer((_) async => 0);
        when(
          () => mocks.subscriptionPromptNotifier.maybePromptAfterJokeViewed(
            any(),
          ),
        ).thenReturn(false);
        when(
          () => mocks.subscriptionPromptNotifier.state,
        ).thenReturn(const SubscriptionPromptState());
        when(
          () => mocks.reviewCoordinator.maybePromptForReview(
            numDaysUsed: any(named: 'numDaysUsed'),
            numSavedJokes: any(named: 'numSavedJokes'),
            numSharedJokes: any(named: 'numSharedJokes'),
            numJokesViewed: any(named: 'numJokesViewed'),
            source: any(named: 'source'),
            context: any(named: 'context'),
          ),
        ).thenAnswer((_) async {});
        when(() => mocks.reviewStore.hasRequested()).thenReturn(false);

        final container = ProviderContainer(
          overrides: [
            brightnessProvider.overrideWithValue(Brightness.light),
            subscriptionPromptProvider.overrideWith(
              (ref) => mocks.subscriptionPromptNotifier,
            ),
            reviewPromptCoordinatorProvider.overrideWithValue(
              mocks.reviewCoordinator,
            ),
            remoteConfigValuesProvider.overrideWithValue(
              const _TestRemoteConfigValues(reviewRequestEnabled: true),
            ),
            isAdminProvider.overrideWithValue(false),
            reviewPromptStateStoreProvider.overrideWithValue(mocks.reviewStore),
          ],
        );
        final testRefProvider = Provider<Ref>((ref) => ref);
        final ref = container.read(testRefProvider);

        final service = AppUsageService(
          settingsService: settingsService,
          ref: ref,
          analyticsService: mocks.analytics,
          jokeCloudFn: mocks.jokeCloudFn,
          categoryInteractionsService: _MockCategoryInteractionsService(),
          jokeInteractionsRepository: mocks.repo,
          jokeRepository: _MockJokeRepository(),
          reviewPromptCoordinator: mocks.reviewCoordinator,
          isDebugMode: true,
        );

        await service.logJokeViewed('j1', context: _FakeBuildContext());

        verify(
          () => mocks.subscriptionPromptNotifier.maybePromptAfterJokeViewed(1),
        ).called(1);
        verify(
          () => mocks.reviewCoordinator.maybePromptForReview(
            numDaysUsed: any(named: 'numDaysUsed'),
            numSavedJokes: any(named: 'numSavedJokes'),
            numSharedJokes: any(named: 'numSharedJokes'),
            numJokesViewed: any(named: 'numJokesViewed'),
            source: ReviewRequestSource.jokeViewed,
            context: any(named: 'context'),
          ),
        ).called(1);
        container.dispose();
      },
    );
  });

  group('AppUsageService saved/shared via repo', () {
    test('saveJoke and unsaveJoke update repo and counts from repo', () async {
      final mocks = TestMocks();
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final container = ProviderContainer();
      final ref = container.read(Provider<Ref>((ref) => ref));

      var savedCount = 0;
      when(() => mocks.repo.setSaved(any())).thenAnswer((_) async {
        savedCount += 1;
        return true;
      });
      when(() => mocks.repo.setUnsaved(any())).thenAnswer((_) async {
        savedCount = savedCount > 0 ? savedCount - 1 : 0;
        return true;
      });
      when(() => mocks.repo.countSaved()).thenAnswer((_) async => savedCount);
      when(() => mocks.repo.countViewed()).thenAnswer((_) async => 0);
      when(() => mocks.repo.countShared()).thenAnswer((_) async => 0);

      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mocks.analytics,
        jokeCloudFn: mocks.jokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mocks.repo,
        jokeRepository: _MockJokeRepository(),
        reviewPromptCoordinator: mocks.reviewCoordinator,
        isDebugMode: true,
      );

      expect(await service.getNumSavedJokes(), 0);
      await service.saveJoke('s1', context: _FakeBuildContext());
      expect(await service.getNumSavedJokes(), 1);
      await service.saveJoke('s2', context: _FakeBuildContext());
      expect(await service.getNumSavedJokes(), 2);
      await service.unsaveJoke('s1');
      expect(await service.getNumSavedJokes(), 1);
      await service.unsaveJoke('s2');
      expect(await service.getNumSavedJokes(), 0);

      verify(() => mocks.repo.setSaved('s1')).called(1);
      verify(() => mocks.repo.setSaved('s2')).called(1);
      verify(() => mocks.repo.setUnsaved('s1')).called(1);
      verify(() => mocks.repo.setUnsaved('s2')).called(1);
    });

    test('getSavedJokeIds mirrors repository order', () async {
      final mocks = TestMocks();
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final container = ProviderContainer();
      final ref = container.read(Provider<Ref>((ref) => ref));

      final savedAtOne = DateTime(2024, 1, 1);
      final savedAtTwo = DateTime(2024, 2, 1);
      when(() => mocks.repo.getSavedJokeInteractions()).thenAnswer(
        (_) async => [
          JokeInteraction(
            jokeId: 'first',
            viewedTimestamp: null,
            savedTimestamp: savedAtOne,
            sharedTimestamp: null,
            lastUpdateTimestamp: savedAtOne,
          ),
          JokeInteraction(
            jokeId: 'second',
            viewedTimestamp: null,
            savedTimestamp: savedAtTwo,
            sharedTimestamp: null,
            lastUpdateTimestamp: savedAtTwo,
          ),
        ],
      );

      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mocks.analytics,
        jokeCloudFn: mocks.jokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mocks.repo,
        jokeRepository: _MockJokeRepository(),
        reviewPromptCoordinator: mocks.reviewCoordinator,
        isDebugMode: true,
      );

      expect(await service.getSavedJokeIds(), ['first', 'second']);
      verify(() => mocks.repo.getSavedJokeInteractions()).called(1);
    });

    test('getViewedJokeIds mirrors repository order', () async {
      final mocks = TestMocks();
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final container = ProviderContainer();
      final ref = container.read(Provider<Ref>((ref) => ref));

      final viewedAtOne = DateTime(2024, 3, 1);
      final viewedAtTwo = DateTime(2024, 3, 5);
      when(() => mocks.repo.getViewedJokeInteractions()).thenAnswer(
        (_) async => [
          JokeInteraction(
            jokeId: 'v1',
            viewedTimestamp: viewedAtOne,
            savedTimestamp: null,
            sharedTimestamp: null,
            lastUpdateTimestamp: viewedAtOne,
          ),
          JokeInteraction(
            jokeId: 'v2',
            viewedTimestamp: viewedAtTwo,
            savedTimestamp: null,
            sharedTimestamp: null,
            lastUpdateTimestamp: viewedAtTwo,
          ),
        ],
      );

      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mocks.analytics,
        jokeCloudFn: mocks.jokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mocks.repo,
        jokeRepository: _MockJokeRepository(),
        reviewPromptCoordinator: mocks.reviewCoordinator,
        isDebugMode: true,
      );

      expect(await service.getViewedJokeIds(), ['v1', 'v2']);
      verify(() => mocks.repo.getViewedJokeInteractions()).called(1);
    });

    test('getSharedJokeIds mirrors repository order', () async {
      final mocks = TestMocks();
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final container = ProviderContainer();
      final ref = container.read(Provider<Ref>((ref) => ref));

      final sharedAtOne = DateTime(2024, 4, 1);
      final sharedAtTwo = DateTime(2024, 4, 10);
      when(() => mocks.repo.getSharedJokeInteractions()).thenAnswer(
        (_) async => [
          JokeInteraction(
            jokeId: 's1',
            viewedTimestamp: null,
            savedTimestamp: null,
            sharedTimestamp: sharedAtOne,
            lastUpdateTimestamp: sharedAtOne,
          ),
          JokeInteraction(
            jokeId: 's2',
            viewedTimestamp: null,
            savedTimestamp: null,
            sharedTimestamp: sharedAtTwo,
            lastUpdateTimestamp: sharedAtTwo,
          ),
        ],
      );

      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mocks.analytics,
        jokeCloudFn: mocks.jokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mocks.repo,
        jokeRepository: _MockJokeRepository(),
        reviewPromptCoordinator: mocks.reviewCoordinator,
        isDebugMode: true,
      );

      expect(await service.getSharedJokeIds(), ['s1', 's2']);
      verify(() => mocks.repo.getSharedJokeInteractions()).called(1);
    });

    test('getUnviewedJokeIds returns only unviewed joke IDs', () async {
      final mocks = TestMocks();
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final container = ProviderContainer();
      final ref = container.read(Provider<Ref>((ref) => ref));

      final viewedAtOne = DateTime(2024, 3, 1);
      final viewedAtTwo = DateTime(2024, 3, 5);
      when(() => mocks.repo.getJokeInteractions(any())).thenAnswer((
        invocation,
      ) async {
        final jokeIds = invocation.positionalArguments.first as List<String>;
        // Return interactions for jokes that have been viewed
        return jokeIds
            .where((id) => ['joke-1', 'joke-3'].contains(id))
            .map(
              (id) => JokeInteraction(
                jokeId: id,
                viewedTimestamp: id == 'joke-1' ? viewedAtOne : viewedAtTwo,
                savedTimestamp: null,
                sharedTimestamp: null,
                lastUpdateTimestamp: id == 'joke-1' ? viewedAtOne : viewedAtTwo,
              ),
            )
            .toList();
      });

      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mocks.analytics,
        jokeCloudFn: mocks.jokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mocks.repo,
        jokeRepository: _MockJokeRepository(),
        reviewPromptCoordinator: mocks.reviewCoordinator,
        isDebugMode: true,
      );

      final jokeIds = ['joke-1', 'joke-2', 'joke-3', 'joke-4'];
      final unviewedIds = await service.getUnviewedJokeIds(jokeIds);

      // Only unviewed jokes should be returned
      expect(unviewedIds, contains('joke-2'));
      expect(unviewedIds, contains('joke-4'));
      expect(unviewedIds, isNot(contains('joke-1')));
      expect(unviewedIds, isNot(contains('joke-3')));
      expect(unviewedIds.length, 2);

      verify(() => mocks.repo.getJokeInteractions(jokeIds)).called(1);
    });

    test(
      'getUnviewedJokeIds returns all joke IDs when none are viewed',
      () async {
        final mocks = TestMocks();
        final prefs = await SharedPreferences.getInstance();
        final settingsService = SettingsService(prefs);
        final container = ProviderContainer();
        final ref = container.read(Provider<Ref>((ref) => ref));

        when(
          () => mocks.repo.getJokeInteractions(any()),
        ).thenAnswer((_) async => <JokeInteraction>[]);

        final service = AppUsageService(
          settingsService: settingsService,
          ref: ref,
          analyticsService: mocks.analytics,
          jokeCloudFn: mocks.jokeCloudFn,
          categoryInteractionsService: _MockCategoryInteractionsService(),
          jokeInteractionsRepository: mocks.repo,
          jokeRepository: _MockJokeRepository(),
          reviewPromptCoordinator: mocks.reviewCoordinator,
          isDebugMode: true,
        );

        final jokeIds = ['joke-1', 'joke-2', 'joke-3'];
        final unviewedIds = await service.getUnviewedJokeIds(jokeIds);

        // All jokes should be returned when none are viewed
        expect(unviewedIds, containsAll(jokeIds));
        expect(unviewedIds.length, 3);

        verify(() => mocks.repo.getJokeInteractions(jokeIds)).called(1);
      },
    );

    test(
      'getUnviewedJokeIds returns empty list when all jokes are viewed',
      () async {
        final mocks = TestMocks();
        final prefs = await SharedPreferences.getInstance();
        final settingsService = SettingsService(prefs);
        final container = ProviderContainer();
        final ref = container.read(Provider<Ref>((ref) => ref));

        final viewedAtOne = DateTime(2024, 3, 1);
        final viewedAtTwo = DateTime(2024, 3, 5);
        final viewedAtThree = DateTime(2024, 3, 10);
        when(() => mocks.repo.getJokeInteractions(any())).thenAnswer((
          invocation,
        ) async {
          final jokeIds = invocation.positionalArguments.first as List<String>;
          // Return interactions for all jokes (all viewed)
          return jokeIds.map((id) {
            DateTime viewedAt;
            switch (id) {
              case 'joke-1':
                viewedAt = viewedAtOne;
                break;
              case 'joke-2':
                viewedAt = viewedAtTwo;
                break;
              case 'joke-3':
                viewedAt = viewedAtThree;
                break;
              default:
                viewedAt = DateTime.now();
            }
            return JokeInteraction(
              jokeId: id,
              viewedTimestamp: viewedAt,
              savedTimestamp: null,
              sharedTimestamp: null,
              lastUpdateTimestamp: viewedAt,
            );
          }).toList();
        });

        final service = AppUsageService(
          settingsService: settingsService,
          ref: ref,
          analyticsService: mocks.analytics,
          jokeCloudFn: mocks.jokeCloudFn,
          categoryInteractionsService: _MockCategoryInteractionsService(),
          jokeInteractionsRepository: mocks.repo,
          jokeRepository: _MockJokeRepository(),
          reviewPromptCoordinator: mocks.reviewCoordinator,
          isDebugMode: true,
        );

        final jokeIds = ['joke-1', 'joke-2', 'joke-3'];
        final unviewedIds = await service.getUnviewedJokeIds(jokeIds);

        // No jokes should be returned when all are viewed
        expect(unviewedIds, isEmpty);

        verify(() => mocks.repo.getJokeInteractions(jokeIds)).called(1);
      },
    );

    test('getUnviewedJokeIds handles empty input list', () async {
      final mocks = TestMocks();
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final container = ProviderContainer();
      final ref = container.read(Provider<Ref>((ref) => ref));

      when(
        () => mocks.repo.getJokeInteractions(any()),
      ).thenAnswer((_) async => <JokeInteraction>[]);

      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mocks.analytics,
        jokeCloudFn: mocks.jokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mocks.repo,
        jokeRepository: _MockJokeRepository(),
        reviewPromptCoordinator: mocks.reviewCoordinator,
        isDebugMode: true,
      );

      final unviewedIds = await service.getUnviewedJokeIds([]);

      // Empty list should be returned
      expect(unviewedIds, isEmpty);

      // Should not call repository with empty list
      verifyNever(() => mocks.repo.getJokeInteractions(any()));
    });

    test('shareJoke updates repo and counts from repo', () async {
      final mocks = TestMocks();
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final container = ProviderContainer(
        overrides: [
          brightnessProvider.overrideWithValue(Brightness.light),
          feedScreenStatusProvider.overrideWithValue(false),
        ],
      );
      final ref = container.read(Provider<Ref>((ref) => ref));

      var sharedCount = 0;
      when(() => mocks.repo.setShared(any())).thenAnswer((_) async {
        sharedCount += 1;
        return true;
      });
      when(() => mocks.repo.countShared()).thenAnswer((_) async => sharedCount);
      when(() => mocks.repo.countViewed()).thenAnswer((_) async => 0);
      when(() => mocks.repo.countSaved()).thenAnswer((_) async => 0);

      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mocks.analytics,
        jokeCloudFn: mocks.jokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mocks.repo,
        jokeRepository: _MockJokeRepository(),
        reviewPromptCoordinator: mocks.reviewCoordinator,
        isDebugMode: true,
      );

      expect(await service.getNumSharedJokes(), 0);
      await service.shareJoke('x1', context: _FakeBuildContext());
      expect(await service.getNumSharedJokes(), 1);
      await service.shareJoke('x2', context: _FakeBuildContext());
      expect(await service.getNumSharedJokes(), 2);

      verify(() => mocks.repo.setShared('x1')).called(1);
      verify(() => mocks.repo.setShared('x2')).called(1);
    });
  });

  group('AppUsageService._pushUsageSnapshot', () {
    test('passes correct requestedReview value to cloud function', () async {
      final mocks = TestMocks();
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);

      when(() => mocks.reviewStore.hasRequested()).thenAnswer((_) => true);
      when(
        () => mocks.jokeCloudFn.trackUsage(
          numDaysUsed: any<int>(named: 'numDaysUsed'),
          numSaved: any<int>(named: 'numSaved'),
          numViewed: any<int>(named: 'numViewed'),
          numNavigated: any<int>(named: 'numNavigated'),
          numShared: any<int>(named: 'numShared'),
          requestedReview: any<bool?>(named: 'requestedReview'),
        ),
      ).thenAnswer((_) async {});

      final testRefProvider = Provider<Ref>((ref) => ref);
      final container = ProviderContainer(
        overrides: [
          brightnessProvider.overrideWithValue(Brightness.light),
          feedScreenStatusProvider.overrideWithValue(false),
          reviewPromptStateStoreProvider.overrideWithValue(mocks.reviewStore),
          isAdminProvider.overrideWithValue(false),
        ],
      );
      final ref = container.read(testRefProvider);

      // Stub repo counts used by _pushUsageSnapshot
      when(() => mocks.repo.countSaved()).thenAnswer((_) async => 2);
      when(() => mocks.repo.countViewed()).thenAnswer((_) async => 5);
      when(() => mocks.repo.countNavigated()).thenAnswer((_) async => 4);
      when(() => mocks.repo.countShared()).thenAnswer((_) async => 1);

      final testService = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mocks.analytics,
        jokeCloudFn: mocks.jokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mocks.repo,
        jokeRepository: _MockJokeRepository(),
        reviewPromptCoordinator: mocks.reviewCoordinator,
        isDebugMode: false,
      );

      // Simulate a new day to trigger _pushUsageSnapshot
      final yesterday = DateTime.now().subtract(const Duration(days: 1));
      final yesterdayStr =
          '${yesterday.year.toString()}-${yesterday.month.toString().padLeft(2, '0')}-${yesterday.day.toString().padLeft(2, '0')}';
      await settingsService.setString('last_used_date', yesterdayStr);

      await testService.logAppUsage();

      // Allow microtasks to complete
      await Future.delayed(Duration.zero);

      final captured = verify(
        () => mocks.jokeCloudFn.trackUsage(
          numDaysUsed: any(named: 'numDaysUsed'),
          numSaved: any(named: 'numSaved'),
          numViewed: any(named: 'numViewed'),
          numNavigated: any(named: 'numNavigated'),
          numShared: any(named: 'numShared'),
          requestedReview: captureAny(named: 'requestedReview'),
        ),
      ).captured;

      expect(captured.first, isTrue);
    });
  });
}
