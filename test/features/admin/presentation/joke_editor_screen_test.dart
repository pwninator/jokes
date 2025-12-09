import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_editor_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class MockJokeRepository extends Mock implements JokeRepository {}

class MockPerformanceService extends Mock implements PerformanceService {}

class MockImageService extends Mock implements ImageService {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

void main() {
  group('JokeEditorScreen', () {
    late MockJokeCloudFunctionService mockJokeService;
    late MockJokeRepository mockJokeRepository;
    late MockPerformanceService mockPerformanceService;
    late MockImageService mockImageService;
    late MockAnalyticsService mockAnalyticsService;

    setUpAll(() {
      registerFallbackValue(TraceName.fsRead);
      registerFallbackValue(<String, String>{});
    });

    setUp(() {
      mockJokeService = MockJokeCloudFunctionService();
      mockJokeRepository = MockJokeRepository();
      mockPerformanceService = MockPerformanceService();
      mockImageService = MockImageService();
      mockAnalyticsService = MockAnalyticsService();

      when(
        () => mockPerformanceService.startNamedTrace(
          name: any(named: 'name'),
          key: any(named: 'key'),
          attributes: any(named: 'attributes'),
        ),
      ).thenReturn(null);
      when(
        () => mockPerformanceService.stopNamedTrace(
          name: any(named: 'name'),
          key: any(named: 'key'),
        ),
      ).thenReturn(null);
      when(
        () => mockImageService.getProcessedJokeImageUrl(
          any(),
          width: any(named: 'width'),
        ),
      ).thenReturn(null);
      when(() => mockImageService.isValidImageUrl(any())).thenReturn(false);
      when(
        () => mockAnalyticsService.logErrorImageLoad(
          jokeId: any(named: 'jokeId'),
          imageType: any(named: 'imageType'),
          imageUrlHash: any(named: 'imageUrlHash'),
          errorMessage: any(named: 'errorMessage'),
        ),
      ).thenAnswer((_) async {});
    });

    Widget buildScreen({Joke? joke}) {
      return ProviderScope(
        overrides: [
          jokeCloudFunctionServiceProvider.overrideWithValue(mockJokeService),
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          performanceServiceProvider.overrideWithValue(mockPerformanceService),
          imageServiceProvider.overrideWithValue(mockImageService),
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
          if (joke != null)
            jokeStreamByIdProvider(
              joke.id,
            ).overrideWith((ref) => Stream.value(joke)),
        ],
        child: MaterialApp(
          theme: lightTheme,
          home: Scaffold(body: JokeEditorScreen(jokeId: joke?.id)),
        ),
      );
    }

    testWidgets('renders three-stage layout for new jokes', (tester) async {
      await tester.pumpWidget(buildScreen());

      expect(find.text('Step 1: Enter setup & punchline'), findsOneWidget);
      expect(find.text('Step 2: Refine scene ideas'), findsOneWidget);
      expect(find.text('Step 3: Generate images'), findsOneWidget);

      expect(find.byKey(const Key('setupTextField')), findsOneWidget);
      expect(find.byKey(const Key('punchlineTextField')), findsOneWidget);
      expect(find.byKey(const Key('saveJokeButton')), findsOneWidget);
      expect(find.byKey(const Key('setupSceneIdeaTextField')), findsNothing);
    });

    testWidgets('tapping create button calls cloud function', (tester) async {
      const setupText = 'Setup';
      const punchlineText = 'Punchline';

      when(
        () => mockJokeService.createJokeWithResponse(
          setupText: setupText,
          punchlineText: punchlineText,
          adminOwned: true,
        ),
      ).thenAnswer(
        (_) async => const Joke(
          id: 'joke-123',
          setupText: setupText,
          punchlineText: punchlineText,
          setupSceneIdea: 'scene 1',
          punchlineSceneIdea: 'scene 2',
        ),
      );

      await tester.pumpWidget(buildScreen());
      await tester.enterText(
        find.byKey(const Key('setupTextField')),
        setupText,
      );
      await tester.enterText(
        find.byKey(const Key('punchlineTextField')),
        punchlineText,
      );

      await tester.tap(find.byKey(const Key('saveJokeButton')));
      await tester.pumpAndSettle();

      verify(
        () => mockJokeService.createJokeWithResponse(
          setupText: setupText,
          punchlineText: punchlineText,
          adminOwned: true,
        ),
      ).called(1);
    });

    testWidgets('updating existing joke uses CF with optional regen flag', (
      tester,
    ) async {
      const joke = Joke(
        id: 'j-regen',
        setupText: 'Old setup',
        punchlineText: 'Old punchline',
        setupSceneIdea: 'Old scene setup',
        punchlineSceneIdea: 'Old scene punch',
      );

      when(
        () => mockJokeService.updateJokeTextViaCreationProcess(
          jokeId: joke.id,
          setupText: any(named: 'setupText'),
          punchlineText: any(named: 'punchlineText'),
          regenerateSceneIdeas: any(named: 'regenerateSceneIdeas'),
        ),
      ).thenAnswer(
        (_) async => const Joke(
          id: 'j-regen',
          setupText: 'New setup',
          punchlineText: 'New punch',
          setupSceneIdea: 'Regenerated scene setup',
          punchlineSceneIdea: 'Regenerated scene punch',
        ),
      );

      await tester.pumpWidget(buildScreen(joke: joke));
      await tester.pumpAndSettle();

      // Expand stage 1 if it was auto-collapsed
      await tester.tap(find.text('Step 1: Enter setup & punchline'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('setupTextField')),
        'New setup',
      );
      await tester.enterText(
        find.byKey(const Key('punchlineTextField')),
        'New punch',
      );

      // Toggle regen checkbox
      await tester.tap(find.byKey(const Key('regenerateSceneIdeasCheckbox')));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('updateJokeButton')));
      await tester.pumpAndSettle();

      verify(
        () => mockJokeService.updateJokeTextViaCreationProcess(
          jokeId: joke.id,
          setupText: 'New setup',
          punchlineText: 'New punch',
          regenerateSceneIdeas: true,
        ),
      ).called(1);
    });

    testWidgets('scene idea suggestion triggers modify call', (tester) async {
      const joke = Joke(
        id: 'j1',
        setupText: 'Setup',
        punchlineText: 'Punchline',
        setupSceneIdea: 'Old setup idea',
        punchlineSceneIdea: 'Old punchline idea',
      );

      when(
        () => mockJokeService.modifyJokeSceneIdeas(
          jokeId: joke.id,
          setupSuggestion: any(named: 'setupSuggestion'),
          punchlineSuggestion: any(named: 'punchlineSuggestion'),
          setupSceneIdea: any(named: 'setupSceneIdea'),
          punchlineSceneIdea: any(named: 'punchlineSceneIdea'),
        ),
      ).thenAnswer(
        (_) async => Joke(
          id: joke.id,
          setupText: joke.setupText,
          punchlineText: joke.punchlineText,
          setupSceneIdea: 'New setup idea',
          punchlineSceneIdea: 'Old punchline idea',
        ),
      );

      await tester.pumpWidget(buildScreen(joke: joke));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('setupSceneSuggestionTextField')),
        'make sillier',
      );
      await tester.tap(find.byKey(const Key('setupSceneSuggestionButton')));
      await tester.pumpAndSettle();

      verify(
        () => mockJokeService.modifyJokeSceneIdeas(
          jokeId: joke.id,
          setupSuggestion: 'make sillier',
          punchlineSuggestion: null,
          setupSceneIdea: 'Old setup idea',
          punchlineSceneIdea: 'Old punchline idea',
        ),
      ).called(1);
    });

    testWidgets('generate descriptions button calls cloud function', (
      tester,
    ) async {
      const joke = Joke(
        id: 'j1',
        setupText: 'Setup',
        punchlineText: 'Punchline',
        setupSceneIdea: 'scene 1',
        punchlineSceneIdea: 'scene 2',
      );

      when(
        () => mockJokeService.generateImageDescriptionsViaCreationProcess(
          jokeId: joke.id,
          setupSceneIdea: any(named: 'setupSceneIdea'),
          punchlineSceneIdea: any(named: 'punchlineSceneIdea'),
        ),
      ).thenAnswer(
        (_) async => const Joke(
          id: 'j1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          setupSceneIdea: 'scene 1',
          punchlineSceneIdea: 'scene 2',
          setupImageDescription: 'desc 1',
          punchlineImageDescription: 'desc 2',
        ),
      );

      await tester.pumpWidget(buildScreen(joke: joke));
      await tester.pumpAndSettle();

      final descriptionsButton = find.byKey(
        const Key('generateImageDescriptionsButton'),
      );
      await tester.ensureVisible(descriptionsButton);
      await tester.pumpAndSettle();
      await tester.tap(descriptionsButton);
      await tester.pumpAndSettle();

      verify(
        () => mockJokeService.generateImageDescriptionsViaCreationProcess(
          jokeId: joke.id,
          setupSceneIdea: 'scene 1',
          punchlineSceneIdea: 'scene 2',
        ),
      ).called(1);
    });

    testWidgets('generate images button calls creation process', (
      tester,
    ) async {
      const joke = Joke(
        id: 'j1',
        setupText: 'Setup',
        punchlineText: 'Punchline',
        setupSceneIdea: 'scene 1',
        punchlineSceneIdea: 'scene 2',
        setupImageDescription: 'desc 1',
        punchlineImageDescription: 'desc 2',
      );

      when(
        () => mockJokeService.generateImagesViaCreationProcess(
          jokeId: joke.id,
          imageQuality: any(named: 'imageQuality'),
          setupSceneIdea: any(named: 'setupSceneIdea'),
          punchlineSceneIdea: any(named: 'punchlineSceneIdea'),
          setupImageDescription: any(named: 'setupImageDescription'),
          punchlineImageDescription: any(named: 'punchlineImageDescription'),
        ),
      ).thenAnswer(
        (_) async => const Joke(
          id: 'j1',
          setupText: 'Setup',
          punchlineText: 'Punchline',
          setupSceneIdea: 'scene 1',
          punchlineSceneIdea: 'scene 2',
          setupImageDescription: 'desc 1',
          punchlineImageDescription: 'desc 2',
          allSetupImageUrls: ['a.png'],
          allPunchlineImageUrls: ['b.png'],
        ),
      );

      await tester.pumpWidget(buildScreen(joke: joke));
      await tester.pumpAndSettle();

      final imagesButton = find.byKey(const Key('generateImagesButton'));
      await tester.ensureVisible(imagesButton);
      await tester.pumpAndSettle();
      await tester.tap(imagesButton);
      await tester.pumpAndSettle();

      verify(
        () => mockJokeService.generateImagesViaCreationProcess(
          jokeId: joke.id,
          imageQuality: any(named: 'imageQuality'),
          setupSceneIdea: 'scene 1',
          punchlineSceneIdea: 'scene 2',
          setupImageDescription: 'desc 1',
          punchlineImageDescription: 'desc 2',
        ),
      ).called(1);
    });

    testWidgets('save selection button updates repository', (tester) async {
      const joke = Joke(
        id: 'j1',
        setupText: 'Setup',
        punchlineText: 'Punchline',
        setupImageDescription: 'desc 1',
        punchlineImageDescription: 'desc 2',
        setupSceneIdea: 'scene 1',
        punchlineSceneIdea: 'scene 2',
        setupImageUrl: 'setup.png',
        punchlineImageUrl: 'punch.png',
        allSetupImageUrls: ['setup.png', 'setup2.png'],
        allPunchlineImageUrls: ['punch.png', 'punch2.png'],
      );

      when(
        () => mockJokeRepository.updateJoke(
          jokeId: joke.id,
          setupText: joke.setupText,
          punchlineText: joke.punchlineText,
          setupImageUrl: any(named: 'setupImageUrl'),
          punchlineImageUrl: any(named: 'punchlineImageUrl'),
          setupImageDescription: any(named: 'setupImageDescription'),
          punchlineImageDescription: any(named: 'punchlineImageDescription'),
        ),
      ).thenAnswer((_) async {});

      await tester.pumpWidget(buildScreen(joke: joke));
      await tester.pumpAndSettle();

      final saveButton = find.byKey(const Key('saveImageSelectionButton'));
      await tester.ensureVisible(saveButton);
      await tester.pumpAndSettle();
      await tester.tap(saveButton);
      await tester.pumpAndSettle();

      verify(
        () => mockJokeRepository.updateJoke(
          jokeId: joke.id,
          setupText: joke.setupText,
          punchlineText: joke.punchlineText,
          setupImageUrl: joke.setupImageUrl,
          punchlineImageUrl: joke.punchlineImageUrl,
          setupImageDescription: joke.setupImageDescription,
          punchlineImageDescription: joke.punchlineImageDescription,
        ),
      ).called(1);
    });
  });
}
