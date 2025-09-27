import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart'
    show JokeImageCarouselController;
import 'package:snickerdoodle/src/config/router/app_router.dart' show RailHost;
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_pagination.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_navigation_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';

/// Reusable vertical viewer for a list of jokes with CTA button
class JokeListViewer extends ConsumerStatefulWidget {
  const JokeListViewer({
    super.key,
    this.paginationState,
    this.paginationStateProvider,
    required this.jokeContext,
    required this.viewerId,
    this.onInitRegisterReset,
    this.showCtaWhenEmpty = false,
    this.emptyState,
    this.showSimilarSearchButton = true,
    this.loadMoreConfig,
  }) : assert(
         paginationState != null || paginationStateProvider != null,
         'Provide either paginationState or paginationStateProvider',
       );

  final JokeListPaginationState? paginationState;
  final ProviderListenable<JokeListPaginationState>? paginationStateProvider;
  final String jokeContext;
  final String viewerId;
  final Function(VoidCallback)? onInitRegisterReset;
  final bool showCtaWhenEmpty;
  final Widget? emptyState;
  final bool showSimilarSearchButton;
  final JokeListLoadMoreConfig? loadMoreConfig;

  @override
  ConsumerState<JokeListViewer> createState() => _JokeListViewerState();
}

class _JokeListViewerState extends ConsumerState<JokeListViewer> {
  static const _emptyJokes = <JokeWithDate>[];

  int _currentPage = 0;
  late final PageController _pageController;
  final Map<String, int> _currentImageStates = {};
  final Map<String, JokeImageCarouselController> _carouselControllers = {};
  String _lastNavigationMethod = AnalyticsNavigationMethod.swipe;
  bool _pendingForwardLoad = false;
  bool _pendingBackwardLoad = false;
  AsyncValue<List<JokeWithDate>>? _lastItemsValue;
  List<String> _lastKnownIds = const [];
  String? _currentJokeId;
  JokeListPaginationState? _latestState;

  @override
  void initState() {
    super.initState();
    final initialIndex = ref.read(jokeViewerPageIndexProvider(widget.viewerId));
    _currentPage = initialIndex;
    _pageController = PageController(initialPage: initialIndex);
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
    if (!mounted || !_pageController.hasClients) return;
    ref.read(jokeViewerPageIndexProvider(widget.viewerId).notifier).state = 0;
    setState(() {
      _currentPage = 0;
      _currentJokeId = _lastKnownIds.isNotEmpty ? _lastKnownIds.first : null;
      _currentImageStates.clear();
    });
    _pageController.jumpToPage(0);
  }

  void _cleanupStateForIds(List<String> validIds) {
    if (_currentImageStates.isNotEmpty) {
      _currentImageStates.removeWhere((key, value) => !validIds.contains(key));
    }
    if (_carouselControllers.isNotEmpty) {
      final remove = _carouselControllers.keys
          .where((key) => !validIds.contains(key))
          .toList();
      for (final key in remove) {
        _carouselControllers.remove(key);
      }
    }
  }

  void _syncWithState(JokeListPaginationState state) {
    _latestState = state;
    final itemsValue = state.items;

    if (_lastItemsValue == itemsValue) {
      if (!state.forwardStatus.isLoading) _pendingForwardLoad = false;
      if (!state.backwardStatus.isLoading) _pendingBackwardLoad = false;
      return;
    }
    _lastItemsValue = itemsValue;

    final jokes = itemsValue.valueOrNull ?? _emptyJokes;
    final ids = jokes.map((j) => j.joke.id).toList(growable: false);

    _cleanupStateForIds(ids);
    _lastKnownIds = ids;

    if (!state.forwardStatus.isLoading) _pendingForwardLoad = false;
    if (!state.backwardStatus.isLoading) _pendingBackwardLoad = false;

    if (ids.isEmpty) {
      _currentJokeId = null;
      _currentPage = 0;
      return;
    }

    if (_currentJokeId == null) {
      final savedIndex = ref.read(jokeViewerPageIndexProvider(widget.viewerId));
      final desiredIndex = savedIndex.clamp(0, ids.length - 1);
      _currentJokeId = ids[desiredIndex];
      _schedulePageJump(desiredIndex);
    } else {
      final currentIndex = ids.indexOf(_currentJokeId!);
      if (currentIndex == -1) {
        final fallbackIndex = _currentPage.clamp(0, ids.length - 1);
        _currentJokeId = ids[fallbackIndex];
        _schedulePageJump(fallbackIndex);
      } else if (currentIndex != _currentPage) {
        _schedulePageJump(currentIndex);
      }
    }

    final currentIndex = ids.indexOf(_currentJokeId!);
    if (currentIndex != -1) {
      _maybeTriggerLoadMore(index: currentIndex, jokes: jokes, state: state);
    }
  }

  void _schedulePageJump(int index) {
    if (index < 0) return;
    if (index == _currentPage) return;
    final newId = index < _lastKnownIds.length ? _lastKnownIds[index] : null;
    _currentJokeId = newId;
    _currentPage = index;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (_pageController.hasClients) {
        _pageController.jumpToPage(index);
      }
      ref.read(jokeViewerPageIndexProvider(widget.viewerId).notifier).state =
          index;
    });
  }

  void _onImageStateChanged(String jokeId, int imageIndex) {
    setState(() {
      _currentImageStates[jokeId] = imageIndex;
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

  void _maybeTriggerLoadMore({
    required int index,
    required List<JokeWithDate> jokes,
    required JokeListPaginationState state,
  }) {
    final config = widget.loadMoreConfig;
    if (config == null) return;

    final forwardTrigger = config.forward;
    if (forwardTrigger != null &&
        state.forwardStatus.hasMore &&
        !state.forwardStatus.isLoading &&
        !_pendingForwardLoad) {
      final remainingForward = jokes.length - 1 - index;
      if (remainingForward <= forwardTrigger.threshold) {
        _pendingForwardLoad = true;
        forwardTrigger.onThresholdReached(ref).whenComplete(() {
          if (!mounted) {
            _pendingForwardLoad = false;
            return;
          }
          setState(() {
            _pendingForwardLoad = false;
          });
        });
      }
    }

    final backwardTrigger = config.backward;
    if (backwardTrigger != null &&
        state.backwardStatus.hasMore &&
        !state.backwardStatus.isLoading &&
        !_pendingBackwardLoad) {
      final remainingBackward = index;
      if (remainingBackward <= backwardTrigger.threshold) {
        _pendingBackwardLoad = true;
        backwardTrigger.onThresholdReached(ref).whenComplete(() {
          if (!mounted) {
            _pendingBackwardLoad = false;
            return;
          }
          setState(() {
            _pendingBackwardLoad = false;
          });
        });
      }
    }
  }

  void _handlePageChanged(int index, List<JokeWithDate> jokes) {
    if (!mounted || index < 0 || index >= jokes.length) return;

    final joke = jokes[index].joke;
    setState(() {
      _currentPage = index;
      _currentJokeId = joke.id;
    });
    ref.read(jokeViewerPageIndexProvider(widget.viewerId).notifier).state =
        index;

    final analyticsService = ref.read(analyticsServiceProvider);
    final revealModeEnabled = ref.read(jokeViewerRevealProvider);
    analyticsService.logJokeNavigation(
      joke.id,
      index,
      method: _lastNavigationMethod,
      jokeContext: widget.jokeContext,
      jokeViewerMode: revealModeEnabled
          ? JokeViewerMode.reveal
          : JokeViewerMode.bothAdaptive,
    );

    final state = _latestState;
    if (state != null) {
      _maybeTriggerLoadMore(index: index, jokes: jokes, state: state);
    }

    _lastNavigationMethod = AnalyticsNavigationMethod.swipe;
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
    final int currentImageIndex = currentJoke != null
        ? (_currentImageStates[currentJoke.id] ?? 0)
        : 0;

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
                    final joke = jokesWithDates[_currentPage].joke;
                    setState(() {
                      _currentImageStates[joke.id] = 1;
                    });
                    _carouselControllers[joke.id]?.revealPunchline();
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
    final stateProvider = widget.paginationStateProvider;
    final JokeListPaginationState state;
    if (widget.paginationState != null) {
      state = widget.paginationState!;
    } else if (stateProvider != null) {
      state = ref.watch(stateProvider);
    } else {
      state = const JokeListPaginationState(
        items: AsyncValue<List<JokeWithDate>>.data(<JokeWithDate>[]),
      );
    }
    _syncWithState(state);

    final AsyncValue<List<JokeWithDate>> effectiveAsync = state.items;

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

        return Column(
          children: [
            Expanded(
              child: PageView.builder(
                key: const Key('joke_viewer_page_view'),
                controller: _pageController,
                scrollDirection: Axis.vertical,
                itemCount: jokesWithDates.length,
                onPageChanged: (index) =>
                    _handlePageChanged(index, jokesWithDates),
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

                  final controller = _carouselControllers[joke.id] ??=
                      JokeImageCarouselController();

                  // Title shows index (1-based) for search context, otherwise date (if any)
                  final String? titleForCard =
                      widget.jokeContext == AnalyticsJokeContext.search
                      ? '${index + 1}'
                      : formattedDate;

                  return Center(
                    child: Container(
                      width: isLandscape ? null : double.infinity,
                      height: isLandscape ? double.infinity : null,
                      padding: const EdgeInsets.only(
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
                            _onImageStateChanged(joke.id, imageIndex),
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
