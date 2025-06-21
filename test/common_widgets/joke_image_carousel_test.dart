import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

import '../test_helpers/firebase_mocks.dart';

void main() {
  group('JokeImageCarousel Widget Tests', () {
    Widget createTestWidget({
      required Widget child,
      List<Override> additionalOverrides = const [],
    }) {
      return ProviderScope(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(
          additionalOverrides: additionalOverrides,
        ),
        child: MaterialApp(theme: lightTheme, home: Scaffold(body: child)),
      );
    }

    const testJoke = Joke(
      id: '1',
      setupText: 'Test setup',
      punchlineText: 'Test punchline',
      setupImageUrl: 'https://example.com/setup.jpg',
      punchlineImageUrl: 'https://example.com/punchline.jpg',
    );

    group('Basic Functionality', () {
      testWidgets('should display image carousel with page indicators', (
        tester,
      ) async {
        // arrange
        const widget = JokeImageCarousel(joke: testJoke);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump(); // Allow for post-frame callbacks

        // assert
        expect(find.byType(PageView), findsOneWidget);
        expect(find.byType(Card), findsOneWidget);
        
        // Check for page indicators (should be 2 Container widgets for indicators)
        final pageIndicators = find.byWidgetPredicate(
          (widget) => widget is AnimatedContainer && 
                     widget.decoration is BoxDecoration &&
                     (widget.decoration as BoxDecoration).borderRadius == BorderRadius.circular(4),
        );
        expect(pageIndicators, findsNWidgets(2));
      });

      testWidgets(
        'should not show regenerate button when isAdminMode is false',
        (tester) async {
          // arrange
          const widget = JokeImageCarousel(joke: testJoke, isAdminMode: false);

          // act
          await tester.pumpWidget(createTestWidget(child: widget));
          await tester.pump();

          // assert
          expect(find.text('Regenerate Images'), findsNothing);
          expect(find.byIcon(Icons.refresh), findsNothing);
        },
      );

      testWidgets('should show regenerate button when isAdminMode is true', (
        tester,
      ) async {
        // arrange
        const widget = JokeImageCarousel(joke: testJoke, isAdminMode: true);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();
        await tester.pump(); // Allow for provider state updates

        // assert
        expect(find.textContaining('Regenerate'), findsOneWidget);
        expect(find.byIcon(Icons.refresh), findsOneWidget);
      });
    });

    group('Admin Mode Functionality', () {
      testWidgets('should have regenerate button that can be tapped', (
        tester,
      ) async {
        // arrange
        const widget = JokeImageCarousel(joke: testJoke, isAdminMode: true);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();
        await tester.pump(); // Allow for provider state updates

        // Find the button by its icon instead since ElevatedButton.icon has a different structure
        final refreshIcon = find.byIcon(Icons.refresh);
        expect(refreshIcon, findsOneWidget);

        // We can also verify the text exists somewhere
        expect(find.textContaining('Regenerate'), findsOneWidget);

        // Tap the button (tap on the icon which is part of the button)
        await tester.tap(refreshIcon);
        await tester.pump();

        // assert - icon should still be there after tap
        expect(refreshIcon, findsOneWidget);
      });

      testWidgets('should not show error container when there is no error', (
        tester,
      ) async {
        // arrange
        const widget = JokeImageCarousel(joke: testJoke, isAdminMode: true);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();
        await tester.pump(); // Allow for provider state updates

        // assert
        expect(find.byIcon(Icons.error_outline), findsNothing);
      });
    });

    group('Default Parameters', () {
      testWidgets('should use default isAdminMode value of false', (
        tester,
      ) async {
        // arrange
        const widget = JokeImageCarousel(joke: testJoke);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // assert
        expect(find.text('Regenerate Images'), findsNothing);
      });
    });

    group('Image Preloading', () {
      testWidgets(
        'should handle valid URLs during preloading without errors',
        (tester) async {
          // arrange
          const setupUrl = 'https://example.com/setup.jpg';
          const punchlineUrl = 'https://example.com/punchline.jpg';

          const jokeWithValidUrls = Joke(
            id: '1',
            setupText: 'Test setup',
            punchlineText: 'Test punchline',
            setupImageUrl: setupUrl,
            punchlineImageUrl: punchlineUrl,
          );

          const widget = JokeImageCarousel(joke: jokeWithValidUrls);

          // act
          await tester.pumpWidget(createTestWidget(child: widget));
          await tester.pump(); // Initial pump
          await tester.pump(); // Allow post-frame callback to execute

          // assert
          expect(tester.takeException(), isNull);
          expect(find.byType(PageView), findsOneWidget);
        },
      );

      testWidgets(
        'should handle null image URLs gracefully during preloading',
        (tester) async {
          // arrange
          const jokeWithNullUrls = Joke(
            id: '1',
            setupText: 'Test setup',
            punchlineText: 'Test punchline',
            setupImageUrl: null,
            punchlineImageUrl: null,
          );

          const widget = JokeImageCarousel(joke: jokeWithNullUrls);

          // act
          await tester.pumpWidget(createTestWidget(child: widget));
          await tester.pump();
          await tester.pump();

          // assert
          expect(tester.takeException(), isNull);
          expect(find.byType(PageView), findsOneWidget);
        },
      );

      testWidgets(
        'should handle invalid image URLs gracefully during preloading',
        (tester) async {
          // arrange
          const invalidSetupUrl = 'invalid-setup-url';
          const invalidPunchlineUrl = 'invalid-punchline-url';

          const jokeWithInvalidUrls = Joke(
            id: '1',
            setupText: 'Test setup',
            punchlineText: 'Test punchline',
            setupImageUrl: invalidSetupUrl,
            punchlineImageUrl: invalidPunchlineUrl,
          );

          const widget = JokeImageCarousel(joke: jokeWithInvalidUrls);

          // act
          await tester.pumpWidget(createTestWidget(child: widget));
          await tester.pump();
          await tester.pump();

          // assert
          expect(tester.takeException(), isNull);
          expect(find.byType(PageView), findsOneWidget);
        },
      );

      testWidgets(
        'should handle mixed valid and invalid URLs during preloading',
        (tester) async {
          // arrange
          const validSetupUrl = 'https://example.com/setup.jpg';
          const invalidPunchlineUrl = 'invalid-punchline-url';

          const jokeWithMixedUrls = Joke(
            id: '1',
            setupText: 'Test setup',
            punchlineText: 'Test punchline',
            setupImageUrl: validSetupUrl,
            punchlineImageUrl: invalidPunchlineUrl,
          );

          const widget = JokeImageCarousel(joke: jokeWithMixedUrls);

          // act
          await tester.pumpWidget(createTestWidget(child: widget));
          await tester.pump();
          await tester.pump();

          // assert
          expect(tester.takeException(), isNull);
          expect(find.byType(PageView), findsOneWidget);
        },
      );
    });

    group('Tap Behavior', () {
      testWidgets(
        'should call onSetupTap when setup image is tapped and callback is provided',
        (tester) async {
          // arrange
          bool setupTapCalled = false;
          final widget = JokeImageCarousel(
            joke: testJoke,
            onSetupTap: () => setupTapCalled = true,
          );

          // act
          await tester.pumpWidget(createTestWidget(child: widget));
          await tester.pump();

          // Tap on the GestureDetector (which covers the entire carousel)
          await tester.tap(find.byType(GestureDetector));
          await tester.pump();

          // assert
          expect(setupTapCalled, isTrue);
        },
      );

      testWidgets(
        'should call onPunchlineTap when punchline image is tapped and callback is provided',
        (tester) async {
          // arrange
          bool punchlineTapCalled = false;
          final widget = JokeImageCarousel(
            joke: testJoke,
            onPunchlineTap: () => punchlineTapCalled = true,
          );

          // act
          await tester.pumpWidget(createTestWidget(child: widget));
          await tester.pump();

          // First tap should navigate to punchline (default behavior)
          await tester.tap(find.byType(GestureDetector));
          await tester.pump();
          // Use pump with specific duration instead of pumpAndSettle to avoid timeout
          await tester.pump(const Duration(milliseconds: 400));

          // Second tap should call the punchline callback
          await tester.tap(find.byType(GestureDetector));
          await tester.pump();

          // assert
          expect(punchlineTapCalled, isTrue);
        },
      );

      testWidgets('should handle taps when no callbacks are provided', (
        tester,
      ) async {
        // arrange
        const widget = JokeImageCarousel(joke: testJoke);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // First tap should not cause any exceptions (should navigate to punchline)
        await tester.tap(find.byType(GestureDetector));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));

        // Second tap should also not cause exceptions (should navigate back to setup)
        await tester.tap(find.byType(GestureDetector));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));

        // assert - no exceptions
        expect(tester.takeException(), isNull);
        expect(find.byType(PageView), findsOneWidget);
      });

      testWidgets('should navigate between pages with default tap behavior', (
        tester,
      ) async {
        // arrange
        const widget = JokeImageCarousel(joke: testJoke);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));
        await tester.pump();

        // Tap to go to punchline
        await tester.tap(find.byType(GestureDetector));
        await tester.pump(const Duration(milliseconds: 400));

        // Tap again to go back to setup
        await tester.tap(find.byType(GestureDetector));
        await tester.pump(const Duration(milliseconds: 400));

        // assert - widget should still be functioning correctly
        expect(find.byType(PageView), findsOneWidget);
        expect(tester.takeException(), isNull);
      });
    });
  });
}
