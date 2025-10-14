import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/share_joke_button.dart';
import 'package:snickerdoodle/src/core/providers/joke_share_providers.dart';
import 'package:snickerdoodle/src/core/services/joke_share_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class MockJokeShareService extends Mock implements JokeShareService {}

class _FakeBuildContext extends Fake implements BuildContext {}

void main() {
  group('ShareJokeButton', () {
    late MockJokeShareService mockJokeShareService;
    late Joke testJoke;
    late StreamController<bool> sharedController;

    setUpAll(() {
      registerFallbackValue(
        const Joke(
          id: 'fallback-joke-id',
          setupText: 'Fallback setup',
          punchlineText: 'Fallback punchline',
        ),
      );
      registerFallbackValue(_FakeBuildContext());
    });

    Widget createTestWidget({
      required Widget child,
      List<Override> additionalOverrides = const [],
    }) {
      return ProviderScope(
        overrides: [
          jokeShareServiceProvider.overrideWithValue(mockJokeShareService),
          // Override the isJokeShared provider for our test joke ID
          isJokeSharedProvider(
            testJoke.id,
          ).overrideWith((ref) => sharedController.stream),
          ...additionalOverrides,
        ],
        child: MaterialApp(
          theme: lightTheme,
          home: Scaffold(body: child),
        ),
      );
    }

    setUp(() {
      mockJokeShareService = MockJokeShareService();
      testJoke = const Joke(
        id: 'test-joke-id',
        setupText: 'Why did the chicken cross the road?',
        punchlineText: 'To get to the other side!',
      );
      sharedController = StreamController<bool>.broadcast();
      // Don't add initial value here - add it after widget is created
    });

    tearDown(() {
      sharedController.close();
    });

    testWidgets('should display share icon', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          child: ShareJokeButton(joke: testJoke, jokeContext: 'test-context'),
        ),
      );

      // Add initial value after widget subscribes
      sharedController.add(false);
      await tester.pump();

      expect(find.byIcon(Icons.share_outlined), findsOneWidget);
    });

    testWidgets('should use custom size when provided', (tester) async {
      const customSize = 32.0;

      await tester.pumpWidget(
        createTestWidget(
          child: ShareJokeButton(
            joke: testJoke,
            jokeContext: 'test-context',
            size: customSize,
          ),
        ),
      );

      sharedController.add(false);
      await tester.pump();

      final icon = tester.widget<Icon>(find.byIcon(Icons.share_outlined));
      expect(icon.size, customSize);
    });

    testWidgets('should complete sharing successfully', (tester) async {
      when(
        () => mockJokeShareService.shareJoke(
          any(),
          jokeContext: any(named: 'jokeContext'),
          controller: any(named: 'controller'),
          context: any(named: 'context'),
        ),
      ).thenAnswer((_) async => true);

      await tester.pumpWidget(
        createTestWidget(
          child: ShareJokeButton(joke: testJoke, jokeContext: 'test-context'),
        ),
      );

      sharedController.add(false);
      await tester.pump();

      await tester.tap(find.byIcon(Icons.share_outlined));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
    });

    testWidgets(
      'shows determinate progress dialog and closes on pre-share callback',
      (tester) async {
        when(
          () => mockJokeShareService.shareJoke(
            any(),
            jokeContext: any(named: 'jokeContext'),
            controller: any(named: 'controller'),
            context: any(named: 'context'),
          ),
        ).thenAnswer((invocation) async {
          // Capture controller and simulate pre-share callback
          final controller =
              invocation.namedArguments[#controller]
                  as SharePreparationController?;
          // Wait a frame so dialog can build
          await Future<void>.delayed(const Duration(milliseconds: 10));
          controller?.onBeforePlatformShare?.call();
          return true;
        });

        await tester.pumpWidget(
          createTestWidget(
            child: ShareJokeButton(joke: testJoke, jokeContext: 'test-context'),
          ),
        );

        sharedController.add(false);
        await tester.pump();

        await tester.tap(find.byIcon(Icons.share_outlined));
        await tester.pump();

        // Dialog visible
        expect(
          find.byKey(Key('share_joke_button-progress-dialog-${testJoke.id}')),
          findsOneWidget,
        );

        // Determinate progress UI present
        expect(
          find.byKey(Key('share_joke_button-progress-bar-${testJoke.id}')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('share_joke_button-progress-text-static')),
          findsOneWidget,
        );

        // After callback it should close
        await tester.pumpAndSettle();
        expect(
          find.byKey(Key('share_joke_button-progress-dialog-${testJoke.id}')),
          findsNothing,
        );
      },
    );

    testWidgets('cancel button aborts sharing and closes dialog', (
      tester,
    ) async {
      // ShareJoke returns false when canceled
      when(
        () => mockJokeShareService.shareJoke(
          any(),
          jokeContext: any(named: 'jokeContext'),
          controller: any(named: 'controller'),
          context: any(named: 'context'),
        ),
      ).thenAnswer((invocation) async {
        final controller =
            invocation.namedArguments[#controller]
                as SharePreparationController?;
        // Wait until the test presses Cancel
        while (controller?.isCanceled != true) {
          await Future<void>.delayed(const Duration(milliseconds: 10));
        }
        return false;
      });

      await tester.pumpWidget(
        createTestWidget(
          child: ShareJokeButton(joke: testJoke, jokeContext: 'test-context'),
        ),
      );

      sharedController.add(false);
      await tester.pump();

      await tester.tap(find.byIcon(Icons.share_outlined));
      await tester.pump();

      // Dialog visible
      final cancelFinder = find.byKey(
        Key('share_joke_button-cancel-button-${testJoke.id}'),
      );
      expect(cancelFinder, findsOneWidget);

      await tester.tap(cancelFinder);
      await tester.pumpAndSettle();

      // Dialog closed
      expect(
        find.byKey(Key('share_joke_button-progress-dialog-${testJoke.id}')),
        findsNothing,
      );
    });

    testWidgets('should call share service with correct parameters', (
      tester,
    ) async {
      const jokeContext = 'test-context';

      when(
        () => mockJokeShareService.shareJoke(
          any(),
          jokeContext: any(named: 'jokeContext'),
          controller: any(named: 'controller'),
          context: any(named: 'context'),
        ),
      ).thenAnswer((_) async => true);

      await tester.pumpWidget(
        createTestWidget(
          child: ShareJokeButton(joke: testJoke, jokeContext: jokeContext),
        ),
      );

      sharedController.add(false);
      await tester.pump();

      // Tap the share button
      await tester.tap(find.byIcon(Icons.share_outlined));
      await tester.pumpAndSettle();

      // Verify share service was called with correct parameters
      verify(
        () => mockJokeShareService.shareJoke(
          testJoke,
          jokeContext: jokeContext,
          controller: any(named: 'controller'),
          context: any(named: 'context'),
        ),
      ).called(1);
    });

    testWidgets('should handle share error gracefully', (tester) async {
      const errorMessage = 'Share failed';

      when(
        () => mockJokeShareService.shareJoke(
          any(),
          jokeContext: any(named: 'jokeContext'),
          controller: any(named: 'controller'),
          context: any(named: 'context'),
        ),
      ).thenThrow(Exception(errorMessage));

      await tester.pumpWidget(
        createTestWidget(
          child: ShareJokeButton(joke: testJoke, jokeContext: 'test-context'),
        ),
      );

      sharedController.add(false);
      await tester.pump();

      await tester.tap(find.byIcon(Icons.share_outlined));
      await tester.pumpAndSettle();

      // Verify UI doesn't crash and share button is still present
      expect(tester.takeException(), isNull);
      expect(find.byIcon(Icons.share_outlined), findsOneWidget);
    });
  });
}

// removed duplicate _MockPerf at file end
