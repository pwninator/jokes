import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_creator_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';

import '../../../test_helpers/firebase_mocks.dart';

void main() {
  group('JokeCreatorScreen', () {
    setUp(() {
      FirebaseMocks.reset();
    });

    Widget createTestWidget() {
      return ProviderScope(
        overrides: FirebaseMocks.getFirebaseProviderOverrides(),
        child: const MaterialApp(
          home: JokeCreatorScreen(),
        ),
      );
    }

    group('UI Elements', () {
      testWidgets('should display all required UI elements', (tester) async {
        await tester.pumpWidget(createTestWidget());

        // Check for app bar
        expect(find.text('Joke Creator'), findsOneWidget);

        // Check for instructions
        expect(
          find.text('Enter instructions for joke generation and critique:'),
          findsOneWidget,
        );

        // Check for text field
        expect(find.byType(TextFormField), findsOneWidget);
        expect(
          find.text('Enter detailed instructions for the AI to generate and critique jokes...'),
          findsOneWidget,
        );

        // Check for generate button
        expect(find.text('Generate'), findsOneWidget);

        // Check for info text
        expect(
          find.text('The AI will generate and critique jokes based on your instructions.'),
          findsOneWidget,
        );
      });

      testWidgets('should show form validation error for empty instructions', (tester) async {
        await tester.pumpWidget(createTestWidget());

        // Tap generate button without entering instructions
        await tester.tap(find.text('Generate'));
        await tester.pump();

        // Check for validation error
        expect(
          find.text('Please enter instructions for joke generation'),
          findsOneWidget,
        );
      });

      testWidgets('should show form validation error for short instructions', (tester) async {
        await tester.pumpWidget(createTestWidget());

        // Enter very short instructions
        await tester.enterText(find.byType(TextFormField), 'short');
        await tester.tap(find.text('Generate'));
        await tester.pump();

        // Check for validation error
        expect(
          find.text('Instructions must be at least 10 characters long'),
          findsOneWidget,
        );
      });
    });

    group('Joke Generation', () {
      testWidgets('should show loading state during generation', (tester) async {
        // Setup mock to delay response
        final mockService = FirebaseMocks.mockCloudFunctionService;
        when(mockService.critiqueJokes(
          instructions: anyNamed('instructions'),
        )).thenAnswer((_) async {
          await Future.delayed(const Duration(milliseconds: 100));
          return {'success': true, 'data': {'jokes': []}};
        });

        await tester.pumpWidget(createTestWidget());

        // Enter valid instructions
        await tester.enterText(
          find.byType(TextFormField),
          'Generate some funny jokes about programming',
        );

        // Tap generate button
        await tester.tap(find.text('Generate'));
        await tester.pump();

        // Check for loading indicator
        expect(find.byType(CircularProgressIndicator), findsOneWidget);

        // Check that button is disabled
        final button = tester.widget<ElevatedButton>(
          find.byType(ElevatedButton),
        );
        expect(button.onPressed, isNull);

        // Wait for completion
        await tester.pumpAndSettle();
      });

      testWidgets('should call cloud function service with correct parameters', (tester) async {
        const instructions = 'Generate some funny jokes about programming';
        
        final mockService = FirebaseMocks.mockCloudFunctionService;
        when(mockService.critiqueJokes(
          instructions: instructions,
        )).thenAnswer((_) async => {'success': true, 'data': {'jokes': []}});

        await tester.pumpWidget(createTestWidget());

        // Enter instructions
        await tester.enterText(find.byType(TextFormField), instructions);

        // Tap generate button
        await tester.tap(find.text('Generate'));
        await tester.pumpAndSettle();

        // Verify cloud function was called
        verify(mockService.critiqueJokes(
          instructions: instructions,
        )).called(1);
      });

      testWidgets('should display success message and results on successful generation', (tester) async {
        const instructions = 'Generate some funny jokes';
        const mockData = {
          'jokes': [
            {'setup': 'Why did the programmer quit?', 'punchline': 'Because they didn\'t get arrays!'}
          ]
        };

        final mockService = FirebaseMocks.mockCloudFunctionService;
        when(mockService.critiqueJokes(
          instructions: instructions,
        )).thenAnswer((_) async => {'success': true, 'data': mockData});

        await tester.pumpWidget(createTestWidget());

        // Enter instructions and generate
        await tester.enterText(find.byType(TextFormField), instructions);
        await tester.tap(find.text('Generate'));
        await tester.pumpAndSettle();

        // Check for success message
        expect(find.text('Jokes generated successfully!'), findsOneWidget);

        // Check for results section
        expect(find.text('Generation Results:'), findsOneWidget);
        expect(find.text('Generation Successful'), findsOneWidget);
        expect(find.byIcon(Icons.check_circle), findsOneWidget);
      });

      testWidgets('should display error message on failed generation', (tester) async {
        const instructions = 'Generate some funny jokes';
        const errorMessage = 'Failed to generate jokes';

        final mockService = FirebaseMocks.mockCloudFunctionService;
        when(mockService.critiqueJokes(
          instructions: instructions,
        )).thenAnswer((_) async => {'success': false, 'error': errorMessage});

        await tester.pumpWidget(createTestWidget());

        // Enter instructions and generate
        await tester.enterText(find.byType(TextFormField), instructions);
        await tester.tap(find.text('Generate'));
        await tester.pumpAndSettle();

        // Check for error message in snackbar
        expect(find.text('Error: $errorMessage'), findsOneWidget);

        // Check for error in results section
        expect(find.text('Generation Failed'), findsOneWidget);
        expect(find.byIcon(Icons.error), findsOneWidget);
      });

      testWidgets('should handle service exception gracefully', (tester) async {
        const instructions = 'Generate some funny jokes';

        final mockService = FirebaseMocks.mockCloudFunctionService;
        when(mockService.critiqueJokes(
          instructions: instructions,
        )).thenThrow(Exception('Network error'));

        await tester.pumpWidget(createTestWidget());

        // Enter instructions and generate
        await tester.enterText(find.byType(TextFormField), instructions);
        await tester.tap(find.text('Generate'));
        await tester.pumpAndSettle();

        // Check for error handling
        expect(find.textContaining('Error generating jokes'), findsOneWidget);
        expect(find.text('Generation Failed'), findsOneWidget);
      });
    });

    group('Results Display', () {
      testWidgets('should display response data in formatted container', (tester) async {
        const instructions = 'Generate jokes';
        const mockData = {'result': 'test data', 'count': 5};

        final mockService = FirebaseMocks.mockCloudFunctionService;
        when(mockService.critiqueJokes(
          instructions: instructions,
        )).thenAnswer((_) async => {'success': true, 'data': mockData});

        await tester.pumpWidget(createTestWidget());

        // Generate results
        await tester.enterText(find.byType(TextFormField), instructions);
        await tester.tap(find.text('Generate'));
        await tester.pumpAndSettle();

        // Check for formatted results
        expect(find.text('Response Data:'), findsOneWidget);
        expect(find.textContaining('result'), findsOneWidget);
        expect(find.textContaining('test data'), findsOneWidget);
      });

      testWidgets('should handle null response data', (tester) async {
        const instructions = 'Generate jokes';

        final mockService = FirebaseMocks.mockCloudFunctionService;
        when(mockService.critiqueJokes(
          instructions: instructions,
        )).thenAnswer((_) async => {'success': true, 'data': null});

        await tester.pumpWidget(createTestWidget());

        // Generate results
        await tester.enterText(find.byType(TextFormField), instructions);
        await tester.tap(find.text('Generate'));
        await tester.pumpAndSettle();

        // Check for null data handling
        expect(find.text('No data received'), findsOneWidget);
      });

      testWidgets('should clear previous results when generating new ones', (tester) async {
        const instructions = 'Generate jokes';

        final mockService = FirebaseMocks.mockCloudFunctionService;
        // First successful generation
        when(mockService.critiqueJokes(
          instructions: instructions,
        )).thenAnswer((_) async => {'success': true, 'data': {'first': 'result'}});

        await tester.pumpWidget(createTestWidget());

        await tester.enterText(find.byType(TextFormField), instructions);
        await tester.tap(find.text('Generate'));
        await tester.pumpAndSettle();

        expect(find.text('Generation Results:'), findsOneWidget);

        // Second generation with different result
        when(mockService.critiqueJokes(
          instructions: instructions,
        )).thenAnswer((_) async => {'success': true, 'data': {'second': 'result'}});

        await tester.tap(find.text('Generate'));
        await tester.pumpAndSettle();

        // Should show new results
        expect(find.textContaining('second'), findsOneWidget);
        expect(find.textContaining('first'), findsNothing);
      });
    });
  });
} 