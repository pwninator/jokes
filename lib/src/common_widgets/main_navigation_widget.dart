import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_admin_screen.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_viewer_screen.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';

class MainNavigationWidget extends ConsumerStatefulWidget {
  const MainNavigationWidget({super.key});

  @override
  ConsumerState<MainNavigationWidget> createState() => _MainNavigationWidgetState();
}

class _MainNavigationWidgetState extends ConsumerState<MainNavigationWidget> {
  int _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    final isAdmin = ref.watch(isAdminProvider);
    final currentUser = ref.watch(currentUserProvider);
    
    // Define screens based on user permissions
    final List<Widget> screens = [
      const JokeViewerScreen(),
      const UserSettingsScreen(),
      if (isAdmin) const JokeAdminScreen(),
    ];

    // Define navigation items based on user permissions
    final List<BottomNavigationBarItem> navItems = [
      const BottomNavigationBarItem(
        icon: Icon(Icons.mood),
        label: 'Jokes',
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

    // Ensure selected index is valid when user permissions change
    if (_selectedIndex >= screens.length) {
      _selectedIndex = 0;
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Snickerdoodle'),
        actions: [
          // Show user info and auth status
          if (currentUser != null)
            Padding(
              padding: const EdgeInsets.only(right: 8.0),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      currentUser.isAnonymous 
                        ? Icons.person_outline 
                        : Icons.person,
                      size: 16,
                    ),
                    Text(
                      currentUser.isAnonymous 
                        ? 'Guest' 
                        : currentUser.displayName ?? 'User',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
      body: screens[_selectedIndex],
      bottomNavigationBar: BottomNavigationBar(
        type: BottomNavigationBarType.fixed,
        items: navItems,
        currentIndex: _selectedIndex,
        onTap: (index) {
          setState(() {
            _selectedIndex = index;
          });
        },
      ),
    );
  }
}
