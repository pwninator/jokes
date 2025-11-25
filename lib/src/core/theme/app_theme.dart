import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

const Color primaryColor = Color(0xFFB8860B); // Warm golden sugar cookie
const Color accentColor = Color(0xFF1976D2); // Complementary blue
const Color secondaryAccent = Color(0xFF42A5F5); // Lighter blue accent

ColorScheme lightColorScheme = ColorScheme.fromSeed(
  brightness: Brightness.light,
  dynamicSchemeVariant: DynamicSchemeVariant.content,
  seedColor: Color.fromARGB(255, 243, 179, 51),
  primary: Color.fromARGB(255, 198, 109, 0),
  secondaryContainer: Color.fromARGB(255, 227, 215, 190),
  // tertiary: Color.fromARGB(255, 82, 134, 254),
  // onTertiary: Colors.white,
  // tertiaryContainer: Color.fromARGB(255, 154, 127, 250),
  // onTertiaryContainer: Colors.white,
  error: Color.fromARGB(255, 198, 41, 41),
);

ColorScheme darkColorScheme = ColorScheme.fromSeed(
  brightness: Brightness.dark,
  dynamicSchemeVariant: DynamicSchemeVariant.content,
  seedColor: Color.fromARGB(255, 229, 156, 72),
  // tertiary: Color.fromARGB(255, 128, 166, 255),
  // onTertiary: Colors.white,
  // tertiaryContainer: Color.fromARGB(255, 154, 127, 250),
  // onTertiaryContainer: Colors.white,
  error: Color.fromARGB(255, 198, 41, 41),
);

final TextTheme textTheme = GoogleFonts.nunitoTextTheme(const TextTheme());

const AppBarTheme appBarTheme = AppBarTheme(
  backgroundColor: Colors.transparent,
  elevation: 0,
);

const double buttonRadius = 64;

ElevatedButtonThemeData buildElevatedButtonTheme(ColorScheme colorScheme) {
  return ElevatedButtonThemeData(
    style: ElevatedButton.styleFrom(
      backgroundColor: colorScheme.primaryContainer,
      foregroundColor: colorScheme.onPrimaryContainer,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(buttonRadius),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
    ),
  );
}

OutlinedButtonThemeData buildOutlinedButtonTheme(ColorScheme colorScheme) {
  return OutlinedButtonThemeData(
    style: OutlinedButton.styleFrom(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(buttonRadius),
      ),
    ),
  );
}

TextButtonThemeData buildTextButtonTheme(ColorScheme colorScheme) {
  return TextButtonThemeData(
    style: TextButton.styleFrom(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(buttonRadius),
      ),
    ),
  );
}

SwitchThemeData buildSwitchTheme(ColorScheme colorScheme) {
  return SwitchThemeData(
    thumbColor: WidgetStateProperty.resolveWith<Color?>((
      Set<WidgetState> states,
    ) {
      if (states.contains(WidgetState.disabled)) {
        return null;
      }
      if (states.contains(WidgetState.selected)) {
        return lightColorScheme.primary;
      }
      return null;
    }),
    trackColor: WidgetStateProperty.resolveWith<Color?>((
      Set<WidgetState> states,
    ) {
      if (states.contains(WidgetState.disabled)) {
        return null;
      }
      if (states.contains(WidgetState.selected)) {
        return lightColorScheme.primary.withValues(alpha: 0.5);
      }
      return null;
    }),
  );
}

CardThemeData buildCardTheme(ColorScheme colorScheme) {
  return CardThemeData(
    color: colorScheme.surfaceContainerHigh,
    elevation: 0,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(12),
      side: BorderSide(
        color: colorScheme.outline.withValues(alpha: 0.2),
        width: 0.5,
      ),
    ),
  );
}

final ThemeData lightTheme =
    ThemeData.from(
      colorScheme: lightColorScheme,
      textTheme: textTheme,
    ).copyWith(
      extensions: [AppColorExtension.light],
      appBarTheme: appBarTheme,
      elevatedButtonTheme: buildElevatedButtonTheme(lightColorScheme),
      outlinedButtonTheme: buildOutlinedButtonTheme(lightColorScheme),
      textButtonTheme: buildTextButtonTheme(lightColorScheme),
      cardTheme: buildCardTheme(lightColorScheme),
      switchTheme: buildSwitchTheme(lightColorScheme),
    );

final ThemeData darkTheme =
    ThemeData.from(colorScheme: darkColorScheme, textTheme: textTheme).copyWith(
      extensions: [AppColorExtension.dark],
      elevatedButtonTheme: buildElevatedButtonTheme(darkColorScheme),
      outlinedButtonTheme: buildOutlinedButtonTheme(darkColorScheme),
      textButtonTheme: buildTextButtonTheme(darkColorScheme),
      cardTheme: buildCardTheme(darkColorScheme),
      switchTheme: buildSwitchTheme(darkColorScheme),
    );

@immutable
class AppColorExtension extends ThemeExtension<AppColorExtension> {
  const AppColorExtension({
    required this.success,
    required this.warning,
    required this.googleBlue,
    required this.authError,
  });

  final Color success;
  final Color warning;
  final Color googleBlue;
  final Color authError;

  static const AppColorExtension light = AppColorExtension(
    success: Color(0xFF4CAF50),
    warning: Color(0xFFFF9800),
    googleBlue: Color(0xFF4285F4),
    authError: Color(0xFFD32F2F),
  );

  static const AppColorExtension dark = AppColorExtension(
    success: Color(0xFF66BB6A),
    warning: Color(0xFFFFB74D),
    googleBlue: Color(0xFF4285F4),
    authError: Color(0xFFEF5350),
  );

  @override
  AppColorExtension copyWith({
    Color? success,
    Color? warning,
    Color? googleBlue,
    Color? authError,
  }) {
    return AppColorExtension(
      success: success ?? this.success,
      warning: warning ?? this.warning,
      googleBlue: googleBlue ?? this.googleBlue,
      authError: authError ?? this.authError,
    );
  }

  @override
  AppColorExtension lerp(AppColorExtension? other, double t) {
    if (other is! AppColorExtension) {
      return this;
    }
    return AppColorExtension(
      success: Color.lerp(success, other.success, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      googleBlue: Color.lerp(googleBlue, other.googleBlue, t)!,
      authError: Color.lerp(authError, other.authError, t)!,
    );
  }
}

extension AppThemeExtension on ThemeData {
  AppColorExtension get appColors => extension<AppColorExtension>()!;
}

TextStyle menuTitleTextStyle(BuildContext context) {
  return Theme.of(context).textTheme.bodyMedium!;
}

TextStyle menuSubtitleTextStyle(BuildContext context) {
  return Theme.of(context).textTheme.bodySmall!.copyWith(
    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
  );
}

Color jokeIconButtonBaseColor(BuildContext context) {
  return Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7);
}

Color jokeSaveButtonColor(BuildContext context) {
  return Theme.of(context).colorScheme.error;
}

Color jokeShareButtonColor(BuildContext context) {
  return Theme.of(context).colorScheme.tertiary;
}
