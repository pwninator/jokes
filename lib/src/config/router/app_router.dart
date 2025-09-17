import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/subscription_prompt_overlay.dart';
import 'package:snickerdoodle/src/config/router/route_guards.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/features/admin/presentation/deep_research_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_admin_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_categories_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_category_editor_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_creator_screen.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_feedback_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_editor_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_management_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_scheduler_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/users_analytics_screen.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/auth/presentation/auth_wrapper.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/daily_jokes_screen.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/saved_jokes_screen.dart';
import 'package:snickerdoodle/src/features/search/presentation/search_screen.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';

const List<TabConfig> _allTabs = [
  TabConfig(
    id: TabId.daily,
    route: AppRoutes.jokes,
    label: 'Daily Jokes',
    icon: Icons.mood,
  ),
  TabConfig(
    id: TabId.discover,
    route: AppRoutes.search,
    label: 'Discover',
    icon: Icons.explore,
  ),
  TabConfig(
    id: TabId.saved,
    route: AppRoutes.saved,
    label: 'Saved Jokes',
    icon: Icons.favorite,
  ),
  TabConfig(
    id: TabId.settings,
    route: AppRoutes.settings,
    label: 'Settings',
    icon: Icons.settings,
  ),
  TabConfig(
    id: TabId.admin,
    route: AppRoutes.admin,
    label: 'Admin',
    icon: Icons.admin_panel_settings,
    requiresAdmin: true,
  ),
];

/// Bottom navigation: central configuration
enum TabId { daily, discover, saved, settings, admin }

class TabConfig {
  final TabId id;
  final String route;
  final String label;
  final IconData icon;
  final bool requiresAdmin;

  const TabConfig({
    required this.id,
    required this.route,
    required this.label,
    required this.icon,
    this.requiresAdmin = false,
  });
}

List<TabConfig> _visibleTabs(bool isAdmin) {
  return _allTabs.where((t) => !t.requiresAdmin || isAdmin).toList();
}

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
      observers: [
        FirebaseAnalyticsObserver(
          analytics: ref.read(firebaseAnalyticsProvider),
        ),
      ],
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
          observers: [
            FirebaseAnalyticsObserver(
              analytics: ref.read(firebaseAnalyticsProvider),
            ),
          ],
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
              builder: (context, state) => const DailyJokesScreen(),
            ),

            // Saved Jokes
            GoRoute(
              path: AppRoutes.saved,
              name: RouteNames.saved,
              builder: (context, state) => const SavedJokesScreen(),
            ),

            // Search
            GoRoute(
              path: AppRoutes.search,
              name: RouteNames.search,
              builder: (context, state) => const SearchScreen(),
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

            // Admin Deep Research
            GoRoute(
              path: AppRoutes.adminDeepResearch,
              name: RouteNames.adminDeepResearch,
              builder: (context, state) => const DeepResearchScreen(),
            ),

            // Admin Joke Categories
            GoRoute(
              path: AppRoutes.adminCategories,
              name: RouteNames.adminCategories,
              builder: (context, state) => const JokeCategoriesScreen(),
            ),

            GoRoute(
              path: AppRoutes.adminCategoryEditor,
              name: RouteNames.adminCategoryEditor,
              builder: (context, state) {
                final category = state.extra as JokeCategory?;
                if (category == null) {
                  return const Center(child: Text('Category not found'));
                }
                return JokeCategoryEditorScreen(category: category);
              },
            ),

            // Admin Feedback
            GoRoute(
              path: AppRoutes.adminFeedback,
              name: RouteNames.adminFeedback,
              builder: (context, state) => const JokeFeedbackScreen(),
            ),

            // Admin Users Analytics
            GoRoute(
              path: AppRoutes.adminUsers,
              name: RouteNames.adminUsers,
              builder: (context, state) => const UsersAnalyticsScreen(),
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

    // Build navigation items from central config
    final tabs = _visibleTabs(isAdmin);
    final List<BottomNavigationBarItem> navItems = tabs
        .map((t) => BottomNavigationBarItem(icon: Icon(t.icon), label: t.label))
        .toList();

    // Convert to NavigationRail destinations
    final List<NavigationRailDestination> railDestinations = tabs
        .map(
          (t) => NavigationRailDestination(
            icon: Icon(t.icon),
            label: Text(t.label),
          ),
        )
        .toList();

    return Consumer(
      builder: (context, ref, _) {
        final resize = ref.watch(keyboardResizeProvider);
        return Scaffold(
          resizeToAvoidBottomInset: resize,
          body: isLandscape
              ? Row(
                  children: [
                    SafeArea(
                      child: SizedBox(
                        width: 180,
                        child: Consumer(
                          builder: (context, ref, _) {
                            final bottomSlot = ref.watch(
                              railBottomSlotProvider,
                            );
                            return Column(
                              children: [
                                Expanded(
                                  child: NavigationRail(
                                    destinations: railDestinations,
                                    selectedIndex: selectedIndex,
                                    onDestinationSelected: (index) {
                                      _navigateToIndex(context, index, isAdmin);
                                    },
                                    backgroundColor: Theme.of(
                                      context,
                                    ).colorScheme.surface,
                                    selectedIconTheme: IconThemeData(
                                      color: Theme.of(
                                        context,
                                      ).colorScheme.primary,
                                    ),
                                    unselectedIconTheme: IconThemeData(
                                      color: Theme.of(context)
                                          .colorScheme
                                          .onSurface
                                          .withValues(alpha: 0.6),
                                    ),
                                    selectedLabelTextStyle: TextStyle(
                                      fontWeight: FontWeight.w600,
                                      color: Theme.of(
                                        context,
                                      ).colorScheme.primary,
                                    ),
                                    unselectedLabelTextStyle: TextStyle(
                                      fontWeight: FontWeight.normal,
                                      color: Theme.of(context)
                                          .colorScheme
                                          .onSurface
                                          .withValues(alpha: 0.6),
                                    ),
                                    extended: true,
                                    useIndicator: false,
                                  ),
                                ),
                                if (bottomSlot != null)
                                  Padding(
                                    padding: const EdgeInsets.all(12.0),
                                    child: bottomSlot,
                                  ),
                              ],
                            );
                          },
                        ),
                      ),
                    ),
                    const VerticalDivider(thickness: 1, width: 1),
                    Expanded(child: RailHost(railWidth: 180, child: child)),
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
      },
    );
  }

  /// Get selected index from current route
  static int _getSelectedIndexFromRoute(String route, bool isAdmin) {
    final tabs = _visibleTabs(isAdmin);
    final idx = tabs.indexWhere((t) => route.startsWith(t.route));
    if (idx >= 0) return idx;
    return 0;
  }

  /// Navigate to tab index
  static void _navigateToIndex(BuildContext context, int index, bool isAdmin) {
    final tabs = _visibleTabs(isAdmin);
    if (index < 0 || index >= tabs.length) {
      context.go(AppRoutes.jokes);
      return;
    }

    // Special handling for Discover (Search) tab: focus field if already there
    final selectedTab = tabs[index];
    if (selectedTab.route == AppRoutes.search) {
      final currentLocation = GoRouterState.of(context).uri.path;
      if (currentLocation.startsWith(AppRoutes.search)) {
        // Already on search screen, trigger focus instead of navigating
        final container = ProviderScope.containerOf(context);
        container.read(searchFieldFocusTriggerProvider.notifier).state = true;

        // Reset the trigger after a short delay to allow the SearchScreen to handle it
        Future.delayed(const Duration(milliseconds: 100), () {
          if (context.mounted) {
            final resetContainer = ProviderScope.containerOf(context);
            resetContainer
                    .read(searchFieldFocusTriggerProvider.notifier)
                    .state =
                false;
          }
        });
        return;
      }
    }

    context.go(selectedTab.route);
  }
}

/// Inherited widget to indicate that a NavigationRail is present in the layout
class RailHost extends InheritedWidget {
  final double railWidth;

  const RailHost({super.key, required this.railWidth, required super.child});

  @override
  bool updateShouldNotify(covariant RailHost oldWidget) =>
      oldWidget.railWidth != railWidth;
}
