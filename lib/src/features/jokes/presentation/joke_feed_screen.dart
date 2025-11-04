import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_configured_screen.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_slots.dart';

class JokeFeedScreen extends ConsumerStatefulWidget implements TitledScreen {
  const JokeFeedScreen({super.key});

  @override
  String get title => 'Joke Feed';

  @override
  ConsumerState<JokeFeedScreen> createState() => _JokeFeedScreenState();
}

class _JokeFeedScreenState extends ConsumerState<JokeFeedScreen> {
  late final CompositeJokeDataSource _dataSource;

  @override
  void initState() {
    super.initState();
    _dataSource = CompositeJokeDataSource(ref);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        ref.read(railBottomSlotProvider.notifier).state = null;
      }
    });
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AppBarConfiguredScreen(
      title: 'Joke Feed',
      automaticallyImplyLeading: false,
      body: JokeListViewer(
        dataSource: _dataSource,
        jokeContext: AnalyticsJokeContext.jokeFeed,
        viewerId: 'joke_feed',
        injectionStrategies: [
          EndOfFeedInjectedCardStrategy(
            jokeContext: AnalyticsJokeContext.jokeFeed,
          ),
        ],
      ),
    );
  }
}
