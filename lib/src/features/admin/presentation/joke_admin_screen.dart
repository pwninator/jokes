import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';

class JokeAdminScreen extends ConsumerWidget implements TitledScreen {
  const JokeAdminScreen({super.key});

  @override
  String get title => 'Admin';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final allFeedback = ref.watch(allFeedbackProvider);
    final unread = allFeedback.when(
      data: (items) => items.where((entry) {
        if (entry.conversation.isEmpty) return false;
        final last = entry.conversation.last;
        if (last.speaker == SpeakerType.admin) return false;
        final view = entry.lastAdminViewTime;
        return view == null || view.isBefore(last.timestamp);
      }).length,
      loading: () => 0,
      error: (e, st) => 0,
    );
    return AdaptiveAppBarScreen(
      title: 'Admin',
      automaticallyImplyLeading: false,
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Feedback Card with unread badge
              Card(
                child: ListTile(
                  key: const Key('joke_admin_screen-feedback-tile'),
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
                            color: Colors.red.shade600,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            unread > 99 ? '99+' : '$unread',
                            style: TextStyle(
                              color: Colors.white,
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

              // Book Creator Card
              Card(
                child: ListTile(
                  key: const Key('joke_admin_screen-book-creator-tile'),
                  leading: const Icon(Icons.book_online),
                  title: const Text('Book Creator'),
                  subtitle: const Text('Create books from existing jokes'),
                  trailing: const Icon(Icons.arrow_forward_ios),
                  onTap: () {
                    context.push(AppRoutes.adminBookCreator);
                  },
                ),
              ),

              const SizedBox(height: 8),

              // Users Analytics Card
              Card(
                child: ListTile(
                  key: const Key('joke_admin_screen-users-tile'),
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
                  key: const Key('joke_admin_screen-categories-tile'),
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
                  key: const Key('joke_admin_screen-creator-tile'),
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
                  key: const Key('joke_admin_screen-management-tile'),
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
                  key: const Key('joke_admin_screen-scheduler-tile'),
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
                  key: const Key('joke_admin_screen-deep-research-tile'),
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
