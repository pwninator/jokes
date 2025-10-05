import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/share_joke_button.dart';
import 'package:snickerdoodle/src/core/providers/joke_share_providers.dart';
import 'package:snickerdoodle/src/core/services/joke_share_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class MockJokeShareService extends Mock implements JokeShareService {}

class _FakeBuildContext extends Fake implements BuildContext {}

void main() {
  group('ShareJokeButton', () {
    late MockJokeShareService mockJokeShareService;
    const testJoke = Joke(
      id: 'test-joke-id',
      setupText: 'Why did the chicken cross the road?',
      punchlineText: 'To get to the other side!',
    );

    setUpAll(() {
      registerFallbackValue(testJoke);
      registerFallbackValue(_FakeBuildContext());
    });

    setUp(() {
      mockJokeShareService = MockJokeShareService();
    });

    Widget createTestWidget({required Widget child}) {
      return ProviderScope(
        overrides: [
          jokeShareServiceProvider.overrideWithValue(mockJokeShareService),
        ],
        child: MaterialApp(home: Scaffold(body: child)),
      );
    }

    testWidgets('renders correctly and respects custom properties', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          child: const ShareJokeButton(joke: testJoke, jokeContext: 'test'),
        ),
      );
      expect(find.byIcon(Icons.share), findsOneWidget);
      final defaultIcon = tester.widget<Icon>(find.byIcon(Icons.share));
      expect(defaultIcon.size, 24.0);

      await tester.pumpWidget(
        createTestWidget(
          child: const ShareJokeButton(
            joke: testJoke,
            jokeContext: 'test',
            size: 48.0,
          ),
        ),
      );
      final customIcon = tester.widget<Icon>(find.byIcon(Icons.share));
      expect(customIcon.size, 48.0);
    });

    testWidgets('successful share flow shows and hides dialog correctly', (tester) async {
      when(() => mockJokeShareService.shareJoke(
            any(),
            jokeContext: any(named: 'jokeContext'),
            controller: any(named: 'controller'),
            context: any(named: 'context'),
          )).thenAnswer((invocation) async {
        final controller = invocation.namedArguments[#controller] as SharePreparationController?;
        await Future.delayed(const Duration(milliseconds: 50));
        controller?.onBeforePlatformShare?.call();
        return true;
      });

      await tester.pumpWidget(
        createTestWidget(
          child: const ShareJokeButton(joke: testJoke, jokeContext: 'test-context'),
        ),
      );

      await tester.tap(find.byIcon(Icons.share));
      await tester.pump();

      expect(find.byType(AlertDialog), findsOneWidget);
      expect(find.byKey(const Key('share_joke_button-progress-text-static')), findsOneWidget);

      await tester.pumpAndSettle();

      expect(find.byType(AlertDialog), findsNothing);
      verify(() => mockJokeShareService.shareJoke(
            testJoke,
            jokeContext: 'test-context',
            controller: any(named: 'controller'),
            context: any(named: 'context'),
          )).called(1);
    });

    testWidgets('handles cancellation correctly', (tester) async {
      when(() => mockJokeShareService.shareJoke(
            any(),
            jokeContext: any(named: 'jokeContext'),
            controller: any(named: 'controller'),
            context: any(named: 'context'),
          )).thenAnswer((_) async => false);

      await tester.pumpWidget(
        createTestWidget(
          child: const ShareJokeButton(joke: testJoke, jokeContext: 'test-context'),
        ),
      );

      await tester.tap(find.byIcon(Icons.share));
      await tester.pump();
      expect(find.byType(AlertDialog), findsOneWidget);

      await tester.tap(find.byKey(Key('share_joke_button-cancel-button-${testJoke.id}')));
      await tester.pumpAndSettle();

      expect(find.byType(AlertDialog), findsNothing);
    });

    testWidgets('handles service errors gracefully', (tester) async {
      when(() => mockJokeShareService.shareJoke(
            any(),
            jokeContext: any(named: 'jokeContext'),
            controller: any(named: 'controller'),
            context: any(named: 'context'),
          )).thenThrow(Exception('Share failed'));

      await tester.pumpWidget(
        createTestWidget(
          child: const ShareJokeButton(joke: testJoke, jokeContext: 'test-context'),
        ),
      );

      await tester.tap(find.byIcon(Icons.share));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.byType(AlertDialog), findsNothing);
    });
  });
}