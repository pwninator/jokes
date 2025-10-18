import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';
import 'package:snickerdoodle/src/data/reviews/reviews_repository.dart';

// Mock classes for AppReviewService dependencies
class MockNativeReviewAdapter extends Mock implements NativeReviewAdapter {}

class MockReviewPromptStateStore extends Mock
    implements ReviewPromptStateStore {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockReviewsRepository extends Mock implements ReviewsRepository {}

void main() {
  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(ReviewRequestSource.adminTest);
  });

  late MockNativeReviewAdapter mockNativeAdapter;
  late MockReviewPromptStateStore mockStateStore;
  late MockAnalyticsService mockAnalyticsService;
  late MockReviewsRepository mockReviewsRepository;
  late AppReviewService service;

  setUp(() {
    // Create fresh mocks per test
    mockNativeAdapter = MockNativeReviewAdapter();
    mockStateStore = MockReviewPromptStateStore();
    mockAnalyticsService = MockAnalyticsService();
    mockReviewsRepository = MockReviewsRepository();

    // Create service with mocked dependencies
    service = AppReviewService(
      nativeAdapter: mockNativeAdapter,
      stateStore: mockStateStore,
      getReviewPromptVariant: () => ReviewPromptVariant.bunny,
      analyticsService: mockAnalyticsService,
      reviewsRepository: mockReviewsRepository,
    );

    // Setup default successful behaviors
    when(
      () => mockAnalyticsService.logAppReviewAttempt(
        source: any(named: 'source'),
        variant: any(named: 'variant'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mockAnalyticsService.logAppReviewAccepted(
        source: any(named: 'source'),
        variant: any(named: 'variant'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mockAnalyticsService.logAppReviewDeclined(
        source: any(named: 'source'),
        variant: any(named: 'variant'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mockAnalyticsService.logErrorAppReviewAvailability(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mockAnalyticsService.logErrorAppReviewRequest(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => mockReviewsRepository.recordAppReview(),
    ).thenAnswer((_) async {});
  });

  group('AppReviewService', () {
    group('isAvailable', () {
      test('returns true when native is available', () async {
        when(
          () => mockNativeAdapter.isAvailable(),
        ).thenAnswer((_) async => true);

        final result = await service.isAvailable();

        expect(result, isTrue);
        verify(() => mockNativeAdapter.isAvailable()).called(1);
        verifyNever(
          () => mockAnalyticsService.logErrorAppReviewAvailability(
            source: any(named: 'source'),
            errorMessage: any(named: 'errorMessage'),
          ),
        );
      });

      test('returns false and logs analytics when native throws', () async {
        when(
          () => mockNativeAdapter.isAvailable(),
        ).thenThrow(Exception('boom'));

        final result = await service.isAvailable();

        expect(result, isFalse);
        verify(() => mockNativeAdapter.isAvailable()).called(1);
        verify(
          () => mockAnalyticsService.logErrorAppReviewAvailability(
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
        when(
          () => mockNativeAdapter.isAvailable(),
        ).thenAnswer((_) async => false);
        when(() => mockStateStore.hasRequested()).thenAnswer((_) => false);

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

        verify(() => mockNativeAdapter.isAvailable()).called(1);
        verifyNever(
          () => mockAnalyticsService.logAppReviewAttempt(
            source: any(named: 'source'),
            variant: any(named: 'variant'),
          ),
        );
      });

      testWidgets('shows dialog and processes accept', (tester) async {
        when(
          () => mockNativeAdapter.isAvailable(),
        ).thenAnswer((_) async => true);
        when(() => mockStateStore.hasRequested()).thenAnswer((_) => false);
        when(() => mockNativeAdapter.requestReview()).thenAnswer((_) async {});
        when(() => mockStateStore.markRequested()).thenAnswer((_) async {});

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
          () => mockNativeAdapter.isAvailable(),
          () => mockStateStore.hasRequested(),
          () => mockStateStore.markRequested(),
          () => mockAnalyticsService.logAppReviewAttempt(
            source: 'joke_viewed',
            variant: 'bunny',
          ),
          () => mockAnalyticsService.logAppReviewAccepted(
            source: 'joke_viewed',
            variant: 'bunny',
          ),
          () => mockNativeAdapter.requestReview(),
        ]);
      });

      testWidgets('shows dialog and processes decline', (tester) async {
        when(
          () => mockNativeAdapter.isAvailable(),
        ).thenAnswer((_) async => true);
        when(() => mockStateStore.hasRequested()).thenAnswer((_) => false);
        when(() => mockStateStore.markRequested()).thenAnswer((_) async {});

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
          () => mockNativeAdapter.isAvailable(),
          () => mockStateStore.hasRequested(),
          () => mockStateStore.markRequested(),
          () => mockAnalyticsService.logAppReviewAttempt(
            source: 'joke_saved',
            variant: 'bunny',
          ),
          () => mockAnalyticsService.logAppReviewDeclined(
            source: 'joke_saved',
            variant: 'bunny',
          ),
        ]);
        verifyNever(() => mockNativeAdapter.requestReview());
      });

      testWidgets(
        'handles feedback intent by dismissing and not calling native review',
        (tester) async {
          when(
            () => mockNativeAdapter.isAvailable(),
          ).thenAnswer((_) async => true);
          when(() => mockStateStore.hasRequested()).thenAnswer((_) => false);
          when(() => mockStateStore.markRequested()).thenAnswer((_) async {});

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
          verify(() => mockNativeAdapter.isAvailable()).called(1);
          verify(() => mockStateStore.hasRequested()).called(1);
          verify(() => mockStateStore.markRequested()).called(1);
          verifyNever(() => mockNativeAdapter.requestReview());
        },
      );

      testWidgets('does not prompt again after user dismisses on first call', (
        tester,
      ) async {
        when(
          () => mockNativeAdapter.isAvailable(),
        ).thenAnswer((_) async => true);
        when(() => mockStateStore.markRequested()).thenAnswer((_) async {});

        // First call: not requested yet
        when(() => mockStateStore.hasRequested()).thenAnswer((_) => false);

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
        when(() => mockStateStore.hasRequested()).thenAnswer((_) => true);

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
        verify(() => mockStateStore.markRequested()).called(1);

        // Verify hasRequested was called twice (once per requestReview call)
        verify(() => mockStateStore.hasRequested()).called(2);

        // Native review should never be called since user dismissed
        verifyNever(() => mockNativeAdapter.requestReview());
      });
    });
  });
}
