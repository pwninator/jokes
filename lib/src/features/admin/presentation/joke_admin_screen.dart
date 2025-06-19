import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_management_screen.dart';

class JokeAdminScreen extends StatelessWidget {
  const JokeAdminScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Admin Panel',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 24),

            // Info Card - Custom Claims
            Card(
              child: ListTile(
                leading: const Icon(Icons.info_outline),
                title: const Text('User Role Management'),
                subtitle: const Text(
                  'User roles are managed via Firebase Auth custom claims',
                ),
                trailing: const Icon(Icons.admin_panel_settings),
                onTap: () {
                  showDialog(
                    context: context,
                    builder:
                        (context) => AlertDialog(
                          title: const Text('User Role Management'),
                          content: const Text(
                            'User roles are managed using Firebase Auth custom claims. '
                            'To assign admin roles, use the Firebase Admin SDK or '
                            'Firebase Cloud Functions.',
                          ),
                          actions: [
                            TextButton(
                              onPressed: () => Navigator.of(context).pop(),
                              child: const Text('OK'),
                            ),
                          ],
                        ),
                  );
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
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (context) => const JokeManagementScreen(),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
