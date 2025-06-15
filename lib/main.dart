import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:jokes/src/app.dart';
// Note: Removed 'package:jokes/src/core/theme/app_theme.dart'; as it's not directly used here anymore.
// It will be used in app.dart

void main() {
  runApp(
    const ProviderScope(
      child: App(),
    ),
  );
}
