import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/annotations.dart';
import 'package:mockito/mockito.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_editor_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

import 'joke_editor_screen_test.mocks.dart';

@GenerateMocks([JokeCloudFunctionService])
void main() {
  group('JokeEditorScreen', () {
    late MockJokeCloudFunctionService mockJokeService;

    setUp(() {
      mockJokeService = MockJokeCloudFunctionService();
    });

    Widget createTestWidget({Joke? joke}) {
      return ProviderScope(
        overrides: [
          jokeCloudFunctionServiceProvider.overrideWithValue(mockJokeService),
        ],
        child: MaterialApp(
          theme: lightTheme,
          home: JokeEditorScreen(joke: joke),
        ),
      );
    }

    testWidgets('displays correct title for create mode', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            jokeCloudFunctionServiceProvider.overrideWithValue(mockJokeService),
          ],
          child: MaterialApp(
            theme: lightTheme,
            home: const JokeEditorScreen(),
          ),
        ),
      );

      expect(find.text('Add New Joke'), findsOneWidget);
      expect(find.text('Create a new joke by filling out the setup and punchline below:'), findsOneWidget);
      expect(find.text('Save Joke'), findsOneWidget);
    });

    testWidgets('displays correct title for edit mode', (tester) async {
      const joke = Joke(
        id: 'test-id',
        setupText: 'Test setup',
        punchlineText: 'Test punchline',
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            jokeCloudFunctionServiceProvider.overrideWithValue(mockJokeService),
          ],
          child: MaterialApp(
            theme: lightTheme,
            home: const JokeEditorScreen(joke: joke),
          ),
        ),
      );

      expect(find.text('Edit Joke'), findsOneWidget);
      expect(find.text('Edit the joke setup and punchline below:'), findsOneWidget);
      expect(find.text('Update Joke'), findsOneWidget);
    });

    testWidgets('pre-populates fields in edit mode', (tester) async {
      const joke = Joke(
        id: 'test-id',
        setupText: 'Test setup',
        punchlineText: 'Test punchline',
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            jokeCloudFunctionServiceProvider.overrideWithValue(mockJokeService),
          ],
          child: MaterialApp(
            theme: lightTheme,
            home: const JokeEditorScreen(joke: joke),
          ),
        ),
      );

      expect(find.text('Test setup'), findsOneWidget);
      expect(find.text('Test punchline'), findsOneWidget);
    });

    testWidgets('validates form fields', (tester) async {
      await tester.pumpWidget(createTestWidget());

      // Try to save without filling fields
      await tester.tap(find.text('Save Joke'));
      await tester.pump();

      expect(find.text('Please enter a setup for the joke'), findsOneWidget);
      expect(find.text('Please enter a punchline for the joke'), findsOneWidget);
    });

    testWidgets('validates minimum field length', (tester) async {
      await tester.pumpWidget(createTestWidget());

      // Enter short text
      await tester.enterText(find.byType(TextFormField).first, 'Hi');
      await tester.enterText(find.byType(TextFormField).last, 'Ha');
      await tester.tap(find.text('Save Joke'));
      await tester.pump();

      expect(find.text('Setup must be at least 5 characters long'), findsOneWidget);
      expect(find.text('Punchline must be at least 5 characters long'), findsOneWidget);
    });

    group('Create Mode', () {
      testWidgets('creates joke successfully and clears form', (tester) async {
        when(mockJokeService.createJokeWithResponse(
          setupText: 'Why did the chicken cross the road?',
          punchlineText: 'To get to the other side!',
        )).thenAnswer((_) async => {'success': true, 'data': {}});

        await tester.pumpWidget(createTestWidget());

        // Fill form
        await tester.enterText(find.byType(TextFormField).first, 'Why did the chicken cross the road?');
        await tester.enterText(find.byType(TextFormField).last, 'To get to the other side!');

        // Save joke
        await tester.tap(find.text('Save Joke'));
        await tester.pump();

        // Verify service was called
        verify(mockJokeService.createJokeWithResponse(
          setupText: 'Why did the chicken cross the road?',
          punchlineText: 'To get to the other side!',
        )).called(1);

        // Wait for async operations
        await tester.pump();

        // Verify success message
        expect(find.text('Joke saved successfully!'), findsOneWidget);

        // Verify form was cleared
        final setupField = tester.widget<TextFormField>(find.byType(TextFormField).first);
        final punchlineField = tester.widget<TextFormField>(find.byType(TextFormField).last);
        expect(setupField.controller?.text, isEmpty);
        expect(punchlineField.controller?.text, isEmpty);
      });

      testWidgets('handles create error', (tester) async {
        when(mockJokeService.createJokeWithResponse(
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
        )).thenAnswer((_) async => {'success': false, 'error': 'Test error message'});

        await tester.pumpWidget(createTestWidget());

        // Fill form
        await tester.enterText(find.byType(TextFormField).first, 'Test setup');
        await tester.enterText(find.byType(TextFormField).last, 'Test punchline');

        // Save joke
        await tester.tap(find.text('Save Joke'));
        await tester.pump();
        await tester.pump();

        // Verify error message
        expect(find.text('Error: Test error message'), findsOneWidget);
      });
    });

    group('Edit Mode', () {
      testWidgets('updates joke successfully and navigates back', (tester) async {
        const joke = Joke(
          id: 'test-id',
          setupText: 'Original setup',
          punchlineText: 'Original punchline',
          setupImageUrl: 'setup.jpg',
          punchlineImageUrl: 'punchline.jpg',
        );

        when(mockJokeService.updateJoke(
          jokeId: 'test-id',
          setupText: 'Updated setup',
          punchlineText: 'Updated punchline',
          setupImageUrl: 'setup.jpg',
          punchlineImageUrl: 'punchline.jpg',
        )).thenAnswer((_) async => {'success': true, 'data': {}});

        await tester.pumpWidget(createTestWidget(joke: joke));

        // Update form
        await tester.enterText(find.byType(TextFormField).first, 'Updated setup');
        await tester.enterText(find.byType(TextFormField).last, 'Updated punchline');

        // Update joke
        await tester.tap(find.text('Update Joke'));
        await tester.pump();

        // Verify service was called
        verify(mockJokeService.updateJoke(
          jokeId: 'test-id',
          setupText: 'Updated setup',
          punchlineText: 'Updated punchline',
          setupImageUrl: 'setup.jpg',
          punchlineImageUrl: 'punchline.jpg',
        )).called(1);

        // Wait for async operations
        await tester.pump();

        // Verify success message
        expect(find.text('Joke updated successfully!'), findsOneWidget);
      });

      testWidgets('handles update error', (tester) async {
        const joke = Joke(
          id: 'test-id',
          setupText: 'Original setup',
          punchlineText: 'Original punchline',
        );

        when(mockJokeService.updateJoke(
          jokeId: 'test-id',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageUrl: null,
          punchlineImageUrl: null,
        )).thenAnswer((_) async => {'success': false, 'error': 'Update failed'});

        await tester.pumpWidget(createTestWidget(joke: joke));

        // Update form
        await tester.enterText(find.byType(TextFormField).first, 'Test setup');
        await tester.enterText(find.byType(TextFormField).last, 'Test punchline');

        // Update joke
        await tester.tap(find.text('Update Joke'));
        await tester.pump();
        await tester.pump();

        // Verify error message
        expect(find.text('Error: Update failed'), findsOneWidget);
      });
    });

    testWidgets('shows loading state when saving', (tester) async {
      // Create a completer to control when the mock returns
      final completer = Completer<Map<String, dynamic>>();
      when(mockJokeService.createJokeWithResponse(
        setupText: 'Test setup',
        punchlineText: 'Test punchline',
      )).thenAnswer((_) => completer.future);

      await tester.pumpWidget(createTestWidget());

      // Fill form
      await tester.enterText(find.byType(TextFormField).first, 'Test setup');
      await tester.enterText(find.byType(TextFormField).last, 'Test punchline');

      // Save joke
      await tester.tap(find.text('Save Joke'));
      await tester.pump(); // Trigger the async operation

      // Verify loading state (before async operation completes)
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Save Joke'), findsNothing);

      // Complete the async operation
      completer.complete({'success': true, 'data': {}});
      await tester.pump();
      await tester.pump();

      // Verify loading state is gone
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });
  });
} 