import 'package:flutter/material.dart';

const Color primaryColor = Color.fromARGB(255, 193, 122, 45);

ColorScheme lightColorScheme = ColorScheme.fromSeed(
  // seedColor: Colors.deepPurple,
  seedColor: Color(0xFFC59B6D),
  brightness: Brightness.light,
).copyWith(primary: primaryColor, error: Color.fromARGB(255, 239, 118, 118));

ColorScheme darkColorScheme = ColorScheme.fromSeed(
  // seedColor: Colors.deepPurple,
  seedColor: Color(0xFFC59B6D),
  brightness: Brightness.dark,
).copyWith(error: Color.fromARGB(255, 163, 34, 34));

const TextTheme textTheme = TextTheme(
  headlineMedium: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
);

const AppBarTheme appBarTheme = AppBarTheme(
  backgroundColor: Colors.transparent,
  elevation: 0,
);

final ThemeData lightTheme =
    ThemeData.from(
      colorScheme: lightColorScheme,
      textTheme: textTheme,
    ).copyWith(
      extensions: [AppColorExtension.light],
      appBarTheme: appBarTheme,
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: lightColorScheme.primary,
          foregroundColor: lightColorScheme.onPrimary,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
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
            borderRadius: BorderRadius.circular(10),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
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
