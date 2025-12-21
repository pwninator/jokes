import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/bouncing_button.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/url_launcher_service.dart';
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
    this.carouselController,
    this.onImageStateChanged,
    this.jokeConfig,
  });

  final BuildContext context;
  final WidgetRef ref;
  final int index;
  final bool isLandscape;
  final String jokeContext;
  final bool showSimilarSearchButton;
  final JokeImageCarouselController? carouselController;
  final void Function(int imageIndex)? onImageStateChanged;
  final JokeEntryViewConfig? jokeConfig;
}

/// Additional metadata needed to render joke entries.
class JokeEntryViewConfig {
  const JokeEntryViewConfig({
    required this.formattedDate,
    required this.jokesToPreload,
    required this.dataSource,
    this.showUserRatingButtons = false,
  });

  final String? formattedDate;
  final List<Joke> jokesToPreload;
  final String? dataSource;
  final bool showUserRatingButtons;
}

class BookPromoFakeJokeVariant {
  const BookPromoFakeJokeVariant({
    required this.variantId,
    required this.setupImageUrl,
    required this.punchlineImageUrl,
  });

  final String variantId;
  final String setupImageUrl;
  final String punchlineImageUrl;
}

const Map<String, BookPromoFakeJokeVariant> fakeJokeVariants = {
  'fake_joke_zoo': BookPromoFakeJokeVariant(
    variantId: 'fake_joke_zoo',
    setupImageUrl:
        "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/pun_agent_image_20251220_063100_488567.png",
    punchlineImageUrl:
        "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/_joke_assets/pun_agent_image_20251220_063154_684068_2.png",
  ),
  'fake_joke_bunny': BookPromoFakeJokeVariant(
    variantId: 'fake_joke_bunny',
    setupImageUrl:
        "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/pun_agent_image_20251220_082928_515313.png",
    punchlineImageUrl:
        "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/_joke_assets/pun_agent_image_20251220_072939_329947_2.png",
  ),
  'fake_joke_read': BookPromoFakeJokeVariant(
    variantId: 'fake_joke_read',
    setupImageUrl:
        "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/pun_agent_image_20251220_063842_639194.png",
    punchlineImageUrl:
        "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/_joke_assets/pun_agent_image_20251220_073731_191925_2.png",
  ),
};

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
      onImageStateChanged: config.onImageStateChanged,
      isAdminMode: false,
      jokesToPreload: jokeConfig.jokesToPreload,
      showSaveButton: true,
      showShareButton: true,
      showAdminRatingButtons: false,
      showUserRatingButtons: jokeConfig.showUserRatingButtons,
      jokeContext: config.jokeContext,
      controller: config.carouselController,
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
    final remoteValues = config.ref.read(remoteConfigValuesProvider);
    final requestedVariantId = remoteValues
        .getString(RemoteParam.bookPromoCardVariant)
        .trim()
        .toLowerCase();
    final fallbackVariant = fakeJokeVariants.values.first;
    final variant = fakeJokeVariants[requestedVariantId] ?? fallbackVariant;
    final resolvedVariantId = variant.variantId;

    return _BookPromoWithCta(
      jokeContext: config.jokeContext,
      variant: variant,
      variantString: resolvedVariantId,
      isLandscape: config.isLandscape,
      carouselController: config.carouselController,
      onImageStateChanged: config.onImageStateChanged,
    );
  }
}

class _BookPromoWithCta extends ConsumerWidget {
  const _BookPromoWithCta({
    required this.jokeContext,
    required this.variant,
    required this.variantString,
    required this.isLandscape,
    required this.carouselController,
    required this.onImageStateChanged,
  });

  static final Uri _bookUrl = Uri.parse(
    'http://snickerdoodlejokes.com/book-animal-jokes',
  );

  final String jokeContext;
  final BookPromoFakeJokeVariant variant;
  final String variantString;
  final bool isLandscape;
  final JokeImageCarouselController? carouselController;
  final void Function(int imageIndex)? onImageStateChanged;

  Future<void> _onTapAmazon(BuildContext context, WidgetRef ref) async {
    try {
      final analytics = ref.read(analyticsServiceProvider);
      analytics.logBookPromoAmazonButtonTapped(
        jokeContext: jokeContext,
        bookPromoVariant: variantString,
      );

      final launcher = ref.read(urlLauncherServiceProvider);
      final didLaunch = await launcher.launchUrl(_bookUrl);
      if (!didLaunch) {
        AppLogger.error(
          'BOOK_PROMO: launchUrl returned false (variant=$variantString, url=$_bookUrl)',
        );
      }
    } catch (e, stack) {
      AppLogger.error(
        'BOOK_PROMO: failed to open Amazon link: $e',
        stackTrace: stack,
      );
    }
  }

  Widget _buildCta(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          "We just launched a Snickerdoodle Jokes book!",
          style: theme.textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.w600,
          ),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          child: BouncingButton(
            buttonKey: Key(
              'slot_entry_renderers-book-promo-amazon-button-$variantString',
            ),
            isPositive: true,
            style: ButtonStyle(
              backgroundColor: WidgetStateProperty.resolveWith((states) {
                return theme.colorScheme.tertiaryContainer;
              }),
            ),
            onPressed: () => _onTapAmazon(context, ref),
            child: const Text(
              'See it on Amazon!',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w900,
                letterSpacing: 0.5,
              ),
            ),
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final card = _FakeJokePromoCard(
      jokeContext: jokeContext,
      variant: variant,
      variantString: variantString,
      carouselController: carouselController,
      onImageStateChanged: onImageStateChanged,
    );

    if (isLandscape) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              flex: 2,
              child: SizedBox.expand(child: Center(child: card)),
            ),
            Expanded(
              flex: 1,
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: _buildCta(context, ref),
              ),
            ),
          ],
        ),
      );
    } else {
      // In portrait, this promo must fit alongside the global viewer CTA
      // (e.g. "Next joke") which lives outside of the PageView.
      // Make this promo page own the available height so BOTH_ADAPTIVE mode can
      // shrink the images to fit *with* the promo CTA visible.
      return SizedBox.expand(
        child: Column(
          children: [
            Expanded(child: Center(child: card)),
            _buildCta(context, ref),
          ],
        ),
      );
    }
  }
}

class _FakeJokePromoCard extends ConsumerStatefulWidget {
  const _FakeJokePromoCard({
    required this.jokeContext,
    required this.variant,
    required this.variantString,
    this.carouselController,
    this.onImageStateChanged,
  });

  final String jokeContext;
  final BookPromoFakeJokeVariant variant;
  final String variantString;
  final JokeImageCarouselController? carouselController;
  final void Function(int imageIndex)? onImageStateChanged;

  @override
  ConsumerState<_FakeJokePromoCard> createState() => _FakeJokePromoCardState();
}

class _FakeJokePromoCardState extends ConsumerState<_FakeJokePromoCard> {
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
      analytics.logBookPromoCardViewed(
        jokeContext: widget.jokeContext,
        bookPromoVariant: widget.variantString,
      );
      final appUsage = ref.read(appUsageServiceProvider);
      final now = ref.read(clockProvider)();
      await appUsage.setBookPromoCardLastShown(now);
      _logged = true;
    } catch (e, stack) {
      AppLogger.error(
        'FAKE_JOKE_BOOK_PROMO analytics error: $e',
        stackTrace: stack,
      );
    }
  }

  Joke _buildFakeJoke() {
    return Joke(
      id: widget.variant.variantId,
      setupText: 'Fake joke setup (${widget.variant.variantId})',
      punchlineText: 'Fake joke punchline (${widget.variant.variantId})',
      setupImageUrl: widget.variant.setupImageUrl,
      punchlineImageUrl: widget.variant.punchlineImageUrl,
    );
  }

  @override
  Widget build(BuildContext context) {
    final fakeJoke = _buildFakeJoke();
    return JokeCard(
      key: Key('fake-joke-card-${widget.variant.variantId}'),
      joke: fakeJoke,
      jokeContext: widget.jokeContext,
      controller: widget.carouselController,
      onImageStateChanged: widget.onImageStateChanged,
      showSaveButton: false,
      showShareButton: false,
      showAdminRatingButtons: false,
      showUserRatingButtons: false,
      showSimilarSearchButton: false,
      showUsageStats: false,
      skipJokeTracking: true,
    );
  }
}
