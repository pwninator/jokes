import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:showcaseview/showcaseview.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/onboarding_tour_state_store.dart';

final GlobalKey _feedShowcaseKey = GlobalKey(debugLabel: 'onboarding-feed');
final GlobalKey _discoverShowcaseKey = GlobalKey(
  debugLabel: 'onboarding-discover',
);
final GlobalKey _savedShowcaseKey = GlobalKey(debugLabel: 'onboarding-saved');

class OnboardingTourStep {
  OnboardingTourStep({
    required this.key,
    required this.title,
    required this.description,
    required this.automationKey,
  });

  final GlobalKey key;
  final String title;
  final String description;
  final Key automationKey;
}

class OnboardingTourSteps {
  OnboardingTourSteps()
    : feed = OnboardingTourStep(
        key: _feedShowcaseKey,
        title: 'Joke Feed',
        description:
            'Scroll this feed to enjoy a never-ending stream of jokes.',
        automationKey: const Key('app_router-tab-feed-button'),
      ),
      discover = OnboardingTourStep(
        key: _discoverShowcaseKey,
        title: 'Discover',
        description:
            'Browse jokes by specific categories. New categories are added regularly!',
        automationKey: const Key('app_router-tab-discover-button'),
      ),
      saved = OnboardingTourStep(
        key: _savedShowcaseKey,
        title: 'Saved Jokes',
        description: 'Find all the jokes you\'ve favorited here.',
        automationKey: const Key('app_router-tab-saved-button'),
      );

  final OnboardingTourStep feed;
  final OnboardingTourStep discover;
  final OnboardingTourStep saved;

  Iterable<OnboardingTourStep> get all => [feed, discover, saved];

  List<GlobalKey> get orderedKeys => all.map((step) => step.key).toList();

  List<GlobalKey> mountedKeys() {
    return all
        .map((step) => step.key)
        .where((key) => key.currentContext != null)
        .cast<GlobalKey>()
        .toList();
  }
}

final onboardingTourStepsProvider = Provider<OnboardingTourSteps>((ref) {
  return OnboardingTourSteps();
});

Widget wrapWithOnboardingShowcase({
  required OnboardingTourStep? step,
  required Widget child,
  required Color tooltipBackgroundColor,
  required Color tooltipTextColor,
  TooltipPosition? tooltipPosition,
}) {
  if (step == null) return child;
  return Showcase(
    key: step.key,
    title: step.title,
    description: step.description,
    disposeOnTap: false,
    onTargetClick: () {
      AppLogger.debug('ONBOARDING_TOUR: Target tapped');
      ShowcaseView.get().next(force: true);
    },
    onToolTipClick: () {
      AppLogger.debug('ONBOARDING_TOUR: Tooltip tapped');
      ShowcaseView.get().next(force: true);
    },
    tooltipPosition: tooltipPosition,
    tooltipBackgroundColor: tooltipBackgroundColor,
    textColor: tooltipTextColor,
    child: KeyedSubtree(key: step.automationKey, child: child),
  );
}

class OnboardingTourLauncher extends ConsumerStatefulWidget {
  const OnboardingTourLauncher({required this.child, super.key});

  final Widget child;

  @override
  ConsumerState<OnboardingTourLauncher> createState() =>
      _OnboardingTourLauncherState();
}

class _OnboardingTourLauncherState
    extends ConsumerState<OnboardingTourLauncher> {
  bool _tourCompleted = false;
  bool _tourStarted = false;
  bool _shouldRunTour = false;

  @override
  void initState() {
    super.initState();
    ShowcaseView.register(
      onFinish: _handleShowcaseFinished,
      onDismiss: _handleShowcaseDismissed,
    );
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybeStartTour());
  }

  @override
  void dispose() {
    try {
      ShowcaseView.get().unregister();
    } catch (_) {
      // Safe to ignore if already unregistered
    }
    super.dispose();
  }

  Future<void> _maybeStartTour() async {
    if (!mounted || _tourCompleted || _tourStarted) return;

    final store = ref.read(onboardingTourStateStoreProvider);
    if (!_shouldRunTour) {
      final shouldShow = await store.shouldShowTour();
      if (!mounted || _tourCompleted) return;
      if (!shouldShow) {
        AppLogger.debug('ONBOARDING_TOUR: Skipping tour because flag is false');
        return;
      }
      _shouldRunTour = true;
    }

    final keys = ref.read(onboardingTourStepsProvider).orderedKeys;

    _tourStarted = true;
    AppLogger.debug(
      'ONBOARDING_TOUR: Starting showcase with ${keys.length} steps',
    );
    Future<void>.delayed(
      const Duration(milliseconds: 100),
      () => ShowcaseView.get().startShowCase(keys),
    );
  }

  Future<void> _completeTour(OnboardingTourStateStore store) async {
    if (_tourCompleted) return;
    _tourCompleted = true;
    await store.markCompleted();
  }

  void _handleShowcaseFinished() {
    final store = ref.read(onboardingTourStateStoreProvider);
    unawaited(_completeTour(store));
  }

  void _handleShowcaseDismissed(GlobalKey? _) {
    final store = ref.read(onboardingTourStateStoreProvider);
    unawaited(_completeTour(store));
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
