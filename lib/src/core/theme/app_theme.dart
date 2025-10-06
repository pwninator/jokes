import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

const Color primaryColor = Color(0xFFB8860B); // Warm golden sugar cookie
const Color accentColor = Color(0xFF1976D2); // Complementary blue
const Color secondaryAccent = Color(0xFF42A5F5); // Lighter blue accent

ColorScheme lightColorScheme = ColorScheme.fromSeed(
  brightness: Brightness.light,
  dynamicSchemeVariant: DynamicSchemeVariant.content,
  seedColor: Color.fromARGB(255, 239, 167, 22),
  primary: Color.fromARGB(255, 198, 109, 0),
  // tertiary: Color.fromARGB(255, 118, 83, 247),
  // onTertiary: Colors.white,
  // tertiaryContainer: Color.fromARGB(255, 154, 127, 250),
  // onTertiaryContainer: Colors.white,
  error: Color.fromARGB(255, 198, 41, 41),
);

ColorScheme darkColorScheme = ColorScheme.fromSeed(
  brightness: Brightness.dark,
  dynamicSchemeVariant: DynamicSchemeVariant.content,
  seedColor: Color.fromARGB(255, 229, 156, 72),
  // tertiary: Color.fromARGB(255, 118, 83, 247),
  // onTertiary: Colors.white,
  // tertiaryContainer: Color.fromARGB(255, 154, 127, 250),
  // onTertiaryContainer: Colors.white,
  error: Color.fromARGB(255, 198, 41, 41),
);

final TextTheme textTheme = GoogleFonts.nunitoSansTextTheme(
  const TextTheme(
    headlineMedium: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
  ),
);

const AppBarTheme appBarTheme = AppBarTheme(
  backgroundColor: Colors.transparent,
  elevation: 0,
);

ElevatedButtonThemeData buildElevatedButtonTheme(ColorScheme colorScheme) {
  return ElevatedButtonThemeData(
    style: ElevatedButton.styleFrom(
      backgroundColor: colorScheme.primaryContainer,
      foregroundColor: colorScheme.onPrimaryContainer,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(buttonRadius),
      ),
      elevation: 4,
    ),
  );
}

const double buttonRadius = 64;

final ThemeData lightTheme =
    ThemeData.from(
      colorScheme: lightColorScheme,
      textTheme: textTheme,
    ).copyWith(
      extensions: [AppColorExtension.light],
      appBarTheme: appBarTheme,
      elevatedButtonTheme: buildElevatedButtonTheme(lightColorScheme),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(buttonRadius),
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(buttonRadius),
          ),
        ),
      ),
      cardTheme: CardThemeData(
        color: lightColorScheme.surfaceContainerHigh,
        elevation: 4,
      ),
    );

final ThemeData darkTheme =
    ThemeData.from(colorScheme: darkColorScheme, textTheme: textTheme).copyWith(
      extensions: [AppColorExtension.dark],
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: darkColorScheme.primary,
          foregroundColor: darkColorScheme.onPrimary,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(buttonRadius),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(buttonRadius),
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(buttonRadius),
          ),
        ),
      ),
      cardTheme: CardThemeData(
        color: darkColorScheme.surfaceContainerHigh,
        elevation: 1,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(
            color: darkColorScheme.outline.withValues(alpha: 0.2),
            width: 0.5,
          ),
        ),
      ),
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
