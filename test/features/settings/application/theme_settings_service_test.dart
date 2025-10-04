import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';
import 'package:snickerdoodle/src/features/settings/application/theme_settings_service.dart';

// Mock class for SettingsService
class MockSettingsService extends Mock implements SettingsService {}

void main() {
  group('ThemeSettingsService', () {
    late MockSettingsService mockSettingsService;
    late ThemeSettingsService themeSettingsService;

    setUp(() {
      mockSettingsService = MockSettingsService();
      themeSettingsService = ThemeSettingsService(mockSettingsService);
    });

    group('getThemeMode', () {
      test('returns ThemeMode.system when no preference is stored', () async {
        when(
          () => mockSettingsService.getString('theme_mode'),
        ).thenReturn(null);

        final result = await themeSettingsService.getThemeMode();

        expect(result, ThemeMode.system);
        verify(() => mockSettingsService.getString('theme_mode')).called(1);
      });

      test('returns ThemeMode.light when light preference is stored', () async {
        when(
          () => mockSettingsService.getString('theme_mode'),
        ).thenReturn('light');

        final result = await themeSettingsService.getThemeMode();

        expect(result, ThemeMode.light);
        verify(() => mockSettingsService.getString('theme_mode')).called(1);
      });

      test('returns ThemeMode.dark when dark preference is stored', () async {
        when(
          () => mockSettingsService.getString('theme_mode'),
        ).thenReturn('dark');

        final result = await themeSettingsService.getThemeMode();

        expect(result, ThemeMode.dark);
        verify(() => mockSettingsService.getString('theme_mode')).called(1);
      });

      test(
        'returns ThemeMode.system when system preference is stored',
        () async {
          when(
            () => mockSettingsService.getString('theme_mode'),
          ).thenReturn('system');

          final result = await themeSettingsService.getThemeMode();

          expect(result, ThemeMode.system);
          verify(() => mockSettingsService.getString('theme_mode')).called(1);
        },
      );

      test('returns ThemeMode.system for invalid preference string', () async {
        when(
          () => mockSettingsService.getString('theme_mode'),
        ).thenReturn('invalid_theme_mode');

        final result = await themeSettingsService.getThemeMode();

        expect(result, ThemeMode.system);
        verify(() => mockSettingsService.getString('theme_mode')).called(1);
      });
    });

    group('setThemeMode', () {
      test('stores light theme mode preference', () async {
        when(
          () => mockSettingsService.setString('theme_mode', 'light'),
        ).thenAnswer((_) async => {});

        await themeSettingsService.setThemeMode(ThemeMode.light);

        verify(
          () => mockSettingsService.setString('theme_mode', 'light'),
        ).called(1);
      });

      test('stores dark theme mode preference', () async {
        when(
          () => mockSettingsService.setString('theme_mode', 'dark'),
        ).thenAnswer((_) async => {});

        await themeSettingsService.setThemeMode(ThemeMode.dark);

        verify(
          () => mockSettingsService.setString('theme_mode', 'dark'),
        ).called(1);
      });

      test('stores system theme mode preference', () async {
        when(
          () => mockSettingsService.setString('theme_mode', 'system'),
        ).thenAnswer((_) async => {});

        await themeSettingsService.setThemeMode(ThemeMode.system);

        verify(
          () => mockSettingsService.setString('theme_mode', 'system'),
        ).called(1);
      });
    });
  });

  group('ThemeModeNotifier', () {
    late MockSettingsService mockSettingsService;
    late ThemeSettingsService themeSettingsService;
    late ProviderContainer container;

    setUp(() {
      mockSettingsService = MockSettingsService();
      themeSettingsService = ThemeSettingsService(mockSettingsService);

      container = ProviderContainer(
        overrides: [
          settingsServiceProvider.overrideWithValue(mockSettingsService),
          themeSettingsServiceProvider.overrideWithValue(themeSettingsService),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    group('initialization', () {
      test('loads saved theme mode on initialization', () async {
        when(
          () => mockSettingsService.getString('theme_mode'),
        ).thenReturn('dark');

        container.read(themeModeProvider.notifier);

        // Wait for initialization to complete
        await Future.delayed(Duration.zero);

        expect(container.read(themeModeProvider), ThemeMode.dark);
        verify(() => mockSettingsService.getString('theme_mode')).called(1);
      });

      test('defaults to system theme when no preference is saved', () async {
        when(
          () => mockSettingsService.getString('theme_mode'),
        ).thenReturn(null);

        container.read(themeModeProvider.notifier);

        // Wait for initialization to complete
        await Future.delayed(Duration.zero);

        expect(container.read(themeModeProvider), ThemeMode.system);
        verify(() => mockSettingsService.getString('theme_mode')).called(1);
      });
    });

    group('setThemeMode', () {
      test(
        'updates state and saves preference when theme mode changes',
        () async {
          when(
            () => mockSettingsService.getString('theme_mode'),
          ).thenReturn(null);
          when(
            () => mockSettingsService.setString('theme_mode', 'light'),
          ).thenAnswer((_) async => {});

          final notifier = container.read(themeModeProvider.notifier);

          // Wait for initialization
          await Future.delayed(Duration.zero);

          // Change theme mode
          await notifier.setThemeMode(ThemeMode.light);

          expect(container.read(themeModeProvider), ThemeMode.light);
          verify(
            () => mockSettingsService.setString('theme_mode', 'light'),
          ).called(1);
        },
      );

      test('can switch between all theme modes', () async {
        when(
          () => mockSettingsService.getString('theme_mode'),
        ).thenReturn(null);
        when(
          () => mockSettingsService.setString(any(), any()),
        ).thenAnswer((_) async => {});

        final notifier = container.read(themeModeProvider.notifier);

        // Wait for initialization
        await Future.delayed(Duration.zero);

        // Test switching to light
        await notifier.setThemeMode(ThemeMode.light);
        expect(container.read(themeModeProvider), ThemeMode.light);

        // Test switching to dark
        await notifier.setThemeMode(ThemeMode.dark);
        expect(container.read(themeModeProvider), ThemeMode.dark);

        // Test switching back to system
        await notifier.setThemeMode(ThemeMode.system);
        expect(container.read(themeModeProvider), ThemeMode.system);

        verify(
          () => mockSettingsService.setString('theme_mode', 'light'),
        ).called(1);
        verify(
          () => mockSettingsService.setString('theme_mode', 'dark'),
        ).called(1);
        verify(
          () => mockSettingsService.setString('theme_mode', 'system'),
        ).called(1);
      });
    });
  });
}
