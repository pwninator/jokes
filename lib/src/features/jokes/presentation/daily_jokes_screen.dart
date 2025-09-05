import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';

class DailyJokesScreen extends ConsumerStatefulWidget implements TitledScreen {
  const DailyJokesScreen({super.key});

  @override
  String get title => 'Daily Jokes';

  @override
  ConsumerState<DailyJokesScreen> createState() => _DailyJokesScreenState();
}

class _DailyJokesScreenState extends ConsumerState<DailyJokesScreen> {
  @override
  void dispose() {
    // Clear rail bottom slot when leaving the screen
    try {
      ref.read(railBottomSlotProvider.notifier).state = null;
    } catch (_) {}
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final jokesWithDateAsyncValue = ref.watch(monthlyJokesWithDateProvider);

    return AdaptiveAppBarScreen(
      title: 'Daily Jokes',
      body: JokeListViewer(
        jokesAsyncValue: jokesWithDateAsyncValue,
        jokeContext: AnalyticsJokeContext.dailyJokes,
        showSimilarSearchButton: true,
      ),
    );
  }
}
