import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/joke_text_card.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_population_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';

// Mock classes
class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeViewerSettingsService extends Mock
    implements JokeViewerSettingsService {}

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

// Fake classes for mocktail
class FakeJoke extends Fake implements Joke {}

void main() {
  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(FakeJoke());
  });

  late MockJokeRepository mockJokeRepository;
  late MockJokeViewerSettingsService mockJokeViewerSettingsService;
  late MockJokeCloudFunctionService mockJokeCloudFunctionService;

  setUp(() {
    mockJokeRepository = MockJokeRepository();
    mockJokeViewerSettingsService = MockJokeViewerSettingsService();
    mockJokeCloudFunctionService = MockJokeCloudFunctionService();

    // Stub default behavior
    when(
      () => mockJokeViewerSettingsService.getReveal(),
    ).thenAnswer((_) async => false);
  });

  Widget createTestWidget({
    required Widget child,
    List<Override> additionalOverrides = const [],
  }) {
    return ProviderScope(
      overrides: [
        jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
        jokeViewerSettingsServiceProvider.overrideWithValue(
          mockJokeViewerSettingsService,
        ),
        jokePopulationProvider.overrideWith((ref) {
          return JokePopulationNotifier(mockJokeCloudFunctionService);
        }),
        ...additionalOverrides,
      ],
      child: MaterialApp.router(
        theme: lightTheme,
        routerConfig: GoRouter(
          routes: [
            GoRoute(
              path: '/',
              builder: (context, state) => Scaffold(body: child),
            ),
          ],
        ),
      ),
    );
  }

  group('JokeTextCard admin/non-admin action buttons', () {
    testWidgets('non-admin shows no admin buttons', (tester) async {
      const joke = Joke(
        id: 'na1',
        setupText: 'Setup',
        punchlineText: 'Punch',
        setupImageUrl: null,
        punchlineImageUrl: null,
      );

      // Render via JokeCard to reflect real usage
      const widget = JokeCard(joke: joke, jokeContext: 'test');

      await tester.pumpWidget(createTestWidget(child: widget));

      // Ensure text card is being used
      expect(find.byType(JokeTextCard), findsOneWidget);

      // No admin buttons should be shown
      expect(find.byKey(const Key('delete-joke-button')), findsNothing);
      expect(find.byKey(const Key('edit-joke-button')), findsNothing);
      expect(find.byKey(const Key('populate-joke-button')), findsNothing);
    });

    testWidgets('admin shows delete, edit, and populate buttons', (
      tester,
    ) async {
      const joke = Joke(
        id: 'ad1',
        setupText: 'Setup',
        punchlineText: 'Punch',
        setupImageUrl: null,
        punchlineImageUrl: null,
      );

      const widget = JokeCard(
        joke: joke,
        jokeContext: 'test',
        isAdminMode: true,
      );

      await tester.pumpWidget(createTestWidget(child: widget));

      // Ensure text card is being used
      expect(find.byType(JokeTextCard), findsOneWidget);

      // All three admin buttons should exist
      expect(find.byKey(const Key('delete-joke-button')), findsOneWidget);
      expect(find.byKey(const Key('edit-joke-button')), findsOneWidget);
      expect(find.byKey(const Key('populate-joke-button')), findsOneWidget);
    });
  });
}
