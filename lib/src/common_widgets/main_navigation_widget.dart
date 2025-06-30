import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
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
      setState(() {
        _selectedIndex = safeIndex;
      });
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
      const BottomNavigationBarItem(icon: Icon(Icons.mood), label: 'Jokes'),
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
                  NavigationRail(
                    destinations: railDestinations,
                    selectedIndex: _selectedIndex,
                    onDestinationSelected: (index) {
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
                    labelType: NavigationRailLabelType.all,
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
                  setState(() {
                    _selectedIndex = index;
                  });
                },
              ),
    );
  }
}
