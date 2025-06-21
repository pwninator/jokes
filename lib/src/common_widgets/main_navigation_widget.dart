import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_admin_screen.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_viewer_screen.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';

class MainNavigationWidget extends ConsumerStatefulWidget {
  const MainNavigationWidget({super.key});

  @override
  ConsumerState<MainNavigationWidget> createState() =>
      _MainNavigationWidgetState();
}

class _MainNavigationWidgetState extends ConsumerState<MainNavigationWidget> {
  int _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    final isAdmin = ref.watch(isAdminProvider);
    final isLandscape = MediaQuery.of(context).orientation == Orientation.landscape;

    // Define screens based on user permissions
    final List<Widget> screens = [
      const JokeViewerScreen(),
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
    final List<NavigationRailDestination> railDestinations = navItems
        .map((item) => NavigationRailDestination(
              icon: item.icon,
              label: Text(item.label!),
            ))
        .toList();

    // Ensure selected index is valid when user permissions change
    if (_selectedIndex >= screens.length) {
      _selectedIndex = 0;
    }

    return Scaffold(
      body: isLandscape
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
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
                  ),
                  selectedLabelTextStyle: TextStyle(
                    fontWeight: FontWeight.w600,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                  unselectedLabelTextStyle: TextStyle(
                    fontWeight: FontWeight.normal,
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
                  ),
                  labelType: NavigationRailLabelType.all,
                ),
                const VerticalDivider(thickness: 1, width: 1),
                Expanded(child: screens[_selectedIndex]),
              ],
            )
          : screens[_selectedIndex],
      bottomNavigationBar: isLandscape
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
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
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
