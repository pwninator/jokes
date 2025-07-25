import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/settings/application/theme_settings_service.dart';

class App extends ConsumerWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeMode = ref.watch(themeModeProvider);
    final router = ref.watch(goRouterProvider);

    // Initialize analytics and set up notification service
    ref.listen(analyticsInitializationProvider, (previous, current) {
      current.whenData((_) {
        // Set up notification service with analytics
        final analyticsService = ref.read(analyticsServiceProvider);
        NotificationService().setAnalyticsService(analyticsService);
      });
    });

    return MaterialApp.router(
      title: 'Snickerdoodle Jokes',
      theme: lightTheme,
      darkTheme: darkTheme,
      themeMode: themeMode,
      routerConfig: router,
    );
  }
}
