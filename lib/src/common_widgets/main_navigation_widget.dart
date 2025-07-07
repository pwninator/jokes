import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_admin_screen.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_viewer_screen.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';

class MainNavigationWidget extends ConsumerStatefulWidget {
  const MainNavigationWidget({super.key});

  // Global key to access this widget's state from outside
  static final GlobalKey<MainNavigationWidgetState> navigationKey =
      GlobalKey<MainNavigationWidgetState>();

  @override
  ConsumerState<MainNavigationWidget> createState() =>
      MainNavigationWidgetState();
}

class MainNavigationWidgetState extends ConsumerState<MainNavigationWidget> {
  int _selectedIndex = 0;

  // Callback to reset JokeViewerScreen
  VoidCallback? _resetJokeViewer;

  /// Method to programmatically navigate to a specific tab
  void navigateToTab(int index) {
    if (mounted && index >= 0) {
      final isAdmin = ref.read(isAdminProvider);
      final maxIndex =
          isAdmin ? 2 : 1; // 0=Jokes, 1=Settings, 2=Admin (if admin)

      final safeIndex = index.clamp(0, maxIndex);

      // Track analytics for tab change
      _trackTabChange(_selectedIndex, safeIndex, 'programmatic');

      setState(() {
        _selectedIndex = safeIndex;
      });
    }
  }

  /// Track analytics for tab changes
  void _trackTabChange(int previousIndex, int newIndex, String method) {
    if (previousIndex == newIndex) return;

    final analyticsService = ref.read(analyticsServiceProvider);
    final previousTab = _indexToAppTab(previousIndex);
    final newTab = _indexToAppTab(newIndex);

    if (previousTab != null && newTab != null) {
      analyticsService.logTabChanged(previousTab, newTab, method: method);
    }
  }

  /// Convert tab index to AppTab enum
  AppTab? _indexToAppTab(int index) {
    final isAdmin = ref.read(isAdminProvider);
    switch (index) {
      case 0:
        return AppTab.jokes;
      case 1:
        return AppTab.settings;
      case 2:
        return isAdmin ? AppTab.admin : null;
      default:
        return null;
    }
  }

  /// Method to navigate to jokes tab and reset to first joke
  void navigateToJokesAndReset() {
    navigateToTab(0); // Navigate to Jokes tab

    // Reset joke viewer to first joke after navigation
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _resetJokeViewer?.call();
    });
  }

  @override
  Widget build(BuildContext context) {
    final isAdmin = ref.watch(isAdminProvider);
    final isLandscape =
        MediaQuery.of(context).orientation == Orientation.landscape;

    // Define screens based on user permissions
    final List<Widget> screens = [
      JokeViewerScreen(
        onResetCallback: (callback) => _resetJokeViewer = callback,
      ),
      const UserSettingsScreen(),
      if (isAdmin) const JokeAdminScreen(),
    ];

    // Define navigation items based on user permissions
    final List<BottomNavigationBarItem> navItems = [
      const BottomNavigationBarItem(icon: Icon(Icons.mood), label: 'Daily Jokes'),
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

    // Convert navigation items to NavigationRail destinations
    final List<NavigationRailDestination> railDestinations =
        navItems
            .map(
              (item) => NavigationRailDestination(
                icon: item.icon,
                label: Text(item.label!),
              ),
            )
            .toList();

    // Ensure selected index is valid when user permissions change
    if (_selectedIndex >= screens.length) {
      _selectedIndex = 0;
    }

    return Scaffold(
      body:
          isLandscape
              ? Row(
                children: [
                  SafeArea(
                    child: SizedBox(
                      width: 160,
                      child: NavigationRail(
                        destinations: railDestinations,
                        selectedIndex: _selectedIndex,
                        onDestinationSelected: (index) {
                          // Track analytics for tab change
                          _trackTabChange(_selectedIndex, index, 'tap');

                          setState(() {
                            _selectedIndex = index;
                          });
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
                        extended:
                            true, // This ensures icon and text are on the same line
                        useIndicator:
                            false, // No background color on selected item
                      ),
                    ),
                  ),
                  const VerticalDivider(thickness: 1, width: 1),
                  Expanded(child: screens[_selectedIndex]),
                ],
              )
              : screens[_selectedIndex],
      bottomNavigationBar:
          isLandscape
              ? null
              : BottomNavigationBar(
                type: BottomNavigationBarType.fixed,
                items: navItems,
                currentIndex: _selectedIndex,
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
                  // Track analytics for tab change
                  _trackTabChange(_selectedIndex, index, 'tap');

                  setState(() {
                    _selectedIndex = index;
                  });
                },
              ),
    );
  }
}
