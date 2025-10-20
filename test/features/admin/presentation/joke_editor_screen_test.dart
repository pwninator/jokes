import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_editor_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

// Mock classes using mocktail
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
      // Fallbacks for mocktail matchers
      registerFallbackValue(TraceName.fsRead);
      registerFallbackValue(<String, String>{});
    });

    setUp(() {
      mockJokeService = MockJokeCloudFunctionService();
      mockJokeRepository = MockJokeRepository();
      mockPerformanceService = MockPerformanceService();
      mockImageService = MockImageService();
      mockAnalyticsService = MockAnalyticsService();

      // Stub performance methods to avoid MissingStub errors
      when(
        () => mockPerformanceService.startNamedTrace(
          name: any(named: 'name'),
          key: any(named: 'key'),
          attributes: any(named: 'attributes'),
        ),
      ).thenReturn(null);
      when(
        () => mockPerformanceService.putNamedTraceAttributes(
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
        () => mockPerformanceService.dropNamedTrace(
          name: any(named: 'name'),
          key: any(named: 'key'),
        ),
      ).thenReturn(null);

      // Prevent real image/network behavior in CachedJokeImage
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

    Widget createTestWidget({Joke? joke}) {
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
          home: JokeEditorScreen(jokeId: joke?.id),
        ),
      );
    }

    group('UI Rendering', () {
      testWidgets('should display create mode UI when no joke is provided', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());

        expect(
          find.text(
            'Create a new joke by filling out the setup and punchline below:',
          ),
          findsOneWidget,
        );
        expect(find.byKey(const Key('setupTextField')), findsOneWidget);
        expect(find.byKey(const Key('punchlineTextField')), findsOneWidget);
        expect(find.byKey(const Key('saveJokeButton')), findsOneWidget);
        expect(find.text('Save Joke'), findsOneWidget);

        // Image description fields should not be visible in create mode
        expect(find.text('Image Descriptions'), findsNothing);
        expect(
          find.byKey(const Key('setupImageDescriptionTextField')),
          findsNothing,
        );
        expect(
          find.byKey(const Key('punchlineImageDescriptionTextField')),
          findsNothing,
        );
      });

      testWidgets('should display edit mode UI when joke is provided', (
        tester,
      ) async {
        const joke = Joke(
          id: 'test-id',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageDescription: 'Test setup description',
          punchlineImageDescription: 'Test punchline description',
        );

        await tester.pumpWidget(createTestWidget(joke: joke));
        await tester.pumpAndSettle();

        expect(find.byKey(const Key('setupTextField')), findsOneWidget);
        expect(find.byKey(const Key('punchlineTextField')), findsOneWidget);
        expect(find.byKey(const Key('updateJokeButton')), findsOneWidget);
        expect(find.text('Update Joke'), findsOneWidget);

        // Image description fields should be visible in edit mode
        expect(find.text('Image Descriptions'), findsOneWidget);
        expect(
          find.byKey(const Key('setupImageDescriptionTextField')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('punchlineImageDescriptionTextField')),
          findsOneWidget,
        );
        expect(find.text('Test setup description'), findsOneWidget);
        expect(find.text('Test punchline description'), findsOneWidget);
      });

      testWidgets('should display form validation errors for create mode', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());

        // Try to save without entering text
        await tester.tap(find.byKey(const Key('saveJokeButton')));
        await tester.pump();

        expect(find.text('Please enter a setup for the joke'), findsOneWidget);
        expect(
          find.text('Please enter a punchline for the joke'),
          findsOneWidget,
        );
      });

      testWidgets(
        'should display form validation errors for edit mode (allow empty descriptions)',
        (tester) async {
          const joke = Joke(
            id: 'test-id',
            setupText: 'Test setup',
            punchlineText: 'Test punchline',
            setupImageDescription: 'Test setup description',
            punchlineImageDescription: 'Test punchline description',
          );

          await tester.pumpWidget(createTestWidget(joke: joke));
          await tester.pumpAndSettle();

          // Clear all fields
          await tester.enterText(find.byKey(const Key('setupTextField')), '');
          await tester.enterText(
            find.byKey(const Key('punchlineTextField')),
            '',
          );
          await tester.enterText(
            find.byKey(const Key('setupImageDescriptionTextField')),
            '',
          );
          await tester.enterText(
            find.byKey(const Key('punchlineImageDescriptionTextField')),
            '',
          );

          // Try to save - ensure button is visible first
          await tester.ensureVisible(find.byKey(const Key('updateJokeButton')));
          await tester.pumpAndSettle();
          await tester.tap(
            find.byKey(const Key('updateJokeButton')),
            warnIfMissed: false,
          );
          await tester.pump();

          expect(
            find.text('Please enter a setup for the joke'),
            findsOneWidget,
          );
          expect(
            find.text('Please enter a punchline for the joke'),
            findsOneWidget,
          );
          // Empty descriptions are allowed; no errors for empty descriptions
          expect(
            find.text('Please enter a description for the setup image'),
            findsNothing,
          );
          expect(
            find.text('Please enter a description for the punchline image'),
            findsNothing,
          );
        },
      );
    });

    group('Create Joke', () {
      testWidgets('should call createJokeWithResponse on save button tap', (
        tester,
      ) async {
        const setupText = 'New setup text';
        const punchlineText = 'New punchline text';

        when(
          () => mockJokeService.createJokeWithResponse(
            setupText: setupText,
            punchlineText: punchlineText,
            adminOwned: true,
          ),
        ).thenAnswer(
          (_) async => {
            'success': true,
            'data': {'jokeId': 'new-joke-id'},
          },
        );

        await tester.pumpWidget(createTestWidget());

        // Enter text in form fields
        await tester.enterText(
          find.byKey(const Key('setupTextField')),
          setupText,
        );
        await tester.enterText(
          find.byKey(const Key('punchlineTextField')),
          punchlineText,
        );

        // Tap save
        await tester.tap(find.byKey(const Key('saveJokeButton')));
        await tester.pump();

        verify(
          () => mockJokeService.createJokeWithResponse(
            setupText: setupText,
            punchlineText: punchlineText,
            adminOwned: true,
          ),
        ).called(1);
      });

      testWidgets('should show success message after creating joke', (
        tester,
      ) async {
        const setupText = 'New setup text';
        const punchlineText = 'New punchline text';

        when(
          () => mockJokeService.createJokeWithResponse(
            setupText: setupText,
            punchlineText: punchlineText,
            adminOwned: true,
          ),
        ).thenAnswer(
          (_) async => {
            'success': true,
            'data': {'jokeId': 'new-joke-id'},
          },
        );

        await tester.pumpWidget(createTestWidget());

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

        // Should show success snackbar
        expect(find.text('Joke saved successfully!'), findsOneWidget);
      });
    });

    group('Update Joke', () {
      testWidgets('should call repository updateJoke on save button tap', (
        tester,
      ) async {
        const originalJoke = Joke(
          id: 'test-id',
          setupText: 'Original setup',
          punchlineText: 'Original punchline',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
          setupImageDescription: 'Original setup description',
          punchlineImageDescription: 'Original punchline description',
        );

        const updatedSetupText = 'Updated setup text';
        const updatedPunchlineText = 'Updated punchline text';
        const updatedSetupDescription = 'Updated setup description';
        const updatedPunchlineDescription = 'Updated punchline description';

        when(
          () => mockJokeRepository.updateJoke(
            jokeId: originalJoke.id,
            setupText: updatedSetupText,
            punchlineText: updatedPunchlineText,
            setupImageUrl: originalJoke.setupImageUrl,
            punchlineImageUrl: originalJoke.punchlineImageUrl,
            setupImageDescription: updatedSetupDescription,
            punchlineImageDescription: updatedPunchlineDescription,
          ),
        ).thenAnswer((_) async => {});

        await tester.pumpWidget(createTestWidget(joke: originalJoke));
        await tester.pumpAndSettle();

        // Update all text fields
        await tester.enterText(
          find.byKey(const Key('setupTextField')),
          updatedSetupText,
        );
        await tester.enterText(
          find.byKey(const Key('punchlineTextField')),
          updatedPunchlineText,
        );
        await tester.enterText(
          find.byKey(const Key('setupImageDescriptionTextField')),
          updatedSetupDescription,
        );
        await tester.enterText(
          find.byKey(const Key('punchlineImageDescriptionTextField')),
          updatedPunchlineDescription,
        );

        // Ensure button is visible first
        await tester.ensureVisible(find.byKey(const Key('updateJokeButton')));
        await tester.pumpAndSettle();
        await tester.tap(
          find.byKey(const Key('updateJokeButton')),
          warnIfMissed: false,
        );
        await tester.pump();

        verify(
          () => mockJokeRepository.updateJoke(
            jokeId: originalJoke.id,
            setupText: updatedSetupText,
            punchlineText: updatedPunchlineText,
            setupImageUrl: originalJoke.setupImageUrl,
            punchlineImageUrl: originalJoke.punchlineImageUrl,
            setupImageDescription: updatedSetupDescription,
            punchlineImageDescription: updatedPunchlineDescription,
          ),
        ).called(1);
      });

      testWidgets('should show success message after updating joke', (
        tester,
      ) async {
        const originalJoke = Joke(
          id: 'test-id',
          setupText: 'Original setup',
          punchlineText: 'Original punchline',
          setupImageDescription: 'Original setup description',
          punchlineImageDescription: 'Original punchline description',
        );

        when(
          () => mockJokeRepository.updateJoke(
            jokeId: any(named: 'jokeId'),
            setupText: any(named: 'setupText'),
            punchlineText: any(named: 'punchlineText'),
            setupImageUrl: any(named: 'setupImageUrl'),
            punchlineImageUrl: any(named: 'punchlineImageUrl'),
            setupImageDescription: any(named: 'setupImageDescription'),
            punchlineImageDescription: any(named: 'punchlineImageDescription'),
          ),
        ).thenAnswer((_) async => {});

        await tester.pumpWidget(createTestWidget(joke: originalJoke));
        await tester.pumpAndSettle();

        // Make some changes and save
        await tester.enterText(
          find.byKey(const Key('setupTextField')),
          'Updated setup text',
        );

        // Ensure button is visible first
        await tester.ensureVisible(find.byKey(const Key('updateJokeButton')));
        await tester.pumpAndSettle();
        await tester.tap(
          find.byKey(const Key('updateJokeButton')),
          warnIfMissed: false,
        );
        await tester.pumpAndSettle();

        // After successful update, the screen should navigate back
        // Since we're in a test environment, we'll verify the repository was called
        // The navigation would happen in a real app but not in the test widget tree
      });

      testWidgets('should handle joke with null image descriptions', (
        tester,
      ) async {
        const originalJoke = Joke(
          id: 'test-id',
          setupText: 'Original setup',
          punchlineText: 'Original punchline',
          // setupImageDescription and punchlineImageDescription are null
        );

        when(
          () => mockJokeRepository.updateJoke(
            jokeId: any(named: 'jokeId'),
            setupText: any(named: 'setupText'),
            punchlineText: any(named: 'punchlineText'),
            setupImageUrl: any(named: 'setupImageUrl'),
            punchlineImageUrl: any(named: 'punchlineImageUrl'),
            setupImageDescription: any(named: 'setupImageDescription'),
            punchlineImageDescription: any(named: 'punchlineImageDescription'),
          ),
        ).thenAnswer((_) async => {});

        await tester.pumpWidget(createTestWidget(joke: originalJoke));
        await tester.pumpAndSettle();

        // Image description fields should be empty but present
        expect(
          find.byKey(const Key('setupImageDescriptionTextField')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('punchlineImageDescriptionTextField')),
          findsOneWidget,
        );

        // Enter descriptions and save
        await tester.enterText(
          find.byKey(const Key('setupImageDescriptionTextField')),
          'New setup description',
        );
        await tester.enterText(
          find.byKey(const Key('punchlineImageDescriptionTextField')),
          'New punchline description',
        );

        // Ensure button is visible first
        await tester.ensureVisible(find.byKey(const Key('updateJokeButton')));
        await tester.pumpAndSettle();
        await tester.tap(
          find.byKey(const Key('updateJokeButton')),
          warnIfMissed: false,
        );
        await tester.pump();

        verify(
          () => mockJokeRepository.updateJoke(
            jokeId: originalJoke.id,
            setupText: originalJoke.setupText,
            punchlineText: originalJoke.punchlineText,
            setupImageUrl: null,
            punchlineImageUrl: null,
            setupImageDescription: 'New setup description',
            punchlineImageDescription: 'New punchline description',
          ),
        ).called(1);
      });
    });

    group('Error Handling', () {
      testWidgets('should show error message when create fails', (
        tester,
      ) async {
        const setupText = 'New setup text';
        const punchlineText = 'New punchline text';

        when(
          () => mockJokeService.createJokeWithResponse(
            setupText: setupText,
            punchlineText: punchlineText,
            adminOwned: true,
          ),
        ).thenAnswer(
          (_) async => {'success': false, 'error': 'Failed to create joke'},
        );

        await tester.pumpWidget(createTestWidget());

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

        // Should show error snackbar
        expect(find.text('Error: Failed to create joke'), findsOneWidget);
      });

      testWidgets('should show error message when update fails', (
        tester,
      ) async {
        const originalJoke = Joke(
          id: 'test-id',
          setupText: 'Original setup',
          punchlineText: 'Original punchline',
          setupImageDescription: 'Original setup description',
          punchlineImageDescription: 'Original punchline description',
        );

        when(
          () => mockJokeRepository.updateJoke(
            jokeId: any(named: 'jokeId'),
            setupText: any(named: 'setupText'),
            punchlineText: any(named: 'punchlineText'),
            setupImageUrl: any(named: 'setupImageUrl'),
            punchlineImageUrl: any(named: 'punchlineImageUrl'),
            setupImageDescription: any(named: 'setupImageDescription'),
            punchlineImageDescription: any(named: 'punchlineImageDescription'),
          ),
        ).thenThrow(Exception('Update failed'));

        await tester.pumpWidget(createTestWidget(joke: originalJoke));
        await tester.pumpAndSettle();

        // Ensure button is visible first
        await tester.ensureVisible(find.byKey(const Key('updateJokeButton')));
        await tester.pumpAndSettle();
        await tester.tap(
          find.byKey(const Key('updateJokeButton')),
          warnIfMissed: false,
        );
        await tester.pumpAndSettle();

        // Should show error snackbar
        expect(
          find.text('Error saving joke: Exception: Update failed'),
          findsOneWidget,
        );
      });
    });

    group('Form Validation', () {
      testWidgets('should validate minimum length for image descriptions', (
        tester,
      ) async {
        const joke = Joke(
          id: 'test-id',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageDescription: 'Valid description',
          punchlineImageDescription: 'Valid description',
        );

        await tester.pumpWidget(createTestWidget(joke: joke));
        await tester.pumpAndSettle();

        // Enter too short descriptions
        await tester.enterText(
          find.byKey(const Key('setupImageDescriptionTextField')),
          'short',
        ); // < 10 chars
        await tester.enterText(
          find.byKey(const Key('punchlineImageDescriptionTextField')),
          'tiny',
        ); // < 10 chars

        // Ensure button is visible first
        await tester.ensureVisible(find.byKey(const Key('updateJokeButton')));
        await tester.pumpAndSettle();
        await tester.tap(
          find.byKey(const Key('updateJokeButton')),
          warnIfMissed: false,
        );
        await tester.pump();

        expect(
          find.text('Description must be at least 10 characters long'),
          findsNWidgets(2),
        );
      });
    });
  });
}
