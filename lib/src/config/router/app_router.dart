import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/subscription_prompt_overlay.dart';
import 'package:snickerdoodle/src/config/router/route_guards.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_admin_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_creator_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_editor_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_management_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_scheduler_screen.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/auth/presentation/auth_wrapper.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_viewer_screen.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/saved_jokes_screen.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';

/// App router configuration
class AppRouter {
  AppRouter._();

  /// Create the main GoRouter instance
  static GoRouter createRouter({
    required Ref ref,
    Listenable? refreshListenable,
  }) {
    return GoRouter(
      navigatorKey: NotificationService.navigatorKey,
      initialLocation: AppRoutes.jokes,
      refreshListenable: refreshListenable,
      debugLogDiagnostics: true,
      redirect: AuthGuard.redirect,
      routes: [
        // Auth route
        GoRoute(
          path: AppRoutes.auth,
          name: RouteNames.auth,
          builder: (context, state) => const AuthWrapper(),
        ),

        // Main shell route with tab navigation
        ShellRoute(
          builder: (context, state, child) {
            return Consumer(
              builder: (context, ref, _) {
                final isAdmin = ref.watch(isAdminProvider);
                final isLandscape =
                    MediaQuery.of(context).orientation == Orientation.landscape;

                return SubscriptionPromptOverlay(
                  child: _buildMainNavigation(
                    context: context,
                    child: child,
                    isAdmin: isAdmin,
                    isLandscape: isLandscape,
                    currentLocation: state.uri.path,
                  ),
                );
              },
            );
          },
          routes: [
            // Daily Jokes
            GoRoute(
              path: AppRoutes.jokes,
              name: RouteNames.jokes,
              builder: (context, state) => const JokeViewerScreen(
                jokeContext: AnalyticsJokeContext.dailyJokes,
                screenTitle: 'Daily Jokes',
              ),
            ),

            // Saved Jokes
            GoRoute(
              path: AppRoutes.saved,
              name: RouteNames.saved,
              builder: (context, state) => const SavedJokesScreen(),
            ),

            // Settings
            GoRoute(
              path: AppRoutes.settings,
              name: RouteNames.settings,
              builder: (context, state) => const UserSettingsScreen(),
            ),

            // Admin home/dashboard
            GoRoute(
              path: AppRoutes.admin,
              name: RouteNames.admin,
              builder: (context, state) => const JokeAdminScreen(),
            ),

            // Admin sub-routes
            GoRoute(
              path: AppRoutes.adminCreator,
              name: RouteNames.adminCreator,
              builder: (context, state) => const JokeCreatorScreen(),
            ),

            GoRoute(
              path: AppRoutes.adminManagement,
              name: RouteNames.adminManagement,
              builder: (context, state) => const JokeManagementScreen(),
            ),

            GoRoute(
              path: AppRoutes.adminScheduler,
              name: RouteNames.adminScheduler,
              builder: (context, state) => const JokeSchedulerScreen(),
            ),

            GoRoute(
              path: AppRoutes.adminEditor,
              name: RouteNames.adminEditor,
              builder: (context, state) => const JokeEditorScreen(),
            ),

            GoRoute(
              path: AppRoutes.adminEditorWithJoke,
              name: RouteNames.adminEditorWithJoke,
              builder: (context, state) {
                final jokeId = state.pathParameters['jokeId'];
                return JokeEditorScreen(jokeId: jokeId);
              },
            ),
          ],
        ),
      ],
    );
  }

  /// Build the main navigation structure based on current route and user permissions
  static Widget _buildMainNavigation({
    required BuildContext context,
    required Widget child,
    required bool isAdmin,
    required bool isLandscape,
    required String currentLocation,
  }) {
    // Determine selected index based on current route
    int selectedIndex = _getSelectedIndexFromRoute(currentLocation, isAdmin);

    // Build navigation items
    final List<BottomNavigationBarItem> navItems = [
      const BottomNavigationBarItem(
        icon: Icon(Icons.mood),
        label: 'Daily Jokes',
      ),
      const BottomNavigationBarItem(
        icon: Icon(Icons.favorite),
        label: 'Saved Jokes',
      ),
      const BottomNavigationBarItem(
        icon: Icon(Icons.settings),
        label: 'Settings',
      ),
      if (isAdmin)
        const BottomNavigationBarItem(
          icon: Icon(Icons.admin_panel_settings),
          label: 'Admin',
        ),
    ];

    // Convert to NavigationRail destinations
    final List<NavigationRailDestination> railDestinations = navItems
        .map(
          (item) => NavigationRailDestination(
            icon: item.icon,
            label: Text(item.label!),
          ),
        )
        .toList();

    return Scaffold(
      body: isLandscape
          ? Row(
              children: [
                SafeArea(
                  child: SizedBox(
                    width: 180,
                    child: NavigationRail(
                      destinations: railDestinations,
                      selectedIndex: selectedIndex,
                      onDestinationSelected: (index) {
                        _navigateToIndex(context, index, isAdmin);
                      },
                      backgroundColor: Theme.of(context).colorScheme.surface,
                      selectedIconTheme: IconThemeData(
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      unselectedIconTheme: IconThemeData(
                        color: Theme.of(
                          context,
                        ).colorScheme.onSurface.withValues(alpha: 0.6),
                      ),
                      selectedLabelTextStyle: TextStyle(
                        fontWeight: FontWeight.w600,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      unselectedLabelTextStyle: TextStyle(
                        fontWeight: FontWeight.normal,
                        color: Theme.of(
                          context,
                        ).colorScheme.onSurface.withValues(alpha: 0.6),
                      ),
                      extended: true,
                      useIndicator: false,
                    ),
                  ),
                ),
                const VerticalDivider(thickness: 1, width: 1),
                Expanded(child: child),
              ],
            )
          : child,
      bottomNavigationBar: isLandscape
          ? null
          : BottomNavigationBar(
              type: BottomNavigationBarType.fixed,
              items: navItems,
              currentIndex: selectedIndex,
              selectedItemColor: Theme.of(context).colorScheme.primary,
              unselectedItemColor: Theme.of(
                context,
              ).colorScheme.onSurface.withValues(alpha: 0.6),
              selectedLabelStyle: TextStyle(
                fontWeight: FontWeight.w600,
                color: Theme.of(context).colorScheme.primary,
              ),
              unselectedLabelStyle: TextStyle(
                fontWeight: FontWeight.normal,
                color: Theme.of(
                  context,
                ).colorScheme.onSurface.withValues(alpha: 0.6),
              ),
              backgroundColor: Theme.of(context).colorScheme.surface,
              onTap: (index) {
                _navigateToIndex(context, index, isAdmin);
              },
            ),
    );
  }

  /// Get selected index from current route
  static int _getSelectedIndexFromRoute(String route, bool isAdmin) {
    if (route.startsWith('/saved')) return 1;
    if (route.startsWith('/settings')) return 2;
    if (route.startsWith('/admin') && isAdmin) return 3;
    return 0; // Default to jokes
  }

  /// Navigate to tab index
  static void _navigateToIndex(BuildContext context, int index, bool isAdmin) {
    String route;
    switch (index) {
      case 0:
        route = AppRoutes.jokes;
        break;
      case 1:
        route = AppRoutes.saved;
        break;
      case 2:
        route = AppRoutes.settings;
        break;
      case 3:
        route = isAdmin ? AppRoutes.admin : AppRoutes.jokes;
        break;
      default:
        route = AppRoutes.jokes;
    }

    context.go(route);
  }
}
