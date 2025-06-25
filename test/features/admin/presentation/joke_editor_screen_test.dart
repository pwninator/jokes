import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_editor_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

import '../../../test_helpers/firebase_mocks.dart';

// Mock classes using mocktail
class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

void main() {
  group('JokeEditorScreen', () {
    late MockJokeCloudFunctionService mockJokeService;

    setUp(() {
      FirebaseMocks.reset();
      mockJokeService = MockJokeCloudFunctionService();
    });

    Widget createTestWidget({Joke? joke}) {
      return ProviderScope(
        overrides: [
          ...FirebaseMocks.getFirebaseProviderOverrides(),
          jokeCloudFunctionServiceProvider.overrideWithValue(mockJokeService),
        ],
        child: MaterialApp(
          theme: lightTheme,
          home: JokeEditorScreen(joke: joke),
        ),
      );
    }

    group('UI Rendering', () {
      testWidgets('should display create mode UI when no joke is provided', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());

        expect(find.text('Add New Joke'), findsOneWidget);
        expect(
          find.text(
            'Create a new joke by filling out the setup and punchline below:',
          ),
          findsOneWidget,
        );
        expect(find.text('Setup'), findsOneWidget);
        expect(find.text('Punchline'), findsOneWidget);
        expect(find.text('Save Joke'), findsOneWidget);
        expect(find.byType(TextFormField), findsNWidgets(2));
      });

      testWidgets('should display edit mode UI when joke is provided', (
        tester,
      ) async {
        const joke = Joke(
          id: 'test-id',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
        );

        await tester.pumpWidget(createTestWidget(joke: joke));

        expect(find.text('Edit Joke'), findsOneWidget);
        expect(
          find.text('Edit the joke setup and punchline below:'),
          findsOneWidget,
        );
        expect(find.text('Test setup'), findsOneWidget);
        expect(find.text('Test punchline'), findsOneWidget);
        expect(find.text('Update Joke'), findsOneWidget);
      });

      testWidgets('should display form validation errors', (tester) async {
        await tester.pumpWidget(createTestWidget());

        // Try to save without entering text
        await tester.tap(find.text('Save Joke'));
        await tester.pump();

        expect(find.text('Please enter a setup for the joke'), findsOneWidget);
        expect(
          find.text('Please enter a punchline for the joke'),
          findsOneWidget,
        );
      });
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
          ),
        ).thenAnswer(
          (_) async => {
            'success': true,
            'data': {'jokeId': 'new-joke-id'},
          },
        );

        await tester.pumpWidget(createTestWidget());

        // Enter text in form fields
        await tester.enterText(find.byType(TextFormField).first, setupText);
        await tester.enterText(find.byType(TextFormField).last, punchlineText);

        // Tap save
        await tester.tap(find.text('Save Joke'));
        await tester.pump();

        verify(
          () => mockJokeService.createJokeWithResponse(
            setupText: setupText,
            punchlineText: punchlineText,
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
          ),
        ).thenAnswer(
          (_) async => {
            'success': true,
            'data': {'jokeId': 'new-joke-id'},
          },
        );

        await tester.pumpWidget(createTestWidget());

        await tester.enterText(find.byType(TextFormField).first, setupText);
        await tester.enterText(find.byType(TextFormField).last, punchlineText);

        await tester.tap(find.text('Save Joke'));
        await tester.pumpAndSettle();

        // Should show success snackbar
        expect(find.text('Joke saved successfully!'), findsOneWidget);
      });
    });

    group('Update Joke', () {
      testWidgets('should call updateJoke on save button tap', (tester) async {
        const originalJoke = Joke(
          id: 'test-id',
          setupText: 'Original setup',
          punchlineText: 'Original punchline',
        );

        const updatedSetupText = 'Updated setup text';
        const updatedPunchlineText = 'Updated punchline text';

        when(
          () => mockJokeService.updateJoke(
            jokeId: originalJoke.id,
            setupText: updatedSetupText,
            punchlineText: updatedPunchlineText,
            setupImageUrl: null,
            punchlineImageUrl: null,
          ),
        ).thenAnswer(
          (_) async => {
            'success': true,
            'data': {'message': 'Updated successfully'},
          },
        );

        await tester.pumpWidget(createTestWidget(joke: originalJoke));

        // Clear and enter new text
        await tester.enterText(
          find.byType(TextFormField).first,
          updatedSetupText,
        );
        await tester.enterText(
          find.byType(TextFormField).last,
          updatedPunchlineText,
        );

        await tester.tap(find.text('Update Joke'));
        await tester.pump();

        verify(
          () => mockJokeService.updateJoke(
            jokeId: originalJoke.id,
            setupText: updatedSetupText,
            punchlineText: updatedPunchlineText,
            setupImageUrl: null,
            punchlineImageUrl: null,
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
        );

        when(
          () => mockJokeService.updateJoke(
            jokeId: originalJoke.id,
            setupText: any(named: 'setupText'),
            punchlineText: any(named: 'punchlineText'),
            setupImageUrl: any(named: 'setupImageUrl'),
            punchlineImageUrl: any(named: 'punchlineImageUrl'),
          ),
        ).thenAnswer(
          (_) async => {
            'success': true,
            'data': {'message': 'Updated successfully'},
          },
        );

        await tester.pumpWidget(createTestWidget(joke: originalJoke));

        // Make some changes and save
        await tester.enterText(
          find.byType(TextFormField).first,
          'Updated setup text',
        );

        await tester.tap(find.text('Update Joke'));
        await tester
            .pump(); // Don't use pumpAndSettle as the screen may navigate away

        // Should show success snackbar (briefly, before navigation)
        expect(find.text('Joke updated successfully!'), findsOneWidget);
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
          ),
        ).thenAnswer(
          (_) async => {'success': false, 'error': 'Failed to create joke'},
        );

        await tester.pumpWidget(createTestWidget());

        await tester.enterText(find.byType(TextFormField).first, setupText);
        await tester.enterText(find.byType(TextFormField).last, punchlineText);

        await tester.tap(find.text('Save Joke'));
        await tester.pumpAndSettle();

        // Should show error snackbar
        expect(find.text('Error: Failed to create joke'), findsOneWidget);
      });
    });
  });
}
