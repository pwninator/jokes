import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_creator_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_management_screen.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_scheduler_screen.dart';

class JokeAdminScreen extends StatelessWidget implements TitledScreen {
  const JokeAdminScreen({super.key});

  @override
  String get title => 'Admin';

  @override
  Widget build(BuildContext context) {
    return Navigator(
      onGenerateRoute: (settings) {
        switch (settings.name) {
          case '/':
            return MaterialPageRoute(
              builder: (context) => const _AdminHomeScreen(),
            );
          case '/joke-management':
            return MaterialPageRoute(
              builder: (context) => const JokeManagementScreen(),
            );
          case '/joke-creator':
            return MaterialPageRoute(
              builder: (context) => const JokeCreatorScreen(),
            );
          case '/joke-scheduler':
            return MaterialPageRoute(
              builder: (context) => const JokeSchedulerScreen(),
            );
          default:
            return MaterialPageRoute(
              builder: (context) => const _AdminHomeScreen(),
            );
        }
      },
    );
  }
}

class _AdminHomeScreen extends StatelessWidget {
  const _AdminHomeScreen();

  @override
  Widget build(BuildContext context) {
    return AdaptiveAppBarScreen(
      title: 'Admin',
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Joke Creator Card
              Card(
                child: ListTile(
                  leading: const Icon(Icons.auto_awesome),
                  title: const Text('Joke Creator'),
                  subtitle: const Text(
                    'Generate jokes using AI with custom instructions',
                  ),
                  trailing: const Icon(Icons.arrow_forward_ios),
                  onTap: () {
                    Navigator.of(context).pushNamed('/joke-creator');
                  },
                ),
              ),

              const SizedBox(height: 8),

              // Joke Management Card
              Card(
                child: ListTile(
                  leading: const Icon(Icons.mood),
                  title: const Text('Joke Management'),
                  subtitle: const Text('Add, edit, and moderate jokes'),
                  trailing: const Icon(Icons.arrow_forward_ios),
                  onTap: () {
                    Navigator.of(context).pushNamed('/joke-management');
                  },
                ),
              ),

              const SizedBox(height: 8),

              // Joke Scheduler Card
              Card(
                child: ListTile(
                  leading: const Icon(Icons.schedule),
                  title: const Text('Joke Scheduler'),
                  subtitle: const Text('Schedule jokes for daily delivery'),
                  trailing: const Icon(Icons.arrow_forward_ios),
                  onTap: () {
                    Navigator.of(context).pushNamed('/joke-scheduler');
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
