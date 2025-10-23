import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';

class _MockAppReviewService extends Mock implements AppReviewService {}

class _MockStateStore extends Mock implements ReviewPromptStateStore {}

class _FakeBuildContext extends Fake implements BuildContext {}

/// Helper to get a BuildContext for tests that need it
Future<BuildContext> _getTestContext(WidgetTester tester) async {
  await tester.pumpWidget(MaterialApp(home: Container()));
  return tester.element(find.byType(Container));
}

class _FakeRemoteValues implements RemoteConfigValues {
  _FakeRemoteValues({
    required this.minDays,
    required this.minSaved,
    required this.minShared,
    this.minViewed = 0,
    this.requireDailySub = false,
  });

  final int minDays;
  final int minSaved;
  final int minShared;
  final int minViewed;
  final bool requireDailySub;

  @override
  bool getBool(RemoteParam param) {
    switch (param) {
      case RemoteParam.defaultJokeViewerReveal:
        return false;
      case RemoteParam.reviewRequestFromJokeViewed:
        return true;
      case RemoteParam.reviewRequireDailySubscription:
        return requireDailySub;
      case RemoteParam.shareImagesMode:
        return false;
      case RemoteParam.reviewPromptVariant:
        return false;
      case RemoteParam.adDisplayMode:
        return false;
      case RemoteParam.bannerAdPosition:
        return false;
      case RemoteParam.subscriptionPromptMinJokesViewed:
      case RemoteParam.feedbackMinJokesViewed:
      case RemoteParam.reviewMinDaysUsed:
      case RemoteParam.reviewMinSavedJokes:
      case RemoteParam.reviewMinSharedJokes:
      case RemoteParam.reviewMinViewedJokes:
        return false;
    }
  }

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
      case RemoteParam.defaultJokeViewerReveal:
        return 0;
      case RemoteParam.shareImagesMode:
        return 0;
      case RemoteParam.reviewPromptVariant:
        return 0;
      case RemoteParam.reviewRequestFromJokeViewed:
        return 0;
      case RemoteParam.reviewRequireDailySubscription:
        return 0;
      case RemoteParam.adDisplayMode:
        return 0;
      case RemoteParam.bannerAdPosition:
        return 0;
    }
  }

  @override
  String getString(RemoteParam param) => '';

  @override
  T getEnum<T>(RemoteParam param) {
    final descriptor = remoteParams[param]!;
    return (descriptor.enumDefault ?? '') as T;
  }
}

void main() {
  setUpAll(() {
    registerFallbackValue(ReviewRequestSource.jokeViewed);
    registerFallbackValue(_FakeBuildContext());
  });

  group('ReviewPromptCoordinator', () {
    late _MockAppReviewService review;
    late _MockStateStore store;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      review = _MockAppReviewService();
      store = _MockStateStore();
    });

    testWidgets('early return when already requested', (tester) async {
      final context = await _getTestContext(tester);

      // Arrange
      final values = _FakeRemoteValues(minDays: 5, minSaved: 3, minShared: 1);
      when(() => store.hasRequested()).thenAnswer((_) => true);

      final coordinator = ReviewPromptCoordinator(
        getRemoteValues: () => values,
        appReviewService: review,
        stateStore: store,
        getIsDailySubscribed: () => true,
        getIsAdmin: () => false,
      );

      // Act
      await coordinator.maybePromptForReview(
        numDaysUsed: 5,
        numSavedJokes: 3,
        numSharedJokes: 1,
        numJokesViewed: 0,
        source: ReviewRequestSource.jokeViewed,
        context: context,
      );

      // Assert
      verify(() => store.hasRequested()).called(1);
      verifyNever(
        () => review.requestReview(
          source: any(named: 'source'),
          context: any(named: 'context'),
        ),
      );
      verifyNever(() => store.markRequested());
    });

    testWidgets('ineligible does not call review', (tester) async {
      final context = await _getTestContext(tester);

      // Arrange thresholds high
      final values = _FakeRemoteValues(
        minDays: 10,
        minSaved: 10,
        minShared: 10,
      );
      when(() => store.hasRequested()).thenAnswer((_) => false);

      final coordinator = ReviewPromptCoordinator(
        getRemoteValues: () => values,
        appReviewService: review,
        stateStore: store,
        getIsDailySubscribed: () => true,
        getIsAdmin: () => false,
      );

      // Act
      await coordinator.maybePromptForReview(
        numDaysUsed: 5,
        numSavedJokes: 5,
        numSharedJokes: 5,
        numJokesViewed: 5,
        source: ReviewRequestSource.jokeViewed,
        context: context,
      );

      // Assert
      verifyNever(
        () => review.requestReview(
          source: any(named: 'source'),
          context: any(named: 'context'),
        ),
      );
      verifyNever(() => store.markRequested());
    });

    testWidgets('eligible + not available does not mark requested', (
      tester,
    ) async {
      final context = await _getTestContext(tester);

      // Arrange thresholds low
      final values = _FakeRemoteValues(minDays: 1, minSaved: 1, minShared: 1);
      when(() => store.hasRequested()).thenAnswer((_) => false);

      when(
        () => review.requestReview(
          source: any(named: 'source'),
          context: any(named: 'context'),
        ),
      ).thenAnswer((_) async => ReviewRequestResult.notAvailable);

      final coordinator = ReviewPromptCoordinator(
        getRemoteValues: () => values,
        appReviewService: review,
        stateStore: store,
        getIsDailySubscribed: () => true,
        getIsAdmin: () => false,
      );

      // Act
      await coordinator.maybePromptForReview(
        numDaysUsed: 1,
        numSavedJokes: 1,
        numSharedJokes: 1,
        numJokesViewed: 0,
        source: ReviewRequestSource.jokeViewed,
        context: context,
      );

      // Assert
      verify(
        () => review.requestReview(
          source: any(named: 'source'),
          context: any(named: 'context'),
        ),
      ).called(1);
      verifyNever(() => store.markRequested());
    });

    testWidgets(
      'eligible + success marks requested (service handles marking)',
      (tester) async {
        final context = await _getTestContext(tester);

        final values = _FakeRemoteValues(minDays: 1, minSaved: 1, minShared: 1);
        when(() => store.hasRequested()).thenAnswer((_) => false);

        when(
          () => review.requestReview(
            source: any(named: 'source'),
            context: any(named: 'context'),
          ),
        ).thenAnswer((_) async => ReviewRequestResult.shown);

        final coordinator = ReviewPromptCoordinator(
          getRemoteValues: () => values,
          appReviewService: review,
          stateStore: store,
          getIsDailySubscribed: () => true,
          getIsAdmin: () => false,
        );

        await coordinator.maybePromptForReview(
          numDaysUsed: 1,
          numSavedJokes: 1,
          numSharedJokes: 1,
          numJokesViewed: 0,
          source: ReviewRequestSource.jokeViewed,
          context: context,
        );

        // Service marks internally; coordinator doesn't call store
        verifyNever(() => store.markRequested());
      },
    );

    testWidgets(
      'eligible + error does not mark requested (service handles marking)',
      (tester) async {
        final context = await _getTestContext(tester);

        final values = _FakeRemoteValues(minDays: 1, minSaved: 1, minShared: 1);
        when(() => store.hasRequested()).thenAnswer((_) => false);

        when(
          () => review.requestReview(
            source: any(named: 'source'),
            context: any(named: 'context'),
          ),
        ).thenAnswer((_) async => ReviewRequestResult.error);

        final coordinator = ReviewPromptCoordinator(
          getRemoteValues: () => values,
          appReviewService: review,
          stateStore: store,
          getIsDailySubscribed: () => true,
          getIsAdmin: () => false,
        );

        await coordinator.maybePromptForReview(
          numDaysUsed: 1,
          numSavedJokes: 1,
          numSharedJokes: 1,
          numJokesViewed: 0,
          source: ReviewRequestSource.jokeViewed,
          context: context,
        );

        verifyNever(() => store.markRequested());
      },
    );

    testWidgets(
      'zero thresholds allow immediate eligibility when other thresholds met',
      (tester) async {
        final context = await _getTestContext(tester);

        // Set minSaved and minShared to 0; keep minDays at 1 to avoid prompting on day 0
        final values = _FakeRemoteValues(minDays: 1, minSaved: 0, minShared: 0);
        when(() => store.hasRequested()).thenAnswer((_) => false);

        // Do not save/share any jokes; with zero thresholds it should still be eligible
        when(
          () => review.requestReview(
            source: any(named: 'source'),
            context: any(named: 'context'),
          ),
        ).thenAnswer((_) async => ReviewRequestResult.notAvailable);

        final coordinator = ReviewPromptCoordinator(
          getRemoteValues: () => values,
          appReviewService: review,
          stateStore: store,
          getIsDailySubscribed: () => true,
          getIsAdmin: () => false,
        );

        await coordinator.maybePromptForReview(
          numDaysUsed: 1,
          numSavedJokes: 0,
          numSharedJokes: 0,
          numJokesViewed: 0,
          source: ReviewRequestSource.jokeViewed,
          context: context,
        );

        verify(
          () => review.requestReview(
            source: any(named: 'source'),
            context: any(named: 'context'),
          ),
        ).called(1);
      },
    );

    testWidgets('ineligible when viewed jokes below threshold', (tester) async {
      final context = await _getTestContext(tester);

      // Arrange thresholds include viewed
      final values = _FakeRemoteValues(
        minDays: 1,
        minSaved: 1,
        minShared: 1,
        minViewed: 2,
      );
      when(() => store.hasRequested()).thenAnswer((_) => false);

      final coordinator = ReviewPromptCoordinator(
        getRemoteValues: () => values,
        appReviewService: review,
        stateStore: store,
        getIsDailySubscribed: () => true,
        getIsAdmin: () => false,
      );

      // Act
      await coordinator.maybePromptForReview(
        numDaysUsed: 1,
        numSavedJokes: 1,
        numSharedJokes: 1,
        numJokesViewed: 1, // Below threshold of 2
        source: ReviewRequestSource.jokeViewed,
        context: context,
      );

      // Assert: should not request review because viewed < minViewed
      verifyNever(
        () => review.requestReview(
          source: any(named: 'source'),
          context: any(named: 'context'),
        ),
      );
    });

    testWidgets('eligible when viewed jokes meets threshold calls review', (
      tester,
    ) async {
      final context = await _getTestContext(tester);

      final values = _FakeRemoteValues(
        minDays: 1,
        minSaved: 1,
        minShared: 1,
        minViewed: 1,
      );
      when(() => store.hasRequested()).thenAnswer((_) => false);

      when(
        () => review.requestReview(
          source: any(named: 'source'),
          context: any(named: 'context'),
        ),
      ).thenAnswer((_) async => ReviewRequestResult.notAvailable);

      final coordinator = ReviewPromptCoordinator(
        getRemoteValues: () => values,
        appReviewService: review,
        stateStore: store,
        getIsDailySubscribed: () => true,
        getIsAdmin: () => false,
      );

      await coordinator.maybePromptForReview(
        numDaysUsed: 1,
        numSavedJokes: 1,
        numSharedJokes: 1,
        numJokesViewed: 1,
        source: ReviewRequestSource.jokeViewed,
        context: context,
      );

      verify(
        () => review.requestReview(
          source: any(named: 'source'),
          context: any(named: 'context'),
        ),
      ).called(1);
    });

    testWidgets(
      'gated by daily subscription when required and not subscribed',
      (tester) async {
        final context = await _getTestContext(tester);

        final values = _FakeRemoteValues(
          minDays: 1,
          minSaved: 0,
          minShared: 0,
          minViewed: 0,
          requireDailySub: true,
        );
        when(() => store.hasRequested()).thenAnswer((_) => false);

        final coordinator = ReviewPromptCoordinator(
          getRemoteValues: () => values,
          appReviewService: review,
          stateStore: store,
          getIsDailySubscribed: () => false,
          getIsAdmin: () => false,
        );

        await coordinator.maybePromptForReview(
          numDaysUsed: 1,
          numSavedJokes: 0,
          numSharedJokes: 0,
          numJokesViewed: 0,
          source: ReviewRequestSource.jokeViewed,
          context: context,
        );

        verifyNever(
          () => review.requestReview(
            source: any(named: 'source'),
            context: any(named: 'context'),
          ),
        );
      },
    );

    testWidgets('allows when required and subscribed', (tester) async {
      final context = await _getTestContext(tester);

      final values = _FakeRemoteValues(
        minDays: 1,
        minSaved: 0,
        minShared: 0,
        minViewed: 0,
        requireDailySub: true,
      );
      when(() => store.hasRequested()).thenAnswer((_) => false);

      when(
        () => review.requestReview(
          source: any(named: 'source'),
          context: any(named: 'context'),
        ),
      ).thenAnswer((_) async => ReviewRequestResult.notAvailable);

      final coordinator = ReviewPromptCoordinator(
        getRemoteValues: () => values,
        appReviewService: review,
        stateStore: store,
        getIsDailySubscribed: () => true,
        getIsAdmin: () => false,
      );

      await coordinator.maybePromptForReview(
        numDaysUsed: 1,
        numSavedJokes: 0,
        numSharedJokes: 0,
        numJokesViewed: 0,
        source: ReviewRequestSource.jokeViewed,
        context: context,
      );

      verify(
        () => review.requestReview(
          source: any(named: 'source'),
          context: any(named: 'context'),
        ),
      ).called(1);
    });
  });
}
