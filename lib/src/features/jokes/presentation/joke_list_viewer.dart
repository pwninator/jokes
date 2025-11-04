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
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_navigation_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_slots.dart';
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
    this.injectionStrategies = const [],
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
  final List<JokeListInjectionStrategy> injectionStrategies;

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

  int? _nearestJokeIndexForSlot(JokeListSlotSequence sequence, int slotIndex) {
    final direct = sequence.jokeIndexForSlot(slotIndex);
    if (direct != null) return direct;
    final prevSlot = sequence.lastJokeSlotAtOrBefore(slotIndex);
    if (prevSlot != null) {
      final prevIndex = sequence.jokeIndexForSlot(prevSlot);
      if (prevIndex != null) return prevIndex;
    }
    final nextSlot = sequence.firstJokeSlotAfter(slotIndex);
    if (nextSlot != null) {
      final nextIndex = sequence.jokeIndexForSlot(nextSlot);
      if (nextIndex != null) return nextIndex;
    }
    return null;
  }

  int? _slotIndexForStoredJoke(
    JokeListSlotSequence sequence,
    int storedJokeIndex,
  ) {
    if (!sequence.hasJokes) return null;
    final maxIndex = sequence.totalJokes - 1;
    final clamped = storedJokeIndex.clamp(0, maxIndex);
    final normalized = (clamped as num).toInt();
    return sequence.slotIndexForJokeIndex(normalized);
  }

  Widget _buildCTAButton({
    required BuildContext context,
    required JokeListSlotSequence slotSequence,
  }) {
    final isLandscape =
        MediaQuery.of(context).orientation == Orientation.landscape;
    final bool isEmpty = !slotSequence.hasJokes;

    Joke? currentJoke;
    String? currentJokeId;
    int? currentJokeIndex;
    if (!isEmpty) {
      currentJokeIndex = slotSequence.jokeIndexForSlot(_currentPage);
      if (currentJokeIndex != null) {
        final jokeWithDate = slotSequence.jokes[currentJokeIndex];
        currentJoke = jokeWithDate.joke;
        currentJokeId = currentJoke.id;
      }
    }
    final bool isLastSlot =
        slotSequence.slotCount == 0 ||
        _currentPage >= slotSequence.slotCount - 1;

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
    final bool disabled =
        slotSequence.slotCount == 0 || (!showReveal && isLastSlot);

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
                      slotSequence.slotCount,
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
        if (widget.dataSource != null) {
          hasMore = ref.watch(widget.dataSource!.hasMore);
          isLoading = ref.watch(widget.dataSource!.isLoading);
        }
        final slotSequence = JokeListSlotSequence(
          jokes: jokesWithDates,
          strategies: widget.injectionStrategies,
          hasMore: hasMore,
          isLoading: isLoading,
        );
        final targetSlot = _slotIndexForStoredJoke(
          slotSequence,
          storedJokeIndex,
        );
        final nearestForCurrent = _nearestJokeIndexForSlot(
          slotSequence,
          _currentPage,
        );
        final shouldJump =
            targetSlot != null &&
            targetSlot != _currentPage &&
            (storedJokeIndex != nearestForCurrent ||
                !_pageController.hasClients);
        if (shouldJump) {
          _scheduleJumpTo(targetSlot);
        }
        final isLandscape =
            MediaQuery.of(context).orientation == Orientation.landscape;
        final bool railPresent =
            context.dependOnInheritedWidgetOfExactType<RailHost>() != null;
        final Widget? railBottomWidget =
            (isLandscape && railPresent && slotSequence.hasJokes)
            ? _buildCTAButton(context: context, slotSequence: slotSequence)
            : null;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (!mounted) return;
          final current = ref.read(railBottomSlotProvider);
          if (!identical(current, railBottomWidget)) {
            ref.read(railBottomSlotProvider.notifier).state = railBottomWidget;
          }
        });

        if (slotSequence.slotCount == 0) {
          // Defensive: if a data source forgot to emit loading on first-load,
          // fallback to loading UI when it reports loading and no items.
          if (widget.dataSource != null &&
              ref.watch(widget.dataSource!.isDataPending) == true) {
            return const Center(child: CircularProgressIndicator());
          }

          final isOnline = ref.read(isOnlineNowProvider);
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
                _buildCTAButton(context: context, slotSequence: slotSequence),
            ],
          );
        }

        final safeCurrentPage = _currentPage
            .clamp(0, slotSequence.slotCount - 1)
            .toInt();
        if (_currentPage != safeCurrentPage) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              setState(() {
                _currentPage = safeCurrentPage;
              });
              final fallbackIndex = _nearestJokeIndexForSlot(
                slotSequence,
                safeCurrentPage,
              );
              if (fallbackIndex != null) {
                ref
                        .read(
                          jokeViewerPageIndexProvider(widget.viewerId).notifier,
                        )
                        .state =
                    fallbackIndex;
              }
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
                itemCount: slotSequence.slotCount,
                onPageChanged: (index) {
                  if (mounted) {
                    setState(() {
                      _currentPage = index;
                    });
                    if (_scheduledJumpTarget == index) {
                      _scheduledJumpTarget = null;
                    }
                    final jokeIndex = slotSequence.jokeIndexForSlot(index);
                    final previousStoredIndex = ref.read(
                      jokeViewerPageIndexProvider(widget.viewerId),
                    );
                    final nearestIndex = _nearestJokeIndexForSlot(
                      slotSequence,
                      index,
                    );
                    final nextStoredIndex =
                        jokeIndex ?? nearestIndex ?? previousStoredIndex;
                    ref
                            .read(
                              jokeViewerPageIndexProvider(
                                widget.viewerId,
                              ).notifier,
                            )
                            .state =
                        nextStoredIndex;

                    // Report viewing position to data source for auto-loading
                    final int? viewingIndex;
                    if (jokeIndex != null) {
                      viewingIndex = jokeIndex;
                    } else {
                      final previousSlot = slotSequence.lastJokeSlotAtOrBefore(
                        index,
                      );
                      viewingIndex = previousSlot != null
                          ? slotSequence.jokeIndexForSlot(previousSlot)
                          : null;
                    }
                    if (viewingIndex != null) {
                      widget.dataSource?.updateViewingIndex(viewingIndex);
                    }

                    if (jokeIndex != null) {
                      final analyticsService = ref.read(
                        analyticsServiceProvider,
                      );
                      final jokeWithDate = slotSequence.jokes[jokeIndex];
                      final joke = jokeWithDate.joke;
                      final jokeScrollDepth = jokeIndex;

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
                    }

                    _lastNavigationMethod = AnalyticsNavigationMethod.swipe;
                  }
                },
                itemBuilder: (context, index) {
                  final slot = slotSequence.slotAt(index);
                  final isLandscape =
                      MediaQuery.of(context).orientation ==
                      Orientation.landscape;

                  Widget child;
                  String keySuffix;

                  if (slot is JokeSlot) {
                    final jokeWithDate = slot.joke;
                    final joke = jokeWithDate.joke;
                    final date = jokeWithDate.date;
                    final dataSource = jokeWithDate.dataSource;

                    final formattedDate = date != null
                        ? '${date.month}/${date.day}/${date.year}'
                        : null;

                    final List<Joke> jokesToPreload = [];
                    int? nextSlot = slotSequence.firstJokeSlotAfter(index);
                    if (nextSlot != null) {
                      final nextJokeIndex = slotSequence.jokeIndexForSlot(
                        nextSlot,
                      );
                      if (nextJokeIndex != null) {
                        jokesToPreload.add(
                          slotSequence.jokes[nextJokeIndex].joke,
                        );
                      }
                      nextSlot = slotSequence.firstJokeSlotAfter(nextSlot);
                      if (nextSlot != null) {
                        final secondIndex = slotSequence.jokeIndexForSlot(
                          nextSlot,
                        );
                        if (secondIndex != null) {
                          jokesToPreload.add(
                            slotSequence.jokes[secondIndex].joke,
                          );
                        }
                      }
                    }

                    final controller =
                        _carouselControllers[joke.id] ??
                        (_carouselControllers[joke.id] =
                            JokeImageCarouselController());

                    child = JokeCard(
                      key: Key(joke.id),
                      joke: joke,
                      index: slot.jokeIndex,
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
                    keySuffix = 'joke-${joke.id}';
                  } else if (slot is InjectedSlot) {
                    child = slot.build(context);
                    keySuffix = 'injected-${slot.id}';
                  } else {
                    throw StateError(
                      'Unsupported slot type: ${slot.runtimeType}',
                    );
                  }

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
            if ((!isLandscape || !railPresent) && slotSequence.hasJokes)
              _buildCTAButton(context: context, slotSequence: slotSequence),
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
