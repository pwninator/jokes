import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_admin_screen.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_viewer_screen.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';

// Mock screen widgets for testing
class MockJokeViewerScreen extends StatelessWidget implements TitledScreen {
  const MockJokeViewerScreen({super.key});

  @override
  String get title => 'Daily Jokes';

  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: Text('Mock Jokes Screen')));
  }
}

class MockUserSettingsScreen extends StatelessWidget implements TitledScreen {
  const MockUserSettingsScreen({super.key});

  @override
  String get title => 'Settings';

  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: Text('Mock Settings Screen')));
  }
}

class MockJokeAdminScreen extends StatelessWidget implements TitledScreen {
  const MockJokeAdminScreen({super.key});

  @override
  String get title => 'Admin';

  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: Text('Mock Admin Screen')));
  }
}

// Test version of MainNavigationWidget that uses mock screens
class TestableMainNavigationWidget extends ConsumerStatefulWidget {
  const TestableMainNavigationWidget({super.key});

  @override
  ConsumerState<TestableMainNavigationWidget> createState() =>
      _TestableMainNavigationWidgetState();
}

class _TestableMainNavigationWidgetState
    extends ConsumerState<TestableMainNavigationWidget> {
  int _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    final isAdmin = ref.watch(isAdminProvider);
    final isLandscape =
        MediaQuery.of(context).orientation == Orientation.landscape;

    // Define mock screens for testing
    final List<Widget> screens = [
      const MockJokeViewerScreen(),
      const MockUserSettingsScreen(),
      if (isAdmin) const MockJokeAdminScreen(),
    ];

    // Define navigation items based on user permissions
    final List<BottomNavigationBarItem> navItems = [
      const BottomNavigationBarItem(
        icon: Icon(Icons.mood),
        label: 'Daily Jokes',
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

void main() {
  group('TitledScreen Tests', () {
    testWidgets('JokeViewerScreen returns correct title', (tester) async {
      const screen = JokeViewerScreen();
      expect((screen as TitledScreen).title, equals('Daily Jokes'));
    });

    testWidgets('UserSettingsScreen returns correct title', (tester) async {
      const screen = UserSettingsScreen();
      expect((screen as TitledScreen).title, equals('Settings'));
    });

    testWidgets('JokeAdminScreen returns correct title', (tester) async {
      const screen = JokeAdminScreen();
      expect((screen as TitledScreen).title, equals('Admin'));
    });

    testWidgets('Mock screens have correct titles', (tester) async {
      const jokeScreen = MockJokeViewerScreen();
      const settingsScreen = MockUserSettingsScreen();
      const adminScreen = MockJokeAdminScreen();

      expect((jokeScreen as TitledScreen).title, equals('Daily Jokes'));
      expect((settingsScreen as TitledScreen).title, equals('Settings'));
      expect((adminScreen as TitledScreen).title, equals('Admin'));
    });
  });

  group('MainNavigationWidget Adaptive Navigation Tests', () {
    Widget createTestWidget({required bool isAdmin, required Size screenSize}) {
      return ProviderScope(
        overrides: [isAdminProvider.overrideWith((ref) => isAdmin)],
        child: MaterialApp(
          home: MediaQuery(
            data: MediaQueryData(size: screenSize),
            child: const TestableMainNavigationWidget(),
          ),
        ),
      );
    }

    group('Portrait Mode', () {
      testWidgets(
        'shows BottomNavigationBar in portrait mode for regular user',
        (tester) async {
          await tester.pumpWidget(
            createTestWidget(
              isAdmin: false,
              screenSize: const Size(400, 800), // Portrait
            ),
          );

          expect(find.byType(BottomNavigationBar), findsOneWidget);
          expect(find.byType(NavigationRail), findsNothing);
          expect(find.byIcon(Icons.mood), findsOneWidget);
          expect(find.byIcon(Icons.settings), findsOneWidget);
          expect(find.byIcon(Icons.admin_panel_settings), findsNothing);
        },
      );

      testWidgets('shows BottomNavigationBar in portrait mode for admin user', (
        tester,
      ) async {
        await tester.pumpWidget(
          createTestWidget(
            isAdmin: true,
            screenSize: const Size(400, 800), // Portrait
          ),
        );

        expect(find.byType(BottomNavigationBar), findsOneWidget);
        expect(find.byType(NavigationRail), findsNothing);
        expect(find.byIcon(Icons.mood), findsOneWidget);
        expect(find.byIcon(Icons.settings), findsOneWidget);
        expect(find.byIcon(Icons.admin_panel_settings), findsOneWidget);
      });
    });

    group('Landscape Mode', () {
      testWidgets('shows NavigationRail in landscape mode for regular user', (
        tester,
      ) async {
        await tester.pumpWidget(
          createTestWidget(
            isAdmin: false,
            screenSize: const Size(800, 400), // Landscape
          ),
        );

        expect(find.byType(NavigationRail), findsOneWidget);
        expect(find.byType(BottomNavigationBar), findsNothing);
        expect(find.byIcon(Icons.mood), findsOneWidget);
        expect(find.byIcon(Icons.settings), findsOneWidget);
        expect(find.byIcon(Icons.admin_panel_settings), findsNothing);
      });

      testWidgets('shows NavigationRail in landscape mode for admin user', (
        tester,
      ) async {
        await tester.pumpWidget(
          createTestWidget(
            isAdmin: true,
            screenSize: const Size(800, 400), // Landscape
          ),
        );

        expect(find.byType(NavigationRail), findsOneWidget);
        expect(find.byType(BottomNavigationBar), findsNothing);
        expect(find.byIcon(Icons.mood), findsOneWidget);
        expect(find.byIcon(Icons.settings), findsOneWidget);
        expect(find.byIcon(Icons.admin_panel_settings), findsOneWidget);
      });

      testWidgets('displays correct layout structure in landscape mode', (
        tester,
      ) async {
        await tester.pumpWidget(
          createTestWidget(
            isAdmin: false,
            screenSize: const Size(800, 400), // Landscape
          ),
        );

        expect(find.byType(Row), findsOneWidget);
        expect(find.byType(VerticalDivider), findsOneWidget);
        // The Expanded widget that wraps the screen content in the Row
        expect(find.byType(Expanded), findsAtLeastNWidgets(1));
      });
    });

    group('Navigation Behavior', () {
      testWidgets('navigation works in portrait mode', (tester) async {
        await tester.pumpWidget(
          createTestWidget(isAdmin: false, screenSize: const Size(400, 800)),
        );

        // Initially should show MockJokeViewerScreen
        expect(find.text('Mock Jokes Screen'), findsOneWidget);
        expect(find.text('Mock Settings Screen'), findsNothing);

        // Tap on settings
        await tester.tap(find.byIcon(Icons.settings));
        await tester.pumpAndSettle();

        // Should now show MockUserSettingsScreen
        expect(find.text('Mock Settings Screen'), findsOneWidget);
        expect(find.text('Mock Jokes Screen'), findsNothing);
      });

      testWidgets('navigation works in landscape mode', (tester) async {
        await tester.pumpWidget(
          createTestWidget(isAdmin: true, screenSize: const Size(800, 400)),
        );

        // Initially should show MockJokeViewerScreen
        expect(find.text('Mock Jokes Screen'), findsOneWidget);
        expect(find.text('Mock Admin Screen'), findsNothing);

        // Tap on admin in NavigationRail
        await tester.tap(find.byIcon(Icons.admin_panel_settings));
        await tester.pumpAndSettle();

        // Should now show MockJokeAdminScreen
        expect(find.text('Mock Admin Screen'), findsOneWidget);
        expect(find.text('Mock Jokes Screen'), findsNothing);
      });
    });

    group('Responsive Behavior', () {
      testWidgets(
        'switches from portrait to landscape layout when orientation changes',
        (tester) async {
          // Start in portrait
          await tester.pumpWidget(
            createTestWidget(isAdmin: false, screenSize: const Size(400, 800)),
          );

          expect(find.byType(BottomNavigationBar), findsOneWidget);
          expect(find.byType(NavigationRail), findsNothing);

          // Switch to landscape
          await tester.pumpWidget(
            createTestWidget(isAdmin: false, screenSize: const Size(800, 400)),
          );

          expect(find.byType(NavigationRail), findsOneWidget);
          expect(find.byType(BottomNavigationBar), findsNothing);
        },
      );
    });
  });
}
