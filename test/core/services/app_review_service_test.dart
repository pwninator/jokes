import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';

import '../../test_helpers/analytics_mocks.dart';
import '../../test_helpers/core_mocks.dart';

class _MockNativeReviewAdapter extends Mock implements NativeReviewAdapter {}

class _MockStateStore extends Mock implements ReviewPromptStateStore {}

void main() {
  late _MockNativeReviewAdapter native;
  late MockAnalyticsService analytics;
  late AppReviewService service;
  late _MockStateStore store;

  setUpAll(() {
    registerFallbackValue(ReviewRequestSource.adminTest);
    registerAnalyticsFallbackValues();
  });

  setUp(() {
    AnalyticsMocks.reset();

    native = _MockNativeReviewAdapter();
    analytics = AnalyticsMocks.mockAnalyticsService;
    store = _MockStateStore();
    service = AppReviewService(
      nativeAdapter: native,
      stateStore: store,
      getReviewPromptVariant: () => ReviewPromptVariant.bunny,
      analyticsService: analytics,
      reviewsRepository: CoreMocks.mockReviewsRepository,
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
        when(() => store.hasRequested()).thenAnswer((_) => false);

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
        when(() => store.hasRequested()).thenAnswer((_) => false);
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
          () => store.hasRequested(),
          () => store.markRequested(),
          () => analytics.logAppReviewAttempt(
            source: 'joke_viewed',
            variant: 'bunny',
          ),
          () => analytics.logAppReviewAccepted(
            source: 'joke_viewed',
            variant: 'bunny',
          ),
          () => native.requestReview(),
        ]);
      });

      testWidgets('shows dialog and processes decline', (tester) async {
        when(() => native.isAvailable()).thenAnswer((_) async => true);
        when(() => store.hasRequested()).thenAnswer((_) => false);
        when(() => store.markRequested()).thenAnswer((_) async {});

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
          () => store.hasRequested(),
          () => store.markRequested(),
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
      });

      testWidgets(
        'handles feedback intent by dismissing and not calling native review',
        (tester) async {
          when(() => native.isAvailable()).thenAnswer((_) async => true);
          when(() => store.hasRequested()).thenAnswer((_) => false);
          when(() => store.markRequested()).thenAnswer((_) async {});

          await tester.pumpWidget(
            MaterialApp(
              home: Builder(
                builder: (context) {
                  return ElevatedButton(
                    onPressed: () async {
                      await service.requestReview(
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

          // Trigger
          await tester.tap(find.text('Request Review'));
          await tester.pumpAndSettle();

          // Tap the feedback link in dialog
          final feedbackKey = find.byKey(
            const Key('app_review_prompt_dialog-feedback-link-bunny'),
          );
          expect(feedbackKey, findsOneWidget);
          await tester.tap(feedbackKey);
          await tester.pumpAndSettle();

          // Ensure no native review was requested
          verify(() => native.isAvailable()).called(1);
          verify(() => store.hasRequested()).called(1);
          verify(() => store.markRequested()).called(1);
          verifyNever(() => native.requestReview());
        },
      );

      testWidgets('does not prompt again after user dismisses on first call', (
        tester,
      ) async {
        when(() => native.isAvailable()).thenAnswer((_) async => true);
        when(() => store.markRequested()).thenAnswer((_) async {});

        // First call: not requested yet
        when(() => store.hasRequested()).thenAnswer((_) => false);

        ReviewRequestResult? firstResult;
        ReviewRequestResult? secondResult;

        await tester.pumpWidget(
          MaterialApp(
            home: Builder(
              builder: (context) {
                return ElevatedButton(
                  onPressed: () async {
                    firstResult = await service.requestReview(
                      source: ReviewRequestSource.jokeViewed,
                      context: context,
                    );
                    secondResult = await service.requestReview(
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

        // Tap button to trigger first review request
        await tester.tap(find.text('Request Review'));
        await tester.pumpAndSettle();

        // Dialog should be shown
        expect(
          find.byKey(
            const Key('app_review_prompt_dialog-dismiss-button-bunny'),
          ),
          findsOneWidget,
        );

        // Update mock: after markRequested is called, hasRequested should return true
        when(() => store.hasRequested()).thenAnswer((_) => true);

        // User dismisses the dialog
        await tester.tap(
          find.byKey(
            const Key('app_review_prompt_dialog-dismiss-button-bunny'),
          ),
        );
        await tester.pumpAndSettle();

        // First request should be dismissed
        expect(firstResult, ReviewRequestResult.dismissed);

        // Second request should be notAvailable (already requested)
        expect(secondResult, ReviewRequestResult.notAvailable);

        // Verify markRequested was only called once (during first request)
        verify(() => store.markRequested()).called(1);

        // Verify hasRequested was called twice (once per requestReview call)
        verify(() => store.hasRequested()).called(2);

        // Native review should never be called since user dismissed
        verifyNever(() => native.requestReview());
      });
    });
  });
}
