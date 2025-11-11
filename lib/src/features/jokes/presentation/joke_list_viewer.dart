import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/bouncing_button.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart'
    show JokeImageCarouselController;
import 'package:snickerdoodle/src/config/router/app_router.dart' show RailHost;
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_navigation_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_entries.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_entry_renderers.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/slot_source.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';
import 'package:snickerdoodle/src/utils/joke_viewer_utils.dart';

/// Reusable vertical viewer for a list of jokes with CTA button
class JokeListViewer extends ConsumerStatefulWidget {
  const JokeListViewer({
    super.key,
    required this.slotSource,
    required this.jokeContext,
    required this.viewerId,
    this.onInitRegisterReset,
    this.showCtaWhenEmpty = false,
    this.emptyState,
    this.showSimilarSearchButton = true,
  });

  final SlotSource slotSource;
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
  static const List<SlotEntryRenderer> _slotEntryRenderers = [
    JokeSlotEntryRenderer(),
    EndOfFeedSlotEntryRenderer(),
  ];

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

  JokeImageCarouselController _controllerForJoke(String jokeId) {
    return _carouselControllers.putIfAbsent(
      jokeId,
      () => JokeImageCarouselController(),
    );
  }

  List<Joke> _jokesToPreload(List<SlotEntry> entries, int index) {
    final jokes = <Joke>[];
    for (var offset = 1; offset <= 2; offset++) {
      final targetIndex = index + offset;
      if (targetIndex >= entries.length) {
        break;
      }
      final entry = entries[targetIndex];
      if (entry is JokeSlotEntry) {
        jokes.add(entry.joke.joke);
      }
    }
    return jokes;
  }

  void _goToNextCard(int totalEntries, {required String method}) {
    final nextPage = _currentPage + 1;
    if (nextPage >= totalEntries) {
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

  int? _slotIndexForStoredJoke(int totalEntries, int storedJokeIndex) {
    if (totalEntries == 0) return null;
    final maxIndex = totalEntries - 1;
    final clamped = storedJokeIndex.clamp(0, maxIndex);
    final normalized = (clamped as num).toInt();
    return normalized;
  }

  Widget _buildCTAButton({
    required BuildContext context,
    required List<SlotEntry> entries,
  }) {
    final isLandscape =
        MediaQuery.of(context).orientation == Orientation.landscape;
    final bool isEmpty = entries.isEmpty;

    Joke? currentJoke;
    String? currentJokeId;
    int? currentJokeIndex;
    bool currentEntryIsJoke = false;
    if (!isEmpty) {
      currentJokeIndex = _currentPage.clamp(0, entries.length - 1);
      final currentEntry = entries[currentJokeIndex];
      if (currentEntry is JokeSlotEntry) {
        final jokeWithDate = currentEntry.joke;
        currentEntryIsJoke = true;
        currentJoke = jokeWithDate.joke;
        currentJokeId = currentJoke.id;
      }
    }
    final bool isLastEntry =
        entries.isEmpty || _currentPage >= entries.length - 1;

    final bool hasPunchlineImage =
        currentEntryIsJoke &&
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
    final bool disabled = entries.isEmpty || (!showReveal && isLastEntry);

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
                      entries.length,
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
    required int entryCount,
  }) {
    if (!_isJokeFeedViewer || _emptyStateLogged) return;
    final analyticsService = ref.read(analyticsServiceProvider);
    analyticsService.logJokeFeedEndEmptyViewed(jokeContext: widget.jokeContext);
    final dataSourceType = widget.slotSource.debugLabel ?? 'unknown';
    final ({int count, bool hasMore}) resultMetadata = ref.read(
      widget.slotSource.resultCountProvider,
    );
    final logDetails = <String, Object?>{
      'viewerId': widget.viewerId,
      'jokeContext': widget.jokeContext,
      'hasMore': hasMore,
      'isLoading': isLoading,
      'isDataPending': isDataPending,
      'isOnline': isOnline,
      'entryCount': entryCount,
      'dataSourceType': dataSourceType,
      'result.count': resultMetadata.count,
      'result.hasMore': resultMetadata.hasMore,
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

  SlotEntryRenderer _rendererFor(SlotEntry entry) {
    for (final renderer in _slotEntryRenderers) {
      if (renderer.supports(entry)) {
        return renderer;
      }
    }
    throw StateError('No renderer registered for ${entry.runtimeType}');
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

    final slotEntriesAsync = ref.watch(widget.slotSource.slotsProvider);

    return slotEntriesAsync.when(
      data: (entries) {
        final hasMore = ref.watch(widget.slotSource.hasMoreProvider);
        final isLoading = ref.watch(widget.slotSource.isLoadingProvider);
        final isDataPending = ref.watch(
          widget.slotSource.isDataPendingProvider,
        );
        final totalEntries = entries.length;
        if (_emptyStateLogged && totalEntries > 0 && _isJokeFeedViewer) {
          _emptyStateLogged = false;
        }
        final targetSlot = _slotIndexForStoredJoke(
          totalEntries,
          storedJokeIndex,
        );
        if (targetSlot != null && targetSlot != _currentPage) {
          _scheduleJumpTo(targetSlot);
        }
        final isLandscape =
            MediaQuery.of(context).orientation == Orientation.landscape;
        final bool railPresent =
            context.dependOnInheritedWidgetOfExactType<RailHost>() != null;
        final Widget? railBottomWidget =
            (isLandscape && railPresent && totalEntries > 0)
            ? _buildCTAButton(context: context, entries: entries)
            : null;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (!mounted) return;
          final current = ref.read(railBottomSlotProvider);
          if (!identical(current, railBottomWidget)) {
            ref.read(railBottomSlotProvider.notifier).state = railBottomWidget;
          }
        });

        if (totalEntries == 0) {
          final isOnline = ref.read(isOnlineNowProvider);
          _maybeLogFeedEmptyState(
            hasMore: hasMore,
            isLoading: isLoading,
            isDataPending: isDataPending,
            isOnline: isOnline,
            entryCount: totalEntries,
          );
          // Defensive: if a data source forgot to emit loading on first-load,
          // fallback to loading UI when it reports loading and no items.
          if (isDataPending) {
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
                _buildCTAButton(context: context, entries: entries),
            ],
          );
        }

        final safeCurrentPage = _currentPage.clamp(0, totalEntries - 1).toInt();
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
                itemCount: totalEntries,
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

                    widget.slotSource.onViewingIndexUpdated?.call(index);

                    final analyticsService = ref.read(analyticsServiceProvider);
                    Joke? analyticsJoke;
                    String? analyticsJokeContextSuffix;
                    if (entries[index] case JokeSlotEntry(:final joke)) {
                      analyticsJoke = joke.joke;
                      analyticsJokeContextSuffix = joke.dataSource;
                    }

                    final viewerCtx = getJokeViewerContext(context, ref);
                    if (analyticsJoke != null) {
                      analyticsService.logJokeNavigation(
                        analyticsJoke.id,
                        index,
                        method: _lastNavigationMethod,
                        jokeContext: widget.jokeContext,
                        jokeContextSuffix: analyticsJokeContextSuffix,
                        jokeViewerMode: viewerCtx.jokeViewerMode,
                        brightness: viewerCtx.brightness,
                        screenOrientation: viewerCtx.screenOrientation,
                      );
                    }

                    _lastNavigationMethod = AnalyticsNavigationMethod.swipe;
                  }
                },
                itemBuilder: (context, index) {
                  final isLandscape =
                      MediaQuery.of(context).orientation ==
                      Orientation.landscape;
                  final entry = entries[index];
                  final renderer = _rendererFor(entry);

                  final SlotEntryViewConfig viewConfig;
                  if (entry is JokeSlotEntry) {
                    final jokeWithDate = entry.joke;
                    final joke = jokeWithDate.joke;
                    final date = jokeWithDate.date;
                    final formattedDate = date != null
                        ? '${date.month}/${date.day}/${date.year}'
                        : null;
                    viewConfig = SlotEntryViewConfig(
                      context: context,
                      ref: ref,
                      index: index,
                      isLandscape: isLandscape,
                      jokeContext: widget.jokeContext,
                      showSimilarSearchButton: widget.showSimilarSearchButton,
                      jokeConfig: JokeEntryViewConfig(
                        formattedDate: formattedDate,
                        jokesToPreload: _jokesToPreload(entries, index),
                        carouselController: _controllerForJoke(joke.id),
                        onImageStateChanged: (imageIndex) =>
                            _onImageStateChanged(joke.id, imageIndex),
                        dataSource: jokeWithDate.dataSource,
                      ),
                    );
                  } else {
                    viewConfig = SlotEntryViewConfig(
                      context: context,
                      ref: ref,
                      index: index,
                      isLandscape: isLandscape,
                      jokeContext: widget.jokeContext,
                      showSimilarSearchButton: widget.showSimilarSearchButton,
                    );
                  }

                  final child = renderer.build(
                    entry: entry,
                    config: viewConfig,
                  );
                  final keySuffix = renderer.key(entry, viewConfig);

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
            if ((!isLandscape || !railPresent) && totalEntries > 0)
              _buildCTAButton(context: context, entries: entries),
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
