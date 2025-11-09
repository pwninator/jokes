import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/bouncing_button.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart'
    show JokeImageCarouselController;
import 'package:snickerdoodle/src/config/router/app_router.dart' show RailHost;
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_navigation_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';
import 'package:snickerdoodle/src/utils/joke_viewer_utils.dart';

/// Reusable vertical viewer for a list of jokes with CTA button
class JokeListViewer extends ConsumerStatefulWidget {
  const JokeListViewer({
    super.key,
    this.jokesAsyncValue,
    this.jokesAsyncProvider,
    this.dataSource,
    required this.jokeContext,
    required this.viewerId,
    this.onInitRegisterReset,
    this.showCtaWhenEmpty = false,
    this.emptyState,
    this.showSimilarSearchButton = true,
  });

  final AsyncValue<List<JokeWithDate>>? jokesAsyncValue;
  final ProviderListenable<AsyncValue<List<JokeWithDate>>>? jokesAsyncProvider;
  final JokeListDataSource? dataSource;
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
  final Map<String, int> _currentImageStates = {};
  final Map<String, JokeImageCarouselController> _carouselControllers = {};
  String _lastNavigationMethod = AnalyticsNavigationMethod.swipe;
  int? _scheduledJumpTarget;
  bool _emptyStateLogged = false;

  @override
  void initState() {
    super.initState();
    _pageController = PageController(
      viewportFraction: 1.0,
      // For some reason, _resetToFirstJoke() always resets not to 0, but to this
      // initialPage value. So, set it to 0 and jump to the initialIndex so that
      // resets bring it back to 0.
      initialPage: 0,
    );
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

  void _onImageStateChanged(String jokeId, int imageIndex) {
    setState(() {
      _currentImageStates[jokeId] = imageIndex;
    });
  }

  void _goToNextCard(int totalSlots, {required String method}) {
    final nextPage = _currentPage + 1;
    if (nextPage >= totalSlots) {
      return;
    }

    _lastNavigationMethod = method;
    _pageController.animateToPage(
      nextPage,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
  }

  void _scheduleJumpTo(int targetSlot) {
    if (_scheduledJumpTarget == targetSlot) {
      return;
    }
    _scheduledJumpTarget = targetSlot;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (!_pageController.hasClients) {
        _scheduledJumpTarget = null;
        _scheduleJumpTo(targetSlot);
        return;
      }
      _pageController.jumpToPage(targetSlot);
    });
  }

  int? _slotIndexForStoredJoke(int totalSlots, int storedJokeIndex) {
    if (totalSlots == 0) return null;
    final maxIndex = totalSlots - 1;
    final clamped = storedJokeIndex.clamp(0, maxIndex);
    final normalized = (clamped as num).toInt();
    return normalized;
  }

  Widget _buildCTAButton({
    required BuildContext context,
    required List<JokeWithDate> jokes,
  }) {
    final isLandscape =
        MediaQuery.of(context).orientation == Orientation.landscape;
    final bool isEmpty = jokes.isEmpty;

    Joke? currentJoke;
    String? currentJokeId;
    int? currentJokeIndex;
    if (!isEmpty) {
      currentJokeIndex = _currentPage.clamp(0, jokes.length - 1);
      final jokeWithDate = jokes[currentJokeIndex];
      currentJoke = jokeWithDate.joke;
      currentJokeId = currentJoke.id;
    }
    final bool isLastSlot = jokes.isEmpty || _currentPage >= jokes.length - 1;

    final bool hasPunchlineImage =
        currentJoke != null &&
        currentJoke.punchlineImageUrl != null &&
        currentJoke.punchlineImageUrl!.trim().isNotEmpty;
    final int currentImageIndex = currentJokeId != null
        ? _currentImageStates[currentJokeId] ?? 0
        : 0;

    // Respect user preference: if reveal mode is disabled (show both),
    // there is nothing to reveal, so CTA should be "Next joke" only.
    final bool revealModeEnabled = ref.watch(jokeViewerRevealProvider);
    final bool showReveal =
        revealModeEnabled && hasPunchlineImage && currentImageIndex == 0;
    final String label = showReveal ? 'Reveal' : 'Next joke';
    final bool disabled = jokes.isEmpty || (!showReveal && isLastSlot);

    return SizedBox(
      width: double.infinity,
      child: SafeArea(
        minimum: isLandscape
            ? EdgeInsets.zero
            : const EdgeInsets.only(left: 16, right: 16, bottom: 16),
        child: BouncingButton(
          buttonKey: const Key('joke_list_viewer-cta-button'),
          isPositive: true,
          onPressed: disabled
              ? null
              : () {
                  if (showReveal && currentJokeId != null) {
                    final revealJokeId = currentJokeId;
                    setState(() {
                      _currentImageStates[revealJokeId] = 1;
                    });
                    _carouselControllers[revealJokeId]?.revealPunchline();
                  } else {
                    _goToNextCard(
                      jokes.length,
                      method: AnalyticsNavigationMethod.ctaNextJoke,
                    );
                  }
                },
          child: Text(
            label,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.5,
            ),
          ),
        ),
      ),
    );
  }

  void _maybeLogFeedEmptyState({
    required bool hasMore,
    required bool isLoading,
    required bool isDataPending,
    required bool isOnline,
    required int jokesLength,
    required int slotCount,
  }) {
    if (!_isJokeFeedViewer || _emptyStateLogged) return;
    final analyticsService = ref.read(analyticsServiceProvider);
    analyticsService.logJokeFeedEndEmptyViewed(jokeContext: widget.jokeContext);
    final dataSourceType = widget.dataSource?.runtimeType.toString() ?? 'none';
    final ({int count, bool hasMore})? resultMetadata =
        widget.dataSource != null
        ? ref.read(widget.dataSource!.resultCount)
        : null;
    final logDetails = <String, Object?>{
      'viewerId': widget.viewerId,
      'jokeContext': widget.jokeContext,
      'hasMore': hasMore,
      'isLoading': isLoading,
      'isDataPending': isDataPending,
      'isOnline': isOnline,
      'jokesLength': jokesLength,
      'slotCount': slotCount,
      'dataSourceType': dataSourceType,
      if (resultMetadata != null) 'result.count': resultMetadata.count,
      if (resultMetadata != null) 'result.hasMore': resultMetadata.hasMore,
    }..removeWhere((_, value) => value == null);
    final formatted = logDetails.entries
        .map((entry) => '${entry.key}=${entry.value}')
        .join(', ');
    unawaited(_logFeedEmptyStateUsage(formattedDetails: formatted));
    _emptyStateLogged = true;
  }

  Future<void> _logFeedEmptyStateUsage({
    required String formattedDetails,
  }) async {
    final appUsage = ref.read(appUsageServiceProvider);
    final jokesViewed = await appUsage.getNumJokesViewed();
    final jokesNavigated = await appUsage.getNumJokesNavigated();
    AppLogger.error(
      'PAGING_INTERNAL: COMPOSITE: Empty feed state shown ($formattedDetails, '
      'usage.jokesViewed=$jokesViewed, usage.jokesNavigated=$jokesNavigated)',
    );
  }

  bool get _isJokeFeedViewer =>
      widget.jokeContext == AnalyticsJokeContext.jokeFeed;

  @override
  Widget build(BuildContext context) {
    // If this viewer is not on the current (top) route, avoid any heavy work.
    // This prevents offscreen rebuilds from watching providers, loading images,
    // and stopping performance traces from unrelated screens still mounted in the stack.
    final route = ModalRoute.of(context);
    final bool isCurrentRoute = route?.isCurrent ?? true;
    if (!isCurrentRoute) {
      return const SizedBox.expand();
    }

    final int storedJokeIndex = ref.watch(
      jokeViewerPageIndexProvider(widget.viewerId),
    );

    final AsyncValue<List<JokeWithDate>> effectiveAsync =
        widget.dataSource != null
        ? ref.watch(widget.dataSource!.items)
        : (widget.jokesAsyncValue ??
              (widget.jokesAsyncProvider != null
                  ? ref.watch(widget.jokesAsyncProvider!)
                  : const AsyncValue<List<JokeWithDate>>.data(
                      <JokeWithDate>[],
                    )));

    return effectiveAsync.when(
      data: (jokesWithDates) {
        bool hasMore = false;
        bool isLoading = false;
        bool isDataPending = false;
        if (widget.dataSource != null) {
          hasMore = ref.watch(widget.dataSource!.hasMore);
          isLoading = ref.watch(widget.dataSource!.isLoading);
          isDataPending = ref.watch(widget.dataSource!.isDataPending);
        }
        final totalSlots = jokesWithDates.length;
        if (_emptyStateLogged && totalSlots > 0 && _isJokeFeedViewer) {
          _emptyStateLogged = false;
        }
        final targetSlot = _slotIndexForStoredJoke(totalSlots, storedJokeIndex);
        if (targetSlot != null && targetSlot != _currentPage) {
          _scheduleJumpTo(targetSlot);
        }
        final isLandscape =
            MediaQuery.of(context).orientation == Orientation.landscape;
        final bool railPresent =
            context.dependOnInheritedWidgetOfExactType<RailHost>() != null;
        final Widget? railBottomWidget =
            (isLandscape && railPresent && totalSlots > 0)
            ? _buildCTAButton(context: context, jokes: jokesWithDates)
            : null;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (!mounted) return;
          final current = ref.read(railBottomSlotProvider);
          if (!identical(current, railBottomWidget)) {
            ref.read(railBottomSlotProvider.notifier).state = railBottomWidget;
          }
        });

        if (totalSlots == 0) {
          final isOnline = ref.read(isOnlineNowProvider);
          _maybeLogFeedEmptyState(
            hasMore: hasMore,
            isLoading: isLoading,
            isDataPending: isDataPending,
            isOnline: isOnline,
            jokesLength: jokesWithDates.length,
            slotCount: totalSlots,
          );
          // Defensive: if a data source forgot to emit loading on first-load,
          // fallback to loading UI when it reports loading and no items.
          if (widget.dataSource != null && isDataPending == true) {
            return const Center(child: CircularProgressIndicator());
          }

          if (!isOnline) {
            return const Center(
              child: Text('No internet connection. Please try again later.'),
            );
          }

          final empty =
              widget.emptyState ??
              const Center(child: Text('No jokes found! Try adding some.'));
          if (isLandscape && railPresent) return empty;
          return Column(
            children: [
              Expanded(child: empty),
              if (widget.showCtaWhenEmpty)
                _buildCTAButton(context: context, jokes: jokesWithDates),
            ],
          );
        }

        final safeCurrentPage = _currentPage.clamp(0, totalSlots - 1).toInt();
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
                itemCount: totalSlots,
                onPageChanged: (index) {
                  if (mounted) {
                    setState(() {
                      _currentPage = index;
                    });
                    if (_scheduledJumpTarget == index) {
                      _scheduledJumpTarget = null;
                    }
                    ref
                            .read(
                              jokeViewerPageIndexProvider(
                                widget.viewerId,
                              ).notifier,
                            )
                            .state =
                        index;

                    widget.dataSource?.updateViewingIndex(index);

                    final analyticsService = ref.read(analyticsServiceProvider);
                    final jokeWithDate = jokesWithDates[index];
                    final joke = jokeWithDate.joke;
                    final jokeScrollDepth = index;

                    final viewerCtx = getJokeViewerContext(context, ref);
                    analyticsService.logJokeNavigation(
                      joke.id,
                      jokeScrollDepth,
                      method: _lastNavigationMethod,
                      jokeContext: widget.jokeContext,
                      jokeContextSuffix: jokeWithDate.dataSource,
                      jokeViewerMode: viewerCtx.jokeViewerMode,
                      brightness: viewerCtx.brightness,
                      screenOrientation: viewerCtx.screenOrientation,
                    );

                    _lastNavigationMethod = AnalyticsNavigationMethod.swipe;
                  }
                },
                itemBuilder: (context, index) {
                  final isLandscape =
                      MediaQuery.of(context).orientation ==
                      Orientation.landscape;

                  final jokeWithDate = jokesWithDates[index];
                  final joke = jokeWithDate.joke;
                  final date = jokeWithDate.date;
                  final dataSource = jokeWithDate.dataSource;

                  final formattedDate = date != null
                      ? '${date.month}/${date.day}/${date.year}'
                      : null;

                  final List<Joke> jokesToPreload = [];
                  final nextIndex = index + 1;
                  if (nextIndex < totalSlots) {
                    jokesToPreload.add(jokesWithDates[nextIndex].joke);
                  }
                  final secondIndex = index + 2;
                  if (secondIndex < totalSlots) {
                    jokesToPreload.add(jokesWithDates[secondIndex].joke);
                  }

                  final controller =
                      _carouselControllers[joke.id] ??
                      (_carouselControllers[joke.id] =
                          JokeImageCarouselController());

                  final child = JokeCard(
                    key: Key(joke.id),
                    joke: joke,
                    index: index,
                    title: formattedDate,
                    dataSource: dataSource,
                    onImageStateChanged: (imageIndex) =>
                        _onImageStateChanged(joke.id, imageIndex),
                    isAdminMode: false,
                    jokesToPreload: jokesToPreload,
                    showSaveButton: true,
                    showShareButton: true,
                    showAdminRatingButtons: false,
                    jokeContext: widget.jokeContext,
                    controller: controller,
                    showSimilarSearchButton: widget.showSimilarSearchButton,
                  );
                  final keySuffix = 'joke-${joke.id}';

                  return Center(
                    key: ValueKey('page-$keySuffix'),
                    child: Container(
                      width: isLandscape ? null : double.infinity,
                      height: isLandscape ? double.infinity : null,
                      padding: const EdgeInsets.only(
                        left: 16.0,
                        right: 16.0,
                        top: 4.0,
                        bottom: 4.0,
                      ),
                      child: child,
                    ),
                  );
                },
              ),
            ),
            if ((!isLandscape || !railPresent) && totalSlots > 0)
              _buildCTAButton(context: context, jokes: jokesWithDates),
          ],
        );
      },
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (error, stackTrace) {
        AppLogger.warn('Error loading jokes: $error');
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
