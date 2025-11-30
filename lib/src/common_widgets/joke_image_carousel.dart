import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:smooth_page_indicator/smooth_page_indicator.dart';
import 'package:snickerdoodle/src/common_widgets/admin_approval_controls.dart';
import 'package:snickerdoodle/src/common_widgets/admin_joke_action_buttons.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/common_widgets/reschedule_dialog.dart';
import 'package:snickerdoodle/src/common_widgets/save_joke_button.dart';
import 'package:snickerdoodle/src/common_widgets/share_joke_button.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/constants/joke_constants.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_population_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_thumbs_reaction.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';
import 'package:snickerdoodle/src/features/settings/application/admin_settings_service.dart';

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
  final Function(int)? onImageStateChanged;
  final bool isAdminMode;
  final List<Joke>? jokesToPreload;
  final bool showSaveButton;
  final bool showShareButton;
  final bool showAdminRatingButtons;
  final bool showUserRatingButtons;
  final bool showUsageStats;
  final String? title;
  final String jokeContext;
  final JokeImageCarouselController? controller;
  final String? overlayBadgeText;
  final bool showSimilarSearchButton;
  final JokeViewerMode mode;
  final String? dataSource;

  const JokeImageCarousel({
    super.key,
    required this.joke,
    this.index,
    this.onImageStateChanged,
    this.isAdminMode = false,
    this.jokesToPreload,
    this.showSaveButton = false,
    this.showShareButton = false,
    this.showAdminRatingButtons = false,
    this.showUserRatingButtons = false,
    this.showUsageStats = false,
    this.title,
    required this.jokeContext,
    this.controller,
    this.overlayBadgeText,
    this.showSimilarSearchButton = false,
    this.mode = JokeViewerMode.reveal,
    this.dataSource,
  });

  @override
  ConsumerState<JokeImageCarousel> createState() => _JokeImageCarouselState();
}

class _JokeImageCarouselState extends ConsumerState<JokeImageCarousel> {
  // Duration a page must be visible to be considered "viewed"
  static const Duration _jokeImageViewThreshold = Duration(milliseconds: 1300);

  late PageController _pageController;
  int _currentIndex = 0;
  late PerformanceService _perf;

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
  bool _nextPrecacheScheduled = false;
  bool _navigationLogged = false;

  bool get _hasBothImages {
    final joke = widget.joke;
    return joke.setupImageUrl != null &&
        joke.setupImageUrl!.isNotEmpty &&
        joke.punchlineImageUrl != null &&
        joke.punchlineImageUrl!.isNotEmpty;
  }

  void _startViewTimerForIndex(int index) {
    _viewTimer?.cancel();
    if (!_hasBothImages || _jokeViewedLogged || widget.isAdminMode) return;
    _viewTimer = Timer(_jokeImageViewThreshold, () async {
      if (!mounted || _jokeViewedLogged) return;
      final analyticsService = ref.read(analyticsServiceProvider);
      if (index == 0) {
        _setupThresholdMet = true;
        if (!_setupEventLogged) {
          _setupEventLogged = true;
          if (!widget.isAdminMode) {
            analyticsService.logJokeSetupViewed(
              widget.joke.id,
              navigationMethod:
                  _navMethodSetup ?? AnalyticsNavigationMethod.none,
              jokeContext: widget.jokeContext,
              jokeContextSuffix: widget.dataSource,
              jokeViewerMode: widget.mode,
            );
          }
          // If image missing, log error context for missing parts
          if (widget.joke.setupImageUrl == null ||
              widget.joke.setupImageUrl!.isEmpty) {
            analyticsService.logErrorJokeImagesMissing(
              jokeId: widget.joke.id,
              missingParts: 'setup',
            );
          }
        }
        // For non-REVEAL modes (VERTICAL, HORIZONTAL, BOTH_ADAPTIVE),
        // automatically chain a second timer to count punchline viewed
        // and then consider the joke fully viewed.
        if (widget.mode != JokeViewerMode.reveal) {
          // Set navigation attribution for punchline + full view to programmatic
          _navMethodPunchline = AnalyticsNavigationMethod.programmatic;
          _lastNavigationMethod = AnalyticsNavigationMethod.programmatic;
          _viewTimer = Timer(_jokeImageViewThreshold, () async {
            if (!mounted || _jokeViewedLogged) return;
            _punchlineThresholdMet = true;
            if (!_punchlineEventLogged) {
              _punchlineEventLogged = true;
              if (!widget.isAdminMode) {
                final analyticsServiceInner = ref.read(
                  analyticsServiceProvider,
                );
                analyticsServiceInner.logJokePunchlineViewed(
                  widget.joke.id,
                  navigationMethod:
                      _navMethodPunchline ??
                      AnalyticsNavigationMethod.programmatic,
                  jokeContext: widget.jokeContext,
                  jokeContextSuffix: widget.dataSource,
                  jokeViewerMode: widget.mode,
                );
              }
            }
            await _maybeLogJokeFullyViewed();
          });
        }
      } else if (index == 1) {
        _punchlineThresholdMet = true;
        if (!_punchlineEventLogged) {
          _punchlineEventLogged = true;
          if (!widget.isAdminMode) {
            analyticsService.logJokePunchlineViewed(
              widget.joke.id,
              navigationMethod:
                  _navMethodPunchline ?? AnalyticsNavigationMethod.swipe,
              jokeContext: widget.jokeContext,
              jokeContextSuffix: widget.dataSource,
              jokeViewerMode: widget.mode,
            );
          }
          if (widget.joke.punchlineImageUrl == null ||
              widget.joke.punchlineImageUrl!.isEmpty) {
            analyticsService.logErrorJokeImagesMissing(
              jokeId: widget.joke.id,
              missingParts: 'punchline',
            );
          }
        }
      }
      await _maybeLogJokeFullyViewed();
    });
  }

  void _logNavigationIfNeeded() {
    if (_navigationLogged || widget.isAdminMode || !mounted) return;
    try {
      final appUsageService = ref.read(appUsageServiceProvider);
      _navigationLogged = true;
      Future.sync(
        () => appUsageService.logJokeNavigated(widget.joke.id),
      ).catchError((Object error, StackTrace stackTrace) {
        AppLogger.debug(
          'JOKE_CAROUSEL: logJokeNavigated deferred error: $error\n$stackTrace',
        );
      });
    } catch (error, stackTrace) {
      AppLogger.debug(
        'JOKE_CAROUSEL: logJokeNavigated skipped: $error\n$stackTrace',
      );
    }
  }

  Future<void> _maybeLogJokeFullyViewed() async {
    // Guard against running after disposal or when conditions aren't met
    if (!mounted || _jokeViewedLogged || !_hasBothImages) return;
    if (_setupThresholdMet && _punchlineThresholdMet) {
      _jokeViewedLogged = true;
      final appUsageService = ref.read(appUsageServiceProvider);
      await appUsageService.logJokeViewed(widget.joke.id, context: context);
      final jokesViewedCount = await appUsageService.getNumJokesViewed();
      // Re-check mounted before any further ref.read calls after awaits
      if (!mounted) return;
      final analyticsService = ref.read(analyticsServiceProvider);
      analyticsService.logJokeViewed(
        widget.joke.id,
        totalJokesViewed: jokesViewedCount,
        navigationMethod: _lastNavigationMethod,
        jokeContext: widget.jokeContext,
        jokeContextSuffix: widget.dataSource,
        jokeViewerMode: widget.mode,
      );
      // Re-check mounted before reading another provider
      if (!mounted) return;
    }
  }

  @override
  void initState() {
    super.initState();
    _perf = ref.read(performanceServiceProvider);
    _pageController = PageController();

    // Expose imperative controls to parent if a controller is provided
    widget.controller?._attach(revealPunchline: _revealPunchline);

    // Initialize image state (starts at setup image = index 0)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (widget.onImageStateChanged != null) {
        widget.onImageStateChanged!(0);
      }

      // Record navigation method and start timing for setup image being visible
      _navMethodSetup = AnalyticsNavigationMethod.none;
      _logNavigationIfNeeded();
      _startViewTimerForIndex(0);

      // Start a carousel_to_visible trace once per carousel instance (per joke) - skip in admin mode
      if (!widget.isAdminMode) {
        _perf.startNamedTrace(
          name: TraceName.carouselToVisible,
          key: widget.joke.id,
        );
      }
    });
  }

  @override
  void dispose() {
    // Drop any in-flight carousel trace if we never showed pixels
    _perf.dropNamedTrace(
      name: TraceName.carouselToVisible,
      key: widget.joke.id,
    );
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

  // Programmatic reveal that mirrors tapping the setup image, but attributed to the CTA
  void _revealPunchline() {
    if (_currentIndex != 0) return;
    _lastNavigationMethod = AnalyticsNavigationMethod.ctaRevealPunchline;

    // Only use PageController in REVEAL mode
    if (widget.mode == JokeViewerMode.reveal) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    }
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
                // Joke Stats Section
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
                  child: _buildJokeStats(context),
                ),

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

  Widget _buildJokeStats(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'JOKE STATS',
          style: TextStyle(
            fontFamily: 'monospace',
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: Theme.of(context).colorScheme.primary,
          ),
        ),
        const SizedBox(height: 8),
        // Top row: Views, Saves, Shares
        Row(
          children: [
            _buildStatRow(
              context,
              icon: Icons.visibility,
              value: '${widget.joke.numViews}',
              color: widget.joke.numViews > 0
                  ? Colors.green.withValues(alpha: 0.9)
                  : Theme.of(
                      context,
                    ).colorScheme.onSurface.withValues(alpha: 0.4),
            ),
            const SizedBox(width: 12),
            _buildStatRow(
              context,
              icon: Icons.favorite,
              value: '${widget.joke.numSaves}',
              color: widget.joke.numSaves > 0
                  ? Colors.red.withValues(alpha: 0.9)
                  : Theme.of(
                      context,
                    ).colorScheme.onSurface.withValues(alpha: 0.4),
            ),
            const SizedBox(width: 12),
            _buildStatRow(
              context,
              icon: Icons.share,
              value: '${widget.joke.numShares}',
              color: widget.joke.numShares > 0
                  ? Colors.blue.withValues(alpha: 0.9)
                  : Theme.of(
                      context,
                    ).colorScheme.onSurface.withValues(alpha: 0.4),
            ),
          ],
        ),
        const SizedBox(height: 8),
        // Bottom row: Popularity Score, Saved Users Fraction
        Row(
          children: [
            _buildStatRow(
              context,
              icon: Icons.trending_up,
              value: widget.joke.popularityScore.toStringAsPrecision(3),
              color: widget.joke.popularityScore > 0
                  ? Colors.purple.withValues(alpha: 0.9)
                  : Theme.of(
                      context,
                    ).colorScheme.onSurface.withValues(alpha: 0.4),
            ),
            const SizedBox(width: 12),
            _buildStatRow(
              context,
              icon: Icons.favorite_outline,
              value: widget.joke.numSavedUsersFraction.toStringAsPrecision(2),
              color: widget.joke.numSavedUsersFraction > 0
                  ? Colors.red.withValues(alpha: 0.9)
                  : Theme.of(
                      context,
                    ).colorScheme.onSurface.withValues(alpha: 0.4),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildStatRow(
    BuildContext context, {
    required IconData icon,
    required String value,
    required Color color,
  }) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 20, color: color),
        const SizedBox(width: 4),
        Text(
          value,
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
        ),
      ],
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

  double _getAspectRatio() {
    switch (widget.mode) {
      case JokeViewerMode.reveal:
        return 1.0; // Standard square aspect ratio for single image
      case JokeViewerMode.bothAdaptive:
        // Not used directly; adaptive handled in build with LayoutBuilder
        return 1.0;
    }
  }

  Widget _buildCarouselContent() {
    final setupImage = _buildImagePage(imageUrl: widget.joke.setupImageUrl);
    final punchlineImage = _buildImagePage(
      imageUrl: widget.joke.punchlineImageUrl,
    );

    switch (widget.mode) {
      case JokeViewerMode.reveal:
        return PageView(
          controller: _pageController,
          onPageChanged: _onPageChanged,
          children: [setupImage, punchlineImage],
        );
      case JokeViewerMode.bothAdaptive:
        // Handled in build() where we know constraints and can pick aspect ratio
        // This path should not be used directly
        return const SizedBox.shrink();
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final populationState = ref.watch(jokePopulationProvider);
    final isPopulating = populationState.populatingJokes.contains(
      widget.joke.id,
    );
    final shouldShowDataSource = _shouldShowDataSource();

    return Padding(
      padding: const EdgeInsets.only(bottom: 24.0),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Title and/or data source display
          if (widget.title != null || shouldShowDataSource)
            Padding(
              padding: const EdgeInsets.only(bottom: 8.0),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (widget.title != null)
                    Text(
                      widget.title!,
                      style: theme.textTheme.titleMedium?.copyWith(
                        color: theme.colorScheme.onSurface,
                        fontWeight: FontWeight.w500,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  if (shouldShowDataSource)
                    Text(
                      widget.dataSource ?? 'unknown',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurface.withValues(
                          alpha: 0.6,
                        ),
                        fontFamily: 'monospace',
                      ),
                      textAlign: TextAlign.center,
                    ),
                ],
              ),
            ),
          // Image carousel
          Flexible(
            child: Card(
              elevation: 4,
              child: Stack(
                children: [
                  GestureDetector(
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
                        child: Builder(
                          builder: (context) {
                            if (widget.mode != JokeViewerMode.bothAdaptive) {
                              return AspectRatio(
                                aspectRatio: _getAspectRatio(),
                                child: _buildCarouselContent(),
                              );
                            }
                            // Adaptive: decide orientation & aspect ratio together
                            return LayoutBuilder(
                              builder: (context, constraints) {
                                final setupImage = _buildImagePage(
                                  imageUrl: widget.joke.setupImageUrl,
                                );
                                final punchlineImage = _buildImagePage(
                                  imageUrl: widget.joke.punchlineImageUrl,
                                );
                                final bool preferHorizontal =
                                    constraints.maxWidth >=
                                    constraints.maxHeight;
                                final double aspectRatio = preferHorizontal
                                    ? 2.0
                                    : 0.5;
                                final Widget content = preferHorizontal
                                    ? Row(
                                        children: [
                                          Expanded(child: setupImage),
                                          Expanded(child: punchlineImage),
                                        ],
                                      )
                                    : Column(
                                        children: [
                                          Expanded(child: setupImage),
                                          Expanded(child: punchlineImage),
                                        ],
                                      );
                                return AspectRatio(
                                  aspectRatio: aspectRatio,
                                  child: content,
                                );
                              },
                            );
                          },
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

          // Controls row - always show, but conditionally show page indicators
          SizedBox(
            height: 36,
            child: Row(
              children: [
                // Left spacer
                Expanded(child: _buildLeftControls()),

                // Page indicators (centered) - only show in REVEAL mode
                if (widget.mode == JokeViewerMode.reveal)
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
                Expanded(child: _buildRightControls()),
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
                  // Edit button (middle)
                  Expanded(
                    child: AdminEditJokeButton(
                      jokeId: widget.joke.id,
                      theme: theme,
                      isLoading: isPopulating,
                    ),
                  ),
                  const SizedBox(width: 8.0),
                  // Regenerate Images button (half-width) - hidden for public/daily jokes
                  if (widget.joke.state != JokeState.published &&
                      widget.joke.state != JokeState.daily)
                    Expanded(
                      child: AdminRegenerateImagesButton(
                        jokeId: widget.joke.id,
                        theme: theme,
                        isLoading: isPopulating,
                        hasUpscaledImage:
                            widget.joke.setupImageUrlUpscaled != null ||
                            widget.joke.punchlineImageUrlUpscaled != null,
                      ),
                    )
                  else
                    const Expanded(child: SizedBox()),
                  const SizedBox(width: 8.0),
                  // Modify Images button (half-width)
                  Expanded(
                    child: AdminModifyImageButton(
                      jokeId: widget.joke.id,
                      theme: theme,
                      isLoading: isPopulating,
                      setupImageUrl: widget.joke.setupImageUrl,
                      punchlineImageUrl: widget.joke.punchlineImageUrl,
                      hasUpscaledImage:
                          widget.joke.setupImageUrlUpscaled != null ||
                          widget.joke.punchlineImageUrlUpscaled != null,
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
      imageUrlOrAssetPath: imageUrl,
      fit: BoxFit.cover,
      showLoadingIndicator: true,
      showErrorIcon: true,
      onFirstImagePaint: (widthHint) {
        // Stop app create to first joke trace
        _perf.stopNamedTrace(name: TraceName.appCreateToFirstJoke);
        _perf.stopNamedTrace(name: TraceName.startupToFirstJoke);

        // Stop any active search traces
        _perf.stopNamedTrace(name: TraceName.searchToFirstImage);

        // Also stop the carousel_to_visible trace for this carousel (stop on first pixel of any image)
        _perf.stopNamedTrace(
          name: TraceName.carouselToVisible,
          key: widget.joke.id,
        );

        // After the first image is actually visible, defer preloading of next jokes
        if (!_nextPrecacheScheduled && widthHint != null) {
          _nextPrecacheScheduled = true;
          final nextJokes = widget.jokesToPreload;
          if (nextJokes != null && nextJokes.isNotEmpty) {
            // Fire-and-forget; do not await to avoid blocking UI thread
            final imageService = ref.read(imageServiceProvider);
            imageService.precacheMultipleJokeImages(
              nextJokes,
              width: widthHint,
            );
          }
        }
      },
    );
  }

  Widget _buildRightControls() {
    // Build popularity score and save fraction (left-aligned in right section)
    Widget? statsWidget;
    if (widget.showUsageStats) {
      final Color popularityColor = widget.joke.popularityScore > 0
          ? Colors.purple.withValues(alpha: 0.9)
          : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.4);
      final Color saveFractionColor = widget.joke.numSavedUsersFraction > 0
          ? Colors.red.withValues(alpha: 0.9)
          : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.4);
      statsWidget = Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.trending_up, size: 20, color: popularityColor),
              const SizedBox(width: 4),
              Text(
                widget.joke.popularityScore.toStringAsPrecision(3),
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(width: 12),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.favorite_outline, size: 20, color: saveFractionColor),
              const SizedBox(width: 4),
              Text(
                widget.joke.numSavedUsersFraction.toStringAsPrecision(2),
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ],
      );
    }

    // Build buttons (right-aligned in right section)
    final List<Widget> buttons = [];
    if (widget.showUserRatingButtons) {
      final reactionAsync = ref.watch(
        jokeThumbsReactionProvider(widget.joke.id),
      );
      final reactionWidget = reactionAsync.when(
        data: (reaction) => _buildReactionButtons(reaction),
        loading: () => SizedBox(
          width: 72,
          height: 32,
          child: Center(
            child: SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: Theme.of(context).colorScheme.primary,
              ),
            ),
          ),
        ),
        error: (error, stack) => _buildReactionButtons(JokeThumbsReaction.none),
      );
      buttons.add(reactionWidget);
    }

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
      if (buttons.isNotEmpty) {
        buttons.add(const SizedBox(width: 8));
      }
      buttons.add(
        SaveJokeButton(jokeId: widget.joke.id, jokeContext: widget.jokeContext),
      );
    }

    // If nothing to show, return empty space
    if (statsWidget == null && buttons.isEmpty) {
      return const SizedBox();
    }

    // Return row with stats on left and buttons on right
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        // Left side: popularity score and save fraction
        if (statsWidget != null)
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: statsWidget,
          )
        else
          const SizedBox(),
        // Right side: buttons
        if (buttons.isNotEmpty)
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerRight,
            child: Row(mainAxisSize: MainAxisSize.min, children: buttons),
          )
        else
          const SizedBox(),
      ],
    );
  }

  Widget _buildReactionButtons(JokeThumbsReaction reaction) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _buildThumbButton(
          reaction: reaction,
          targetReaction: JokeThumbsReaction.up,
          icon: Icons.thumb_up,
          keyName: 'joke_carousel-thumbs-up-button-${widget.joke.id}',
        ),
        const SizedBox(width: 8),
        _buildThumbButton(
          reaction: reaction,
          targetReaction: JokeThumbsReaction.down,
          icon: Icons.thumb_down,
          keyName: 'joke_carousel-thumbs-down-button-${widget.joke.id}',
        ),
      ],
    );
  }

  Widget _buildThumbButton({
    required JokeThumbsReaction reaction,
    required JokeThumbsReaction targetReaction,
    required IconData icon,
    required String keyName,
  }) {
    final theme = Theme.of(context);
    final isActive = reaction == targetReaction;
    final bool isUp = targetReaction == JokeThumbsReaction.up;
    final Color activeColor = isUp
        ? theme.colorScheme.primary
        : theme.colorScheme.error;
    final Color borderColor = isActive
        ? activeColor
        : theme.colorScheme.outline.withValues(alpha: 0.6);
    final Color backgroundColor = isActive
        ? activeColor.withValues(alpha: 0.2)
        : theme.colorScheme.surfaceContainerHighest;
    final Color iconColor = isActive
        ? activeColor
        : theme.colorScheme.onSurface.withValues(alpha: 0.7);

    return Material(
      color: Colors.transparent,
      child: InkWell(
        key: Key(keyName),
        onTap: () {
          final usageService = ref.read(appUsageServiceProvider);
          if (targetReaction == JokeThumbsReaction.up) {
            usageService.logJokeThumbsUp(
              widget.joke.id,
              jokeContext: widget.jokeContext,
            );
          } else {
            usageService.logJokeThumbsDown(
              widget.joke.id,
              jokeContext: widget.jokeContext,
            );
          }
        },
        borderRadius: BorderRadius.circular(999),
        child: Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            color: backgroundColor,
            shape: BoxShape.circle,
            border: Border.all(color: borderColor, width: isActive ? 2.0 : 1.0),
          ),
          child: Icon(icon, size: 18, color: iconColor),
        ),
      ),
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

    final isFutureDaily =
        widget.joke.state == JokeState.daily &&
        widget.joke.publicTimestamp != null &&
        widget.joke.publicTimestamp!.isAfter(DateTime.now());

    final badge = Container(
      key: isFutureDaily ? const Key('daily-state-badge') : null,
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

    if (!isFutureDaily) return badge;

    return InkWell(
      onTap: _onTapRescheduleBadge,
      borderRadius: BorderRadius.circular(999),
      child: badge,
    );
  }

  void _onTapRescheduleBadge() async {
    if (widget.joke.publicTimestamp == null) return;
    DateTime initial = DateTime(
      widget.joke.publicTimestamp!.year,
      widget.joke.publicTimestamp!.month,
      widget.joke.publicTimestamp!.day,
    );

    // Get scheduled dates from the provider
    final batchesAsync = ref.read(scheduleBatchesProvider);
    final scheduledDates = <DateTime>[];

    batchesAsync.whenData((batches) {
      for (final batch in batches) {
        for (final entry in batch.jokes.entries) {
          final day = int.tryParse(entry.key);
          if (day != null) {
            scheduledDates.add(DateTime(batch.year, batch.month, day));
          }
        }
      }
    });

    await showDialog<void>(
      context: context,
      builder: (context) => RescheduleDialog(
        jokeId: widget.joke.id,
        initialDate: initial,
        scheduleId: JokeConstants.defaultJokeScheduleId,
        scheduledDates: scheduledDates,
      ),
    );
  }

  Widget _buildLeftControls() {
    final List<Widget> items = [];

    // Similar button (icon + text), shown only when flag enabled and not admin
    if (widget.showSimilarSearchButton && !widget.isAdminMode) {
      items.add(_buildSimilarButton(context));
    }

    if (widget.showUsageStats) {
      // Views counter
      final Color viewColor = widget.joke.numViews > 0
          ? Colors.green.withValues(alpha: 0.9)
          : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.4);
      items.add(
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.visibility, size: 20, color: viewColor),
            const SizedBox(width: 4),
            Text(
              '${widget.joke.numViews}',
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
            ),
          ],
        ),
      );

      // Saves counter
      items.add(const SizedBox(width: 12));
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

      // Shares counter
      items.add(const SizedBox(width: 12));
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
      child: FittedBox(
        fit: BoxFit.scaleDown,
        alignment: Alignment.centerLeft,
        child: Row(mainAxisSize: MainAxisSize.min, children: items),
      ),
    );
  }

  Widget _buildSimilarButton(BuildContext context) {
    final Color baseButtonColor = jokeIconButtonBaseColor(context);

    return Material(
      color: Colors.transparent,
      child: InkWell(
        key: const Key('similar-search-button'),
        onTap: _onTapSimilar,
        borderRadius: BorderRadius.circular(6),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.search, size: 24, color: baseButtonColor),
              const SizedBox(width: 4),
              Text(
                'Similar',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: baseButtonColor,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  bool _shouldShowDataSource() {
    if (widget.dataSource == null) return false;
    final adminSettings = ref.read(adminSettingsServiceProvider);
    return adminSettings.getAdminShowJokeDataSource();
  }

  void _onTapSimilar() async {
    // Skip analytics in admin mode
    if (widget.isAdminMode) return;

    final refLocal = ref;
    final analyticsService = refLocal.read(analyticsServiceProvider);

    // Build query: setup and punchline strings joined together
    final String baseQuery =
        '${widget.joke.setupText} ${widget.joke.punchlineText}'.trim();
    if (baseQuery.isEmpty) return;

    // Log CTA analytics
    analyticsService.logJokeSearchSimilar(
      queryLength: baseQuery.length,
      jokeContext: widget.jokeContext,
    );

    // Update search query provider
    refLocal
        .read(searchQueryProvider(SearchScope.userJokeSearch).notifier)
        .state = SearchQuery(
      query: '${JokeConstants.searchQueryPrefix}$baseQuery',
      maxResults: JokeConstants.userSearchMaxResults,
      publicOnly: JokeConstants.userSearchPublicOnly,
      matchMode: JokeConstants.userSearchMatchMode,
      excludeJokeIds: [widget.joke.id],
      label: JokeConstants.similarJokesLabel,
    );

    // Navigate to search using push so that back returns to previous page
    final nav = refLocal.read(navigationHelpersProvider);
    nav.navigateToRoute(
      AppRoutes.discoverSearch,
      method: 'programmatic',
      push: true,
    );
  }
}
