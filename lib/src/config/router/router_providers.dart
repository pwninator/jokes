import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/config/router/app_router.dart';
import 'package:snickerdoodle/src/config/router/route_guards.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart';

/// Provider for the main GoRouter instance
final goRouterProvider = Provider<GoRouter>((ref) {
  final refreshNotifier = ref.watch(routeRefreshNotifierProvider);

  return AppRouter.createRouter(ref: ref, refreshListenable: refreshNotifier);
});

/// Provider for current route information
final currentRouteProvider = StateProvider<String>((ref) => '/jokes');

/// Provider for navigation analytics tracking
final navigationAnalyticsProvider = Provider<NavigationAnalytics>((ref) {
  return NavigationAnalytics(ref);
});

/// Navigation analytics helper
class NavigationAnalytics {
  final Ref _ref;

  NavigationAnalytics(this._ref);

  /// Track route changes for analytics
  void trackRouteChange(String previousRoute, String newRoute, String method) {
    // Update current route
    _ref.read(currentRouteProvider.notifier).state = newRoute;

    // Convert routes to AppTab equivalents for analytics
    final previousTab = _routeToAppTab(previousRoute);
    final newTab = _routeToAppTab(newRoute);

    // Track tab change if both routes map to tabs
    if (previousTab != null && newTab != null && previousTab != newTab) {
      final analyticsService = _ref.read(analyticsServiceProvider);
      analyticsService.logTabChanged(previousTab, newTab, method: method);
    }
  }

  /// Convert route path to AppTab for analytics compatibility
  AppTab? _routeToAppTab(String route) {
    if (route.startsWith('/jokes')) return AppTab.dailyJokes;
    if (route.startsWith('/saved')) return AppTab.savedJokes;
    if (route.startsWith('/settings')) return AppTab.settings;
    if (route.startsWith('/admin')) return AppTab.admin;
    return null;
  }
}

/// Provider for programmatic navigation helpers
final navigationHelpersProvider = Provider<NavigationHelpers>((ref) {
  return NavigationHelpers(ref);
});

/// Navigation helper methods
class NavigationHelpers {
  final Ref _ref;

  NavigationHelpers(this._ref);

  /// Navigate to a specific route with analytics tracking
  void navigateToRoute(String route, {String method = 'programmatic'}) {
    final router = _ref.read(goRouterProvider);
    final currentRoute = _ref.read(currentRouteProvider);

    // Track the navigation
    final analytics = _ref.read(navigationAnalyticsProvider);
    analytics.trackRouteChange(currentRoute, route, method);

    // Perform navigation
    router.go(route);
  }

  /// Navigate to jokes tab (equivalent to old navigateToJokesAndReset)
  void navigateToJokesAndReset() {
    navigateToRoute('/jokes', method: 'programmatic');
  }

  /// Navigate to admin screen
  void navigateToAdmin() {
    navigateToRoute('/admin', method: 'programmatic');
  }

  /// Navigate to settings
  void navigateToSettings() {
    navigateToRoute('/settings', method: 'programmatic');
  }

  /// Navigate to saved jokes
  void navigateToSaved() {
    navigateToRoute('/saved', method: 'programmatic');
  }
}
