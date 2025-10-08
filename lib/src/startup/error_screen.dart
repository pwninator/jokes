import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

/// Error screen shown when critical startup tasks fail after all retries.
///
/// Provides a retry button that allows the user to attempt startup again.
class ErrorScreen extends StatelessWidget {
  const ErrorScreen({required this.onRetry, super.key});

  /// Callback to retry the startup sequence.
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final colorScheme = darkTheme.colorScheme;
    final appPrimaryColor = colorScheme.primary;
    final backgroundColor = Colors.black;
    final textColor = appPrimaryColor;

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: lightTheme,
      darkTheme: darkTheme,
      themeMode: ThemeMode.dark,
      home: Scaffold(
        backgroundColor: backgroundColor,
        body: TweenAnimationBuilder<double>(
          duration: const Duration(milliseconds: 800),
          tween: Tween(begin: 0.0, end: 1.0),
          builder: (context, value, child) =>
              Opacity(opacity: value, child: child),
          child: LayoutBuilder(
            builder: (context, constraints) {
              return Stack(
                children: [
                  Center(
                    child: Image.asset(
                      JokeConstants.iconCookie01TransparentDark300,
                      width: 250,
                      height: 250,
                      fit: BoxFit.cover,
                    ),
                  ),
                  Positioned(
                    top: constraints.maxHeight * 0.72,
                    left: 0,
                    right: 0,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IntrinsicWidth(
                          child: Column(
                            children: [
                              Text(
                                'We hit a snag...',
                                style: TextStyle(
                                  fontSize: 20,
                                  fontWeight: FontWeight.w600,
                                  color: textColor,
                                  letterSpacing: 0.2,
                                ),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                'Something interrupted joke prep. Give it another try?',
                                style: TextStyle(
                                  fontSize: 14,
                                  color: textColor.withValues(alpha: 0.75),
                                ),
                                textAlign: TextAlign.center,
                              ),
                              const SizedBox(height: 16),
                              ElevatedButton(
                                key: const Key('error_screen-retry-button'),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: appPrimaryColor,
                                  foregroundColor: backgroundColor,
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 32,
                                    vertical: 14,
                                  ),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(24),
                                  ),
                                ),
                                onPressed: onRetry,
                                child: const Text('Retry Startup'),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}
