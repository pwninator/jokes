import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';

import 'slot_entries.dart';

/// Base contract for rendering a [SlotEntry] into a widget.
abstract class SlotEntryRenderer {
  const SlotEntryRenderer();

  bool supports(SlotEntry entry);

  /// Optional key suffix to help the viewer identify stable children.
  String key(SlotEntry entry, SlotEntryViewConfig config) =>
      '${entry.runtimeType}-${config.index}';

  Widget build({
    required SlotEntry entry,
    required SlotEntryViewConfig config,
  });
}

/// Context shared with renderers so they can build appropriate widgets.
class SlotEntryViewConfig {
  const SlotEntryViewConfig({
    required this.context,
    required this.ref,
    required this.index,
    required this.isLandscape,
    required this.jokeContext,
    required this.showSimilarSearchButton,
    this.jokeConfig,
  });

  final BuildContext context;
  final WidgetRef ref;
  final int index;
  final bool isLandscape;
  final String jokeContext;
  final bool showSimilarSearchButton;
  final JokeEntryViewConfig? jokeConfig;
}

/// Additional metadata needed to render joke entries.
class JokeEntryViewConfig {
  const JokeEntryViewConfig({
    required this.formattedDate,
    required this.jokesToPreload,
    required this.carouselController,
    required this.onImageStateChanged,
    required this.dataSource,
  });

  final String? formattedDate;
  final List<Joke> jokesToPreload;
  final JokeImageCarouselController carouselController;
  final void Function(int imageIndex) onImageStateChanged;
  final String? dataSource;
}

class JokeSlotEntryRenderer extends SlotEntryRenderer {
  const JokeSlotEntryRenderer();

  @override
  bool supports(SlotEntry entry) => entry is JokeSlotEntry;

  @override
  String key(SlotEntry entry, SlotEntryViewConfig config) {
    final jokeEntry = entry as JokeSlotEntry;
    return 'joke-${jokeEntry.joke.joke.id}';
  }

  @override
  Widget build({
    required SlotEntry entry,
    required SlotEntryViewConfig config,
  }) {
    final jokeEntry = entry as JokeSlotEntry;
    final jokeConfig = config.jokeConfig;
    if (jokeConfig == null) {
      throw StateError('JokeEntryViewConfig required for JokeSlotEntry.');
    }
    final jokeWithDate = jokeEntry.joke;
    final joke = jokeWithDate.joke;

    return JokeCard(
      key: Key(joke.id),
      joke: joke,
      index: config.index,
      title: jokeConfig.formattedDate,
      dataSource: jokeConfig.dataSource,
      onImageStateChanged: jokeConfig.onImageStateChanged,
      isAdminMode: false,
      jokesToPreload: jokeConfig.jokesToPreload,
      showSaveButton: true,
      showShareButton: true,
      showAdminRatingButtons: false,
      jokeContext: config.jokeContext,
      controller: jokeConfig.carouselController,
      showSimilarSearchButton: config.showSimilarSearchButton,
    );
  }
}

class EndOfFeedSlotEntryRenderer extends SlotEntryRenderer {
  const EndOfFeedSlotEntryRenderer();

  @override
  bool supports(SlotEntry entry) => entry is EndOfFeedSlotEntry;

  @override
  String key(SlotEntry entry, SlotEntryViewConfig config) =>
      'end-of-feed-${config.index}';

  @override
  Widget build({
    required SlotEntry entry,
    required SlotEntryViewConfig config,
  }) {
    final endEntry = entry as EndOfFeedSlotEntry;
    return _EndOfFeedCard(
      jokeContext: endEntry.jokeContext,
      totalJokes: endEntry.totalJokes,
    );
  }
}

class _EndOfFeedCard extends ConsumerStatefulWidget {
  const _EndOfFeedCard({
    required this.jokeContext,
    required this.totalJokes,
  });

  final String jokeContext;
  final int totalJokes;

  @override
  ConsumerState<_EndOfFeedCard> createState() => _EndOfFeedCardState();
}

class _EndOfFeedCardState extends ConsumerState<_EndOfFeedCard> {
  bool _logged = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_logged) return;
    Future.microtask(() async {
      if (!mounted || _logged) return;
      await _logCompositeScrollState();
      final analytics = ref.read(analyticsServiceProvider);
      analytics.logJokeFeedEndViewed(jokeContext: widget.jokeContext);
      _logged = true;
    });
  }

  Future<void> _logCompositeScrollState() async {
    final appUsage = ref.read(appUsageServiceProvider);
    final jokesViewed = await appUsage.getNumJokesViewed();
    final jokesNavigated = await appUsage.getNumJokesNavigated();
    AppLogger.error(
      'PAGING_INTERNAL: COMPOSITE: End-of-feed card viewed ('
      'jokeContext=${widget.jokeContext}, '
      'totalJokes=${widget.totalJokes}, '
      'usage.jokesViewed=$jokesViewed, '
      'usage.jokesNavigated=$jokesNavigated)',
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final background = theme.colorScheme.surfaceContainerHighest;
    final textColor = theme.textTheme.bodyMedium?.color;
    final subtleTextColor = textColor?.withAlpha((0.8 * 255).round());
    return Card(
      elevation: 0,
      color: background,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.emoji_emotions_outlined,
              color: theme.colorScheme.primary,
              size: 28,
            ),
            const SizedBox(height: 12),
            Text(
              "You're all caught up!",
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              'Fresh jokes drop tomorrow. Come back for more laughs!',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: subtleTextColor,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
