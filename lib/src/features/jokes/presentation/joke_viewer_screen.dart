import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class JokeViewerScreen extends ConsumerStatefulWidget implements TitledScreen {
  const JokeViewerScreen({super.key, this.onResetCallback});

  final Function(VoidCallback)? onResetCallback;

  @override
  String get title => 'Jokes';

  @override
  ConsumerState<JokeViewerScreen> createState() => _JokeViewerScreenState();
}

class _JokeViewerScreenState extends ConsumerState<JokeViewerScreen> {
  int _currentPage = 0;
  late PageController _pageController;
  double _hintOpacity = 1.0;

  // Track user learning progress
  static bool _hasSeenSetupToPunchline = false;
  static bool _hasSeenPunchlineToNextJoke = false;

  // Track current image state for each joke (joke index -> image index: 0=setup, 1=punchline)
  final Map<int, int> _currentImageStates = {};

  @override
  void initState() {
    super.initState();
    _pageController = PageController(viewportFraction: 0.9);
    _pageController.addListener(_onScrollChanged);

    // Register reset callback if provided
    widget.onResetCallback?.call(_resetToFirstJoke);
  }

  @override
  void dispose() {
    _pageController.removeListener(_onScrollChanged);
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

      _updateHintOpacity();
    }
  }

  void _onScrollChanged() {
    if (!_pageController.hasClients) return;

    final position = _pageController.page ?? _currentPage.toDouble();
    final currentPageDouble = _currentPage.toDouble();
    final distanceFromCurrentPage = (position - currentPageDouble).abs();

    _updateHintOpacity(distanceFromCurrentPage);
  }

  void _updateHintOpacity([double? scrollDistance]) {
    if (!_shouldShowHint()) {
      if (_hintOpacity != 0.0) {
        setState(() => _hintOpacity = 0.0);
      }
      return;
    }

    final newOpacity =
        scrollDistance != null ? _calculateScrollOpacity(scrollDistance) : 1.0;

    if (_hintOpacity != newOpacity) {
      setState(() => _hintOpacity = newOpacity);
    }
  }

  double _calculateScrollOpacity(double distanceFromCurrentPage) {
    const stepSize = 0.01;
    const opacityReduction = 0.2;
    const maxDistance = (1 / opacityReduction) * stepSize;

    final quantizedDistance =
        (distanceFromCurrentPage / stepSize).round() * stepSize;

    return quantizedDistance >= maxDistance
        ? 0.0
        : 1.0 - (quantizedDistance / stepSize) * opacityReduction;
  }

  void _markGestureLearned({bool? setupToPunchline, bool? punchlineToNext}) {
    bool shouldUpdate = false;

    if (setupToPunchline == true && !_hasSeenSetupToPunchline) {
      _hasSeenSetupToPunchline = true;
      shouldUpdate = true;
    }

    if (punchlineToNext == true && !_hasSeenPunchlineToNextJoke) {
      _hasSeenPunchlineToNextJoke = true;
      shouldUpdate = true;
    }

    if (shouldUpdate) {
      setState(() {}); // Trigger rebuild for hint visibility
      _updateHintOpacity();
    }
  }

  void _onSetupToPunchlineTransition() {
    _markGestureLearned(setupToPunchline: true);
  }

  void _onImageStateChanged(int jokeIndex, int imageIndex) {
    setState(() {
      _currentImageStates[jokeIndex] = imageIndex;
    });

    // Only update hint if it's the current page
    if (jokeIndex == _currentPage) {
      _updateHintOpacity();
    }
  }

  String _getHintText() {
    final currentImageIndex = _currentImageStates[_currentPage] ?? 0;
    return currentImageIndex == 0
        ? 'Tap image for punchline!'
        : 'Tap image for next joke!';
  }

  void _goToNextJoke(int totalJokes) {
    _markGestureLearned(punchlineToNext: true);

    final nextPage = _currentPage + 1;
    if (nextPage < totalJokes) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    }
  }

  bool _shouldShowHint() {
    final currentImageIndex = _currentImageStates[_currentPage] ?? 0;

    if (currentImageIndex == 0) {
      // Showing setup image - only show hint if user hasn't learned setup->punchline
      return !_hasSeenSetupToPunchline;
    } else {
      // Showing punchline image - only show hint if user hasn't learned punchline->next joke
      return !_hasSeenPunchlineToNextJoke;
    }
  }

  @override
  Widget build(BuildContext context) {
    final jokesWithDateAsyncValue = ref.watch(monthlyJokesWithDateProvider);

    return AdaptiveAppBarScreen(
      title: 'Daily Jokes',
      body: jokesWithDateAsyncValue.when(
        data: (jokesWithDates) {
          if (jokesWithDates.isEmpty) {
            return const Center(
              child: Text('No jokes found! Try adding some.'),
            );
          }

          // Ensure current page is within bounds
          final safeCurrentPage = _currentPage.clamp(
            0,
            jokesWithDates.length - 1,
          );
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
                    // Update hint for new page
                    _updateHintOpacity();
                  }
                },
                itemBuilder: (context, index) {
                  final jokeWithDate = jokesWithDates[index];
                  final joke = jokeWithDate.joke;
                  final date = jokeWithDate.date;

                  // Format date as title
                  final formattedDate =
                      '${date.month}/${date.day}/${date.year}';

                  final List<Joke> jokesToPreload = [];
                  if (index + 1 < jokesWithDates.length) {
                    jokesToPreload.add(jokesWithDates[index + 1].joke);
                  }
                  if (index + 2 < jokesWithDates.length) {
                    jokesToPreload.add(jokesWithDates[index + 2].joke);
                  }

                  return Center(
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: JokeCard(
                        joke: joke,
                        index: index,
                        title: formattedDate,
                        onSetupTap: _onSetupToPunchlineTransition,
                        onPunchlineTap:
                            () => _goToNextJoke(jokesWithDates.length),
                        onImageStateChanged:
                            (imageIndex) =>
                                _onImageStateChanged(index, imageIndex),
                        isAdminMode: false,
                        jokesToPreload: jokesToPreload,
                        showSaveButton: true,
                        showThumbsButtons: false,
                      ),
                    ),
                  );
                },
              ),

              // Static hint overlay that doesn't scroll
              if (_shouldShowHint())
                Positioned(
                  bottom: 20,
                  left: 0,
                  right: 0,
                  child: Center(
                    child: Opacity(
                      opacity: _hintOpacity,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 8,
                        ),
                        child: Text(
                          _getHintText(),
                          style: TextStyle(
                            color: Theme.of(
                              context,
                            ).colorScheme.onSurface.withValues(alpha: 0.6),
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),

              // Up arrow indicator (when not at first joke)
              if (_currentPage > 0)
                Positioned(
                  top: 40,
                  left: 0,
                  right: 0,
                  child: Center(
                    child: Opacity(
                      opacity: 0.4,
                      child: Icon(
                        Icons.keyboard_arrow_up,
                        color: Theme.of(
                          context,
                        ).colorScheme.onSurface.withValues(alpha: 0.6),
                        size: 24,
                      ),
                    ),
                  ),
                ),

              // Down arrow indicator (when not at last joke)
              if (_currentPage < jokesWithDates.length - 1)
                Positioned(
                  bottom: 40,
                  left: 0,
                  right: 0,
                  child: Center(
                    child: Opacity(
                      opacity: 0.4,
                      child: Icon(
                        Icons.keyboard_arrow_down,
                        color: Theme.of(
                          context,
                        ).colorScheme.onSurface.withValues(alpha: 0.6),
                        size: 24,
                      ),
                    ),
                  ),
                ),
            ],
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stackTrace) {
          debugPrint('Error loading jokes: $error');
          debugPrint('Stack trace: $stackTrace');
          return Center(child: Text('Error loading jokes: $error'));
        },
      ),
    );
  }
}
