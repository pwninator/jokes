import 'package:flutter/material.dart';

ColorScheme lightColorScheme = ColorScheme.fromSeed(
  seedColor: Colors.deepPurple,
  brightness: Brightness.light,
);

ColorScheme darkColorScheme = ColorScheme.fromSeed(
  seedColor: Colors.deepPurple,
  brightness: Brightness.dark,
);

const TextTheme textTheme = TextTheme(
  headlineMedium: TextStyle(
    fontSize: 24,
    fontWeight: FontWeight.bold,
  ),
);

final ThemeData lightTheme = ThemeData.from(
  colorScheme: lightColorScheme,
  textTheme: textTheme,
);

final ThemeData darkTheme = ThemeData.from(
  colorScheme: darkColorScheme,
  textTheme: textTheme,
);
