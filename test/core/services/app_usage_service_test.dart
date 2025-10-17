import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';
import 'package:snickerdoodle/src/data/jokes/category_interactions_repository.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/settings/application/brightness_provider.dart';
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
          jokeInteractionsRepository: _MockJokeInteractionsRepository(),
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
        jokeInteractionsRepository: _MockJokeInteractionsRepository(),
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
          jokeInteractionsRepository: _MockJokeInteractionsRepository(),
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
    test('writes to repo and counts from repo', () async {
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final mockAnalytics = _MockAnalyticsService();
      final mockJokeCloudFn = _MockJokeCloudFunctionService();
      final mockRepo = _MockJokeInteractionsRepository();
      final container = ProviderContainer(
        overrides: [brightnessProvider.overrideWithValue(Brightness.light)],
      );
      final ref = container.read(Provider<Ref>((ref) => ref));

      var viewedCount = 0;
      when(() => mockRepo.setViewed(any())).thenAnswer((_) async {
        viewedCount += 1;
        return true;
      });
      when(() => mockRepo.countViewed()).thenAnswer((_) async => viewedCount);

      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mockAnalytics,
        jokeCloudFn: mockJokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mockRepo,
      );

      expect(await service.getNumJokesViewed(), 0);
      await service.logJokeViewed('j1');
      expect(await service.getNumJokesViewed(), 1);
      await service.logJokeViewed('j2');
      expect(await service.getNumJokesViewed(), 2);

      verify(() => mockRepo.setViewed('j1')).called(1);
      verify(() => mockRepo.setViewed('j2')).called(1);
    });
  });

  group('AppUsageService saved/shared via repo', () {
    test('saveJoke and unsaveJoke update repo and counts from repo', () async {
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final mockAnalytics = _MockAnalyticsService();
      final mockJokeCloudFn = _MockJokeCloudFunctionService();
      final mockRepo = _MockJokeInteractionsRepository();
      final container = ProviderContainer();
      final ref = container.read(Provider<Ref>((ref) => ref));

      var savedCount = 0;
      when(() => mockRepo.setSaved(any())).thenAnswer((_) async {
        savedCount += 1;
        return true;
      });
      when(() => mockRepo.setUnsaved(any())).thenAnswer((_) async {
        savedCount = savedCount > 0 ? savedCount - 1 : 0;
        return true;
      });
      when(() => mockRepo.countSaved()).thenAnswer((_) async => savedCount);

      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mockAnalytics,
        jokeCloudFn: mockJokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mockRepo,
      );

      expect(await service.getNumSavedJokes(), 0);
      await service.saveJoke('s1');
      expect(await service.getNumSavedJokes(), 1);
      await service.saveJoke('s2');
      expect(await service.getNumSavedJokes(), 2);
      await service.unsaveJoke('s1');
      expect(await service.getNumSavedJokes(), 1);
      await service.unsaveJoke('s2');
      expect(await service.getNumSavedJokes(), 0);

      verify(() => mockRepo.setSaved('s1')).called(1);
      verify(() => mockRepo.setSaved('s2')).called(1);
      verify(() => mockRepo.setUnsaved('s1')).called(1);
      verify(() => mockRepo.setUnsaved('s2')).called(1);
    });

    test('shareJoke updates repo and counts from repo', () async {
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final mockAnalytics = _MockAnalyticsService();
      final mockJokeCloudFn = _MockJokeCloudFunctionService();
      final mockRepo = _MockJokeInteractionsRepository();
      final container = ProviderContainer(
        overrides: [brightnessProvider.overrideWithValue(Brightness.light)],
      );
      final ref = container.read(Provider<Ref>((ref) => ref));

      var sharedCount = 0;
      when(() => mockRepo.setShared(any())).thenAnswer((_) async {
        sharedCount += 1;
        return true;
      });
      when(() => mockRepo.countShared()).thenAnswer((_) async => sharedCount);

      final service = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mockAnalytics,
        jokeCloudFn: mockJokeCloudFn,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mockRepo,
      );

      expect(await service.getNumSharedJokes(), 0);
      await service.shareJoke('x1');
      expect(await service.getNumSharedJokes(), 1);
      await service.shareJoke('x2');
      expect(await service.getNumSharedJokes(), 2);

      verify(() => mockRepo.setShared('x1')).called(1);
      verify(() => mockRepo.setShared('x2')).called(1);
    });
  });

  group('AppUsageService._pushUsageSnapshot', () {
    test('passes correct requestedReview value to cloud function', () async {
      final prefs = await SharedPreferences.getInstance();
      final settingsService = SettingsService(prefs);
      final mockJokeCloudFn = _MockJokeCloudFunctionService();
      final mockReviewStore = _MockReviewPromptStateStore();
      final mockRepo = _MockJokeInteractionsRepository();

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

      // Stub repo counts used by _pushUsageSnapshot
      when(() => mockRepo.countSaved()).thenAnswer((_) async => 2);
      when(() => mockRepo.countViewed()).thenAnswer((_) async => 5);
      when(() => mockRepo.countShared()).thenAnswer((_) async => 1);

      final mockAnalytics = _MockAnalyticsService();
      final testService = AppUsageService(
        settingsService: settingsService,
        ref: ref,
        analyticsService: mockAnalytics,
        jokeCloudFn: mockJokeCloudFn,
        isDebugMode: false,
        categoryInteractionsService: _MockCategoryInteractionsService(),
        jokeInteractionsRepository: mockRepo,
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
