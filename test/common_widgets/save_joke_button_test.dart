import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/save_joke_button.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
// Removed unused PerformanceService import
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

class MockJokeReactionsService extends Mock implements JokeReactionsService {}

class MockAppUsageService extends Mock implements AppUsageService {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class _FakeBuildContext extends Fake implements BuildContext {}

void main() {
  setUpAll(() {
    registerFallbackValue(_FakeBuildContext());
    registerFallbackValue(JokeReactionType.save);
  });

  group('SaveJokeButton', () {
    late MockJokeReactionsService mockJokeReactionsService;
    late MockAppUsageService mockAppUsageService;
    late MockAnalyticsService mockAnalyticsService;
    late StreamController<bool> streamController;

    const jokeId = 'j-123';
    const jokeContext = 'test-ctx';

    Widget createUnderTest() {
      return ProviderScope(
        overrides: [
          // Mock only the services that SaveJokeButton actually uses
          jokeReactionsServiceProvider.overrideWithValue(
            mockJokeReactionsService,
          ),
          appUsageServiceProvider.overrideWithValue(mockAppUsageService),
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          // Provide controlled stream for isJokeSavedProvider directly
          isJokeSavedProvider(
            jokeId,
          ).overrideWith((ref) => streamController.stream),
        ],
        child: MaterialApp(
          theme: lightTheme,
          home: const Scaffold(
            body: Center(
              child: SaveJokeButton(
                jokeId: jokeId,
                jokeContext: jokeContext,
                size: 24,
              ),
            ),
          ),
        ),
      );
    }

    setUp(() {
      mockJokeReactionsService = MockJokeReactionsService();
      mockAppUsageService = MockAppUsageService();
      mockAnalyticsService = MockAnalyticsService();
      streamController = StreamController<bool>.broadcast();

      // Setup default behaviors
      when(
        () => mockAppUsageService.getNumSavedJokes(),
      ).thenAnswer((_) async => 5);
      when(
        () => mockJokeReactionsService.toggleUserReaction(
          any(),
          any(),
          context: any(named: 'context'),
        ),
      ).thenAnswer((_) async => true);

      // Setup analytics service defaults
      when(
        () => mockAnalyticsService.logJokeSaved(
          any(),
          jokeContext: any(named: 'jokeContext'),
          totalJokesSaved: any(named: 'totalJokesSaved'),
        ),
      ).thenAnswer((_) async {});
      when(
        () => mockAnalyticsService.logJokeUnsaved(
          any(),
          jokeContext: any(named: 'jokeContext'),
          totalJokesSaved: any(named: 'totalJokesSaved'),
        ),
      ).thenAnswer((_) async {});
      when(
        () => mockAnalyticsService.logErrorJokeSave(
          jokeId: any(named: 'jokeId'),
          action: any(named: 'action'),
          errorMessage: any(named: 'errorMessage'),
        ),
      ).thenAnswer((_) async {});
    });

    tearDown(() async {
      await streamController.close();
    });

    testWidgets('shows loading indicator while stream has not emitted', (
      tester,
    ) async {
      await tester.pumpWidget(createUnderTest());

      // No event yet -> loading indicator
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.byIcon(Icons.favorite), findsNothing);
      expect(find.byIcon(Icons.favorite_border), findsNothing);
    });

    testWidgets('renders border icon when joke is not saved', (tester) async {
      await tester.pumpWidget(createUnderTest());

      streamController.add(false);
      await tester.pump();

      expect(find.byIcon(Icons.favorite_border), findsOneWidget);
      expect(find.byIcon(Icons.favorite), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets('renders filled red icon when joke is saved', (tester) async {
      await tester.pumpWidget(createUnderTest());

      streamController.add(true);
      await tester.pump();

      final icon = tester.widget<Icon>(find.byIcon(Icons.favorite));
      final context = tester.element(find.byIcon(Icons.favorite));
      final expectedColor = Theme.of(context).colorScheme.error;
      expect(icon.color, expectedColor);
      expect(find.byIcon(Icons.favorite_border), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets('tap calls toggleUserReaction with correct parameters', (
      tester,
    ) async {
      await tester.pumpWidget(createUnderTest());

      streamController.add(false);
      await tester.pump();

      await tester.tap(find.byKey(const Key('save_joke_button-$jokeId')));
      await tester.pump();

      verify(
        () => mockJokeReactionsService.toggleUserReaction(
          jokeId,
          JokeReactionType.save,
          context: any(named: 'context'),
        ),
      ).called(1);
    });

    testWidgets('logs analytics when joke is saved successfully', (
      tester,
    ) async {
      when(
        () => mockJokeReactionsService.toggleUserReaction(
          any(),
          any(),
          context: any(named: 'context'),
        ),
      ).thenAnswer((_) async => true);

      await tester.pumpWidget(createUnderTest());

      streamController.add(false);
      await tester.pump();

      await tester.tap(find.byKey(const Key('save_joke_button-$jokeId')));
      await tester.pump();

      verify(
        () => mockAnalyticsService.logJokeSaved(
          jokeId,
          jokeContext: jokeContext,
          totalJokesSaved: 5,
        ),
      ).called(1);
      verify(() => mockAppUsageService.getNumSavedJokes()).called(1);
    });

    testWidgets('logs analytics when joke is unsaved successfully', (
      tester,
    ) async {
      when(
        () => mockJokeReactionsService.toggleUserReaction(
          any(),
          any(),
          context: any(named: 'context'),
        ),
      ).thenAnswer((_) async => false);

      await tester.pumpWidget(createUnderTest());

      streamController.add(true);
      await tester.pump();

      await tester.tap(find.byKey(const Key('save_joke_button-$jokeId')));
      await tester.pump();

      verify(
        () => mockAnalyticsService.logJokeUnsaved(
          jokeId,
          jokeContext: jokeContext,
          totalJokesSaved: 5,
        ),
      ).called(1);
      verify(() => mockAppUsageService.getNumSavedJokes()).called(1);
    });

    testWidgets('logs error analytics when toggleUserReaction throws', (
      tester,
    ) async {
      const errorMessage = 'Network error';
      when(
        () => mockJokeReactionsService.toggleUserReaction(
          any(),
          any(),
          context: any(named: 'context'),
        ),
      ).thenThrow(Exception(errorMessage));

      await tester.pumpWidget(createUnderTest());

      streamController.add(false);
      await tester.pump();

      await tester.tap(find.byKey(const Key('save_joke_button-$jokeId')));
      await tester.pump();

      verify(
        () => mockAnalyticsService.logErrorJokeSave(
          jokeId: jokeId,
          action: 'toggle',
          errorMessage: 'Exception: $errorMessage',
        ),
      ).called(1);

      // Should not log save/unsave analytics when error occurs
      verifyNever(
        () => mockAnalyticsService.logJokeSaved(
          any(),
          jokeContext: any(named: 'jokeContext'),
          totalJokesSaved: any(named: 'totalJokesSaved'),
        ),
      );
      verifyNever(
        () => mockAnalyticsService.logJokeUnsaved(
          any(),
          jokeContext: any(named: 'jokeContext'),
          totalJokesSaved: any(named: 'totalJokesSaved'),
        ),
      );
    });

    testWidgets('handles stream error gracefully', (tester) async {
      await tester.pumpWidget(createUnderTest());

      streamController.addError(Exception('stream failed'));
      await tester.pump();

      // Fallback icon should render without crash
      expect(find.byIcon(Icons.favorite_border), findsOneWidget);
      expect(find.byIcon(Icons.favorite), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets('updates icon color based on theme when saved', (tester) async {
      await tester.pumpWidget(createUnderTest());

      streamController.add(true);
      await tester.pump();

      final icon = tester.widget<Icon>(find.byIcon(Icons.favorite));
      final context = tester.element(find.byIcon(Icons.favorite));
      final expectedColor = Theme.of(context).colorScheme.error;
      expect(icon.color, expectedColor);
      expect(icon.size, 24.0);
    });

    testWidgets('updates icon color based on theme when not saved', (
      tester,
    ) async {
      await tester.pumpWidget(createUnderTest());

      streamController.add(false);
      await tester.pump();

      final icon = tester.widget<Icon>(find.byIcon(Icons.favorite_border));
      final context = tester.element(find.byIcon(Icons.favorite_border));
      final expectedColor = jokeIconButtonBaseColor(context);
      expect(icon.color, expectedColor);
      expect(icon.size, 24.0);
    });
  });
}
