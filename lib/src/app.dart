import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/providers/crash_reporting_provider.dart';
import 'package:snickerdoodle/src/core/providers/device_orientation_provider.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/settings/application/theme_settings_service.dart';

/// Main app widget rendered after startup tasks complete.
///
/// All initialization (Firebase, SharedPreferences, Analytics, etc.) is
/// handled by the StartupOrchestrator before this widget is created.
class App extends ConsumerStatefulWidget {
  const App({super.key});

  @override
  ConsumerState<App> createState() => _AppState();
}

class _AppState extends ConsumerState<App> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);

    // Start trace from app creation to first joke render
    ref
        .read(performanceServiceProvider)
        .startNamedTrace(name: TraceName.appCreateToFirstJoke);

    // Call logAppUsage after startup completes and remote config is ready
    // This ensures readers of remote config values get the remote values.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      try {
        final appUsageService = ref.read(appUsageServiceProvider);
        unawaited(
          appUsageService.logAppUsage().catchError((
            Object e,
            StackTrace stack,
          ) {
            AppLogger.error('App usage logging failed: $e', stackTrace: stack);
          }),
        );
      } catch (e, stack) {
        AppLogger.error('App usage logging failed: $e', stackTrace: stack);
      }
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      // App came to foreground - refresh Remote Config
      // Firebase SDK handles throttling based on minimumFetchInterval
      _refreshRemoteConfig();
    }
  }

  void _refreshRemoteConfig() {
    try {
      final remoteConfigService = ref.read(remoteConfigServiceProvider);
      remoteConfigService
          .refresh()
          .then((activated) {
            if (activated) {
              AppLogger.debug('Remote Config refreshed with new values');
            }
          })
          .catchError((e) {
            AppLogger.debug('Remote Config refresh skipped or failed: $e');
          });
    } catch (e) {
      AppLogger.debug('Error triggering Remote Config refresh: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final themeMode = ref.watch(themeModeProvider);
    final router = ref.watch(goRouterProvider);

    // Set up ongoing listeners for auth state changes
    // (These sync user properties and crash reporting user ID throughout app lifecycle)
    ref.watch(analyticsUserTrackingProvider);
    ref.watch(crashReportingInitializationProvider);

    return MaterialApp.router(
      title: 'Snickerdoodle Jokes',
      theme: lightTheme,
      darkTheme: darkTheme,
      themeMode: themeMode,
      routerConfig: router,
      builder: (context, child) {
        final subtree = child ?? const SizedBox.shrink();
        return DeviceOrientationObserver(child: subtree);
      },
    );
  }
}
