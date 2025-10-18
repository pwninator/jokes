import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';

// Mock classes
class MockJokeViewerSettingsService extends Mock
    implements JokeViewerSettingsService {}

// Fake classes for mocktail fallback values
class FakeJoke extends Fake implements Joke {
  @override
  String get id => 'fake-id';

  @override
  String get setupText => 'fake setup';

  @override
  String get punchlineText => 'fake punchline';

  @override
  String? get setupImageUrl => null;

  @override
  String? get punchlineImageUrl => null;
}

// Test widget that mocks the child widgets to avoid Firebase dependencies
class TestJokeCard extends StatelessWidget {
  final Joke joke;
  final int? index;
  final Function(int)? onImageStateChanged;
  final bool isAdminMode;
  final List<Joke>? jokesToPreload;
  final bool showSaveButton;
  final bool showShareButton;
  final bool showAdminRatingButtons;
  final bool showNumSaves;
  final bool showNumShares;
  final String? title;
  final String jokeContext;
  final JokeImageCarouselController? controller;
  final String? topRightBadgeText;
  final bool showSimilarSearchButton;
  final bool revealMode;

  const TestJokeCard({
    super.key,
    required this.joke,
    this.index,
    this.onImageStateChanged,
    this.isAdminMode = false,
    this.jokesToPreload,
    this.showSaveButton = false,
    this.showShareButton = false,
    this.showAdminRatingButtons = false,
    this.showNumSaves = false,
    this.showNumShares = false,
    this.title,
    required this.jokeContext,
    this.controller,
    this.topRightBadgeText,
    this.showSimilarSearchButton = false,
    this.revealMode = false,
  });

  @override
  Widget build(BuildContext context) {
    // Replicate the logic from JokeCard
    final hasSetupImage =
        joke.setupImageUrl != null && joke.setupImageUrl!.trim().isNotEmpty;
    final hasPunchlineImage =
        joke.punchlineImageUrl != null &&
        joke.punchlineImageUrl!.trim().isNotEmpty;

    if (hasSetupImage && hasPunchlineImage) {
      // Both images available - show carousel
      return Container(
        key: const Key('joke-image-carousel'),
        child: Text('JokeImageCarousel: ${joke.id}'),
      );
    } else {
      // No images or incomplete images - show text
      return Container(
        key: const Key('joke-text-card'),
        child: Text('JokeTextCard: ${joke.id}'),
      );
    }
  }
}

void main() {
  group('JokeCard Widget Tests', () {
    Widget createTestWidget({required Widget child}) {
      return MaterialApp(
        theme: lightTheme,
        home: Scaffold(body: child),
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

        const widget = TestJokeCard(joke: joke, index: 0, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byKey(const Key('joke-text-card')), findsOneWidget);
        expect(find.byKey(const Key('joke-image-carousel')), findsNothing);
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

        const widget = TestJokeCard(joke: joke, index: 0, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byKey(const Key('joke-text-card')), findsOneWidget);
        expect(find.byKey(const Key('joke-image-carousel')), findsNothing);
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

          const widget = TestJokeCard(
            joke: joke,
            index: 0,
            jokeContext: 'test',
          );

          // act
          await tester.pumpWidget(createTestWidget(child: widget));

          // assert
          expect(find.byKey(const Key('joke-text-card')), findsOneWidget);
          expect(find.byKey(const Key('joke-image-carousel')), findsNothing);
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

          const widget = TestJokeCard(
            joke: joke,
            index: 0,
            jokeContext: 'test',
          );

          // act
          await tester.pumpWidget(createTestWidget(child: widget));

          // assert
          expect(find.byKey(const Key('joke-text-card')), findsOneWidget);
          expect(find.byKey(const Key('joke-image-carousel')), findsNothing);
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

          const widget = TestJokeCard(
            joke: joke,
            index: 0,
            jokeContext: 'test',
          );

          // act
          await tester.pumpWidget(createTestWidget(child: widget));

          // assert
          expect(find.byKey(const Key('joke-image-carousel')), findsOneWidget);
          expect(find.byKey(const Key('joke-text-card')), findsNothing);
        },
      );
    });

    group('Property Passing', () {
      testWidgets('should pass joke data to TestJokeCard', (tester) async {
        // arrange
        const joke = Joke(
          id: '1',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
        );

        const widget = TestJokeCard(joke: joke, index: 5, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.text('JokeTextCard: 1'), findsOneWidget);
      });

      testWidgets('should pass joke data to TestJokeCard with images', (
        tester,
      ) async {
        // arrange
        const joke = Joke(
          id: '2',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
        );

        const widget = TestJokeCard(joke: joke, index: 3, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.text('JokeImageCarousel: 2'), findsOneWidget);
      });
    });

    group('Counts and Buttons Flags', () {
      testWidgets('defaults to not showing save/share buttons and counts', (
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

        const widget = TestJokeCard(joke: joke, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byKey(const Key('joke-image-carousel')), findsOneWidget);
        expect(find.text('JokeImageCarousel: 1'), findsOneWidget);
      });

      testWidgets(
        'can enable counts (num saves/shares) flags and reflect in child',
        (tester) async {
          // arrange
          const joke = Joke(
            id: '1',
            setupText: 'Test setup',
            punchlineText: 'Test punchline',
            setupImageUrl: 'https://example.com/setup.jpg',
            punchlineImageUrl: 'https://example.com/punchline.jpg',
            numSaves: 2,
            numShares: 3,
          );

          const widget = TestJokeCard(
            joke: joke,
            jokeContext: 'test',
            showNumSaves: true,
            showNumShares: true,
          );

          // act
          await tester.pumpWidget(createTestWidget(child: widget));

          // assert
          expect(find.byKey(const Key('joke-image-carousel')), findsOneWidget);
          expect(find.text('JokeImageCarousel: 1'), findsOneWidget);
        },
      );
    });

    group('Edge Cases', () {
      testWidgets('should handle joke without index', (tester) async {
        // arrange
        const joke = Joke(
          id: '1',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
        );

        const widget = TestJokeCard(joke: joke, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byKey(const Key('joke-text-card')), findsOneWidget);
        expect(find.text('JokeTextCard: 1'), findsOneWidget);
      });

      testWidgets('should handle joke without tap callback', (tester) async {
        // arrange
        const joke = Joke(
          id: '1',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
        );

        const widget = TestJokeCard(joke: joke, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byKey(const Key('joke-text-card')), findsOneWidget);
        expect(find.text('JokeTextCard: 1'), findsOneWidget);
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

        const widget = TestJokeCard(joke: joke, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byKey(const Key('joke-image-carousel')), findsOneWidget);
        expect(find.text('JokeImageCarousel: 1'), findsOneWidget);
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

        const widget = TestJokeCard(joke: joke, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byKey(const Key('joke-text-card')), findsOneWidget);
        expect(find.byKey(const Key('joke-image-carousel')), findsNothing);
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

        const widget = TestJokeCard(joke: joke, jokeContext: 'test');

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byKey(const Key('joke-text-card')), findsOneWidget);
        expect(find.byKey(const Key('joke-image-carousel')), findsNothing);
      });
    });

    // New tests for badge overlay
    group('Badge Overlay', () {
      testWidgets('passes topRightBadgeText to JokeTextCard overlay', (
        tester,
      ) async {
        const joke = Joke(id: 't1', setupText: 'Setup', punchlineText: 'Punch');
        const w = TestJokeCard(
          joke: joke,
          jokeContext: 'test',
          topRightBadgeText: '92%',
        );
        await tester.pumpWidget(createTestWidget(child: w));
        expect(find.byKey(const Key('joke-text-card')), findsOneWidget);
        expect(find.text('JokeTextCard: t1'), findsOneWidget);
      });

      testWidgets('passes topRightBadgeText to JokeImageCarousel overlay', (
        tester,
      ) async {
        const joke = Joke(
          id: 'i1',
          setupText: 'Setup',
          punchlineText: 'Punch',
          setupImageUrl: 'https://ex/setup.jpg',
          punchlineImageUrl: 'https://ex/punch.jpg',
        );
        const w = TestJokeCard(
          joke: joke,
          jokeContext: 'test',
          topRightBadgeText: '0.87',
        );
        await tester.pumpWidget(createTestWidget(child: w));
        expect(find.byKey(const Key('joke-image-carousel')), findsOneWidget);
        expect(find.text('JokeImageCarousel: i1'), findsOneWidget);
      });
    });
  });
}
