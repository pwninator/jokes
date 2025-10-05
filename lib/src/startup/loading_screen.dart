import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';

/// Loading screen shown while startup tasks are executing.
///
/// Displays a progress indicator showing how many tasks have completed.
class LoadingScreen extends StatefulWidget {
  const LoadingScreen({
    required this.completed,
    required this.total,
    super.key,
  });

  /// Number of tasks completed.
  final int completed;

  /// Total number of tasks being tracked (critical + best effort).
  final int total;

  @override
  State<LoadingScreen> createState() => _LoadingScreenState();
}

class _LoadingScreenState extends State<LoadingScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(parent: _controller, curve: Curves.easeInOut));

    _controller.forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final progress = widget.completed / widget.total;

    final colorScheme = darkTheme.colorScheme;
    final appPrimaryColor = darkTheme.colorScheme.primary;
    final backgroundColor = Colors.black;

    final textColor = appPrimaryColor;

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: lightTheme,
      darkTheme: darkTheme,
      themeMode: ThemeMode.dark,
      home: Scaffold(
        backgroundColor: backgroundColor,
        body: FadeTransition(
          opacity: _fadeAnimation,
          child: LayoutBuilder(
            builder: (context, constraints) {
              return Stack(
                children: [
                  // Image centered on screen
                  Center(
                    child: Image.asset(
                      'assets/images/icon_cookie_01_transparent_dark_300.png',
                      width: 250,
                      height: 250,
                      fit: BoxFit.cover,
                    ),
                  ),

                  // Text and progress bar at 75% down the screen (halfway in bottom half)
                  Positioned(
                    top: constraints.maxHeight * 0.75,
                    left: 0,
                    right: 0,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IntrinsicWidth(
                          child: Column(
                            children: [
                              Text(
                                'Preparing your jokes...',
                                style: TextStyle(
                                  fontSize: 20,
                                  fontWeight: FontWeight.w500,
                                  color: textColor,
                                  letterSpacing: 0.2,
                                ),
                              ),

                              const SizedBox(height: 8),

                              // Progress bar that fills the width
                              SizedBox(
                                height: 5,
                                child: TweenAnimationBuilder<double>(
                                  duration: const Duration(milliseconds: 1000),
                                  curve: Curves.easeInOut,
                                  tween: Tween<double>(begin: 0, end: progress),
                                  builder: (context, value, _) =>
                                      LinearProgressIndicator(
                                        value: value,
                                        backgroundColor:
                                            colorScheme.surfaceContainerHighest,
                                        valueColor:
                                            AlwaysStoppedAnimation<Color>(
                                              appPrimaryColor,
                                            ),
                                      ),
                                ),
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
