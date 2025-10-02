import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
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
      getReviewPromptVariant: () => ReviewPromptVariant.bunny,
      analyticsService: analytics,
    );

    // Mock successful analytics calls by default
    when(
      () => analytics.logAppReviewAttempt(
        source: any(named: 'source'),
        variant: any(named: 'variant'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => analytics.logAppReviewAccepted(
        source: any(named: 'source'),
        variant: any(named: 'variant'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => analytics.logAppReviewDeclined(
        source: any(named: 'source'),
        variant: any(named: 'variant'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => analytics.logErrorAppReviewAvailability(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => analytics.logErrorAppReviewRequest(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});
  });

  group('AppReviewService', () {
    group('isAvailable', () {
      test('returns true when native is available', () async {
        when(() => native.isAvailable()).thenAnswer((_) async => true);
        expect(await service.isAvailable(), isTrue);
        verify(() => native.isAvailable()).called(1);
        verifyNever(
          () => analytics.logErrorAppReviewAvailability(
            source: any(named: 'source'),
            errorMessage: any(named: 'errorMessage'),
          ),
        );
      });

      test('returns false and logs analytics when native throws', () async {
        when(() => native.isAvailable()).thenThrow(Exception('boom'));
        expect(await service.isAvailable(), isFalse);
        verify(() => native.isAvailable()).called(1);
        verify(
          () => analytics.logErrorAppReviewAvailability(
            source: 'service',
            errorMessage: 'app_review_is_available_failed',
          ),
        ).called(1);
      });
    });

    group('requestReview with context (shows dialog)', () {
      testWidgets('returns notAvailable when API not available', (
        tester,
      ) async {
        when(() => native.isAvailable()).thenAnswer((_) async => false);

        await tester.pumpWidget(
          MaterialApp(
            home: Builder(
              builder: (context) {
                return ElevatedButton(
                  onPressed: () async {
                    final result = await service.requestReview(
                      source: ReviewRequestSource.jokeShared,
                      context: context,
                    );
                    expect(result, ReviewRequestResult.notAvailable);
                  },
                  child: const Text('Test'),
                );
              },
            ),
          ),
        );

        await tester.tap(find.text('Test'));
        await tester.pumpAndSettle();

        verify(() => native.isAvailable()).called(1);
        verifyNever(
          () => analytics.logAppReviewAttempt(
            source: any(named: 'source'),
            variant: any(named: 'variant'),
          ),
        );
      });

      testWidgets('shows dialog and processes accept', (tester) async {
        when(() => native.isAvailable()).thenAnswer((_) async => true);
        when(() => native.requestReview()).thenAnswer((_) async {});
        when(() => store.markRequested()).thenAnswer((_) async {});

        ReviewRequestResult? result;

        await tester.pumpWidget(
          MaterialApp(
            home: Builder(
              builder: (context) {
                return ElevatedButton(
                  onPressed: () async {
                    result = await service.requestReview(
                      source: ReviewRequestSource.jokeViewed,
                      context: context,
                    );
                  },
                  child: const Text('Request Review'),
                );
              },
            ),
          ),
        );

        // Tap button to trigger review request
        await tester.tap(find.text('Request Review'));
        await tester.pumpAndSettle();

        // Dialog should be shown (assert by presence of variant-specific key)
        expect(
          find.byKey(const Key('app_review_prompt_dialog-accept-button-bunny')),
          findsOneWidget,
        );

        // Tap accept button
        await tester.tap(
          find.byKey(const Key('app_review_prompt_dialog-accept-button-bunny')),
        );
        await tester.pumpAndSettle();

        expect(result, ReviewRequestResult.shown);
        verifyInOrder([
          () => native.isAvailable(),
          () => analytics.logAppReviewAttempt(
            source: 'joke_viewed',
            variant: 'bunny',
          ),
          () => analytics.logAppReviewAccepted(
            source: 'joke_viewed',
            variant: 'bunny',
          ),
          () => native.requestReview(),
          () => store.markRequested(),
        ]);
      });

      testWidgets('shows dialog and processes decline', (tester) async {
        when(() => native.isAvailable()).thenAnswer((_) async => true);

        ReviewRequestResult? result;

        await tester.pumpWidget(
          MaterialApp(
            home: Builder(
              builder: (context) {
                return ElevatedButton(
                  onPressed: () async {
                    result = await service.requestReview(
                      source: ReviewRequestSource.jokeSaved,
                      context: context,
                    );
                  },
                  child: const Text('Request Review'),
                );
              },
            ),
          ),
        );

        // Tap button to trigger review request
        await tester.tap(find.text('Request Review'));
        await tester.pumpAndSettle();

        // Dialog should be shown (assert by presence of variant-specific key)
        expect(
          find.byKey(
            const Key('app_review_prompt_dialog-dismiss-button-bunny'),
          ),
          findsOneWidget,
        );

        // Tap dismiss button
        await tester.tap(
          find.byKey(
            const Key('app_review_prompt_dialog-dismiss-button-bunny'),
          ),
        );
        await tester.pumpAndSettle();

        expect(result, ReviewRequestResult.dismissed);
        verifyInOrder([
          () => native.isAvailable(),
          () => analytics.logAppReviewAttempt(
            source: 'joke_saved',
            variant: 'bunny',
          ),
          () => analytics.logAppReviewDeclined(
            source: 'joke_saved',
            variant: 'bunny',
          ),
        ]);
        verifyNever(() => native.requestReview());
        verifyNever(() => store.markRequested());
      });
    });
  });
}
