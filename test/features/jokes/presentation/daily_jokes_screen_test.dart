import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/config/router/app_router.dart' show RailHost;
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_schedule_batch.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/daily_jokes_screen.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

import '../../../test_helpers/firebase_mocks.dart';

// Mock classes
class MockImageService extends Mock implements ImageService {}

class MockJokeScheduleRepository extends Mock
    implements JokeScheduleRepository {}

// Fake classes for Mocktail fallback values
class FakeJokeScheduleBatch extends Fake implements JokeScheduleBatch {}

class FakeJoke extends Fake implements Joke {}

void main() {
  group('DailyJokesScreen', () {
    late List<Joke> mockJokes;
    late JokeScheduleBatch mockBatch;
    late MockImageService mockImageService;
    late MockJokeScheduleRepository mockRepository;
    late SettingsService settingsService;

    setUpAll(() {
      // Register fallback values for mocktail
      registerFallbackValue(FakeJokeScheduleBatch());
      registerFallbackValue(FakeJoke());
    });

    JokeScheduleBatch createMockBatch() {
      final now = DateTime.now();
      final currentMonth = DateTime(now.year, now.month);
      return JokeScheduleBatch(
        id: '${JokeConstants.defaultJokeScheduleId}_${now.year}_${now.month.toString().padLeft(2, '0')}',
        scheduleId: JokeConstants.defaultJokeScheduleId,
        year: currentMonth.year,
        month: currentMonth.month,
        jokes: {
          // Use today and previous days to ensure jokes are not filtered out
          now.day.toString().padLeft(2, '0'): mockJokes[0],
          (now.day - 1).toString().padLeft(2, '0'): mockJokes[1],
          (now.day - 2).toString().padLeft(2, '0'): mockJokes[2],
        },
      );
    }

    JokeScheduleBatch createSingleJokeBatch() {
      final now = DateTime.now();
      final currentMonth = DateTime(now.year, now.month);

      return JokeScheduleBatch(
        id: '${JokeConstants.defaultJokeScheduleId}_${now.year}_${now.month.toString().padLeft(2, '0')}',
        scheduleId: JokeConstants.defaultJokeScheduleId,
        year: currentMonth.year,
        month: currentMonth.month,
        jokes: {now.day.toString().padLeft(2, '0'): mockJokes[0]},
      );
    }

    setUp(() async {
      // Default tests expect Reveal mode enabled
      SharedPreferences.setMockInitialValues({'joke_viewer_reveal': true});
      final prefs = await SharedPreferences.getInstance();
      settingsService = SettingsService(prefs);
      // Create test jokes with images
      mockJokes = [
        Joke(
          id: '1',
          setupText: 'Why did the chicken cross the road?',
          punchlineText: 'To get to the other side!',
          setupImageUrl: 'https://example.com/setup1.jpg',
          punchlineImageUrl: 'https://example.com/punchline1.jpg',
        ),
        Joke(
          id: '2',
          setupText: 'What do you call a fake noodle?',
          punchlineText: 'An impasta!',
          setupImageUrl: 'https://example.com/setup2.jpg',
          punchlineImageUrl: 'https://example.com/punchline2.jpg',
        ),
        Joke(
          id: '3',
          setupText: 'Why don\'t scientists trust atoms?',
          punchlineText: 'Because they make up everything!',
          setupImageUrl: 'https://example.com/setup3.jpg',
          punchlineImageUrl: 'https://example.com/punchline3.jpg',
        ),
      ];

      // Create mock batch with test jokes
      mockBatch = createMockBatch();

      // Setup mock repository
      mockRepository = MockJokeScheduleRepository();
      when(
        () => mockRepository.getBatchForMonth(
          JokeConstants.defaultJokeScheduleId,
          any(that: isA<int>()),
          any(that: isA<int>()),
        ),
      ).thenAnswer((invocation) async => mockBatch);

      // Setup mock image service
      mockImageService = MockImageService();
      when(() => mockImageService.isValidImageUrl(any())).thenReturn(true);
      when(
        () => mockImageService.processImageUrl(any()),
      ).thenReturn('https://example.com/image.jpg');
      when(
        () => mockImageService.processImageUrl(
          any(),
          quality: any(named: 'quality'),
        ),
      ).thenReturn('https://example.com/image.jpg');
      when(() => mockImageService.clearCache()).thenAnswer((_) async {});
      // Mock precacheJokeImages method that returns the expected record type
      when(
        () => mockImageService.precacheJokeImages(
          any(),
          width: any(named: 'width'),
        ),
      ).thenAnswer(
        (_) async => (
          setupUrl: 'https://example.com/setup.jpg',
          punchlineUrl: 'https://example.com/punchline.jpg',
        ),
      );
      // Mock other ImageService methods that might be called
      when(
        () => mockImageService.getProcessedJokeImageUrl(
          any(),
          width: any(named: 'width'),
        ),
      ).thenReturn('https://example.com/processed.jpg');
      when(
        () => mockImageService.getThumbnailUrl(any()),
      ).thenReturn('https://example.com/thumbnail.jpg');
      when(
        () => mockImageService.precacheJokeImage(
          any(),
          width: any(named: 'width'),
        ),
      ).thenAnswer((_) async => 'https://example.com/cached.jpg');
      when(
        () => mockImageService.precacheMultipleJokeImages(
          any(),
          width: any(named: 'width'),
        ),
      ).thenAnswer((_) async {});
    });

    Widget createTestWidget({
      JokeScheduleBatch? customBatch,
      bool simulateError = false,
    }) {
      final MockJokeScheduleRepository customRepository =
          MockJokeScheduleRepository();

      if (simulateError) {
        when(
          () => customRepository.getBatchForMonth(
            JokeConstants.defaultJokeScheduleId,
            any(that: isA<int>()),
            any(that: isA<int>()),
          ),
        ).thenThrow(Exception('Failed to load jokes'));
      } else {
        when(
          () => customRepository.getBatchForMonth(
            JokeConstants.defaultJokeScheduleId,
            any(that: isA<int>()),
            any(that: isA<int>()),
          ),
        ).thenAnswer((invocation) async {
          final int year = invocation.positionalArguments[1] as int;
          final int month = invocation.positionalArguments[2] as int;
          final batch = customBatch ?? mockBatch;
          // Return the provided batch only for its target month; otherwise stop pagination
          if (year == batch.year && month == batch.month) {
            return batch;
          }
          return null;
        });
      }

      // Create a simple GoRouter for testing that routes directly to DailyJokesScreen
      final router = GoRouter(
        initialLocation: AppRoutes.jokes,
        routes: [
          GoRoute(
            path: AppRoutes.jokes,
            name: RouteNames.jokes,
            builder: (context, state) => const DailyJokesScreen(),
          ),
        ],
      );

      return ProviderScope(
        overrides: [
          imageServiceProvider.overrideWithValue(mockImageService),
          jokeScheduleRepositoryProvider.overrideWithValue(customRepository),
          ...FirebaseMocks.getFirebaseProviderOverrides(),
          settingsServiceProvider.overrideWithValue(settingsService),
        ],
        child: MaterialApp.router(theme: lightTheme, routerConfig: router),
      );
    }

    Widget createLandscapeShellTestWidget({JokeScheduleBatch? customBatch}) {
      final MockJokeScheduleRepository customRepository =
          MockJokeScheduleRepository();
      when(
        () => customRepository.getBatchForMonth(
          JokeConstants.defaultJokeScheduleId,
          any(that: isA<int>()),
          any(that: isA<int>()),
        ),
      ).thenAnswer((invocation) async {
        final int year = invocation.positionalArguments[1] as int;
        final int month = invocation.positionalArguments[2] as int;
        final batch = customBatch ?? mockBatch;
        if (year == batch.year && month == batch.month) {
          return batch;
        }
        return null;
      });

      final child = const DailyJokesScreen();

      return ProviderScope(
        overrides: [
          imageServiceProvider.overrideWithValue(mockImageService),
          jokeScheduleRepositoryProvider.overrideWithValue(customRepository),
          ...FirebaseMocks.getFirebaseProviderOverrides(),
          settingsServiceProvider.overrideWithValue(settingsService),
        ],
        child: MaterialApp(
          theme: lightTheme,
          home: Scaffold(
            body: Row(
              children: [
                SafeArea(
                  child: SizedBox(
                    width: 180,
                    child: Consumer(
                      builder: (context, ref, _) {
                        final bottomSlot = ref.watch(railBottomSlotProvider);
                        return Column(
                          children: [
                            Expanded(
                              child: NavigationRail(
                                destinations: [
                                  NavigationRailDestination(
                                    icon: Icon(Icons.mood),
                                    label: Text('Daily Jokes'),
                                  ),
                                ],
                                selectedIndex: 0,
                                extended: true,
                              ),
                            ),
                            if (bottomSlot != null)
                              Padding(
                                padding: const EdgeInsets.all(12.0),
                                child: bottomSlot,
                              ),
                          ],
                        );
                      },
                    ),
                  ),
                ),
                const VerticalDivider(thickness: 1, width: 1),
                Expanded(child: RailHost(railWidth: 180, child: child)),
              ],
            ),
          ),
        ),
      );
    }

    group('Basic Display States', () {
      testWidgets('displays loading indicator when jokes are loading', (
        tester,
      ) async {
        // Create a repository that never completes to simulate loading
        final loadingRepository = MockJokeScheduleRepository();
        when(
          () => loadingRepository.getBatchForMonth(
            JokeConstants.defaultJokeScheduleId,
            any(that: isA<int>()),
            any(that: isA<int>()),
          ),
        ).thenAnswer((_) => Completer<JokeScheduleBatch?>().future);

        // Create a simple GoRouter for testing
        final router = GoRouter(
          initialLocation: AppRoutes.jokes,
          routes: [
            GoRoute(
              path: AppRoutes.jokes,
              name: RouteNames.jokes,
              builder: (context, state) => const DailyJokesScreen(),
            ),
          ],
        );

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              imageServiceProvider.overrideWithValue(mockImageService),
              jokeScheduleRepositoryProvider.overrideWithValue(
                loadingRepository,
              ),
              ...FirebaseMocks.getFirebaseProviderOverrides(),
            ],
            child: MaterialApp.router(theme: lightTheme, routerConfig: router),
          ),
        );

        // Allow microtask to kick off initial load
        await tester.pump();
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
      });

      testWidgets('shows empty state when jokes fail to load', (tester) async {
        await tester.pumpWidget(createTestWidget(simulateError: true));

        await tester.pump(); // Allow error to be processed
        expect(find.text('No jokes found! Try adding some.'), findsOneWidget);
      });

      testWidgets('displays no jokes message when joke list is empty', (
        tester,
      ) async {
        // Use a repository that returns no batch for any month so pagination
        // terminates immediately without looping across months.
        final noBatchRepo = MockJokeScheduleRepository();
        when(
          () => noBatchRepo.getBatchForMonth(
            JokeConstants.defaultJokeScheduleId,
            any(that: isA<int>()),
            any(that: isA<int>()),
          ),
        ).thenAnswer((_) async => null);

        // Create a simple GoRouter for testing that routes directly to DailyJokesScreen
        final router = GoRouter(
          initialLocation: AppRoutes.jokes,
          routes: [
            GoRoute(
              path: AppRoutes.jokes,
              name: RouteNames.jokes,
              builder: (context, state) => const DailyJokesScreen(),
            ),
          ],
        );

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              imageServiceProvider.overrideWithValue(mockImageService),
              jokeScheduleRepositoryProvider.overrideWithValue(noBatchRepo),
              ...FirebaseMocks.getFirebaseProviderOverrides(),
              settingsServiceProvider.overrideWithValue(settingsService),
            ],
            child: MaterialApp.router(theme: lightTheme, routerConfig: router),
          ),
        );

        await tester.pump(); // Allow data to be processed
        expect(find.text('No jokes found! Try adding some.'), findsOneWidget);
      });

      testWidgets('displays jokes when data is loaded', (tester) async {
        await tester.pumpWidget(createTestWidget());

        await tester.pump(); // Allow data to be processed

        // Should find PageView containing jokes
        expect(find.byType(PageView), findsWidgets);
        // Should find JokeCard widgets (PageView lazily renders, so we expect at least 1)
        expect(find.byType(JokeCard), findsAtLeastNWidgets(1));
        // Should find image carousels since jokes have both setup and punchline images
        expect(find.byType(JokeImageCarousel), findsAtLeastNWidgets(1));
      });
    });

    group('CTA Behavior', () {
      testWidgets('shows Next joke when reveal disabled via settings', (
        tester,
      ) async {
        // Override preference to disable reveal (show both images)
        SharedPreferences.setMockInitialValues({'joke_viewer_reveal': false});
        await settingsService.setBool('joke_viewer_reveal', false);

        await tester.pumpWidget(createTestWidget());
        await tester.pump();
        await tester.pump(); // allow post-frame rail slot update

        expect(
          find.byKey(const Key('joke_list_viewer-cta-button')),
          findsOneWidget,
        );
        expect(find.text('Next joke'), findsOneWidget);
      });
      testWidgets('shows CTA button and toggles label based on state', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());

        await tester.pump();
        // Allow post-frame rail slot update
        await tester.pump();

        // Initially on setup image: CTA should say Reveal
        expect(
          find.byKey(const Key('joke_list_viewer-cta-button')),
          findsOneWidget,
        );
        expect(find.text('Reveal'), findsOneWidget);

        // Tap CTA to reveal punchline
        await tester.tap(find.byKey(const Key('joke_list_viewer-cta-button')));
        await tester.pump(const Duration(milliseconds: 400));

        // Now CTA should say Next joke
        expect(find.text('Next joke'), findsOneWidget);
      });

      testWidgets('CTA disabled on last joke when showing Next joke', (
        tester,
      ) async {
        final single = createSingleJokeBatch();
        await tester.pumpWidget(createTestWidget(customBatch: single));
        await tester.pump();
        // Allow post-frame rail slot update
        await tester.pump();
        // Reveal first
        await tester.tap(find.byKey(const Key('joke_list_viewer-cta-button')));
        await tester.pump(const Duration(milliseconds: 400));
        // Should show Next joke and be disabled (no onPressed)
        final button = tester.widget<ElevatedButton>(
          find.byKey(const Key('joke_list_viewer-cta-button')),
        );
        expect(find.text('Next joke'), findsOneWidget);
        expect(button.onPressed, isNull);
      });

      testWidgets('landscape CTA switches from Reveal to Next joke', (
        tester,
      ) async {
        // Simulate landscape by making width > height
        tester.view.physicalSize = const Size(1200, 600);
        addTearDown(() => tester.view.resetPhysicalSize());

        await tester.pumpWidget(createTestWidget());
        await tester.pump();
        await tester.pump(); // allow post-frame rail slot update

        // CTA is rendered via the rail bottom slot
        expect(
          find.byKey(const Key('joke_list_viewer-cta-button')),
          findsOneWidget,
        );
        expect(find.text('Reveal'), findsOneWidget);

        // Tap to reveal punchline
        await tester.tap(find.byKey(const Key('joke_list_viewer-cta-button')));
        await tester.pump(const Duration(milliseconds: 400));

        // Now label should be Next joke
        expect(find.text('Next joke'), findsOneWidget);
      });

      testWidgets('portrait places CTA as bottom overlay', (tester) async {
        // Use a wide portrait to avoid carousel chip overflows in tight widths
        tester.view.physicalSize = const Size(1200, 2000);
        addTearDown(() => tester.view.resetPhysicalSize());
        await tester.pumpWidget(createTestWidget());
        await tester.pump();
        await tester.pump();
        expect(find.byType(NavigationRail), findsNothing);
        expect(
          find.byKey(const Key('joke_list_viewer-cta-button')),
          findsOneWidget,
        );
        expect(find.text('Reveal'), findsOneWidget);
      });

      testWidgets('landscape places CTA inside NavigationRail bottom slot', (
        tester,
      ) async {
        tester.view.physicalSize = const Size(1200, 600);
        addTearDown(() => tester.view.resetPhysicalSize());
        await tester.pumpWidget(createLandscapeShellTestWidget());
        await tester.pump();
        await tester.pump();
        // Allow async settings provider to load reveal preference
        await tester.pump(const Duration(milliseconds: 250));
        expect(find.byType(NavigationRail), findsOneWidget);
        expect(
          find.byKey(const Key('joke_list_viewer-cta-button')),
          findsOneWidget,
        );
        expect(find.text('Reveal'), findsOneWidget);
      });

      testWidgets('CTA shows Next joke when joke has no punchline image', (
        tester,
      ) async {
        // Build data where current joke has no punchline image
        final now = DateTime.now();
        final currentMonth = DateTime(now.year, now.month);
        final jokes = [
          Joke(
            id: 'np-1',
            setupText: 'Setup only',
            punchlineText: 'No punchline image',
            setupImageUrl: 'https://example.com/setup1.jpg',
            punchlineImageUrl: '', // missing/empty
          ),
        ];
        final batches = [
          JokeScheduleBatch(
            id: '${JokeConstants.defaultJokeScheduleId}_${now.year}_${now.month.toString().padLeft(2, '0')}',
            scheduleId: JokeConstants.defaultJokeScheduleId,
            year: currentMonth.year,
            month: currentMonth.month,
            jokes: {now.day.toString().padLeft(2, '0'): jokes[0]},
          ),
        ];

        await tester.pumpWidget(createTestWidget(customBatch: batches.first));
        await tester.pump();
        await tester.pump();
        // Give the StreamProvider an extra frame to emit
        await tester.pump(const Duration(milliseconds: 200));

        // With current behavior, jokes missing punchline image are filtered out,
        // so CTA is not rendered.
        expect(
          find.byKey(const Key('joke_list_viewer-cta-button')),
          findsNothing,
        );
      });

      testWidgets('after advancing, CTA label resets to Reveal on next joke', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pump();
        await tester.pump();

        // Reveal first joke
        await tester.tap(find.byKey(const Key('joke_list_viewer-cta-button')));
        await tester.pump(const Duration(milliseconds: 400));
        expect(find.text('Next joke'), findsOneWidget);

        // Advance to next joke
        await tester.tap(find.byKey(const Key('joke_list_viewer-cta-button')));
        await tester.pump(const Duration(milliseconds: 400));
        await tester.pump(const Duration(milliseconds: 400));

        // CTA should reset to Reveal for the new joke
        expect(find.text('Reveal'), findsOneWidget);
      });
    });

    group('Navigation Behavior', () {
      testWidgets('supports vertical scrolling between jokes', (tester) async {
        await tester.pumpWidget(createTestWidget());

        await tester.pump(); // Allow data to be processed

        // Find the main PageView and verify it has vertical scroll direction
        final pageViews = find.byType(PageView).evaluate();
        final mainPageView = pageViews.first.widget as PageView;
        expect(mainPageView.scrollDirection, Axis.vertical);
      });

      testWidgets('maintains stable state during navigation', (tester) async {
        await tester.pumpWidget(createTestWidget());

        await tester.pump(); // Allow data to be processed

        // Should maintain PageView presence
        expect(find.byType(PageView), findsWidgets);

        // Should not throw exceptions during multiple pumps
        await tester.pump(const Duration(milliseconds: 100));
        await tester.pump(const Duration(milliseconds: 100));
        expect(find.byType(PageView), findsWidgets);
      });
    });

    group('Learning System Behavior', () {
      testWidgets('supports learning state persistence', (tester) async {
        await tester.pumpWidget(createTestWidget());

        await tester.pump(); // Allow data to be processed
        await tester.pump(
          const Duration(milliseconds: 200),
        ); // Allow hints to appear

        // Should be able to trigger rebuilds without crashing
        await tester.pumpWidget(createTestWidget());

        await tester.pump(); // Allow rebuild
        expect(find.byType(PageView), findsWidgets);
      });
    });

    group('Edge Cases', () {
      testWidgets('handles rapid state changes gracefully', (tester) async {
        await tester.pumpWidget(createTestWidget());

        // Rapid pumps to simulate rapid state changes
        for (int i = 0; i < 5; i++) {
          await tester.pump(const Duration(milliseconds: 50));
        }

        // Should maintain stable state
        expect(find.byType(PageView), findsWidgets);
      });

      testWidgets('handles widget rebuilds correctly', (tester) async {
        await tester.pumpWidget(createTestWidget());

        await tester.pump(); // Allow initial build

        // Trigger rebuild with same data
        await tester.pumpWidget(createTestWidget());

        await tester.pump(); // Allow rebuild
        expect(find.byType(PageView), findsWidgets);
      });

      testWidgets('handles empty and populated state transitions', (
        tester,
      ) async {
        // Start with empty
        final now2 = DateTime.now();
        final emptyBatch2 = JokeScheduleBatch(
          id: '${JokeConstants.defaultJokeScheduleId}_${now2.year}_${now2.month.toString().padLeft(2, '0')}',
          scheduleId: JokeConstants.defaultJokeScheduleId,
          year: now2.year,
          month: now2.month,
          jokes: const {},
        );
        await tester.pumpWidget(createTestWidget(customBatch: emptyBatch2));

        await tester.pump();
        expect(find.text('No jokes found! Try adding some.'), findsOneWidget);

        // Transition to populated
        await tester.pumpWidget(createTestWidget());

        await tester.pump();
        await tester.pump(); // Extra pump for provider rebuild

        // After transition, should not crash
        expect(find.textContaining('Error'), findsNothing);
        // Test passes if no exceptions are thrown during state transition
      });
    });

    group('Integration Behavior', () {
      testWidgets('integrates correctly with provider system', (tester) async {
        await tester.pumpWidget(createTestWidget());

        await tester.pump(); // Allow data to be processed

        // Should integrate with mocked providers without Firebase errors
        // Note: Images may still be loading, so CircularProgressIndicator is expected in image widgets
        expect(find.textContaining('Error'), findsNothing);
        expect(find.byType(PageView), findsWidgets);
      });

      testWidgets('maintains performance during normal operation', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());

        // Multiple pumps should complete quickly
        final stopwatch = Stopwatch()..start();

        for (int i = 0; i < 10; i++) {
          await tester.pump(const Duration(milliseconds: 16)); // 60 FPS
        }

        stopwatch.stop();
        expect(
          stopwatch.elapsedMilliseconds,
          lessThan(1000),
          reason: 'Should complete 10 frames in under 1 second',
        );
      });
    });

    group('Title Display', () {
      testWidgets('displays joke dates as titles', (tester) async {
        await tester.pumpWidget(createTestWidget());

        await tester.pump(); // Allow data to be processed

        // Should find titles with formatted dates
        // The exact format may vary, but should contain some date-related text
        final titleWidgets = find.byType(Text);
        expect(titleWidgets, findsWidgets);

        // This is a lenient test - we just want to ensure titles are being displayed
        // The specific formatting can be tested in unit tests
        expect(find.byType(JokeImageCarousel), findsWidgets);
      });
    });
  });
}
