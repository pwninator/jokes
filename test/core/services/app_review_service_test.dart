import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';

class _MockNativeReviewAdapter extends Mock implements NativeReviewAdapter {}

class _MockAnalyticsService extends Mock implements AnalyticsService {}

class _MockStateStore extends Mock implements ReviewPromptStateStore {}

void main() {
  late _MockNativeReviewAdapter native;
  late _MockAnalyticsService analytics;
  late AppReviewService service;
  late _MockStateStore store;

  setUpAll(() {
    registerFallbackValue(ReviewRequestSource.adminTest);
  });

  setUp(() {
    native = _MockNativeReviewAdapter();
    analytics = _MockAnalyticsService();
    store = _MockStateStore();
    service = AppReviewService(
      nativeAdapter: native,
      stateStore: store,
      analyticsService: analytics,
    );

    // Mock successful analytics calls by default
    when(() => analytics.logAppReviewAttempt(source: any(named: 'source')))
        .thenAnswer((_) async {});
    when(() => analytics.logErrorAppReviewAvailability(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'))).thenAnswer((_) async {});
    when(() => analytics.logErrorAppReviewRequest(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'))).thenAnswer((_) async {});
  });

  group('AppReviewService', () {
    group('isAvailable', () {
      test('returns true when native is available', () async {
        when(() => native.isAvailable()).thenAnswer((_) async => true);
        expect(await service.isAvailable(), isTrue);
        verify(() => native.isAvailable()).called(1);
        verifyNever(() => analytics.logErrorAppReviewAvailability(
            source: any(named: 'source'),
            errorMessage: any(named: 'errorMessage')));
      });

      test('returns false and logs analytics when native throws', () async {
        when(() => native.isAvailable()).thenThrow(Exception('boom'));
        expect(await service.isAvailable(), isFalse);
        verify(() => native.isAvailable()).called(1);
        verify(() => analytics.logErrorAppReviewAvailability(
              source: 'service',
              errorMessage: 'app_review_is_available_failed',
            )).called(1);
      });
    });

    group('requestReview', () {
      test('returns notAvailable when API not available', () async {
        when(() => native.isAvailable()).thenAnswer((_) async => false);

        final result = await service.requestReview(
          source: ReviewRequestSource.settings,
        );

        expect(result, ReviewRequestResult.notAvailable);
        verify(() => analytics.logAppReviewAttempt(source: 'settings'))
            .called(1);
        verifyNever(() => native.requestReview());
        verifyNever(() => store.markRequested());
      });

      test('returns shown and marks requested on success', () async {
        when(() => native.isAvailable()).thenAnswer((_) async => true);
        when(() => native.requestReview()).thenAnswer((_) async {});
        when(() => store.markRequested()).thenAnswer((_) async {});

        final result = await service.requestReview(
          source: ReviewRequestSource.auto,
        );

        expect(result, ReviewRequestResult.shown);
        verifyInOrder([
          () => analytics.logAppReviewAttempt(source: 'auto'),
          () => native.isAvailable(),
          () => native.requestReview(),
          () => store.markRequested(),
        ]);
      });

      test('returns error, logs analytics, and does not mark requested on failure',
          () async {
        when(() => native.isAvailable()).thenAnswer((_) async => true);
        when(() => native.requestReview()).thenThrow(Exception('nope'));

        final result = await service.requestReview(
          source: ReviewRequestSource.adminTest,
        );

        expect(result, ReviewRequestResult.error);
        verify(() => analytics.logErrorAppReviewRequest(
              source: 'admin_test',
              errorMessage: 'app_review_request_failed',
            )).called(1);
        verifyNever(() => store.markRequested());
      });
    });
  });
}
