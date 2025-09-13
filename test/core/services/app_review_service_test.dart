import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';

class _MockNativeReviewAdapter extends Mock implements NativeReviewAdapter {}

class _MockAnalyticsService extends Mock implements AnalyticsService {}

class _MockStateStore extends Mock implements ReviewPromptStateStore {}

void main() {
  setUpAll(() {
    registerFallbackValue('');
  });

  group('AppReviewService', () {
    late _MockNativeReviewAdapter native;
    late _MockAnalyticsService analytics;
    late AppReviewService service;
    late _MockStateStore store;

    setUp(() {
      native = _MockNativeReviewAdapter();
      analytics = _MockAnalyticsService();
      store = _MockStateStore();
      service = AppReviewService(
        nativeAdapter: native,
        stateStore: store,
        analyticsService: analytics,
      );
    });

    test('isAvailable returns true when native is available', () async {
      when(() => native.isAvailable()).thenAnswer((_) async => true);

      final result = await service.isAvailable();

      expect(result, isTrue);
      verify(() => native.isAvailable()).called(1);
    });

    test('isAvailable returns false when native throws', () async {
      when(() => native.isAvailable()).thenThrow(Exception('boom'));

      final result = await service.isAvailable();

      expect(result, isFalse);
      verify(() => native.isAvailable()).called(1);
    });

    test('requestReview returns notAvailable when API not available', () async {
      when(() => native.isAvailable()).thenAnswer((_) async => false);

      final result = await service.requestReview(
        source: ReviewRequestSource.adminTest,
      );

      expect(result, ReviewRequestResult.notAvailable);
      verify(() => native.isAvailable()).called(1);
      verifyNever(() => native.requestReview());
      verifyNever(() => store.markRequested());
    });

    test('requestReview returns shown and marks requested on success', () async {
      when(() => native.isAvailable()).thenAnswer((_) async => true);
      when(() => native.requestReview()).thenAnswer((_) async {});
      when(() => store.markRequested()).thenAnswer((_) async {});

      final result = await service.requestReview(
        source: ReviewRequestSource.adminTest,
      );

      expect(result, ReviewRequestResult.shown);
      verifyInOrder([
        () => native.isAvailable(),
        () => native.requestReview(),
      ]);
      verify(() => store.markRequested()).called(1);
    });

    test('requestReview returns error and does not mark requested on failure',
        () async {
      when(() => native.isAvailable()).thenAnswer((_) async => true);
      when(() => native.requestReview()).thenThrow(Exception('nope'));

      final result = await service.requestReview(
        source: ReviewRequestSource.adminTest,
      );

      expect(result, ReviewRequestResult.error);
      verifyInOrder([
        () => native.isAvailable(),
        () => native.requestReview(),
      ]);
      verifyNever(() => store.markRequested());
    });
  });
}
