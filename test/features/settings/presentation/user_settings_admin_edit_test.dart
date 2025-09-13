import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';

import '../../../test_helpers/test_helpers.dart';

class _MockAppUsageService extends Mock implements AppUsageService {}

void main() {
  setUpAll(() {
    registerAnalyticsFallbackValues();
  });

  group('UserSettingsScreen Edit Usage Metrics Dialog', () {
    late _MockAppUsageService mockUsage;

    setUp(() {
      TestHelpers.resetAllMocks();
      mockUsage = _MockAppUsageService();

      // Default getter stubs
      when(() => mockUsage.getFirstUsedDate()).thenAnswer((_) async => null);
      when(() => mockUsage.getLastUsedDate()).thenAnswer((_) async => null);
      when(() => mockUsage.getNumDaysUsed()).thenAnswer((_) async => 0);
      when(() => mockUsage.getNumJokesViewed()).thenAnswer((_) async => 0);
      when(() => mockUsage.getNumSavedJokes()).thenAnswer((_) async => 0);
      when(() => mockUsage.getNumSharedJokes()).thenAnswer((_) async => 0);

      // Setter stubs
      when(() => mockUsage.setFirstUsedDate(any())).thenAnswer((_) async {});
      when(() => mockUsage.setLastUsedDate(any())).thenAnswer((_) async {});
      when(() => mockUsage.setNumDaysUsed(any())).thenAnswer((_) async {});
      when(() => mockUsage.setNumJokesViewed(any())).thenAnswer((_) async {});
      when(() => mockUsage.setNumSavedJokes(any())).thenAnswer((_) async {});
      when(() => mockUsage.setNumSharedJokes(any())).thenAnswer((_) async {});
    });

    ProviderScope _buildApp({List<Override> extra = const []}) => ProviderScope(
      overrides: [
        ...TestHelpers.getAllMockOverrides(testUser: TestHelpers.adminUser),
        appUsageServiceProvider.overrideWithValue(mockUsage),
        ...extra,
      ],
      child: MaterialApp(
        theme: lightTheme,
        darkTheme: darkTheme,
        home: Scaffold(
          body: SingleChildScrollView(
            child: const SizedBox(height: 1200, child: UserSettingsScreen()),
          ),
        ),
      ),
    );

    Future<void> _enableDeveloperMode(WidgetTester tester) async {
      await tester.ensureVisible(find.text('Theme Settings'));
      await tester.pump();
      await tester.tap(find.text('Theme Settings'), warnIfMissed: false);
      await tester.pump(const Duration(milliseconds: 100));
      await tester.ensureVisible(find.text('Theme Settings'));
      await tester.pump();
      await tester.tap(find.text('Theme Settings'), warnIfMissed: false);
      await tester.pump(const Duration(milliseconds: 100));

      await tester.ensureVisible(find.text('Snickerdoodle v0.0.1+1'));
      await tester.pump();
      await tester.tap(
        find.text('Snickerdoodle v0.0.1+1'),
        warnIfMissed: false,
      );
      await tester.pump(const Duration(milliseconds: 100));
      await tester.ensureVisible(find.text('Snickerdoodle v0.0.1+1'));
      await tester.pump();
      await tester.tap(
        find.text('Snickerdoodle v0.0.1+1'),
        warnIfMissed: false,
      );
      await tester.pump(const Duration(milliseconds: 100));

      await tester.ensureVisible(find.text('Notifications'));
      await tester.pump();
      for (int i = 0; i < 4; i++) {
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
      }
      await tester.pumpAndSettle();
    }

    testWidgets('shows button in developer mode', (tester) async {
      await tester.pumpWidget(_buildApp());
      await tester.pumpAndSettle();

      await _enableDeveloperMode(tester);

      // Allow FutureBuilder to resolve
      await tester.pump(const Duration(milliseconds: 50));

      expect(
        find.byKey(const Key('edit-usage-metrics-button')),
        findsOneWidget,
      );
    });

    testWidgets('prefills dialog fields from current values', (tester) async {
      // Stub current values
      when(
        () => mockUsage.getFirstUsedDate(),
      ).thenAnswer((_) async => '2024-01-01');
      when(
        () => mockUsage.getLastUsedDate(),
      ).thenAnswer((_) async => '2024-12-31');
      when(() => mockUsage.getNumDaysUsed()).thenAnswer((_) async => 12);
      when(() => mockUsage.getNumJokesViewed()).thenAnswer((_) async => 34);
      when(() => mockUsage.getNumSavedJokes()).thenAnswer((_) async => 5);
      when(() => mockUsage.getNumSharedJokes()).thenAnswer((_) async => 7);

      await tester.pumpWidget(_buildApp());
      await tester.pumpAndSettle();

      await _enableDeveloperMode(tester);

      final editBtn = find.byKey(const Key('edit-usage-metrics-button'));
      await tester.ensureVisible(editBtn);
      await tester.pump();
      await tester.tap(editBtn, warnIfMissed: false);
      await tester.pumpAndSettle();

      final firstField = tester.widget<TextField>(
        find.byKey(const Key('edit-first-used')),
      );
      final lastField = tester.widget<TextField>(
        find.byKey(const Key('edit-last-used')),
      );
      final daysField = tester.widget<TextField>(
        find.byKey(const Key('edit-num-days-used')),
      );
      final viewedField = tester.widget<TextField>(
        find.byKey(const Key('edit-num-viewed')),
      );
      final savedField = tester.widget<TextField>(
        find.byKey(const Key('edit-num-saved')),
      );
      final sharedField = tester.widget<TextField>(
        find.byKey(const Key('edit-num-shared')),
      );

      expect(firstField.controller!.text, '2024-01-01');
      expect(lastField.controller!.text, '2024-12-31');
      expect(daysField.controller!.text, '12');
      expect(viewedField.controller!.text, '34');
      expect(savedField.controller!.text, '5');
      expect(sharedField.controller!.text, '7');
    });

    testWidgets('submit calls setters with entered values', (tester) async {
      await tester.pumpWidget(_buildApp());
      await tester.pumpAndSettle();

      await _enableDeveloperMode(tester);

      final editBtn = find.byKey(const Key('edit-usage-metrics-button'));
      await tester.ensureVisible(editBtn);
      await tester.pump();
      await tester.tap(editBtn, warnIfMissed: false);
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('edit-first-used')),
        '2025-01-02',
      );
      await tester.enterText(
        find.byKey(const Key('edit-last-used')),
        '2025-09-13',
      );
      await tester.enterText(find.byKey(const Key('edit-num-days-used')), '21');
      await tester.enterText(find.byKey(const Key('edit-num-viewed')), '100');
      await tester.enterText(find.byKey(const Key('edit-num-saved')), '8');
      await tester.enterText(find.byKey(const Key('edit-num-shared')), '9');

      await tester.tap(find.byKey(const Key('edit-usage-submit')));
      await tester.pumpAndSettle();

      verify(() => mockUsage.setFirstUsedDate('2025-01-02')).called(1);
      verify(() => mockUsage.setLastUsedDate('2025-09-13')).called(1);
      verify(() => mockUsage.setNumDaysUsed(21)).called(1);
      verify(() => mockUsage.setNumJokesViewed(100)).called(1);
      verify(() => mockUsage.setNumSavedJokes(8)).called(1);
      verify(() => mockUsage.setNumSharedJokes(9)).called(1);
    });

    testWidgets('cancel does not call setters', (tester) async {
      await tester.pumpWidget(_buildApp());
      await tester.pumpAndSettle();

      await _enableDeveloperMode(tester);

      final editBtn = find.byKey(const Key('edit-usage-metrics-button'));
      await tester.ensureVisible(editBtn);
      await tester.pump();
      await tester.tap(editBtn, warnIfMissed: false);
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('edit-usage-cancel')));
      await tester.pumpAndSettle();

      verifyNever(() => mockUsage.setFirstUsedDate(any()));
      verifyNever(() => mockUsage.setLastUsedDate(any()));
      verifyNever(() => mockUsage.setNumDaysUsed(any()));
      verifyNever(() => mockUsage.setNumJokesViewed(any()));
      verifyNever(() => mockUsage.setNumSavedJokes(any()));
      verifyNever(() => mockUsage.setNumSharedJokes(any()));
    });
  });
}
