import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';

class JokeViewerScreen extends ConsumerStatefulWidget implements TitledScreen {
  const JokeViewerScreen({
    super.key,
    this.jokesProvider,
    required this.jokeContext,
    required this.screenTitle,
  });

  final StreamProvider<List<JokeWithDate>>? jokesProvider;
  final String jokeContext;
  final String screenTitle;

  @override
  String get title => screenTitle;

  @override
  ConsumerState<JokeViewerScreen> createState() => _JokeViewerScreenState();
}

class _JokeViewerScreenState extends ConsumerState<JokeViewerScreen> {
  @override
  void initState() {
    super.initState();
  }

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
    final jokesWithDateAsyncValue = ref.watch(
      widget.jokesProvider ?? monthlyJokesWithDateProvider,
    );

    return AdaptiveAppBarScreen(
      title: widget.screenTitle,
      body: JokeListViewer(
        jokesWithDateAsyncValue: jokesWithDateAsyncValue,
        jokeContext: widget.jokeContext,
      ),
    );
  }
}
