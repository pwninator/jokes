import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:smooth_page_indicator/smooth_page_indicator.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/common_widgets/holdable_button.dart';
import 'package:snickerdoodle/src/common_widgets/joke_reaction_button.dart'
    as reaction_buttons;
import 'package:snickerdoodle/src/common_widgets/share_joke_button.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

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
  final bool showThumbsButtons;
  final String? title;
  final String jokeContext;

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
    this.showThumbsButtons = false,
    this.title,
    required this.jokeContext,
  });

  @override
  ConsumerState<JokeImageCarousel> createState() => _JokeImageCarouselState();
}

class _JokeImageCarouselState extends ConsumerState<JokeImageCarousel> {
  late PageController _pageController;
  int _currentIndex = 0;

  // Track the navigation method that triggered the current page change
  String _lastNavigationMethod = AnalyticsNavigationMethod.swipe;

  @override
  void initState() {
    super.initState();
    _pageController = PageController();
    _preloadImages();

    // Initialize image state (starts at setup image = index 0)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (widget.onImageStateChanged != null) {
        widget.onImageStateChanged!(0);
      }

      // Track initial setup view
      final analyticsService = ref.read(analyticsServiceProvider);
      final joke = widget.joke;
      final hasImages =
          joke.setupImageUrl != null &&
          joke.setupImageUrl!.isNotEmpty &&
          joke.punchlineImageUrl != null &&
          joke.punchlineImageUrl!.isNotEmpty;

      analyticsService.logJokeSetupViewed(
        joke.id,
        hasImages: hasImages,
        navigationMethod: AnalyticsNavigationMethod.none,
        jokeContext: widget.jokeContext,
      );
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

    // Track analytics for joke viewing
    final analyticsService = ref.read(analyticsServiceProvider);
    final joke = widget.joke;
    final hasImages =
        joke.setupImageUrl != null &&
        joke.setupImageUrl!.isNotEmpty &&
        joke.punchlineImageUrl != null &&
        joke.punchlineImageUrl!.isNotEmpty;

    if (index == 0) {
      // User is viewing setup image
      analyticsService.logJokeSetupViewed(
        joke.id,
        hasImages: hasImages,
        navigationMethod: _lastNavigationMethod,
        jokeContext: widget.jokeContext,
      );
    } else if (index == 1) {
      // User is viewing punchline image
      analyticsService.logJokePunchlineViewed(
        joke.id,
        hasImages: hasImages,
        navigationMethod: _lastNavigationMethod,
        jokeContext: widget.jokeContext,
      );

      // Trigger subscription prompt when user views punchline (index 1)
      final subscriptionPromptNotifier = ref.read(
        subscriptionPromptProvider.notifier,
      );
      subscriptionPromptNotifier.startPromptTimer();
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
            const Text('Generation Metadata'),
          ],
        ),
        content: SizedBox(
          width: double.maxFinite,
          child: SingleChildScrollView(
            child: metadata != null && metadata.isNotEmpty
                ? Container(
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
                    child: _buildFormattedMetadata(metadata),
                  )
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

  Widget _buildFormattedMetadata(Map<String, dynamic> metadata) {
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
              child: GestureDetector(
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
                          _buildImagePage(imageUrl: widget.joke.setupImageUrl),
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
            ),
          ),

          // Page indicators and reaction buttons row
          Row(
            children: [
              // Left spacer
              const Expanded(child: SizedBox()),

              // Page indicators (centered)
              SmoothPageIndicator(
                controller: _pageController,
                count: 2,
                effect: WormEffect(
                  dotHeight: 12,
                  dotWidth: 12,
                  spacing: 6,
                  radius: 6,
                  dotColor: theme.colorScheme.onSurface.withValues(alpha: 0.3),
                  activeDotColor: theme.colorScheme.primary,
                ),
              ),

              // Right buttons (save, share, thumbs) or spacer
              Expanded(child: _buildRightButtons()),
            ],
          ),

          // Regenerate buttons (only shown in admin mode)
          if (widget.isAdminMode)
            Padding(
              padding: const EdgeInsets.only(
                left: 16.0,
                right: 16.0,
                bottom: 16.0,
              ),
              child: Row(
                children: [
                  // Hold to Delete button (leftmost)
                  Expanded(
                    child: HoldableButton(
                      key: const Key('delete-joke-button'),
                      icon: Icons.delete,
                      holdCompleteIcon: Icons.delete_forever,
                      onTap: () {
                        // Do nothing on tap
                      },
                      onHoldComplete: () async {
                        final repository = ref.read(jokeRepositoryProvider);
                        await repository.deleteJoke(widget.joke.id);
                      },
                      isEnabled: !isPopulating,
                      theme: theme,
                      color: theme.colorScheme.error,
                      holdDuration: const Duration(seconds: 3),
                    ),
                  ),
                  const SizedBox(width: 8.0),
                  // Hold to Regenerate Edit button (middle)
                  Expanded(
                    child: HoldableButton(
                      key: const Key('edit-joke-button'),
                      icon: Icons.edit,
                      holdCompleteIcon: Icons.refresh,
                      onTap: () {
                        context.pushNamed(
                          RouteNames.adminEditorWithJoke,
                          pathParameters: {'jokeId': widget.joke.id},
                        );
                      },
                      onHoldComplete: () async {
                        final notifier = ref.read(
                          jokePopulationProvider.notifier,
                        );
                        await notifier.populateJoke(
                          widget.joke.id,
                          imagesOnly: false,
                        );
                      },
                      isEnabled: !isPopulating,
                      theme: theme,
                      color: theme.colorScheme.tertiaryContainer,
                    ),
                  ),
                  const SizedBox(width: 8.0),
                  // Regenerate Images button (rightmost)
                  Expanded(
                    child: HoldableButton(
                      key: const Key('regenerate-images-button'),
                      icon: Icons.image,
                      holdCompleteIcon: Icons.hd,
                      onTap: () async {
                        final notifier = ref.read(
                          jokePopulationProvider.notifier,
                        );
                        await notifier.populateJoke(
                          widget.joke.id,
                          imagesOnly: true,
                          additionalParams: {"image_quality": "medium"},
                        );
                      },
                      onHoldComplete: () async {
                        final notifier = ref.read(
                          jokePopulationProvider.notifier,
                        );
                        await notifier.populateJoke(
                          widget.joke.id,
                          imagesOnly: true,
                          additionalParams: {"image_quality": "high"},
                        );
                      },
                      isEnabled: !isPopulating,
                      theme: theme,
                      color: theme.colorScheme.secondaryContainer,
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

    // Add thumbs buttons if enabled
    if (widget.showThumbsButtons) {
      if (buttons.isNotEmpty) {
        buttons.add(const SizedBox(width: 8));
      }
      buttons.addAll([
        reaction_buttons.ThumbsUpJokeButton(
          jokeId: widget.joke.id,
          jokeContext: widget.jokeContext,
        ),
        const SizedBox(width: 8),
        reaction_buttons.ThumbsDownJokeButton(
          jokeId: widget.joke.id,
          jokeContext: widget.jokeContext,
        ),
      ]);
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
        reaction_buttons.SaveJokeButton(
          jokeId: widget.joke.id,
          jokeContext: widget.jokeContext,
        ),
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
}
