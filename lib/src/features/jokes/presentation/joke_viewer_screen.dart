import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart'
    show JokeImageCarouselController;
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/config/router/app_router.dart' show RailHost;
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class JokeViewerScreen extends ConsumerStatefulWidget implements TitledScreen {
  const JokeViewerScreen({
    super.key,
    this.onResetCallback,
    this.jokesProvider,
    required this.jokeContext,
    required this.screenTitle,
  });

  final Function(VoidCallback)? onResetCallback;
  final StreamProvider<List<JokeWithDate>>? jokesProvider;
  final String jokeContext;
  final String screenTitle;

  @override
  String get title => screenTitle;

  @override
  ConsumerState<JokeViewerScreen> createState() => _JokeViewerScreenState();
}

class _JokeViewerScreenState extends ConsumerState<JokeViewerScreen> {
  int _currentPage = 0;
  late PageController _pageController;

  // Track current image state for each joke (joke index -> image index: 0=setup, 1=punchline)
  final Map<int, int> _currentImageStates = {};

  // Controllers for each joke's image carousel
  final Map<int, JokeImageCarouselController> _carouselControllers = {};

  // Track the navigation method that triggered the current page change
  String _lastNavigationMethod = AnalyticsNavigationMethod.swipe;

  @override
  void initState() {
    super.initState();
    _pageController = PageController(viewportFraction: 1.0);

    // Register reset callback if provided
    widget.onResetCallback?.call(_resetToFirstJoke);
  }

  @override
  void dispose() {
    // Clear rail bottom slot when leaving the screen
    try {
      ref.read(railBottomSlotProvider.notifier).state = null;
    } catch (_) {}
    _pageController.dispose();
    super.dispose();
  }

  /// Reset to the first joke (called from outside)
  void _resetToFirstJoke() {
    if (mounted && _pageController.hasClients) {
      setState(() {
        _currentPage = 0;
        _currentImageStates.clear(); // Reset all image states
      });

      _pageController.animateToPage(
        0,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    }
  }

  void _onImageStateChanged(int jokeIndex, int imageIndex) {
    setState(() {
      _currentImageStates[jokeIndex] = imageIndex;
    });
  }

  void _goToNextJoke(int totalJokes) {
    final nextPage = _currentPage + 1;
    if (nextPage < totalJokes) {
      // Set navigation method to tap before triggering page change
      _lastNavigationMethod = AnalyticsNavigationMethod.tap;
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
      // Note: Analytics will be tracked in onPageChanged callback
      // which is triggered by the nextPage() call above
    }
  }

  void _goToNextJokeViaCTA(int totalJokes) {
    final nextPage = _currentPage + 1;
    if (nextPage < totalJokes) {
      _lastNavigationMethod = AnalyticsNavigationMethod.ctaReveal;
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

    final bool showReveal = hasPunchlineImage && currentImageIndex == 0;
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
                    _goToNextJokeViaCTA(total);
                  }
                },
          child: Text(label),
        ),
      ),
    );
  }

  // Hint system removed

  @override
  Widget build(BuildContext context) {
    final jokesWithDateAsyncValue = ref.watch(
      widget.jokesProvider ?? monthlyJokesWithDateProvider,
    );

    return AdaptiveAppBarScreen(
      title: widget.screenTitle,
      body: jokesWithDateAsyncValue.when(
        data: (jokesWithDates) {
          final isLandscape =
              MediaQuery.of(context).orientation == Orientation.landscape;
          // Update NavigationRail bottom slot in landscape (defer to post-frame). Only if rail exists.
          final bool railPresent =
              context.dependOnInheritedWidgetOfExactType<RailHost>() != null;
          final Widget? railBottomWidget = isLandscape && railPresent
              ? _buildCTAButton(
                  context: context,
                  jokesWithDates: jokesWithDates,
                )
              : null;
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!mounted) return;
            ref.read(railBottomSlotProvider.notifier).state = railBottomWidget;
          });

          if (jokesWithDates.isEmpty) {
            final empty = const Center(
              child: Text('No jokes found! Try adding some.'),
            );
            if (isLandscape && railPresent) return empty;
            return Stack(
              children: [
                empty,
                Positioned(
                  left: 0,
                  right: 0,
                  bottom: 0,
                  child: _buildCTAButton(
                    context: context,
                    jokesWithDates: jokesWithDates,
                  ),
                ),
              ],
            );
          }

          // Ensure current page is within bounds
          final safeCurrentPage = _currentPage
              .clamp(0, jokesWithDates.length - 1)
              .toInt();
          if (_currentPage != safeCurrentPage) {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted) {
                setState(() {
                  _currentPage = safeCurrentPage;
                });
              }
            });
          }

          return Stack(
            children: [
              PageView.builder(
                key: const Key('joke_viewer_page_view'),
                controller: _pageController,
                scrollDirection: Axis.vertical,
                itemCount: jokesWithDates.length,
                onPageChanged: (index) {
                  if (mounted) {
                    setState(() {
                      _currentPage = index;
                    });

                    // Track analytics for joke navigation
                    final jokeWithDate = jokesWithDates[index];
                    final joke = jokeWithDate.joke;
                    // index 0 = today (0 days back), index 1 = yesterday (1 day back), etc.
                    final jokeScrollDepth = index;

                    final analyticsService = ref.read(analyticsServiceProvider);
                    analyticsService.logJokeNavigation(
                      joke.id,
                      jokeScrollDepth,
                      method: _lastNavigationMethod,
                      jokeContext: widget.jokeContext,
                    );

                    // Reset navigation method to swipe for next potential swipe gesture
                    _lastNavigationMethod = AnalyticsNavigationMethod.swipe;
                  }
                },
                itemBuilder: (context, index) {
                  final jokeWithDate = jokesWithDates[index];
                  final joke = jokeWithDate.joke;
                  final date = jokeWithDate.date;

                  // Format date as title
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

                  // Determine orientation and apply appropriate sizing
                  final isLandscape =
                      MediaQuery.of(context).orientation ==
                      Orientation.landscape;

                  final controller =
                      _carouselControllers[index] ??
                      (_carouselControllers[index] =
                          JokeImageCarouselController());

                  return Center(
                    child: Container(
                      width: isLandscape ? null : double.infinity,
                      height: isLandscape ? double.infinity : null,
                      padding: EdgeInsets.all(isLandscape ? 0.0 : 16.0),
                      child: JokeCard(
                        key: Key(joke.id),
                        joke: joke,
                        index: index,
                        title: formattedDate,
                        onPunchlineTap: () =>
                            _goToNextJoke(jokesWithDates.length),
                        onImageStateChanged: (imageIndex) =>
                            _onImageStateChanged(index, imageIndex),
                        isAdminMode: false,
                        jokesToPreload: jokesToPreload,
                        showSaveButton: true,
                        showShareButton: true,
                        showThumbsButtons: false,
                        jokeContext: widget.jokeContext,
                        controller: controller,
                      ),
                    ),
                  );
                },
              ),
              if (!isLandscape || !railPresent)
                Positioned(
                  left: 0,
                  right: 0,
                  bottom: 0,
                  child: _buildCTAButton(
                    context: context,
                    jokesWithDates: jokesWithDates,
                  ),
                ),
            ],
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stackTrace) {
          debugPrint('Error loading jokes: $error');
          debugPrint('Stack trace: $stackTrace');
          // Log domain-specific analytics event for load error
          final analyticsService = ref.read(analyticsServiceProvider);
          analyticsService.logErrorJokesLoad(
            source: widget.jokesProvider == null ? 'monthly' : 'saved',
            errorMessage: error.toString(),
          );
          return Center(child: Text('Error loading jokes: $error'));
        },
      ),
    );
  }
}
