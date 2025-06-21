import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
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

    // Ensure selected index is valid when user permissions change
    if (_selectedIndex >= screens.length) {
      _selectedIndex = 0;
    }

    return Scaffold(
      body: screens[_selectedIndex],
      bottomNavigationBar: BottomNavigationBar(
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
