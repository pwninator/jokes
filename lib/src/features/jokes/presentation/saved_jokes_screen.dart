import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_providers.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';

class SavedJokesScreen extends ConsumerStatefulWidget implements TitledScreen {
  const SavedJokesScreen({super.key});

  @override
  String get title => 'Saved Jokes';

  @override
  ConsumerState<SavedJokesScreen> createState() => _SavedJokesScreenState();
}

class _SavedJokesScreenState extends ConsumerState<SavedJokesScreen> {
  late final SavedJokesDataSource _dataSource;

  @override
  void initState() {
    super.initState();

    // Create the data source once and reuse it across rebuilds
    _dataSource = SavedJokesDataSource(ref);

    // Refresh user reactions from SharedPreferences when entering the screen
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(jokeReactionsProvider.notifier).refreshUserReactions();
    });
  }

  @override
  void dispose() {
    try {
      ref.read(railBottomSlotProvider.notifier).state = null;
    } catch (_) {}
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AdaptiveAppBarScreen(
      title: 'Saved Jokes',
      automaticallyImplyLeading: false,
      body: JokeListViewer(
        dataSource: _dataSource,
        jokeContext: AnalyticsJokeContext.savedJokes,
        viewerId: 'saved_jokes',
      ),
    );
  }
}
