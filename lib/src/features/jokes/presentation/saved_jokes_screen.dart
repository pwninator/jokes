import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_viewer_screen.dart';

class SavedJokesScreen extends ConsumerStatefulWidget implements TitledScreen {
  const SavedJokesScreen({super.key});

  @override
  String get title => 'Saved Jokes';

  @override
  ConsumerState<SavedJokesScreen> createState() => _SavedJokesScreenState();
}

class _SavedJokesScreenState extends ConsumerState<SavedJokesScreen> {
  @override
  void initState() {
    super.initState();

    // Refresh user reactions from SharedPreferences when entering the screen
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(jokeReactionsProvider.notifier).refreshUserReactions();
    });
  }

  @override
  Widget build(BuildContext context) {
    return JokeViewerScreen(
      jokesProvider: savedJokesProvider,
      jokeContext: AnalyticsJokeContext.savedJokes,
      screenTitle: 'Saved Jokes',
    );
  }
}
