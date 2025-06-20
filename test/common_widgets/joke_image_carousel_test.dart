import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mockito/mockito.dart';
import 'package:mockito/annotations.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

// Generate mocks
@GenerateMocks([JokeCloudFunctionService])
import 'joke_image_carousel_test.mocks.dart';

void main() {
  group('JokeImageCarousel Widget Tests', () {
    late MockJokeCloudFunctionService mockCloudFunctionService;

    setUp(() {
      mockCloudFunctionService = MockJokeCloudFunctionService();
    });

    Widget createTestWidget({
      required Widget child,
      List<Override> overrides = const [],
    }) {
      return ProviderScope(
        overrides: [
          jokeCloudFunctionServiceProvider.overrideWithValue(mockCloudFunctionService),
          ...overrides,
        ],
        child: MaterialApp(
          theme: lightTheme,
          home: Scaffold(body: child),
        ),
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
      testWidgets('should display image carousel with page indicators', (tester) async {
        // arrange
        const widget = JokeImageCarousel(joke: testJoke);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byType(PageView), findsOneWidget);
        expect(find.byType(Container), findsWidgets); // Page indicators
      });

      testWidgets('should not show regenerate button when isAdminMode is false', (tester) async {
        // arrange
        const widget = JokeImageCarousel(
          joke: testJoke,
          isAdminMode: false,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.text('Regenerate Images'), findsNothing);
        expect(find.byIcon(Icons.refresh), findsNothing);
      });

      testWidgets('should show regenerate button when isAdminMode is true', (tester) async {
        // arrange
        const widget = JokeImageCarousel(
          joke: testJoke,
          isAdminMode: true,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.text('Regenerate Images'), findsOneWidget);
        expect(find.byIcon(Icons.refresh), findsOneWidget);
      });
    });

    group('Admin Mode Functionality', () {


             testWidgets('should have regenerate button that can be tapped', (tester) async {
         // arrange
         const widget = JokeImageCarousel(
           joke: testJoke,
           isAdminMode: true,
         );

         // act
         await tester.pumpWidget(createTestWidget(child: widget));
         
         // Find and tap the regenerate button
         final regenerateButton = find.text('Regenerate Images');
         expect(regenerateButton, findsOneWidget);
         
         await tester.tap(regenerateButton);
         await tester.pump();

         // assert - button should still be there after tap
         expect(regenerateButton, findsOneWidget);
       });

      testWidgets('should not show error container when there is no error', (tester) async {
        // arrange
        const widget = JokeImageCarousel(
          joke: testJoke,
          isAdminMode: true,
        );

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.byIcon(Icons.error_outline), findsNothing);
      });


    });

    group('Default Parameters', () {
      testWidgets('should use default isAdminMode value of false', (tester) async {
        // arrange
        const widget = JokeImageCarousel(joke: testJoke);

        // act
        await tester.pumpWidget(createTestWidget(child: widget));

        // assert
        expect(find.text('Regenerate Images'), findsNothing);
      });
    });
  });
} 