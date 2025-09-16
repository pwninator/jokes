import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';

class JokeAdminScreen extends ConsumerWidget implements TitledScreen {
  const JokeAdminScreen({super.key});

  @override
  String get title => 'Admin';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final unread = ref.watch(unreadFeedbackCountProvider).value ?? 0;
    return AdaptiveAppBarScreen(
      title: 'Admin',
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Feedback Card with unread badge
              Card(
                child: ListTile(
                  leading: const Icon(Icons.feedback),
                  title: const Text('Feedback'),
                  subtitle: const Text('User-submitted feedback'),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (unread > 0)
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: Theme.of(context).colorScheme.error,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            unread > 99 ? '99+' : '$unread',
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.onError,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      const Icon(Icons.arrow_forward_ios),
                    ],
                  ),
                  onTap: () {
                    context.push(AppRoutes.adminFeedback);
                  },
                ),
              ),

              const SizedBox(height: 8),

              // Users Analytics Card
              Card(
                child: ListTile(
                  leading: const Icon(Icons.people_alt),
                  title: const Text('Users'),
                  subtitle: const Text('Daily logins by days-used bucket'),
                  trailing: const Icon(Icons.arrow_forward_ios),
                  onTap: () {
                    context.push(AppRoutes.adminUsers);
                  },
                ),
              ),

              const SizedBox(height: 8),
              // Joke Categories Card
              Card(
                child: ListTile(
                  leading: const Icon(Icons.category),
                  title: const Text('Joke Categories'),
                  subtitle: const Text('Browse categories and images'),
                  trailing: const Icon(Icons.arrow_forward_ios),
                  onTap: () {
                    context.push(AppRoutes.adminCategories);
                  },
                ),
              ),

              const SizedBox(height: 8),

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
                    context.push(AppRoutes.adminCreator);
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
                    context.push(AppRoutes.adminManagement);
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
                    context.push(AppRoutes.adminScheduler);
                  },
                ),
              ),

              const SizedBox(height: 8),

              // Deep Research Card (last in menu)
              Card(
                child: ListTile(
                  leading: const Icon(Icons.science),
                  title: const Text('Deep Research'),
                  subtitle: const Text(
                    'Generate a prompt from search examples',
                  ),
                  trailing: const Icon(Icons.arrow_forward_ios),
                  onTap: () {
                    context.push(AppRoutes.adminDeepResearch);
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
