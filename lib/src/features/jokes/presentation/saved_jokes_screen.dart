import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_configured_screen.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_sources.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_source.dart';

class SavedJokesScreen extends ConsumerStatefulWidget implements TitledScreen {
  const SavedJokesScreen({super.key});

  @override
  String get title => 'Saved Jokes';

  @override
  ConsumerState<SavedJokesScreen> createState() => _SavedJokesScreenState();
}

class _SavedJokesScreenState extends ConsumerState<SavedJokesScreen> {
  late final SlotSource _slotSource;

  @override
  void initState() {
    super.initState();

    // Create the data source once and reuse it across rebuilds
    _slotSource = SlotSource.fromDataSource(SavedJokesDataSource(ref));

    // Refresh user reactions from SharedPreferences when entering the screen
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final notifier = ref.read(savedJokesRefreshTriggerProvider.notifier);
      notifier.state++;
    });
  }

  @override
  void dispose() {
    // Avoid provider reads during unmount in tests; clear after frame if still mounted
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
      title: 'Saved Jokes',
      automaticallyImplyLeading: false,
      body: Column(
        children: [
          Consumer(
            builder: (context, ref, _) {
              final countInfo = ref.watch(_slotSource.resultCountProvider);
              final count = countInfo.count;

              if (count == 0) return const SizedBox.shrink();

              final hasMoreLabel = countInfo.hasMore ? '+' : '';
              final noun = count == 1 ? 'saved joke' : 'saved jokes';
              final label = '$count$hasMoreLabel $noun';

              return Align(
                alignment: Alignment.centerLeft,
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16.0,
                    vertical: 6.0,
                  ),
                  child: Text(
                    label,
                    key: const Key('saved_jokes_screen-results-count'),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
              );
            },
          ),
          Expanded(
            child: JokeListViewer(
              slotSource: _slotSource,
              jokeContext: AnalyticsJokeContext.savedJokes,
              viewerId: 'saved_jokes',
            ),
          ),
        ],
      ),
    );
  }
}
