import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';

class _MockAppReviewService extends Mock implements AppReviewService {}

class _MockStateStore extends Mock implements ReviewPromptStateStore {}

class _FakeRemoteValues implements RemoteConfigValues {
  _FakeRemoteValues({
    required this.minDays,
    required this.minSaved,
    required this.minShared,
    this.minViewed = 0,
  });

  final int minDays;
  final int minSaved;
  final int minShared;
  final int minViewed;

  @override
  bool getBool(RemoteParam param) => false;

  @override
  double getDouble(RemoteParam param) => 0.0;

  @override
  int getInt(RemoteParam param) {
    switch (param) {
      case RemoteParam.reviewMinDaysUsed:
        return minDays;
      case RemoteParam.reviewMinSavedJokes:
        return minSaved;
      case RemoteParam.reviewMinSharedJokes:
        return minShared;
      case RemoteParam.reviewMinViewedJokes:
        return minViewed;
      case RemoteParam.subscriptionPromptMinJokesViewed:
        return 0;
      case RemoteParam.feedbackMinJokesViewed:
        return 0;
    }
  }

  @override
  String getString(RemoteParam param) => '';
}

void main() {
  setUpAll(() {
    registerFallbackValue(ReviewRequestSource.auto);
  });

  group('ReviewPromptCoordinator', () {
    late AppUsageService usage;
    late _MockAppReviewService review;
    late _MockStateStore store;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      usage = AppUsageService(prefs: prefs);
      review = _MockAppReviewService();
      store = _MockStateStore();
    });

    test('early return when already requested', () async {
      // Arrange
      final values = _FakeRemoteValues(minDays: 5, minSaved: 3, minShared: 1);
      when(() => store.hasRequested()).thenAnswer((_) async => true);

      final coordinator = ReviewPromptCoordinator(
        getRemoteValues: () => values,
        appUsageService: usage,
        appReviewService: review,
        stateStore: store,
      );

      // Act
      await coordinator.maybePromptForReview(source: ReviewRequestSource.auto);

      // Assert
      verify(() => store.hasRequested()).called(1);
      verifyNever(() => review.requestReview(source: any(named: 'source')));
      verifyNever(() => store.markRequested());
    });

    test('ineligible does not call review', () async {
      // Arrange thresholds high
      final values = _FakeRemoteValues(
        minDays: 10,
        minSaved: 10,
        minShared: 10,
      );
      when(() => store.hasRequested()).thenAnswer((_) async => false);

      final coordinator = ReviewPromptCoordinator(
        getRemoteValues: () => values,
        appUsageService: usage,
        appReviewService: review,
        stateStore: store,
      );

      // Ensure some low usage values
      expect(await usage.getNumDaysUsed(), 0);
      expect(await usage.getNumSavedJokes(), 0);
      expect(await usage.getNumSharedJokes(), 0);

      // Act
      await coordinator.maybePromptForReview(source: ReviewRequestSource.auto);

      // Assert
      verifyNever(() => review.requestReview(source: any(named: 'source')));
      verifyNever(() => store.markRequested());
    });

    test('eligible + not available does not mark requested', () async {
      // Arrange thresholds low
      final values = _FakeRemoteValues(minDays: 1, minSaved: 1, minShared: 1);
      when(() => store.hasRequested()).thenAnswer((_) async => false);

      // Set usage to thresholds
      await usage.incrementSavedJokesCount();
      await usage.incrementSharedJokesCount();
      // Simulate days used by writing key directly
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt('num_days_used', 1);

      when(
        () => review.requestReview(source: any(named: 'source')),
      ).thenAnswer((_) async => ReviewRequestResult.notAvailable);

      final coordinator = ReviewPromptCoordinator(
        getRemoteValues: () => values,
        appUsageService: usage,
        appReviewService: review,
        stateStore: store,
      );

      // Act
      await coordinator.maybePromptForReview(source: ReviewRequestSource.auto);

      // Assert
      verify(
        () => review.requestReview(source: any(named: 'source')),
      ).called(1);
      verifyNever(() => store.markRequested());
    });

    test(
      'eligible + success marks requested (service handles marking)',
      () async {
        final values = _FakeRemoteValues(minDays: 1, minSaved: 1, minShared: 1);
        when(() => store.hasRequested()).thenAnswer((_) async => false);

        await usage.incrementSavedJokesCount();
        await usage.incrementSharedJokesCount();
        final prefs = await SharedPreferences.getInstance();
        await prefs.setInt('num_days_used', 1);

        when(
          () => review.requestReview(source: any(named: 'source')),
        ).thenAnswer((_) async => ReviewRequestResult.shown);

        final coordinator = ReviewPromptCoordinator(
          getRemoteValues: () => values,
          appUsageService: usage,
          appReviewService: review,
          stateStore: store,
        );

        await coordinator.maybePromptForReview(
          source: ReviewRequestSource.auto,
        );

        // Service marks internally; coordinator doesn't call store
        verifyNever(() => store.markRequested());
      },
    );

    test(
      'eligible + error does not mark requested (service handles marking)',
      () async {
        final values = _FakeRemoteValues(minDays: 1, minSaved: 1, minShared: 1);
        when(() => store.hasRequested()).thenAnswer((_) async => false);

        await usage.incrementSavedJokesCount();
        await usage.incrementSharedJokesCount();
        final prefs = await SharedPreferences.getInstance();
        await prefs.setInt('num_days_used', 1);

        when(
          () => review.requestReview(source: any(named: 'source')),
        ).thenAnswer((_) async => ReviewRequestResult.error);

        final coordinator = ReviewPromptCoordinator(
          getRemoteValues: () => values,
          appUsageService: usage,
          appReviewService: review,
          stateStore: store,
        );

        await coordinator.maybePromptForReview(
          source: ReviewRequestSource.auto,
        );

        verifyNever(() => store.markRequested());
      },
    );

    test('ineligible when viewed jokes below threshold', () async {
      // Arrange thresholds include viewed
      final values = _FakeRemoteValues(
        minDays: 1,
        minSaved: 1,
        minShared: 1,
        minViewed: 2,
      );
      when(() => store.hasRequested()).thenAnswer((_) async => false);

      // Set other usage to thresholds but do not log views
      await usage.incrementSavedJokesCount();
      await usage.incrementSharedJokesCount();
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt('num_days_used', 1);

      final coordinator = ReviewPromptCoordinator(
        getRemoteValues: () => values,
        appUsageService: usage,
        appReviewService: review,
        stateStore: store,
      );

      // Act
      await coordinator.maybePromptForReview(source: ReviewRequestSource.auto);

      // Assert: should not request review because viewed < minViewed
      verifyNever(() => review.requestReview(source: any(named: 'source')));
    });

    test('eligible when viewed jokes meets threshold calls review', () async {
      final values = _FakeRemoteValues(
        minDays: 1,
        minSaved: 1,
        minShared: 1,
        minViewed: 1,
      );
      when(() => store.hasRequested()).thenAnswer((_) async => false);

      await usage.incrementSavedJokesCount();
      await usage.incrementSharedJokesCount();
      await usage.logJokeViewed();
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt('num_days_used', 1);

      when(
        () => review.requestReview(source: any(named: 'source')),
      ).thenAnswer((_) async => ReviewRequestResult.notAvailable);

      final coordinator = ReviewPromptCoordinator(
        getRemoteValues: () => values,
        appUsageService: usage,
        appReviewService: review,
        stateStore: store,
      );

      await coordinator.maybePromptForReview(source: ReviewRequestSource.auto);

      verify(
        () => review.requestReview(source: any(named: 'source')),
      ).called(1);
    });
  });
}
