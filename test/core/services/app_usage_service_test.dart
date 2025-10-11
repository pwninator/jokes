import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/settings/application/brightness_provider.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';
import 'package:snickerdoodle/src/data/jokes/category_interactions_service.dart';

class _MockAnalyticsService extends Mock implements AnalyticsService {}

class _MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class _MockReviewPromptStateStore extends Mock
    implements ReviewPromptStateStore {}

class _MockCategoryInteractionsService extends Mock
    implements CategoryInteractionsService {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() {
    // Needed for mocktail named matcher on Brightness
    registerFallbackValue(Brightness.light);
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

  group('AppUsageService.logAppUsage', () {
    test(
      'first run initializes dates and increments unique day count',
      () async {
        final prefs = await SharedPreferences.getInstance();
        final settingsService = SettingsService(prefs);
        final mockAnalytics = _MockAnalyticsService();
        when(
          () => mockAnalytics.logAppUsageDays(
            numDaysUsed: any<int>(named: 'numDaysUsed'),
            brightness: any<Brightness>(named: 'brightness'),
          ),
        ).thenAnswer((_) async {});
        final container = ProviderContainer(
          overrides: [brightnessProvider.overrideWithValue(Brightness.light)],
        );
        final ref = container.read(Provider<Ref>((ref) => ref));
        final mockJokeCloudFn = _MockJokeCloudFunctionService();
        final service = AppUsageService(
          settingsService: settingsService,
          ref: ref,
          analyticsService: mockAnalytics,
          jokeCloudFn: mockJokeCloudFn,
          categoryInteractionsService: _MockCategoryInteractionsService(),
        );

        await service.logAppUsage();

        expect(await service.getFirstUsedDate(), todayString());
        expect(await service.getLastUsedDate(), todayString());
        expect(await service.getNumDaysUsed(), 1);

        verify(
          () => mockAnalytics.logAppUsageDays(
            numDaysUsed: 1,
            brightness: any(named: 'brightness'),
          ),
        ).called(1);
      },
    );

    test('same day run does not increment unique day count', () async {
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final mockAnalytics = _MockAnalyticsService();
      when(
        () => mockAnalytics.logAppUsageDays(
          numDaysUsed: any<int>(named: 'numDaysUsed'),
          brightness: any<Brightness>(named: 'brightness'),
        ),
      ).thenAnswer((_) async {});
      final container = ProviderContainer(
        overrides: [brightnessProvider.overrideWithValue(Brightness.light)],
      );
      final ref = container.read(Provider<Ref>((ref) => ref));
      final mockJokeCloudFn = _MockJokeCloudFunctionService();
      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mockAnalytics,
        jokeCloudFn: mockJokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
      );

      await service.logAppUsage();
      await service.logAppUsage();

      expect(await service.getNumDaysUsed(), 1);
      expect(await service.getLastUsedDate(), todayString());

      verify(
        () => mockAnalytics.logAppUsageDays(
          numDaysUsed: any(named: 'numDaysUsed'),
          brightness: any(named: 'brightness'),
        ),
      ).called(1);
    });

    test(
      'new day increments unique day count and updates last_used_date',
      () async {
        final prefs = await SharedPreferences.getInstance();
        final settingsService = SettingsService(prefs);
        final mockAnalytics = _MockAnalyticsService();
        when(
          () => mockAnalytics.logAppUsageDays(
            numDaysUsed: any<int>(named: 'numDaysUsed'),
            brightness: any<Brightness>(named: 'brightness'),
          ),
        ).thenAnswer((_) async {});
        final container = ProviderContainer(
          overrides: [brightnessProvider.overrideWithValue(Brightness.light)],
        );
        final ref = container.read(Provider<Ref>((ref) => ref));
        final mockJokeCloudFn = _MockJokeCloudFunctionService();
        final service = AppUsageService(
          settingsService: settingsService,
          ref: ref,
          analyticsService: mockAnalytics,
          jokeCloudFn: mockJokeCloudFn,
          categoryInteractionsService: _MockCategoryInteractionsService(),
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
          () => mockAnalytics.logAppUsageDays(
            numDaysUsed: 2,
            brightness: any(named: 'brightness'),
          ),
        ).called(1);
      },
    );
  });

  group('AppUsageService.logJokeViewed', () {
    test('increments num_jokes_viewed counter', () async {
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final mockAnalytics = _MockAnalyticsService();
      final mockJokeCloudFn = _MockJokeCloudFunctionService();
      final container = ProviderContainer(
        overrides: [brightnessProvider.overrideWithValue(Brightness.light)],
      );
      final ref = container.read(Provider<Ref>((ref) => ref));
      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mockAnalytics,
        jokeCloudFn: mockJokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
      );

      expect(await service.getNumJokesViewed(), 0);
      await service.logJokeViewed();
      expect(await service.getNumJokesViewed(), 1);
      await service.logJokeViewed();
      expect(await service.getNumJokesViewed(), 2);
    });
  });

  group('AppUsageService saved/shared counters', () {
    test(
      'incrementSavedJokesCount and decrementSavedJokesCount update counter with floor at 0',
      () async {
        final prefs = await SharedPreferences.getInstance();
        final settingsService = SettingsService(prefs);
        final mockAnalytics = _MockAnalyticsService();
        final mockJokeCloudFn = _MockJokeCloudFunctionService();
        final container = ProviderContainer();
        final ref = container.read(Provider<Ref>((ref) => ref));
        final service = AppUsageService(
          settingsService: settingsService,
          ref: ref,
          analyticsService: mockAnalytics,
          jokeCloudFn: mockJokeCloudFn,
          categoryInteractionsService: _MockCategoryInteractionsService(),
        );

        expect(await service.getNumSavedJokes(), 0);
        await service.incrementSavedJokesCount();
        expect(await service.getNumSavedJokes(), 1);
        await service.incrementSavedJokesCount();
        expect(await service.getNumSavedJokes(), 2);
        await service.decrementSavedJokesCount();
        expect(await service.getNumSavedJokes(), 1);
        await service.decrementSavedJokesCount();
        expect(await service.getNumSavedJokes(), 0);
        // floor at 0
        await service.decrementSavedJokesCount();
        expect(await service.getNumSavedJokes(), 0);
      },
    );

    test('incrementSharedJokesCount updates counter', () async {
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final mockAnalytics = _MockAnalyticsService();
      final mockJokeCloudFn = _MockJokeCloudFunctionService();
      final container = ProviderContainer(
        overrides: [brightnessProvider.overrideWithValue(Brightness.light)],
      );
      final ref = container.read(Provider<Ref>((ref) => ref));
      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mockAnalytics,
        jokeCloudFn: mockJokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
      );

      expect(await service.getNumSharedJokes(), 0);
      await service.incrementSharedJokesCount();
      expect(await service.getNumSharedJokes(), 1);
      await service.incrementSharedJokesCount();
      expect(await service.getNumSharedJokes(), 2);
    });
  });

  group('AppUsageService._pushUsageSnapshot', () {
    test('passes correct requestedReview value to cloud function', () async {
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final mockJokeCloudFn = _MockJokeCloudFunctionService();
      final mockReviewStore = _MockReviewPromptStateStore();

      when(() => mockReviewStore.hasRequested()).thenAnswer((_) => true);
      when(
        () => mockJokeCloudFn.trackUsage(
          numDaysUsed: any<int>(named: 'numDaysUsed'),
          numSaved: any<int>(named: 'numSaved'),
          numViewed: any<int>(named: 'numViewed'),
          numShared: any<int>(named: 'numShared'),
          requestedReview: any<bool?>(named: 'requestedReview'),
        ),
      ).thenAnswer((_) async {});

      final testRefProvider = Provider<Ref>((ref) => ref);
      final container = ProviderContainer(
        overrides: [
          brightnessProvider.overrideWithValue(Brightness.light),
          reviewPromptStateStoreProvider.overrideWithValue(mockReviewStore),
          isAdminProvider.overrideWithValue(false),
        ],
      );
      final ref = container.read(testRefProvider);

      final mockAnalytics = _MockAnalyticsService();
      final testService = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mockAnalytics,
        jokeCloudFn: mockJokeCloudFn,
        isDebugMode: false,
        categoryInteractionsService: _MockCategoryInteractionsService(),
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
        () => mockJokeCloudFn.trackUsage(
          numDaysUsed: any(named: 'numDaysUsed'),
          numSaved: any(named: 'numSaved'),
          numViewed: any(named: 'numViewed'),
          numShared: any(named: 'numShared'),
          requestedReview: captureAny(named: 'requestedReview'),
        ),
      ).captured;

      expect(captured.first, isTrue);
    });
  });
}
