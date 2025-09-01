import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:smooth_page_indicator/smooth_page_indicator.dart';
import 'package:snickerdoodle/src/common_widgets/admin_approval_controls.dart';
import 'package:snickerdoodle/src/common_widgets/admin_joke_action_buttons.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/common_widgets/save_joke_button.dart';
import 'package:snickerdoodle/src/common_widgets/share_joke_button.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

/// Controller to allow parent widgets to imperatively control the
/// `JokeImageCarousel` (e.g., reveal the punchline programmatically).
class JokeImageCarouselController {
  VoidCallback? _revealPunchline;

  void _attach({required VoidCallback revealPunchline}) {
    _revealPunchline = revealPunchline;
  }

  void _detach() {
    _revealPunchline = null;
  }

  /// Programmatically reveals the punchline (moves from setup → punchline).
  void revealPunchline() {
    _revealPunchline?.call();
  }
}

class JokeImageCarousel extends ConsumerStatefulWidget {
  final Joke joke;
  final int? index;
  final VoidCallback? onSetupTap;
  final VoidCallback? onPunchlineTap;
  final Function(int)? onImageStateChanged;
  final bool isAdminMode;
  final List<Joke>? jokesToPreload;
  final bool showSaveButton;
  final bool showShareButton;
  final bool showAdminRatingButtons;
  final bool showNumSaves;
  final bool showNumShares;
  final String? title;
  final String jokeContext;
  final JokeImageCarouselController? controller;
  final String? overlayBadgeText;

  const JokeImageCarousel({
    super.key,
    required this.joke,
    this.index,
    this.onSetupTap,
    this.onPunchlineTap,
    this.onImageStateChanged,
    this.isAdminMode = false,
    this.jokesToPreload,
    this.showSaveButton = true,
    this.showShareButton = false,
    this.showAdminRatingButtons = false,
    this.showNumSaves = false,
    this.showNumShares = false,
    this.title,
    required this.jokeContext,
    this.controller,
    this.overlayBadgeText,
  });

  @override
  ConsumerState<JokeImageCarousel> createState() => _JokeImageCarouselState();
}

class _JokeImageCarouselState extends ConsumerState<JokeImageCarousel> {
  // Duration a page must be visible to be considered "viewed"
  static const Duration _jokeImageViewThreshold = Duration(seconds: 2);

  late PageController _pageController;
  int _currentIndex = 0;

  // Track the navigation method that triggered the current page change
  String _lastNavigationMethod = AnalyticsNavigationMethod.swipe;

  // Timing and state for full view detection (2s per image)
  Timer? _viewTimer;
  bool _setupThresholdMet = false;
  bool _punchlineThresholdMet = false;
  bool _jokeViewedLogged = false;
  bool _setupEventLogged = false;
  bool _punchlineEventLogged = false;
  String? _navMethodSetup;
  String? _navMethodPunchline;

  bool get _hasBothImages {
    final joke = widget.joke;
    return joke.setupImageUrl != null &&
        joke.setupImageUrl!.isNotEmpty &&
        joke.punchlineImageUrl != null &&
        joke.punchlineImageUrl!.isNotEmpty;
  }

  void _startViewTimerForIndex(int index) {
    _viewTimer?.cancel();
    if (!_hasBothImages || _jokeViewedLogged) return;
    _viewTimer = Timer(_jokeImageViewThreshold, () async {
      if (!mounted || _jokeViewedLogged) return;
      final analyticsService = ref.read(analyticsServiceProvider);
      if (index == 0) {
        _setupThresholdMet = true;
        if (!_setupEventLogged) {
          _setupEventLogged = true;
          if (!widget.isAdminMode) {
            await analyticsService.logJokeSetupViewed(
              widget.joke.id,
              navigationMethod:
                  _navMethodSetup ?? AnalyticsNavigationMethod.none,
              jokeContext: widget.jokeContext,
            );
          }
          // If image missing, log error context for missing parts
          if (widget.joke.setupImageUrl == null ||
              widget.joke.setupImageUrl!.isEmpty) {
            await analyticsService.logErrorJokeImagesMissing(
              jokeId: widget.joke.id,
              missingParts: 'setup',
            );
          }
        }
      } else if (index == 1) {
        _punchlineThresholdMet = true;
        if (!_punchlineEventLogged) {
          _punchlineEventLogged = true;
          if (!widget.isAdminMode) {
            await analyticsService.logJokePunchlineViewed(
              widget.joke.id,
              navigationMethod:
                  _navMethodPunchline ?? AnalyticsNavigationMethod.swipe,
              jokeContext: widget.jokeContext,
            );
          }
          if (widget.joke.punchlineImageUrl == null ||
              widget.joke.punchlineImageUrl!.isEmpty) {
            await analyticsService.logErrorJokeImagesMissing(
              jokeId: widget.joke.id,
              missingParts: 'punchline',
            );
          }
        }
      }
      await _maybeLogJokeFullyViewed();
    });
  }

  Future<void> _maybeLogJokeFullyViewed() async {
    if (_jokeViewedLogged || !_hasBothImages) return;
    if (_setupThresholdMet && _punchlineThresholdMet) {
      _jokeViewedLogged = true;
      final appUsageService = ref.read(appUsageServiceProvider);
      await appUsageService.logJokeViewed();
      final jokesViewedCount = await appUsageService.getNumJokesViewed();
      final analyticsService = ref.read(analyticsServiceProvider);
      if (!widget.isAdminMode) {
        await analyticsService.logJokeViewed(
          widget.joke.id,
          totalJokesViewed: jokesViewedCount,
          navigationMethod: _lastNavigationMethod,
          jokeContext: widget.jokeContext,
        );
        final subscriptionPromptNotifier = ref.read(
          subscriptionPromptProvider.notifier,
        );
        subscriptionPromptNotifier.considerPromptAfterJokeViewed(
          jokesViewedCount,
        );
      }
    }
  }

  @override
  void initState() {
    super.initState();
    _pageController = PageController();
    _preloadImages();
    // Expose imperative controls to parent if a controller is provided
    widget.controller?._attach(revealPunchline: _revealPunchline);

    // Initialize image state (starts at setup image = index 0)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (widget.onImageStateChanged != null) {
        widget.onImageStateChanged!(0);
      }

      // Record navigation method and start timing for setup image being visible
      _navMethodSetup = AnalyticsNavigationMethod.none;
      _startViewTimerForIndex(0);
    });
  }

  void _preloadImages() {
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return; // Ensure the widget is still in the tree
      final imageService = ref.read(imageServiceProvider);

      try {
        // Preload images for the current joke
        await imageService.precacheJokeImages(widget.joke);

        // Preload images for the next jokes
        if (widget.jokesToPreload != null && mounted) {
          await imageService.precacheMultipleJokeImages(widget.jokesToPreload!);
        }
      } catch (e) {
        // Silently handle any precaching errors
        debugPrint('Error during image precaching: $e');
      }
    });
  }

  @override
  void dispose() {
    _viewTimer?.cancel();
    widget.controller?._detach();
    _pageController.dispose();
    super.dispose();
  }

  void _onPageChanged(int index) {
    setState(() {
      _currentIndex = index;
    });

    // Notify parent about image state change
    if (widget.onImageStateChanged != null) {
      widget.onImageStateChanged!(index);
    }

    // Start a 2s timer for the current page
    _startViewTimerForIndex(index);

    if (index == 0) {
      // Record navigation method for setup
      _navMethodSetup = _lastNavigationMethod;
    } else if (index == 1) {
      // Record navigation method for punchline
      _navMethodPunchline = _lastNavigationMethod;
    }

    // Reset navigation method to swipe for next potential swipe gesture
    _lastNavigationMethod = AnalyticsNavigationMethod.swipe;
  }

  void _onImageTap() {
    if (_currentIndex == 0) {
      // Currently showing setup image
      // Call callback if provided (for tracking)
      if (widget.onSetupTap != null) {
        widget.onSetupTap!();
      }
      // Set navigation method to tap before triggering page change
      _lastNavigationMethod = AnalyticsNavigationMethod.tap;
      // Always do default behavior: go to punchline
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      // Currently showing punchline image
      if (widget.onPunchlineTap != null) {
        widget.onPunchlineTap!();
      } else {
        // Set navigation method to tap before triggering page change
        _lastNavigationMethod = AnalyticsNavigationMethod.tap;
        // Default behavior: go back to setup
        _pageController.previousPage(
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeInOut,
        );
      }
    }
  }

  // Programmatic reveal that mirrors tapping the setup image, but attributed to the CTA
  void _revealPunchline() {
    if (_currentIndex != 0) return;
    if (widget.onSetupTap != null) {
      widget.onSetupTap!();
    }
    _lastNavigationMethod = AnalyticsNavigationMethod.ctaReveal;
    _pageController.nextPage(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
  }

  void _onImageLongPress() {
    if (!widget.isAdminMode) return;

    _showGenerationMetadataDialog();
  }

  void _showGenerationMetadataDialog() {
    final metadata = widget.joke.generationMetadata;

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            const Icon(Icons.info_outline, size: 20),
            const SizedBox(width: 8),
            const Text('Joke Details'),
          ],
        ),
        content: SizedBox(
          width: double.maxFinite,
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                // Joke Metadata Section
                if (widget.joke.tags.isNotEmpty || widget.joke.seasonal != null)
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    margin: const EdgeInsets.only(bottom: 16),
                    decoration: BoxDecoration(
                      color: Theme.of(
                        context,
                      ).colorScheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: Theme.of(
                          context,
                        ).colorScheme.outline.withValues(alpha: 0.3),
                      ),
                    ),
                    child: _buildFormattedTags(context),
                  ),

                // Generation Metadata Section
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Theme.of(
                      context,
                    ).colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: Theme.of(
                        context,
                      ).colorScheme.outline.withValues(alpha: 0.3),
                    ),
                  ),
                  child: metadata != null && metadata.isNotEmpty
                      ? _buildFormattedGenerationMetadata(metadata)
                      : Text(
                          'No generation metadata available for this joke.',
                          style: TextStyle(
                            color: Theme.of(
                              context,
                            ).colorScheme.onSurface.withValues(alpha: 0.6),
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Widget _buildFormattedTags(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'JOKE INFO',
          style: TextStyle(
            fontFamily: 'monospace',
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: Theme.of(context).colorScheme.primary,
          ),
        ),
        const SizedBox(height: 8),
        if (widget.joke.tags.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              'Tags: ${widget.joke.tags.join(", ")}',
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
            ),
          ),
        if (widget.joke.seasonal != null)
          Text(
            'Seasonal: ${widget.joke.seasonal}',
            style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
          ),
      ],
    );
  }

  String _formatRawMetadata(Map<String, dynamic> metadata) {
    // Fallback method for unexpected metadata structure
    final buffer = StringBuffer();

    void writeKeyValue(String key, dynamic value, {int indent = 0}) {
      final indentStr = '  ' * indent;

      if (value is Map<String, dynamic>) {
        buffer.writeln('$indentStr$key:');
        value.forEach((k, v) => writeKeyValue(k, v, indent: indent + 1));
      } else if (value is List) {
        buffer.writeln('$indentStr$key: [${value.length} items]');
        for (int i = 0; i < value.length; i++) {
          writeKeyValue('[$i]', value[i], indent: indent + 1);
        }
      } else {
        buffer.writeln('$indentStr$key: $value');
      }
    }

    metadata.forEach((key, value) => writeKeyValue(key, value));

    return buffer.toString().trim();
  }

  Widget _buildFormattedGenerationMetadata(Map<String, dynamic> metadata) {
    // Check if this has the expected structure with generations
    final generations = metadata['generations'] as List<dynamic>?;
    if (generations == null || generations.isEmpty) {
      // Fallback to raw metadata display if structure is unexpected
      return Text(
        _formatRawMetadata(metadata),
        style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
      );
    }

    // Group generations by label, then by model_name
    final Map<String, Map<String, List<Map<String, dynamic>>>> grouped = {};
    final Map<String, Map<String, double>> totalCosts = {};
    final Map<String, Map<String, int>> counts = {};

    for (final generation in generations) {
      if (generation is! Map<String, dynamic>) continue;

      final label = generation['label']?.toString() ?? 'unknown';
      final modelName = generation['model_name']?.toString() ?? 'unknown';
      final cost = (generation['cost'] as num?)?.toDouble() ?? 0.0;

      // Initialize nested maps if needed
      grouped[label] ??= {};
      grouped[label]![modelName] ??= [];
      totalCosts[label] ??= {};
      totalCosts[label]![modelName] ??= 0.0;
      counts[label] ??= {};
      counts[label]![modelName] ??= 0;

      // Add to collections
      grouped[label]![modelName]!.add(generation);
      totalCosts[label]![modelName] = totalCosts[label]![modelName]! + cost;
      counts[label]![modelName] = counts[label]![modelName]! + 1;
    }

    // Calculate grand total cost
    double grandTotal = 0.0;
    for (final labelCosts in totalCosts.values) {
      for (final cost in labelCosts.values) {
        grandTotal += cost;
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        // SUMMARY section
        Text(
          'SUMMARY',
          style: TextStyle(
            fontFamily: 'monospace',
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: Theme.of(context).colorScheme.primary,
          ),
        ),
        const SizedBox(height: 8),
        // Total cost (most prominent)
        Text(
          'Total Cost: \$${grandTotal.toStringAsFixed(4)}',
          style: TextStyle(
            fontFamily: 'monospace',
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: Theme.of(context).colorScheme.tertiary,
          ),
        ),
        const SizedBox(height: 12),
        ..._buildSummarySection(grouped, totalCosts, counts),
        const SizedBox(height: 16),

        // Divider
        Divider(
          color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.5),
        ),
        const SizedBox(height: 16),

        // DETAILS section
        Text(
          'DETAILS',
          style: TextStyle(
            fontFamily: 'monospace',
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: Theme.of(context).colorScheme.primary,
          ),
        ),
        const SizedBox(height: 8),
        ..._buildDetailsSection(grouped),
      ],
    );
  }

  List<Widget> _buildSummarySection(
    Map<String, Map<String, List<Map<String, dynamic>>>> grouped,
    Map<String, Map<String, double>> totalCosts,
    Map<String, Map<String, int>> counts,
  ) {
    final List<Widget> widgets = [];

    for (final label in grouped.keys) {
      // Label (bold, no indent)
      widgets.add(
        Text(
          label,
          style: const TextStyle(
            fontFamily: 'monospace',
            fontSize: 12,
            fontWeight: FontWeight.bold,
          ),
        ),
      );

      // Model names under each label (2 space indent)
      for (final modelName in grouped[label]!.keys) {
        final totalCost = totalCosts[label]![modelName]!;
        final count = counts[label]![modelName]!;
        widgets.add(
          Text(
            '  $modelName: \$${totalCost.toStringAsFixed(4)} ($count)',
            style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
          ),
        );
      }
      widgets.add(const SizedBox(height: 4));
    }

    return widgets;
  }

  List<Widget> _buildDetailsSection(
    Map<String, Map<String, List<Map<String, dynamic>>>> grouped,
  ) {
    final List<Widget> widgets = [];

    for (final label in grouped.keys) {
      for (final modelName in grouped[label]!.keys) {
        final generationList = grouped[label]![modelName]!;

        for (int i = 0; i < generationList.length; i++) {
          final generation = generationList[i];

          // Label (bold, no indent)
          final labelText = i == 0 || generationList.length == 1
              ? label
              : '$label (${i + 1})';
          widgets.add(
            Text(
              labelText,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                fontWeight: FontWeight.bold,
              ),
            ),
          );

          // Model name (2 space indent)
          widgets.add(
            Text(
              '  model_name: $modelName',
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
            ),
          );

          // Cost (2 space indent, formatted)
          final cost = (generation['cost'] as num?)?.toDouble() ?? 0.0;
          widgets.add(
            Text(
              '  cost: \$${cost.toStringAsFixed(4)}',
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
            ),
          );

          // Generation time (2 space indent, only if > 0)
          final genTime =
              (generation['generation_time_sec'] as num?)?.toDouble() ?? 0.0;
          if (genTime > 0) {
            widgets.add(
              Text(
                '  time: ${genTime.toStringAsFixed(2)}s',
                style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
              ),
            );
          }

          // Other fields (2 space indent, excluding retry_count and fields we already handled)
          final excludedFields = {
            'label',
            'model_name',
            'cost',
            'generation_time_sec',
            'retry_count',
          };
          for (final key in generation.keys) {
            if (!excludedFields.contains(key)) {
              final value = generation[key];
              // Handle nested objects like token_counts
              if (value is Map<String, dynamic>) {
                widgets.add(
                  Text(
                    '  $key:',
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 12,
                    ),
                  ),
                );
                for (final nestedKey in value.keys) {
                  widgets.add(
                    Text(
                      '    $nestedKey: ${value[nestedKey]}',
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 12,
                      ),
                    ),
                  );
                }
              } else {
                widgets.add(
                  Text(
                    '  $key: $value',
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 12,
                    ),
                  ),
                );
              }
            }
          }

          // Add spacing between entries (except for the last one)
          if (i < generationList.length - 1 ||
              label != grouped.keys.last ||
              modelName != grouped[label]!.keys.last) {
            widgets.add(const SizedBox(height: 8));
          }
        }
      }
    }

    return widgets;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final populationState = ref.watch(jokePopulationProvider);
    final isPopulating = populationState.populatingJokes.contains(
      widget.joke.id,
    );

    return Padding(
      padding: const EdgeInsets.only(bottom: 24.0),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Title (if provided)
          if (widget.title != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 8.0),
              child: Text(
                widget.title!,
                style: theme.textTheme.titleMedium?.copyWith(
                  color: theme.colorScheme.onSurface,
                  fontWeight: FontWeight.w500,
                ),
                textAlign: TextAlign.center,
              ),
            ),
          // Image carousel
          Flexible(
            child: Card(
              child: Stack(
                children: [
                  GestureDetector(
                    onTap: _onImageTap,
                    onLongPress: widget.isAdminMode ? _onImageLongPress : null,
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(
                        minHeight: 200, // Ensure minimum usable height
                      ),
                      child: ClipRRect(
                        borderRadius: const BorderRadius.vertical(
                          top: Radius.circular(16),
                          bottom: Radius.circular(16),
                        ),
                        child: AspectRatio(
                          aspectRatio: 1.0,
                          child: PageView(
                            controller: _pageController,
                            onPageChanged: _onPageChanged,
                            children: [
                              // Setup image
                              _buildImagePage(
                                imageUrl: widget.joke.setupImageUrl,
                              ),
                              // Punchline image
                              _buildImagePage(
                                imageUrl: widget.joke.punchlineImageUrl,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                  if (widget.overlayBadgeText != null &&
                      widget.overlayBadgeText!.isNotEmpty)
                    Positioned(
                      top: 8,
                      right: 8,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: Theme.of(
                            context,
                          ).colorScheme.surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(999),
                          border: Border.all(
                            color: Theme.of(
                              context,
                            ).colorScheme.outline.withValues(alpha: 0.3),
                          ),
                        ),
                        child: Text(
                          widget.overlayBadgeText!,
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                            color: Theme.of(context).colorScheme.onSurface,
                          ),
                        ),
                      ),
                    ),
                  if (widget.isAdminMode)
                    Positioned(
                      top: 8,
                      left: 8,
                      child: _buildStateBadgeText(context),
                    ),
                ],
              ),
            ),
          ),

          // Page indicators and reaction/count buttons row
          SizedBox(
            height: 36,
            child: Row(
              children: [
                // Left spacer
                Expanded(child: _buildLeftCounts()),

                // Page indicators (centered)
                SmoothPageIndicator(
                  controller: _pageController,
                  count: 2,
                  effect: WormEffect(
                    dotHeight: 12,
                    dotWidth: 12,
                    spacing: 6,
                    radius: 6,
                    dotColor: theme.colorScheme.onSurface.withValues(
                      alpha: 0.3,
                    ),
                    activeDotColor: theme.colorScheme.primary,
                  ),
                ),

                // Right buttons (save, share, admin rating) or spacer
                Expanded(child: _buildRightButtons()),
              ],
            ),
          ),

          // Admin buttons (only shown in admin mode)
          if (widget.isAdminMode)
            Padding(
              padding: const EdgeInsets.only(
                left: 16.0,
                right: 16.0,
                bottom: 16.0,
              ),
              child: Row(
                children: [
                  // Left buttons (conditional based on joke state)
                  if (widget.joke.state == JokeState.approved)
                    // APPROVED: Half-width delete button and half-width publish button
                    Expanded(
                      child: Row(
                        children: [
                          Expanded(
                            child: AdminDeleteJokeButton(
                              jokeId: widget.joke.id,
                              theme: theme,
                              isLoading: isPopulating,
                            ),
                          ),
                          const SizedBox(width: 8.0),
                          Expanded(
                            child: AdminPublishJokeButton(
                              jokeId: widget.joke.id,
                              theme: theme,
                              isLoading: isPopulating,
                            ),
                          ),
                        ],
                      ),
                    )
                  else if (widget.joke.state == JokeState.published)
                    // PUBLISHED: Half-width unpublish button and half-width add-to-daily button
                    Expanded(
                      child: Row(
                        children: [
                          Expanded(
                            child: AdminUnpublishJokeButton(
                              jokeId: widget.joke.id,
                              theme: theme,
                              isLoading: isPopulating,
                            ),
                          ),
                          const SizedBox(width: 8.0),
                          Expanded(
                            child: AdminAddToDailyScheduleButton(
                              jokeId: widget.joke.id,
                              theme: theme,
                              isLoading: isPopulating,
                            ),
                          ),
                        ],
                      ),
                    )
                  else if (widget.joke.state == JokeState.daily)
                    // DAILY: Conditional button based on public_timestamp
                    Expanded(
                      child:
                          widget.joke.publicTimestamp != null &&
                              widget.joke.publicTimestamp!.isAfter(
                                DateTime.now(),
                              )
                          ? // Future daily joke: remove from schedule button
                            AdminRemoveFromDailyScheduleButton(
                              jokeId: widget.joke.id,
                              theme: theme,
                              isLoading: isPopulating,
                            )
                          : // Past daily joke: empty space (no button)
                            const SizedBox(),
                    )
                  else
                    // Other states: Full-width delete button
                    Expanded(
                      child: AdminDeleteJokeButton(
                        jokeId: widget.joke.id,
                        theme: theme,
                        isLoading: isPopulating,
                      ),
                    ),
                  const SizedBox(width: 8.0),
                  // Hold to Regenerate Edit button (middle)
                  Expanded(
                    child: AdminEditJokeButton(
                      jokeId: widget.joke.id,
                      theme: theme,
                      isLoading: isPopulating,
                    ),
                  ),
                  const SizedBox(width: 8.0),
                  // Regenerate Images button (rightmost)
                  Expanded(
                    child: AdminRegenerateImagesButton(
                      jokeId: widget.joke.id,
                      theme: theme,
                      isLoading: isPopulating,
                    ),
                  ),
                ],
              ),
            ),

          // Error display (only shown in admin mode)
          if (widget.isAdminMode && populationState.error != null)
            Padding(
              padding: const EdgeInsets.only(
                left: 16.0,
                right: 16.0,
                bottom: 8.0,
              ),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12.0),
                decoration: BoxDecoration(
                  color: theme.appColors.authError.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8.0),
                  border: Border.all(
                    color: theme.appColors.authError.withValues(alpha: 0.3),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.error_outline,
                      size: 16,
                      color: theme.appColors.authError,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        populationState.error!,
                        style: TextStyle(
                          color: theme.appColors.authError,
                          fontSize: 12,
                        ),
                      ),
                    ),
                    IconButton(
                      onPressed: () {
                        ref.read(jokePopulationProvider.notifier).clearError();
                      },
                      icon: Icon(
                        Icons.close,
                        size: 16,
                        color: theme.appColors.authError,
                      ),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildImagePage({required String? imageUrl}) {
    return CachedJokeImage(
      imageUrl: imageUrl,
      fit: BoxFit.cover,
      showLoadingIndicator: true,
      showErrorIcon: true,
    );
  }

  Widget _buildRightButtons() {
    // Create a list of buttons to show
    final List<Widget> buttons = [];

    // Add admin rating buttons if enabled
    if (widget.showAdminRatingButtons) {
      if (buttons.isNotEmpty) {
        buttons.add(const SizedBox(width: 8));
      }
      buttons.add(AdminApprovalControls(jokeId: widget.joke.id));
    }

    // Add share button if enabled
    if (widget.showShareButton) {
      if (buttons.isNotEmpty) {
        buttons.add(const SizedBox(width: 8));
      }
      buttons.add(
        ShareJokeButton(joke: widget.joke, jokeContext: widget.jokeContext),
      );
    }

    // Add save button if enabled
    if (widget.showSaveButton) {
      buttons.add(
        SaveJokeButton(jokeId: widget.joke.id, jokeContext: widget.jokeContext),
      );
    }

    // If no buttons, return empty space
    if (buttons.isEmpty) {
      return const SizedBox();
    }

    // Return aligned row of buttons
    return Align(
      alignment: Alignment.centerRight,
      child: Row(mainAxisSize: MainAxisSize.min, children: buttons),
    );
  }

  Widget _buildStateBadgeText(BuildContext context) {
    // Determine the display text for the badge
    String displayText;
    if (widget.joke.state == JokeState.daily &&
        widget.joke.publicTimestamp != null) {
      // For daily state, show the public timestamp in YYYY-MM-DD format
      final timestamp = widget.joke.publicTimestamp!;
      displayText =
          '${timestamp.year}-${timestamp.month.toString().padLeft(2, '0')}-${timestamp.day.toString().padLeft(2, '0')}';
    } else {
      // For all other states, show the proper-case state name
      final stateStr = widget.joke.state?.value;
      if (stateStr == null || stateStr.isEmpty) {
        return const SizedBox.shrink();
      }
      final lower = stateStr.toLowerCase();
      displayText = lower[0].toUpperCase() + lower.substring(1);
    }

    // Determine background color based on state
    Color backgroundColor;
    Color borderColor = Theme.of(
      context,
    ).colorScheme.outline.withValues(alpha: 0.2);
    double borderWidth = 1.0;
    switch (widget.joke.state) {
      case JokeState.unknown:
        backgroundColor = Colors.red.withValues(alpha: 1.0);
        break;
      case JokeState.draft:
        backgroundColor = Colors.grey.withValues(alpha: 0.3);
        break;
      case JokeState.unreviewed:
        backgroundColor = Colors.orange.withValues(alpha: 0.3);
        break;
      case JokeState.approved:
        backgroundColor = Colors.green.withValues(alpha: 0.3);
        break;
      case JokeState.rejected:
        backgroundColor = Colors.red.withValues(alpha: 0.3);
        break;
      case JokeState.published:
        backgroundColor = Colors.blue.withValues(alpha: 0.3);
        break;
      case JokeState.daily:
        if (widget.joke.publicTimestamp != null &&
            widget.joke.publicTimestamp!.isAfter(DateTime.now())) {
          backgroundColor = const Color.fromARGB(
            255,
            233,
            109,
            255,
          ).withValues(alpha: 0.8);
          borderColor = backgroundColor.withValues(alpha: 0.8);
          borderWidth = 2.0; // Thicker border for future daily jokes
        } else {
          backgroundColor = Colors.purple.withValues(alpha: 0.3);
        }
        break;
      default:
        backgroundColor = Theme.of(
          context,
        ).colorScheme.primary.withValues(alpha: 0.3);
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: borderColor, width: borderWidth),
      ),
      child: Text(
        displayText,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w600,
          color: Theme.of(context).colorScheme.onPrimary.withValues(alpha: 0.8),
        ),
      ),
    );
  }

  Widget _buildLeftCounts() {
    final List<Widget> items = [];

    if (widget.showNumSaves) {
      final Color saveColor = widget.joke.numSaves > 0
          ? Colors.red.withValues(alpha: 0.9)
          : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.4);
      items.add(
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.favorite, size: 20, color: saveColor),
            const SizedBox(width: 4),
            Text(
              '${widget.joke.numSaves}',
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
            ),
          ],
        ),
      );
    }

    if (widget.showNumShares) {
      if (items.isNotEmpty) items.add(const SizedBox(width: 12));
      final Color shareColor = widget.joke.numShares > 0
          ? Colors.blue.withValues(alpha: 0.9)
          : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.4);
      items.add(
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.share, size: 20, color: shareColor),
            const SizedBox(width: 4),
            Text(
              '${widget.joke.numShares}',
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
            ),
          ],
        ),
      );
    }

    if (items.isEmpty) {
      return const SizedBox();
    }

    return Align(
      alignment: Alignment.centerLeft,
      child: Row(mainAxisSize: MainAxisSize.min, children: items),
    );
  }
}
