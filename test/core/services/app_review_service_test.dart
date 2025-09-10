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

    test(
      'requestReview returns notAvailable and nativeAttempted=false when API not available',
      () async {
        when(() => native.isAvailable()).thenAnswer((_) async => false);

        final resp = await service.requestReview(
          source: ReviewRequestSource.adminTest,
        );

        expect(resp.result, ReviewRequestResult.notAvailable);
        expect(resp.nativeAttempted, isFalse);
        verify(() => native.isAvailable()).called(1);
        verifyNever(() => native.requestReview());
      },
    );

    test(
      'requestReview returns shown and nativeAttempted=true when request succeeds',
      () async {
        when(() => native.isAvailable()).thenAnswer((_) async => true);
        when(() => native.requestReview()).thenAnswer((_) async {});

        final resp = await service.requestReview(
          source: ReviewRequestSource.adminTest,
        );

        expect(resp.result, ReviewRequestResult.shown);
        expect(resp.nativeAttempted, isTrue);
        verifyInOrder([
          () => native.isAvailable(),
          () => native.requestReview(),
        ]);
      },
    );

    test(
      'requestReview returns error and nativeAttempted=true when native throws after availability',
      () async {
        when(() => native.isAvailable()).thenAnswer((_) async => true);
        when(() => native.requestReview()).thenThrow(Exception('nope'));

        final resp = await service.requestReview(
          source: ReviewRequestSource.adminTest,
        );

        expect(resp.result, ReviewRequestResult.error);
        expect(resp.nativeAttempted, isTrue);
        verifyInOrder([
          () => native.isAvailable(),
          () => native.requestReview(),
        ]);
      },
    );
  });
}
