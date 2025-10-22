import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_configured_screen.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';

class DailyJokesScreen extends ConsumerStatefulWidget implements TitledScreen {
  const DailyJokesScreen({super.key});

  @override
  String get title => 'Daily Jokes';

  @override
  ConsumerState<DailyJokesScreen> createState() => _DailyJokesScreenState();
}

class _DailyJokesScreenState extends ConsumerState<DailyJokesScreen>
    with WidgetsBindingObserver {
  Timer? _checkTimer;
  bool _isAppInForeground = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _startJokeDateCheckTimer();
  }

  @override
  void dispose() {
    _stopJokeDateCheckTimer();
    WidgetsBinding.instance.removeObserver(this);
    // Avoid reading providers after disposal; schedule clear post-frame if still mounted.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        ref.read(railBottomSlotProvider.notifier).state = null;
      }
    });
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final wasInForeground = _isAppInForeground;
    _isAppInForeground = state == AppLifecycleState.resumed;

    if (!wasInForeground && _isAppInForeground) {
      // App came to foreground - trigger check if screen is visible
      if (_isScreenVisible()) {
        _triggerStaleCheck();
        _startJokeDateCheckTimer();
      }
    } else if (wasInForeground && !_isAppInForeground) {
      // App went to background - stop timer
      _stopJokeDateCheckTimer();
    }
  }

  bool _isScreenVisible() {
    if (!mounted) return false;
    final currentRoute = GoRouterState.of(context).uri.path;
    return currentRoute == AppRoutes.jokes;
  }

  void _startJokeDateCheckTimer() {
    if (_checkTimer != null && _checkTimer!.isActive) return;
    _checkTimer = Timer.periodic(const Duration(minutes: 1), (_) {
      if (_isAppInForeground && _isScreenVisible()) {
        _triggerStaleCheck();
      }
    });
  }

  void _stopJokeDateCheckTimer() {
    _checkTimer?.cancel();
    _checkTimer = null;
  }

  void _triggerStaleCheck() {
    if (!mounted) return;
    // Increment counter to signal "check now" to the reset trigger
    ref.read(dailyJokesCheckNowProvider.notifier).state++;
  }

  @override
  Widget build(BuildContext context) {
    // Listen to route changes to start/stop timer based on visibility
    ref.listen(currentRouteProvider, (previous, next) {
      if (next == AppRoutes.jokes) {
        // Screen became visible - trigger check and start timer
        if (_isAppInForeground) {
          _triggerStaleCheck();
          _startJokeDateCheckTimer();
        }
      } else {
        // Screen is no longer visible - stop timer
        _stopJokeDateCheckTimer();
      }
    });

    return AppBarConfiguredScreen(
      title: 'Daily Jokes',
      automaticallyImplyLeading: false,
      body: JokeListViewer(
        dataSource: DailyJokesDataSource(ref),
        jokeContext: AnalyticsJokeContext.dailyJokes,
        viewerId: 'daily_jokes',
      ),
    );
  }
}
