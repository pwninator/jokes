import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/data/jokes/joke_interactions_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/data/core/app/app_providers.dart';

import 'slot_entries.dart';

/// Base contract for rendering a [SlotEntry] into a widget.
abstract class SlotEntryRenderer {
  const SlotEntryRenderer();

  bool supports(SlotEntry entry);

  /// Optional key suffix to help the viewer identify stable children.
  String key(SlotEntry entry, SlotEntryViewConfig config) =>
      '${entry.runtimeType}-${config.index}';

  Widget build({required SlotEntry entry, required SlotEntryViewConfig config});
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
    this.showUserRatingButtons = false,
  });

  final String? formattedDate;
  final List<Joke> jokesToPreload;
  final JokeImageCarouselController carouselController;
  final void Function(int imageIndex) onImageStateChanged;
  final String? dataSource;
  final bool showUserRatingButtons;
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
      showUserRatingButtons: jokeConfig.showUserRatingButtons,
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
  const _EndOfFeedCard({required this.jokeContext, required this.totalJokes});

  final String jokeContext;
  final int totalJokes;

  @override
  ConsumerState<_EndOfFeedCard> createState() => _EndOfFeedCardState();
}

class _EndOfFeedCardState extends ConsumerState<_EndOfFeedCard> {
  bool _logged = false;
  bool? _showConnectionMessage;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_logged) {
      Future.microtask(() async {
        if (!mounted || _logged) return;
        await _logCompositeScrollState();
        final analytics = ref.read(analyticsServiceProvider);
        analytics.logJokeFeedEndViewed(jokeContext: widget.jokeContext);
        _logged = true;
      });
    }

    if (_showConnectionMessage == null) {
      Future.microtask(() async {
        if (!mounted) return;
        final isOnline = ref.read(isOnlineNowProvider);
        final interactionsRepository = ref.read(
          jokeInteractionsRepositoryProvider,
        );
        final feedCount = await interactionsRepository.countFeedJokes();
        final showConnection = !isOnline || feedCount < 300;
        if (!mounted) return;
        if (_showConnectionMessage == showConnection) return;
        setState(() {
          _showConnectionMessage = showConnection;
        });
      });
    }
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
    final showConnectionMessage = _showConnectionMessage ?? false;
    final title = showConnectionMessage
        ? "We're having trouble loading your jokes."
        : "You're all caught up!";
    final subtitle = showConnectionMessage
        ? 'Please check that you are connected.'
        : 'Fresh jokes drop tomorrow. Come back for more laughs!';
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
              title,
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              subtitle,
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

class BookPromoSlotEntryRenderer extends SlotEntryRenderer {
  const BookPromoSlotEntryRenderer();

  @override
  bool supports(SlotEntry entry) => entry is BookPromoSlotEntry;

  @override
  String key(SlotEntry entry, SlotEntryViewConfig config) =>
      'book-promo-${config.index}';

  @override
  Widget build({
    required SlotEntry entry,
    required SlotEntryViewConfig config,
  }) {
    entry as BookPromoSlotEntry;
    return _BookPromoCard(jokeContext: config.jokeContext);
  }
}

class _BookPromoCard extends ConsumerStatefulWidget {
  const _BookPromoCard({required this.jokeContext});

  final String jokeContext;

  @override
  ConsumerState<_BookPromoCard> createState() => _BookPromoCardState();
}

class _BookPromoCardState extends ConsumerState<_BookPromoCard> {
  bool _logged = false;

  @override
  void initState() {
    super.initState();
    Future.microtask(_logPromoViewed);
  }

  Future<void> _logPromoViewed() async {
    if (_logged) return;
    try {
      final analytics = ref.read(analyticsServiceProvider);
      analytics.logBookPromoCardViewed(jokeContext: widget.jokeContext);
      final appUsage = ref.read(appUsageServiceProvider);
      final now = ref.read(clockProvider)();
      await appUsage.setBookPromoCardLastShown(now);
      _logged = true;
    } catch (e, stack) {
      AppLogger.error('BOOK_PROMO_CARD analytics error: $e', stackTrace: stack);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final surfaceColor = theme.colorScheme.surfaceContainerHighest;
    final accentColor = theme.colorScheme.primary;
    final textColor = theme.textTheme.titleMedium?.color;
    final subtleTextColor = textColor?.withAlpha((0.7 * 255).round());
    final artworkBackground = theme.colorScheme.surfaceContainerHigh;

    return Card(
      color: surfaceColor,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            AspectRatio(
              aspectRatio: 16 / 9,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: artworkBackground,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Center(
                  child: Icon(Icons.menu_book_outlined, size: 48),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Create your own illustrated joke book',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
                color: textColor,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              'Soon you will be able to bundle your favorites into a custom book '
              'built from the jokes you love most.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: subtleTextColor,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            Text(
              'Keep an eye out for this Book Promo Card. A full image and CTA '
              'will land here once assets are ready.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: subtleTextColor,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: accentColor.withAlpha(120)),
              ),
              child: Text(
                'Book Promo Card',
                style: theme.textTheme.labelLarge?.copyWith(
                  color: accentColor,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
