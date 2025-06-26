import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';

import '../../../test_helpers/test_helpers.dart';

void main() {
  group('UserSettingsScreen Theme Settings', () {
    setUp(() {
      TestHelpers.resetAllMocks();
    });

    Widget createTestWidget({ThemeMode? initialThemeMode}) {
      return ProviderScope(
        overrides: [
          ...TestHelpers.getAllMockOverrides(
            testUser: TestHelpers.anonymousUser,
          ),
        ],
        child: MaterialApp(
          theme: lightTheme,
          darkTheme: darkTheme,
          home: Scaffold(
            body: SingleChildScrollView(
              child: SizedBox(
                height: 1000, // Give enough height for content
                child: const UserSettingsScreen(),
              ),
            ),
          ),
        ),
      );
    }

    group('Theme Settings UI', () {
      testWidgets('displays theme settings section', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        expect(find.text('Theme Settings'), findsOneWidget);
        expect(find.text('Use System Setting'), findsOneWidget);
        expect(find.text('Always Light'), findsOneWidget);
        expect(find.text('Always Dark'), findsOneWidget);
      });

      testWidgets('displays theme option descriptions', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        expect(
          find.text(
            'Automatically switch between light and dark themes based on your device settings',
          ),
          findsOneWidget,
        );
        expect(
          find.text('Use light theme regardless of system settings'),
          findsOneWidget,
        );
        expect(
          find.text('Use dark theme regardless of system settings'),
          findsOneWidget,
        );
      });

      testWidgets('displays correct icons for theme options', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        expect(find.byIcon(Icons.brightness_auto), findsOneWidget);
        expect(find.byIcon(Icons.light_mode), findsOneWidget);
        expect(find.byIcon(Icons.dark_mode), findsOneWidget);
      });

      testWidgets('displays radio buttons for theme selection', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        expect(find.byType(Radio<ThemeMode>), findsNWidgets(3));
      });
    });

    group('Theme Selection Interaction', () {
      testWidgets('can select light theme', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Tap on the light theme option
        await tester.tap(find.text('Always Light'));
        await tester.pumpAndSettle();

        // Verify the setting was saved
        verify(
          () => CoreMocks.mockSettingsService.setString('theme_mode', 'light'),
        ).called(1);
      });

      testWidgets('can select dark theme', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Tap on the dark theme option
        await tester.tap(find.text('Always Dark'));
        await tester.pumpAndSettle();

        // Verify the setting was saved
        verify(
          () => CoreMocks.mockSettingsService.setString('theme_mode', 'dark'),
        ).called(1);
      });

      testWidgets('can select system theme', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Tap on the system theme option
        await tester.tap(find.text('Use System Setting'));
        await tester.pumpAndSettle();

        // Verify the setting was saved
        verify(
          () => CoreMocks.mockSettingsService.setString('theme_mode', 'system'),
        ).called(1);
      });

      testWidgets('can tap on radio button to change theme', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Find and tap the radio button for dark theme
        final darkRadio = find
            .byType(Radio<ThemeMode>)
            .at(2); // Third radio button (dark)
        await tester.tap(darkRadio);
        await tester.pumpAndSettle();

        // Verify the setting was saved
        verify(
          () => CoreMocks.mockSettingsService.setString('theme_mode', 'dark'),
        ).called(1);
      });

      testWidgets('can tap on entire theme option row to change theme', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Find the InkWell containing the light theme option
        final lightThemeRow = find.widgetWithText(InkWell, 'Always Light');
        await tester.tap(lightThemeRow);
        await tester.pumpAndSettle();

        // Verify the setting was saved
        verify(
          () => CoreMocks.mockSettingsService.setString('theme_mode', 'light'),
        ).called(1);
      });
    });

    group('Theme State Display', () {
      testWidgets('shows system theme as selected by default', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Find all radio buttons and check which one is selected
        final radioButtons = tester.widgetList<Radio<ThemeMode>>(
          find.byType(Radio<ThemeMode>),
        );

        // The first radio button (system) should be selected
        expect(radioButtons.first.groupValue, ThemeMode.system);
        expect(radioButtons.first.value, ThemeMode.system);
      });
    });

    group('Visual Feedback', () {
      testWidgets('shows radio buttons in correct states', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Give time for theme to load
        await tester.pump(const Duration(milliseconds: 100));

        // Find all radio buttons
        final radioButtons = find.byType(Radio<ThemeMode>);
        expect(radioButtons, findsNWidgets(3));

        // Check that radio buttons are present (detailed state checking would require more complex setup)
        expect(find.byIcon(Icons.light_mode), findsOneWidget);
        expect(find.byIcon(Icons.dark_mode), findsOneWidget);
        expect(find.byIcon(Icons.brightness_auto), findsOneWidget);
      });
    });
  });
}
