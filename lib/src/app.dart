import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:jokes/src/features/counter_example/presentation/counter_screen.dart';
import 'package:jokes/src/core/theme/app_theme.dart';

class App extends ConsumerWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: 'Flutter Demo', // This can be updated later
      theme: lightTheme,
      darkTheme: darkTheme,
      home: const CounterScreen(), // Changed from placeholder
    );
  }
}
