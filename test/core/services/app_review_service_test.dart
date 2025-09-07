import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';

class _MockNativeReviewAdapter extends Mock implements NativeReviewAdapter {}

class _MockAnalyticsService extends Mock implements AnalyticsService {}

void main() {
  setUpAll(() {
    registerFallbackValue('');
  });

  group('AppReviewService', () {
    late _MockNativeReviewAdapter native;
    late _MockAnalyticsService analytics;
    late AppReviewService service;

    setUp(() {
      native = _MockNativeReviewAdapter();
      analytics = _MockAnalyticsService();
      service = AppReviewService(
        nativeAdapter: native,
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
    });

    test('requestReview returns shown when request succeeds', () async {
      when(() => native.isAvailable()).thenAnswer((_) async => true);
      when(() => native.requestReview()).thenAnswer((_) async {});

      final result = await service.requestReview(
        source: ReviewRequestSource.adminTest,
      );

      expect(result, ReviewRequestResult.shown);
      verifyInOrder([() => native.isAvailable(), () => native.requestReview()]);
    });

    test('requestReview returns error when native throws', () async {
      when(() => native.isAvailable()).thenAnswer((_) async => true);
      when(() => native.requestReview()).thenThrow(Exception('nope'));

      final result = await service.requestReview(
        source: ReviewRequestSource.adminTest,
      );

      expect(result, ReviewRequestResult.error);
      verifyInOrder([() => native.isAvailable(), () => native.requestReview()]);
    });
  });
}
