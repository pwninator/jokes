import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_widget.dart';
import 'package:snickerdoodle/src/common_widgets/badged_icon.dart';
import 'package:snickerdoodle/src/common_widgets/banner_ad_widget.dart';
import 'package:snickerdoodle/src/common_widgets/subscription_prompt_overlay.dart';
import 'package:snickerdoodle/src/config/router/route_guards.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/admin/presentation/deep_research_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_admin_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_categories_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_category_editor_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_creator_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_editor_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_feedback_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_management_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_scheduler_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/users_analytics_screen.dart';
import 'package:snickerdoodle/src/features/ads/banner_ad_service.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/book_creator/book_creator_screen.dart';
import 'package:snickerdoodle/src/features/feedback/presentation/feedback_conversation_screen.dart';
import 'package:snickerdoodle/src/features/feedback/presentation/user_feedback_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_feed_screen.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/daily_jokes_screen.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/saved_jokes_screen.dart';
import 'package:snickerdoodle/src/features/search/application/discover_tab_state.dart';
import 'package:snickerdoodle/src/features/search/presentation/discover_screen.dart';
import 'package:snickerdoodle/src/features/search/presentation/search_screen.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';

const List<TabConfig> _allTabs = [
  TabConfig(
    id: TabId.feed,
    route: AppRoutes.feed,
    label: 'Joke Feed',
    icon: Icons.dynamic_feed,
  ),
  TabConfig(
    id: TabId.daily,
    route: AppRoutes.jokes,
    label: 'Daily Jokes',
    icon: Icons.mood,
  ),
  TabConfig(
    id: TabId.discover,
    route: AppRoutes.discover,
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
enum TabId { feed, daily, discover, saved, settings, admin }

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
      initialLocation: AppRoutes.feed,
      refreshListenable: refreshListenable,
      debugLogDiagnostics: true,
      observers: [
        FirebaseAnalyticsObserver(
          analytics: ref.read(firebaseAnalyticsProvider),
        ),
      ],
      redirect: AuthGuard.redirect,
      routes: [
        // Feedback - top-level utility route accessible from anywhere
        GoRoute(
          path: AppRoutes.feedback,
          name: RouteNames.feedback,
          builder: (context, state) => const UserFeedbackScreen(),
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
                    ref: ref,
                  ),
                );
              },
            );
          },
          routes: [
            // Joke Feed
            GoRoute(
              path: AppRoutes.feed,
              name: RouteNames.feed,
              builder: (context, state) => const JokeFeedScreen(),
            ),

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

            // Discover
            GoRoute(
              path: AppRoutes.discover,
              name: RouteNames.discover,
              builder: (context, state) => const DiscoverScreen(),
              routes: [
                GoRoute(
                  path: 'search',
                  name: RouteNames.discoverSearch,
                  builder: (context, state) => const SearchScreen(),
                ),
              ],
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
              path: AppRoutes.adminBookCreator,
              name: RouteNames.adminBookCreator,
              builder: (context, state) => const BookCreatorScreen(),
            ),
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

            // Admin Category Editor
            GoRoute(
              path: AppRoutes.adminCategoryEditor,
              name: RouteNames.adminCategoryEditor,
              builder: (context, state) {
                final categoryId = state.pathParameters['categoryId']!;
                return JokeCategoryEditorScreen(categoryId: categoryId);
              },
            ),

            // Admin Feedback
            GoRoute(
              path: AppRoutes.adminFeedback,
              name: RouteNames.adminFeedback,
              builder: (context, state) => const JokeFeedbackScreen(),
            ),

            GoRoute(
              path: AppRoutes.adminFeedbackDetails,
              name: RouteNames.adminFeedbackDetails,
              builder: (context, state) {
                final feedbackId = state.pathParameters['feedbackId']!;
                return FeedbackConversationScreen.admin(feedbackId: feedbackId);
              },
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

  /// Get the joke context for analytics based on current route
  static String _getJokeContextFromRoute(String route) {
    if (route.startsWith(AppRoutes.feed)) {
      return AnalyticsJokeContext.jokeFeed;
    } else if (route.startsWith(AppRoutes.saved)) {
      return AnalyticsJokeContext.savedJokes;
    } else if (route.startsWith(AppRoutes.discover)) {
      if (route.contains('/search')) {
        return AnalyticsJokeContext.search;
      }
      return AnalyticsJokeContext.category;
    } else if (route.startsWith(AppRoutes.jokes)) {
      return AnalyticsJokeContext.dailyJokes;
    }
    // Default for other routes (settings, admin, etc.)
    return AnalyticsJokeContext.jokeFeed;
  }

  /// Build the main navigation structure based on current route and user permissions
  static Widget _buildMainNavigation({
    required BuildContext context,
    required Widget child,
    required bool isAdmin,
    required bool isLandscape,
    required String currentLocation,
    required WidgetRef ref,
  }) {
    final jokeContext = _getJokeContextFromRoute(currentLocation);

    // Determine selected index based on current route
    int selectedIndex = _getSelectedIndexFromRoute(currentLocation, isAdmin);

    // Build navigation items from central config
    final tabs = _visibleTabs(isAdmin);

    final Color selectedColor = Theme.of(context).colorScheme.primary;
    final Color unselectedColor = Theme.of(
      context,
    ).colorScheme.onSurface.withValues(alpha: 0.7);

    return Consumer(
      builder: (context, ref, _) {
        final resize = ref.watch(keyboardResizeProvider);
        final hasUnviewed = ref.watch(hasUnviewedCategoriesProvider);

        final iconsAndLabels = tabs.map((tab) {
          final bool isDiscover = tab.id == TabId.discover;
          final Widget iconWidget = isDiscover
              ? BadgedIcon(
                  key: const Key('app_router-discover-tab-icon'),
                  icon: tab.icon,
                  showBadge: hasUnviewed,
                  iconSemanticLabel: tab.label,
                  badgeSemanticLabel: 'New Jokes',
                )
              : Icon(tab.icon, semanticLabel: tab.label);
          return (icon: iconWidget, label: tab.label);
        }).toList();

        // Build BottomNavigationBar items with possible badge for Discover tab
        final List<BottomNavigationBarItem> navItems = iconsAndLabels.map((
          iconAndLabel,
        ) {
          return BottomNavigationBarItem(
            icon: iconAndLabel.icon,
            label: iconAndLabel.label,
          );
        }).toList();

        // Build NavigationRail destinations with possible badge for Discover tab
        final List<NavigationRailDestination> railDestinations = iconsAndLabels
            .map((iconAndLabel) {
              return NavigationRailDestination(
                icon: iconAndLabel.icon,
                label: Text(iconAndLabel.label),
              );
            })
            .toList();

        final appBarConfig = ref.watch(appBarConfigProvider);
        final bannerEligibility = ref.watch(bannerAdEligibilityProvider);
        final showTopBannerAd =
            bannerEligibility.isEligible &&
            bannerEligibility.position == BannerAdPosition.top;
        final showBottomBannerAd =
            bannerEligibility.isEligible &&
            bannerEligibility.position == BannerAdPosition.bottom;

        // Build portrait AppBar using config
        PreferredSizeWidget? portraitAppBar;
        if (!isLandscape) {
          portraitAppBar = AppBarWidget(
            title: appBarConfig?.title ?? 'Snickerdoodle',
            leading: appBarConfig?.leading,
            actions: appBarConfig?.actions,
            automaticallyImplyLeading:
                appBarConfig?.automaticallyImplyLeading ?? true,
          );
        }

        final floatingActionButton = ref.watch(floatingActionButtonProvider);

        return Scaffold(
          resizeToAvoidBottomInset: resize,
          appBar: portraitAppBar,
          floatingActionButton: floatingActionButton,
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
                                      _navigateToIndex(
                                        context,
                                        ref,
                                        index,
                                        selectedIndex,
                                        isAdmin,
                                        currentLocation,
                                      );
                                    },
                                    backgroundColor: Theme.of(
                                      context,
                                    ).colorScheme.surface,
                                    selectedIconTheme: IconThemeData(
                                      color: selectedColor,
                                    ),
                                    unselectedIconTheme: IconThemeData(
                                      color: unselectedColor,
                                    ),
                                    selectedLabelTextStyle: TextStyle(
                                      fontWeight: FontWeight.w600,
                                      color: selectedColor,
                                    ),
                                    unselectedLabelTextStyle: TextStyle(
                                      fontWeight: FontWeight.normal,
                                      color: unselectedColor,
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
                    Expanded(
                      child: RailHost(
                        railWidth: 180,
                        child: Column(
                          children: [
                            SafeArea(child: SizedBox.shrink()),
                            // Landscape banner ad is disabled for now
                            // AdBannerWidget(
                            //   key: Key('banner-ad'),
                            //   jokeContext: jokeContext,
                            // ),
                            Expanded(child: child),
                          ],
                        ),
                      ),
                    ),
                  ],
                )
              : Column(
                  children: [
                    showTopBannerAd
                        ? AdBannerWidget(
                            key: const Key('banner-ad-top'),
                            jokeContext: jokeContext,
                            position: BannerAdPosition.top,
                          )
                        : const SizedBox.shrink(),
                    Expanded(child: child),
                  ],
                ),
          bottomNavigationBar: isLandscape
              ? null
              : Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    MediaQuery.removePadding(
                      context: context,
                      // Remove bottom safe area padding if bottom banner ad is shown
                      removeBottom: showBottomBannerAd,
                      child: BottomNavigationBar(
                        type: BottomNavigationBarType.fixed,
                        items: navItems,
                        currentIndex: selectedIndex,
                        selectedItemColor: selectedColor,
                        unselectedItemColor: unselectedColor,
                        selectedLabelStyle: TextStyle(
                          fontWeight: FontWeight.w700,
                          color: selectedColor,
                          fontSize: 12,
                        ),
                        unselectedLabelStyle: TextStyle(
                          fontWeight: FontWeight.w500,
                          color: unselectedColor,
                          fontSize: 11,
                        ),
                        backgroundColor: Theme.of(context).colorScheme.surface,
                        elevation: 8,
                        selectedIconTheme: IconThemeData(
                          size: 26,
                          color: selectedColor,
                        ),
                        unselectedIconTheme: IconThemeData(
                          size: 24,
                          color: unselectedColor,
                        ),
                        onTap: (index) {
                          _navigateToIndex(
                            context,
                            ref,
                            index,
                            selectedIndex,
                            isAdmin,
                            currentLocation,
                          );
                        },
                      ),
                    ),
                    showBottomBannerAd
                        ? AdBannerWidget(
                            key: const Key('banner-ad-bottom'),
                            jokeContext: jokeContext,
                            position: BannerAdPosition.bottom,
                          )
                        : const SizedBox.shrink(),
                  ],
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
  static void _navigateToIndex(
    BuildContext context,
    WidgetRef ref,
    int newIndex,
    int currentIndex,
    bool isAdmin,
    String currentLocation,
  ) {
    final tabs = _visibleTabs(isAdmin);
    if (newIndex < 0 || newIndex >= tabs.length) {
      context.go(AppRoutes.feed);
      return;
    }

    final targetTab = tabs[newIndex];
    final shouldResetDiscover = shouldResetDiscoverOnNavigation(
      newIndex: newIndex,
      isAdmin: isAdmin,
    );

    if (shouldResetDiscover) {
      resetDiscoverTabState(ref);
    }

    if (newIndex == currentIndex) {
      if (shouldResetDiscover && currentLocation != targetTab.route) {
        context.go(targetTab.route);
      }
      return;
    }

    // Update route state and analytics before navigating so listeners react
    final navigationAnalytics = ref.read(navigationAnalyticsProvider);
    navigationAnalytics.trackRouteChange(
      currentLocation,
      targetTab.route,
      'tab',
    );

    context.push(targetTab.route);
  }

  @visibleForTesting
  static bool shouldResetDiscoverOnNavigation({
    required int newIndex,
    required bool isAdmin,
  }) {
    final tabs = _visibleTabs(isAdmin);
    if (newIndex < 0 || newIndex >= tabs.length) {
      return false;
    }

    return tabs[newIndex].id == TabId.discover;
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
