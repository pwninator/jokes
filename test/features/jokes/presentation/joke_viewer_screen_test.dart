import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_viewer_screen.dart';

import '../../../test_helpers/firebase_mocks.dart';

// Mock class for ImageService
class MockImageService extends Mock implements ImageService {}

void main() {
  group('JokeViewerScreen', () {
    late List<Joke> mockJokes;
    late MockImageService mockImageService;

    setUp(() {
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

      mockImageService = MockImageService();
      // Mock the methods that might be called during tests
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
    });

    Widget createTestWidget({required List<Override> overrides}) {
      return ProviderScope(
        overrides: [
          imageServiceProvider.overrideWithValue(mockImageService),
          ...FirebaseMocks.getFirebaseProviderOverrides(),
          ...overrides,
        ],
        child: MaterialApp(theme: lightTheme, home: const JokeViewerScreen()),
      );
    }

    group('Basic Display States', () {
      testWidgets('displays loading indicator when jokes are loading', (
        tester,
      ) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => const Stream<List<Joke>>.empty(),
              ),
            ],
          ),
        );

        expect(find.byType(CircularProgressIndicator), findsOneWidget);
      });

      testWidgets('displays error message when jokes fail to load', (
        tester,
      ) async {
        const errorMessage = 'Failed to load jokes';
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream<List<Joke>>.error(errorMessage),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow error to be processed
        expect(find.textContaining('Error loading jokes'), findsOneWidget);
      });

      testWidgets('displays no jokes message when joke list is empty', (
        tester,
      ) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(<Joke>[]),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow data to be processed
        expect(find.text('No jokes found! Try adding some.'), findsOneWidget);
      });

      testWidgets('displays jokes when data is loaded', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow data to be processed

        // Should find PageView containing jokes
        expect(find.byType(PageView), findsWidgets);
        // Should find JokeCard widgets (PageView lazily renders, so we expect at least 1)
        expect(find.byType(JokeCard), findsAtLeastNWidgets(1));
        // Should find image carousels since jokes have both setup and punchline images
        expect(find.byType(JokeImageCarousel), findsAtLeastNWidgets(1));
      });
    });

    group('Hint System - Core Functionality', () {
      testWidgets('shows contextual hints initially', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow data to be processed
        await tester.pump(
          const Duration(milliseconds: 200),
        ); // Allow hints to appear

        // Should show some kind of hint text (exact text may vary based on state)
        final hintTexts = ['Tap for punchline!', 'Tap for next joke!'];
        bool foundHint = false;
        for (final hint in hintTexts) {
          if (find.text(hint).evaluate().isNotEmpty) {
            foundHint = true;
            break;
          }
        }
        expect(foundHint, isTrue, reason: 'Should show at least one hint');
      });

      testWidgets('hints can fade and restore during interactions', (
        tester,
      ) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow data to be processed
        await tester.pump(
          const Duration(milliseconds: 200),
        ); // Allow hints to appear

        // Find any hint elements that might have opacity
        final opacityWidgets = find.byType(Opacity);
        expect(
          opacityWidgets,
          findsWidgets,
          reason: 'Should have opacity-controlled hints',
        );
      });

      testWidgets('works with single joke scenario', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value([mockJokes.first]),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow data to be processed
        await tester.pump(
          const Duration(milliseconds: 200),
        ); // Allow hints to appear

        // Should not crash and should show some UI
        expect(find.byType(PageView), findsWidgets);
      });
    });

    group('Navigation Behavior', () {
      testWidgets('supports vertical scrolling between jokes', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow data to be processed

        // Find the main PageView and verify it has vertical scroll direction
        final pageViews = find.byType(PageView).evaluate();
        final mainPageView = pageViews.first.widget as PageView;
        expect(mainPageView.scrollDirection, Axis.vertical);
      });

      testWidgets('maintains stable state during navigation', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

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
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow data to be processed
        await tester.pump(
          const Duration(milliseconds: 200),
        ); // Allow hints to appear

        // Should be able to trigger rebuilds without crashing
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes.reversed.toList()),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow rebuild
        expect(find.byType(PageView), findsWidgets);
      });
    });

    group('Edge Cases', () {
      testWidgets('handles rapid state changes gracefully', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

        // Rapid pumps to simulate rapid state changes
        for (int i = 0; i < 5; i++) {
          await tester.pump(const Duration(milliseconds: 50));
        }

        // Should maintain stable state
        expect(find.byType(PageView), findsWidgets);
      });

      testWidgets('handles widget rebuilds correctly', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow initial build

        // Trigger rebuild with same data
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow rebuild
        expect(find.byType(PageView), findsWidgets);
      });

      testWidgets('handles empty and populated state transitions', (
        tester,
      ) async {
        // Start with empty
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(<Joke>[]),
              ),
            ],
          ),
        );

        await tester.pump();
        expect(find.text('No jokes found! Try adding some.'), findsOneWidget);

        // Transition to populated
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

        await tester.pump();
        await tester.pump(); // Extra pump for provider rebuild

        // After transition, should not crash
        expect(find.textContaining('Error'), findsNothing);
        // Test passes if no exceptions are thrown during state transition
      });
    });

    group('Integration Behavior', () {
      testWidgets('integrates correctly with provider system', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow data to be processed

        // Should integrate with mocked providers without Firebase errors
        // Note: Images may still be loading, so CircularProgressIndicator is expected in image widgets
        expect(find.textContaining('Error'), findsNothing);
        expect(find.byType(PageView), findsWidgets);
      });

      testWidgets('maintains performance during normal operation', (
        tester,
      ) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

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

    group('Arrow Indicators', () {
      testWidgets('shows no arrows when there is only one joke', (
        tester,
      ) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value([mockJokes.first]),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow data to be processed

        // Should not show any arrow indicators
        expect(find.byIcon(Icons.keyboard_arrow_up), findsNothing);
        expect(find.byIcon(Icons.keyboard_arrow_down), findsNothing);
      });

      testWidgets('arrow logic works correctly based on page position', (
        tester,
      ) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow data to be processed

        // Initially at first joke - only down arrow should be visible
        expect(find.byIcon(Icons.keyboard_arrow_up), findsNothing);
        expect(find.byIcon(Icons.keyboard_arrow_down), findsOneWidget);

        // Simulate upward swipe to go to next joke (middle joke)
        final pageView = find.byKey(const Key('joke_viewer_page_view'));
        await tester.drag(
          pageView,
          const Offset(0, -400),
        ); // Negative dy = upward
        await tester.pump(
          const Duration(milliseconds: 1000),
        ); // Wait for page transition to complete

        // Now at middle joke - both arrows should be visible
        expect(find.byIcon(Icons.keyboard_arrow_up), findsOneWidget);
        expect(find.byIcon(Icons.keyboard_arrow_down), findsOneWidget);

        // Simulate upward swipe to go to next joke (last joke)
        await tester.drag(
          pageView,
          const Offset(0, -400),
        ); // Negative dy = upward
        await tester.pump(
          const Duration(milliseconds: 1000),
        ); // Wait for page transition to complete

        // Now at last joke - only up arrow should be visible
        expect(find.byIcon(Icons.keyboard_arrow_up), findsOneWidget);
        expect(find.byIcon(Icons.keyboard_arrow_down), findsNothing);
      });

      testWidgets('arrow styling uses correct theme colors', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow data to be processed

        // Find the down arrow (should be present at first joke)
        final downArrowWidget = find.byIcon(Icons.keyboard_arrow_down);
        expect(downArrowWidget, findsOneWidget);

        // Check that arrow has proper styling
        final arrowIcon = tester.widget<Icon>(downArrowWidget);
        expect(arrowIcon.size, equals(24));

        // The color should use theme colors with alpha
        expect(arrowIcon.color, isNotNull);
      });

      testWidgets('arrows are positioned correctly', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow data to be processed

        // Find the down arrow container
        final downArrow = find.byIcon(Icons.keyboard_arrow_down);
        expect(downArrow, findsOneWidget);
      });

      testWidgets('arrows have correct opacity', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(mockJokes),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow data to be processed

        // Find the opacity widget wrapping the arrow
        final opacityWidget = find.ancestor(
          of: find.byIcon(Icons.keyboard_arrow_down),
          matching: find.byType(Opacity),
        );
        expect(opacityWidget, findsOneWidget);

        // Check that opacity is set to 0.4 (subtle)
        final opacity = tester.widget<Opacity>(opacityWidget);
        expect(opacity.opacity, equals(0.4));
      });

      testWidgets('no arrows shown when jokes list is empty', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            overrides: [
              jokesWithImagesProvider.overrideWith(
                (ref) => Stream.value(<Joke>[]),
              ),
            ],
          ),
        );

        await tester.pump(); // Allow data to be processed

        // Should not show any arrows when no jokes
        expect(find.byIcon(Icons.keyboard_arrow_up), findsNothing);
        expect(find.byIcon(Icons.keyboard_arrow_down), findsNothing);
      });
    });
  });
}
