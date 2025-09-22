import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart'
    show JokeImageCarouselController;
import 'package:snickerdoodle/src/config/router/app_router.dart' show RailHost;
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_navigation_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';

/// Reusable vertical viewer for a list of jokes with CTA button
class JokeListViewer extends ConsumerStatefulWidget {
  const JokeListViewer({
    super.key,
    this.jokesAsyncValue,
    this.jokesAsyncProvider,
    required this.jokeContext,
    required this.viewerId,
    this.onInitRegisterReset,
    this.showCtaWhenEmpty = false,
    this.emptyState,
    this.showSimilarSearchButton = true,
  });

  final AsyncValue<List<JokeWithDate>>? jokesAsyncValue;
  final ProviderListenable<AsyncValue<List<JokeWithDate>>>? jokesAsyncProvider;
  final String jokeContext;
  final String viewerId;
  final Function(VoidCallback)? onInitRegisterReset;
  final bool showCtaWhenEmpty;
  final Widget? emptyState;
  final bool showSimilarSearchButton;

  @override
  ConsumerState<JokeListViewer> createState() => _JokeListViewerState();
}

class _JokeListViewerState extends ConsumerState<JokeListViewer> {
  int _currentPage = 0;
  late PageController _pageController;
  final Map<int, int> _currentImageStates = {};
  final Map<int, JokeImageCarouselController> _carouselControllers = {};
  String _lastNavigationMethod = AnalyticsNavigationMethod.swipe;

  @override
  void initState() {
    super.initState();
    final initialIndex = ref.read(jokeViewerPageIndexProvider(widget.viewerId));
    _pageController = PageController(
      viewportFraction: 1.0,
      // For some reason, _resetToFirstJoke() always resets not to 0, but to this
      // initialPage value. So, set it to 0 and jump to the initialIndex so that
      // resets bring it back to 0.
      initialPage: 0,
    );
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _pageController.hasClients) {
        _pageController.jumpToPage(initialIndex);
      }
    });
    widget.onInitRegisterReset?.call(_resetToFirstJoke);
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _resetToFirstJoke() {
    if (mounted && _pageController.hasClients) {
      ref.read(jokeViewerPageIndexProvider(widget.viewerId).notifier).state = 0;
      setState(() {
        _currentPage = 0;
        _currentImageStates.clear();
      });
      _pageController.jumpToPage(0);
    }
  }

  void _onImageStateChanged(int jokeIndex, int imageIndex) {
    setState(() {
      _currentImageStates[jokeIndex] = imageIndex;
    });
  }

  void _goToNextJoke(int totalJokes, {required String method}) {
    final nextPage = _currentPage + 1;
    if (nextPage < totalJokes) {
      _lastNavigationMethod = method;
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    }
  }

  Widget _buildCTAButton({
    required BuildContext context,
    required List<JokeWithDate> jokesWithDates,
  }) {
    final isLandscape =
        MediaQuery.of(context).orientation == Orientation.landscape;
    final bool isEmpty = jokesWithDates.isEmpty;
    final int total = jokesWithDates.length;
    final bool isLast = total == 0 || _currentPage >= total - 1;

    final Joke? currentJoke = (!isEmpty && _currentPage < total)
        ? jokesWithDates[_currentPage].joke
        : null;
    final bool hasPunchlineImage =
        currentJoke != null &&
        currentJoke.punchlineImageUrl != null &&
        currentJoke.punchlineImageUrl!.trim().isNotEmpty;
    final int currentImageIndex = _currentImageStates[_currentPage] ?? 0;

    // Respect user preference: if reveal mode is disabled (show both),
    // there is nothing to reveal, so CTA should be "Next joke" only.
    final bool revealModeEnabled = ref.watch(jokeViewerRevealProvider);
    final bool showReveal =
        revealModeEnabled && hasPunchlineImage && currentImageIndex == 0;
    final String label = showReveal ? 'Reveal' : 'Next joke';
    final bool disabled = isEmpty || (!showReveal && isLast);

    return SizedBox(
      width: double.infinity,
      child: SafeArea(
        minimum: isLandscape
            ? EdgeInsets.zero
            : const EdgeInsets.only(left: 16, right: 16, bottom: 16),
        child: ElevatedButton(
          key: const Key('joke_viewer_cta_button'),
          onPressed: disabled
              ? null
              : () {
                  if (showReveal) {
                    setState(() {
                      _currentImageStates[_currentPage] = 1;
                    });
                    _carouselControllers[_currentPage]?.revealPunchline();
                  } else {
                    _goToNextJoke(
                      total,
                      method: AnalyticsNavigationMethod.ctaNextJoke,
                    );
                  }
                },
          child: Text(label),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<List<JokeWithDate>> effectiveAsync =
        widget.jokesAsyncValue ??
        (widget.jokesAsyncProvider != null
            ? ref.watch(widget.jokesAsyncProvider!)
            : const AsyncValue<List<JokeWithDate>>.data(<JokeWithDate>[]));

    return effectiveAsync.when(
      data: (jokesWithDates) {
        final isLandscape =
            MediaQuery.of(context).orientation == Orientation.landscape;
        final bool railPresent =
            context.dependOnInheritedWidgetOfExactType<RailHost>() != null;
        final Widget? railBottomWidget =
            (isLandscape && railPresent && jokesWithDates.isNotEmpty)
            ? _buildCTAButton(context: context, jokesWithDates: jokesWithDates)
            : null;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (!mounted) return;
          final current = ref.read(railBottomSlotProvider);
          if (!identical(current, railBottomWidget)) {
            ref.read(railBottomSlotProvider.notifier).state = railBottomWidget;
          }
        });

        if (jokesWithDates.isEmpty) {
          final empty =
              widget.emptyState ??
              const Center(child: Text('No jokes found! Try adding some.'));
          if (isLandscape && railPresent) return empty;
          return Column(
            children: [
              Expanded(child: empty),
              if (widget.showCtaWhenEmpty)
                _buildCTAButton(
                  context: context,
                  jokesWithDates: jokesWithDates,
                ),
            ],
          );
        }

        final safeCurrentPage = _currentPage
            .clamp(0, jokesWithDates.length - 1)
            .toInt();
        if (_currentPage != safeCurrentPage) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              setState(() {
                _currentPage = safeCurrentPage;
              });
              ref
                      .read(
                        jokeViewerPageIndexProvider(widget.viewerId).notifier,
                      )
                      .state =
                  safeCurrentPage;
            }
          });
        }

        return Column(
          children: [
            Expanded(
              child: PageView.builder(
                key: const Key('joke_viewer_page_view'),
                controller: _pageController,
                scrollDirection: Axis.vertical,
                itemCount: jokesWithDates.length,
                onPageChanged: (index) {
                  if (mounted) {
                    setState(() {
                      _currentPage = index;
                    });
                    ref
                            .read(
                              jokeViewerPageIndexProvider(
                                widget.viewerId,
                              ).notifier,
                            )
                            .state =
                        index;

                    final jokeWithDate = jokesWithDates[index];
                    final joke = jokeWithDate.joke;
                    final jokeScrollDepth = index;

                    final analyticsService = ref.read(analyticsServiceProvider);
                    final revealModeEnabled =
                        ref.read(jokeViewerRevealProvider);
                    analyticsService.logJokeNavigation(
                      joke.id,
                      jokeScrollDepth,
                      method: _lastNavigationMethod,
                      jokeContext: widget.jokeContext,
                      jokeViewerMode:
                          revealModeEnabled ? 'reveal' : 'showAll',
                    );

                    _lastNavigationMethod = AnalyticsNavigationMethod.swipe;
                  }
                },
                itemBuilder: (context, index) {
                  final jokeWithDate = jokesWithDates[index];
                  final joke = jokeWithDate.joke;
                  final date = jokeWithDate.date;

                  final formattedDate = date != null
                      ? '${date.month}/${date.day}/${date.year}'
                      : null;

                  final List<Joke> jokesToPreload = [];
                  if (index + 1 < jokesWithDates.length) {
                    jokesToPreload.add(jokesWithDates[index + 1].joke);
                  }
                  if (index + 2 < jokesWithDates.length) {
                    jokesToPreload.add(jokesWithDates[index + 2].joke);
                  }

                  final isLandscape =
                      MediaQuery.of(context).orientation ==
                      Orientation.landscape;

                  final controller =
                      _carouselControllers[index] ??
                      (_carouselControllers[index] =
                          JokeImageCarouselController());

                  // Title shows index (1-based) for search context, otherwise date (if any)
                  final String? titleForCard =
                      widget.jokeContext == AnalyticsJokeContext.search
                      ? '${index + 1}'
                      : formattedDate;

                  return Center(
                    child: Container(
                      width: isLandscape ? null : double.infinity,
                      height: isLandscape ? double.infinity : null,
                      padding: EdgeInsets.only(
                        left: 16.0,
                        right: 16.0,
                        top: 4.0,
                        bottom: 4.0,
                      ),
                      child: JokeCard(
                        key: Key(joke.id),
                        joke: joke,
                        index: index,
                        title: titleForCard,
                        onImageStateChanged: (imageIndex) =>
                            _onImageStateChanged(index, imageIndex),
                        isAdminMode: false,
                        jokesToPreload: jokesToPreload,
                        showSaveButton: true,
                        showShareButton: true,
                        showAdminRatingButtons: false,
                        jokeContext: widget.jokeContext,
                        controller: controller,
                        showSimilarSearchButton: widget.showSimilarSearchButton,
                      ),
                    ),
                  );
                },
              ),
            ),
            if ((!isLandscape || !railPresent) && jokesWithDates.isNotEmpty)
              _buildCTAButton(context: context, jokesWithDates: jokesWithDates),
          ],
        );
      },
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (error, stackTrace) {
        debugPrint('Error loading jokes: $error');
        debugPrint('Stack trace: $stackTrace');
        final analyticsService = ref.read(analyticsServiceProvider);
        analyticsService.logErrorJokesLoad(
          source: 'viewer',
          errorMessage: error.toString(),
        );
        return Center(child: Text('Error loading jokes: $error'));
      },
    );
  }
}
