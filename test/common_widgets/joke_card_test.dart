import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/common_widgets/joke_text_card.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

import '../test_helpers/firebase_mocks.dart';

void main() {
  group('JokeCard Widget Tests', () {
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

    group('State Determination', () {
      testWidgets('should show JokeTextCard when no images are available', (
        tester,
      ) async {
        // arrange
        const joke = Joke(
          id: '1',
          setupText: 'Why did the chicken cross the road?',
          punchlineText: 'To get to the other side!',
          setupImageUrl: null,
          punchlineImageUrl: null,
        );

        const widget = JokeCard(joke: joke, index: 0, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byType(JokeTextCard), findsOneWidget);
        expect(find.byType(JokeImageCarousel), findsNothing);
      });

      testWidgets('should show JokeTextCard when images are empty strings', (
        tester,
      ) async {
        // arrange
        const joke = Joke(
          id: '1',
          setupText: 'Why did the chicken cross the road?',
          punchlineText: 'To get to the other side!',
          setupImageUrl: '',
          punchlineImageUrl: '',
        );

        const widget = JokeCard(joke: joke, index: 0, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byType(JokeTextCard), findsOneWidget);
        expect(find.byType(JokeImageCarousel), findsNothing);
      });

      testWidgets(
        'should show JokeTextCard when only setup image is available',
        (tester) async {
          // arrange
          const joke = Joke(
            id: '1',
            setupText: 'Why did the chicken cross the road?',
            punchlineText: 'To get to the other side!',
            setupImageUrl: 'https://example.com/setup.jpg',
            punchlineImageUrl: null,
          );

          const widget = JokeCard(joke: joke, index: 0, jokeContext: 'test');

          // act
          await tester.pumpWidget(createTestWidget(child: widget));

          // assert
          expect(find.byType(JokeTextCard), findsOneWidget);
          expect(find.byType(JokeImageCarousel), findsNothing);
        },
      );

      testWidgets(
        'should show JokeTextCard when only punchline image is available',
        (tester) async {
          // arrange
          const joke = Joke(
            id: '1',
            setupText: 'Why did the chicken cross the road?',
            punchlineText: 'To get to the other side!',
            setupImageUrl: null,
            punchlineImageUrl: 'https://example.com/punchline.jpg',
          );

          const widget = JokeCard(joke: joke, index: 0, jokeContext: 'test');

          // act
          await tester.pumpWidget(createTestWidget(child: widget));

          // assert
          expect(find.byType(JokeTextCard), findsOneWidget);
          expect(find.byType(JokeImageCarousel), findsNothing);
        },
      );

      testWidgets(
        'should show JokeImageCarousel when both images are available',
        (tester) async {
          // arrange
          const joke = Joke(
            id: '1',
            setupText: 'Why did the chicken cross the road?',
            punchlineText: 'To get to the other side!',
            setupImageUrl: 'https://example.com/setup.jpg',
            punchlineImageUrl: 'https://example.com/punchline.jpg',
          );

          const widget = JokeCard(joke: joke, index: 0, jokeContext: 'test');

          // act
          await tester.pumpWidget(createTestWidget(child: widget));

          // assert
          expect(find.byType(JokeImageCarousel), findsOneWidget);
          expect(find.byType(JokeTextCard), findsNothing);
        },
      );
    });

    group('Property Passing', () {
      testWidgets('should pass all properties to JokeTextCard', (tester) async {
        // arrange
        const joke = Joke(
          id: '1',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
        );

        bool setupTapCalled = false;
        final widget = JokeCard(
          joke: joke,
          index: 5,
          onSetupTap: () => setupTapCalled = true,
          jokeContext: 'test',
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        final jokeTextCard = tester.widget<JokeTextCard>(
          find.byType(JokeTextCard),
        );
        expect(jokeTextCard.joke, equals(joke));
        expect(jokeTextCard.index, equals(5));
        expect(jokeTextCard.onTap, isNotNull);
      });

      testWidgets('should pass properties to JokeImageCarousel', (
        tester,
      ) async {
        // arrange
        const joke = Joke(
          id: '1',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
        );

        bool setupTapCalled = false;
        bool punchlineTapCalled = false;
        final widget = JokeCard(
          joke: joke,
          index: 3,
          onSetupTap: () => setupTapCalled = true,
          onPunchlineTap: () => punchlineTapCalled = true,
          jokeContext: 'test',
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        final jokeImageCarousel = tester.widget<JokeImageCarousel>(
          find.byType(JokeImageCarousel),
        );
        expect(jokeImageCarousel.joke, equals(joke));
        expect(jokeImageCarousel.index, equals(3));
        expect(jokeImageCarousel.onSetupTap, isNotNull);
        expect(jokeImageCarousel.onPunchlineTap, isNotNull);
      });

      testWidgets('should pass isAdminMode to JokeImageCarousel when enabled', (
        tester,
      ) async {
        // arrange
        const joke = Joke(
          id: '1',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
        );

        const widget = JokeCard(
          joke: joke,
          index: 3,
          isAdminMode: true,
          jokeContext: 'test',
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        final jokeImageCarousel = tester.widget<JokeImageCarousel>(
          find.byType(JokeImageCarousel),
        );
        expect(jokeImageCarousel.isAdminMode, isTrue);
      });
    });

    group('Edge Cases', () {
      testWidgets('should handle joke without index', (tester) async {
        // arrange
        const joke = Joke(
          id: '1',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
        );

        const widget = JokeCard(joke: joke, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byType(JokeTextCard), findsOneWidget);
        final jokeTextCard = tester.widget<JokeTextCard>(
          find.byType(JokeTextCard),
        );
        expect(jokeTextCard.index, isNull);
      });

      testWidgets('should handle joke without onSetupTap callback', (
        tester,
      ) async {
        // arrange
        const joke = Joke(
          id: '1',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
        );

        const widget = JokeCard(joke: joke, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byType(JokeTextCard), findsOneWidget);
        final jokeTextCard = tester.widget<JokeTextCard>(
          find.byType(JokeTextCard),
        );
        expect(jokeTextCard.onTap, isNull);
      });

      testWidgets('should use default isAdminMode value', (tester) async {
        // arrange
        const joke = Joke(
          id: '1',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
        );

        const widget = JokeCard(joke: joke, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        final jokeImageCarousel = tester.widget<JokeImageCarousel>(
          find.byType(JokeImageCarousel),
        );
        expect(jokeImageCarousel.isAdminMode, isFalse); // default value
      });
    });

    group('Image URL Validation', () {
      testWidgets('should treat whitespace-only URLs as empty', (tester) async {
        // arrange
        const joke = Joke(
          id: '1',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageUrl: '   ',
          punchlineImageUrl: '\t\n  ',
        );

        const widget = JokeCard(joke: joke, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byType(JokeTextCard), findsOneWidget);
        expect(find.byType(JokeImageCarousel), findsNothing);
      });

      testWidgets('should handle mixed null and empty string cases', (
        tester,
      ) async {
        // arrange
        const joke = Joke(
          id: '1',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageUrl: '',
          punchlineImageUrl: null,
        );

        const widget = JokeCard(joke: joke, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byType(JokeTextCard), findsOneWidget);
        expect(find.byType(JokeImageCarousel), findsNothing);
      });
    });
  });
}
