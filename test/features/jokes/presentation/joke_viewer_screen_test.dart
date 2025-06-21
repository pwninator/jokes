import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_viewer_screen.dart';

import '../../../test_helpers/firebase_mocks.dart';

void main() {
  group('JokeViewerScreen', () {
    // Simple test data
    final testJoke = const Joke(
      id: '1',
      setupText: 'Test setup',
      punchlineText: 'Test punchline',
      setupImageUrl: 'https://example.com/setup.jpg',
      punchlineImageUrl: 'https://example.com/punchline.jpg',
    );

    final testJokes = [
      testJoke,
      const Joke(
        id: '2',
        setupText: 'Setup 2',
        punchlineText: 'Punchline 2',
        setupImageUrl: 'https://example.com/setup2.jpg',
        punchlineImageUrl: 'https://example.com/punchline2.jpg',
      ),
    ];

    Widget createTestWidget({
      required Stream<List<Joke>> jokesStream,
      Key? key,
    }) {
      return ProviderScope(
        key: key, // Add unique key to force recreation
        overrides: [
          ...FirebaseMocks.getFirebaseProviderOverrides(),
          jokesWithImagesProvider.overrideWith((ref) => jokesStream),
        ],
        child: MaterialApp(theme: lightTheme, home: const JokeViewerScreen()),
      );
    }

    group('Widget Structure', () {
      testWidgets('should be a ConsumerStatefulWidget', (tester) async {
        const widget = JokeViewerScreen();
        expect(widget, isA<ConsumerStatefulWidget>());
      });

      testWidgets('should have title property', (tester) async {
        const widget = JokeViewerScreen();
        expect(widget.title, equals('Jokes'));
      });

      testWidgets('should create state without errors', (tester) async {
        const widget = JokeViewerScreen();
        final state = widget.createState();
        expect(state, isNotNull);
        expect(state, isA<ConsumerState>());
      });

      testWidgets('should have correct title property', (tester) async {
        const widget = JokeViewerScreen();
        expect(widget.title, isA<String>());
        expect(widget.title.isNotEmpty, isTrue);
        expect(widget.title, equals('Jokes'));
      });
    });

    group('Widget Properties', () {
      testWidgets('should have null key by default', (tester) async {
        const widget = JokeViewerScreen();
        expect(widget.key, isNull);
      });

      testWidgets('should accept custom key', (tester) async {
        const key = Key('test_key');
        const widget = JokeViewerScreen(key: key);
        expect(widget.key, equals(key));
      });

      testWidgets('should be const constructible', (tester) async {
        // This test ensures the widget can be created as const
        const widget1 = JokeViewerScreen();
        const widget2 = JokeViewerScreen();

        // Both widgets should be created without issues
        expect(widget1, isNotNull);
        expect(widget2, isNotNull);
        expect(widget1.title, equals(widget2.title));
      });
    });

    group('Type Safety', () {
      testWidgets('should maintain type consistency', (tester) async {
        const widget = JokeViewerScreen();

        // Test type inheritance
        expect(widget, isA<Widget>());
        expect(widget, isA<StatefulWidget>());
        expect(widget, isA<ConsumerStatefulWidget>());

        // Test that widget can be instantiated
      });

      testWidgets('should have consistent runtime type', (tester) async {
        const widget1 = JokeViewerScreen();
        const widget2 = JokeViewerScreen();

        expect(widget1.runtimeType, equals(widget2.runtimeType));
        expect(widget1.runtimeType.toString(), equals('JokeViewerScreen'));
      });
    });

    group('Documentation and Coverage', () {
      testWidgets('should exist and be importable', (tester) async {
        // This test ensures the widget exists and can be imported
        expect(JokeViewerScreen, isNotNull);
        expect(JokeViewerScreen.new, isNotNull);
      });

      testWidgets('should have accessible constructor', (tester) async {
        // Test that widget can be constructed with various parameters
        expect(() => const JokeViewerScreen(), returnsNormally);
        expect(() => const JokeViewerScreen(key: Key('test')), returnsNormally);
      });

      testWidgets('should satisfy basic widget contract', (tester) async {
        const widget = JokeViewerScreen();

        // Widget should have basic required properties
        expect(widget.title, isA<String>());
        expect(widget.key, isA<Key?>());

        // Should be able to create state
        final state = widget.createState();
        expect(state, isNotNull);
      });
    });

    group('Edge Cases', () {
      testWidgets('should handle multiple instantiations', (tester) async {
        final widgets = List.generate(
          10,
          (i) => JokeViewerScreen(key: Key('$i')),
        );

        for (final widget in widgets) {
          expect(widget, isNotNull);
          expect(widget.title, equals('Jokes'));
          expect(widget.key, isNotNull);
        }
      });

      testWidgets('should maintain immutability', (tester) async {
        const widget1 = JokeViewerScreen();
        const widget2 = JokeViewerScreen();

        // Properties should be consistent
        expect(widget1.title, equals(widget2.title));
        expect(widget1.runtimeType, equals(widget2.runtimeType));
      });
    });

    group('Basic Structure', () {
      testWidgets('should build without errors', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            jokesStream: Stream.value(<Joke>[]),
            key: const Key('build_test'),
          ),
        );
        await tester.pump();

        expect(find.byType(JokeViewerScreen), findsOneWidget);
        expect(find.byType(Scaffold), findsOneWidget);
        expect(find.byType(AppBar), findsOneWidget);
        expect(find.text('Jokes'), findsOneWidget);
      });
    });

    group('Loading and Empty States', () {
      testWidgets('should show loading indicator initially', (tester) async {
        final controller = StreamController<List<Joke>>();

        await tester.pumpWidget(
          createTestWidget(
            jokesStream: controller.stream,
            key: const Key('loading_test'),
          ),
        );
        await tester.pump();

        expect(find.byType(CircularProgressIndicator), findsOneWidget);

        await controller.close();
      });

      testWidgets('should show empty message when no jokes', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            jokesStream: Stream.value(<Joke>[]),
            key: const Key('empty_message_test'),
          ),
        );
        await tester.pump();

        expect(find.text('No jokes found! Try adding some.'), findsOneWidget);
        expect(find.byType(CircularProgressIndicator), findsNothing);
      });

      testWidgets('should show error message on stream error', (tester) async {
        const errorMessage = 'Test error';
        await tester.pumpWidget(
          createTestWidget(
            jokesStream: Stream.error(errorMessage),
            key: const Key('error_message_test'),
          ),
        );
        await tester.pump();

        expect(
          find.textContaining('Error loading jokes: $errorMessage'),
          findsOneWidget,
        );
        expect(find.byType(CircularProgressIndicator), findsNothing);
      });
    });

    group('Jokes Display', () {
      testWidgets('should display single joke without page indicator', (
        tester,
      ) async {
        await tester.pumpWidget(
          createTestWidget(
            jokesStream: Stream.value([testJoke]),
            key: const Key('single_joke_test'),
          ),
        );

        await tester.pump();

        expect(find.byType(JokeCard), findsOneWidget);
        expect(find.textContaining('of'), findsNothing);
      });

      testWidgets('should display multiple jokes with page indicator', (
        tester,
      ) async {
        await tester.pumpWidget(
          createTestWidget(
            jokesStream: Stream.value(testJokes),
            key: const Key('multiple_jokes_test'),
          ),
        );

        await tester.pump();

        expect(find.byType(JokeCard), findsOneWidget);
        expect(find.textContaining('1 of 2'), findsOneWidget);
      });
    });

    group('Navigation Callbacks', () {
      testWidgets('should provide onPunchlineTap callback to JokeCard', (
        tester,
      ) async {
        await tester.pumpWidget(
          createTestWidget(
            jokesStream: Stream.value(testJokes),
            key: const Key('punchline_callback_test'),
          ),
        );
        await tester.pump();

        final jokeCard = tester.widget<JokeCard>(find.byType(JokeCard));
        expect(jokeCard.onPunchlineTap, isNotNull);
        expect(jokeCard.onSetupTap, isNull);
        expect(jokeCard.isAdminMode, isFalse);
      });

      testWidgets('should call onPunchlineTap without throwing', (
        tester,
      ) async {
        await tester.pumpWidget(
          createTestWidget(
            jokesStream: Stream.value(testJokes),
            key: const Key('punchline_call_test'),
          ),
        );
        await tester.pump();

        final jokeCard = tester.widget<JokeCard>(find.byType(JokeCard));

        // Should not throw when called
        expect(() => jokeCard.onPunchlineTap!(), returnsNormally);
        await tester.pump();

        // Widget should still be functional
        expect(find.byType(JokeCard), findsOneWidget);
        expect(tester.takeException(), isNull);
      });
    });

    group('Stream State Changes', () {
      testWidgets('should handle stream state transitions', (tester) async {
        final controller = StreamController<List<Joke>>();

        await tester.pumpWidget(
          createTestWidget(
            jokesStream: controller.stream,
            key: const Key('stream_transitions_test'),
          ),
        );
        await tester.pump();

        // Initially loading
        expect(find.byType(CircularProgressIndicator), findsOneWidget);

        // Add empty list
        controller.add(<Joke>[]);
        await tester.pump();
        expect(find.text('No jokes found! Try adding some.'), findsOneWidget);
        expect(find.byType(CircularProgressIndicator), findsNothing);

        // Add jokes
        controller.add(testJokes);
        await tester.pump();
        expect(find.byType(JokeCard), findsOneWidget);
        expect(find.textContaining('1 of 2'), findsOneWidget);

        await controller.close();
      });
    });

    group('Widget Lifecycle', () {
      testWidgets('should handle disposal correctly', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            jokesStream: Stream.value(testJokes),
            key: const Key('disposal_test'),
          ),
        );
        await tester.pump();

        // Navigate away to trigger disposal
        await tester.pumpWidget(const MaterialApp(home: Text('Other Screen')));

        // Should not throw exceptions
        expect(tester.takeException(), isNull);
      });

      testWidgets('should handle widget recreation', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            jokesStream: Stream.value([testJoke]),
            key: const Key('first_widget'),
          ),
        );
        await tester.pump();

        expect(find.byType(JokeCard), findsOneWidget);

        // Recreate with different data and unique key to force provider recreation
        await tester.pumpWidget(
          createTestWidget(
            jokesStream: Stream.value(testJokes),
            key: const Key('second_widget'),
          ),
        );
        await tester.pump();

        expect(find.byType(JokeCard), findsOneWidget);
        expect(find.textContaining('1 of 2'), findsOneWidget);
        expect(tester.takeException(), isNull);
      });
    });

    group('Edge Cases', () {
      testWidgets('should handle rapid stream updates', (tester) async {
        final controller = StreamController<List<Joke>>();

        await tester.pumpWidget(
          createTestWidget(
            jokesStream: controller.stream,
            key: const Key('rapid_updates_test'),
          ),
        );
        await tester.pump();

        // Rapid updates
        for (int i = 0; i < 5; i++) {
          controller.add(i.isEven ? <Joke>[] : testJokes);
          await tester.pump();
        }

        // Should handle without throwing
        expect(tester.takeException(), isNull);

        await controller.close();
      });

      testWidgets('should handle null safety correctly', (tester) async {
        // Test with jokes that have null image URLs
        final jokesWithNulls = [
          const Joke(
            id: '1',
            setupText: 'Setup',
            punchlineText: 'Punchline',
            setupImageUrl: null,
            punchlineImageUrl: null,
          ),
        ];

        await tester.pumpWidget(
          createTestWidget(
            jokesStream: Stream.value(jokesWithNulls),
            key: const Key('null_urls_test'),
          ),
        );
        await tester.pump();

        // Should still build without throwing
        expect(tester.takeException(), isNull);
        expect(find.byType(Scaffold), findsOneWidget);
      });

      testWidgets('should handle empty string image URLs', (tester) async {
        final jokesWithEmptyUrls = [
          const Joke(
            id: '1',
            setupText: 'Setup',
            punchlineText: 'Punchline',
            setupImageUrl: '',
            punchlineImageUrl: '',
          ),
        ];

        await tester.pumpWidget(
          createTestWidget(
            jokesStream: Stream.value(jokesWithEmptyUrls),
            key: const Key('empty_urls_test'),
          ),
        );
        await tester.pump();

        // Should still build without throwing
        expect(tester.takeException(), isNull);
        expect(find.byType(Scaffold), findsOneWidget);
      });
    });
  });
}
