import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_configured_screen.dart';
import 'package:snickerdoodle/src/common_widgets/bouncing_button.dart';
import 'package:snickerdoodle/src/common_widgets/notification_hour_widget.dart';
import 'package:snickerdoodle/src/common_widgets/subscription_prompt_dialog.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/core/providers/app_usage_events_provider.dart';
import 'package:snickerdoodle/src/core/providers/app_version_provider.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/feedback_prompt_state_store.dart';
import 'package:snickerdoodle/src/core/services/onboarding_tour_state_store.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';
import 'package:snickerdoodle/src/core/services/url_launcher_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/feedback/presentation/user_feedback_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/settings/application/admin_settings_service.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';
import 'package:snickerdoodle/src/features/settings/application/theme_settings_service.dart';

class UserSettingsScreen extends ConsumerStatefulWidget
    implements TitledScreen {
  const UserSettingsScreen({super.key});

  @override
  String get title => 'Settings';

  @override
  ConsumerState<UserSettingsScreen> createState() => _UserSettingsScreenState();
}

class _UserSettingsScreenState extends ConsumerState<UserSettingsScreen> {
  // Developer mode state (resets on app restart)
  bool _developerModeEnabled = false;
  _UsageMetrics? _cachedUsageMetrics;

  // Secret sequence tracking
  final List<String> _tapSequence = [];
  DateTime? _lastTap;

  // Expected sequence: Theme(2x), Version(2x), Notifications(4x) = 8 taps total
  static const List<String> _secretSequence = [
    'theme',
    'theme',
    'version',
    'version',
    'notifications',
    'notifications',
    'notifications',
    'notifications',
  ];
  static final Uri _privacyPolicyUri = Uri.parse(
    'https://snickerdoodlejokes.com/privacy.html',
  );

  void _handleSecretTap(String tapType) {
    final now = DateTime.now();

    // Reset sequence if more than 2 seconds passed since last tap
    if (_lastTap != null && now.difference(_lastTap!).inSeconds > 2) {
      AppLogger.debug('DEBUG: Settings screen - sequence reset due to timeout');
      _tapSequence.clear();
    }

    AppLogger.debug('DEBUG: Settings screen - adding tap: $tapType');
    _tapSequence.add(tapType);
    _lastTap = now;

    // Check if sequence matches expected pattern so far
    bool sequenceValid = true;
    for (int i = 0; i < _tapSequence.length; i++) {
      if (i >= _secretSequence.length ||
          _tapSequence[i] != _secretSequence[i]) {
        sequenceValid = false;
        break;
      }
    }

    if (!sequenceValid) {
      // Reset on wrong sequence
      _tapSequence.clear();
      AppLogger.debug('DEBUG: Settings screen - sequence invalid');
      return;
    }

    // Check if complete sequence achieved
    if (_tapSequence.length == _secretSequence.length) {
      setState(() {
        _developerModeEnabled = true;
      });

      // Show success message
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text("Congrats! You've unlocked dev mode!"),
          backgroundColor: Theme.of(context).appColors.success,
          duration: const Duration(seconds: 3),
        ),
      );

      // Reset sequence
      _tapSequence.clear();
    }
  }

  Future<void> _openPrivacyPolicy() async {
    try {
      final analyticsService = ref.read(analyticsServiceProvider);
      analyticsService.logPrivacyPolicyOpened();

      final launcher = ref.read(urlLauncherServiceProvider);
      final didLaunch = await launcher.launchUrl(_privacyPolicyUri);
      if (!didLaunch && mounted) {
        AppLogger.warn(
          'PRIVACY_POLICY: launchUrl returned false for privacy policy',
        );
      }
    } catch (error, stackTrace) {
      AppLogger.error(
        'PRIVACY_POLICY: Failed to open privacy policy: $error',
        stackTrace: stackTrace,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final currentUser = ref.watch(currentUserProvider);
    final authController = ref.watch(authControllerProvider);

    return AppBarConfiguredScreen(
      title: 'Settings',
      automaticallyImplyLeading: false,
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Theme Settings Section
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      GestureDetector(
                        key: const Key(
                          'user_settings_screen-theme-settings-secret-tap',
                        ),
                        onTap: () => _handleSecretTap('theme'),
                        child: Text(
                          'Theme Settings',
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                      ),
                      const SizedBox(height: 16),
                      _buildThemeSettings(context, ref),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 8),

              // Joke Viewer Settings Section
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Joke Viewer',
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 12),
                      Consumer(
                        builder: (context, ref, _) {
                          final reveal = ref.watch(jokeViewerRevealProvider);
                          return Row(
                            children: [
                              Icon(
                                reveal
                                    ? Icons.visibility_off
                                    : Icons.view_agenda,
                                color: Theme.of(context).colorScheme.primary,
                              ),
                              const SizedBox(width: 16),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      reveal
                                          ? 'Hide punchline image for a surprise!'
                                          : 'Always show both images',
                                      style: menuTitleTextStyle(context),
                                    ),
                                  ],
                                ),
                              ),
                              Switch(
                                key: const Key('joke-viewer-toggle'),
                                value: reveal,
                                onChanged: (value) async {
                                  await ref
                                      .read(jokeViewerRevealProvider.notifier)
                                      .setReveal(value);
                                },
                              ),
                            ],
                          );
                        },
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 8),

              // Notification Settings Section
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      GestureDetector(
                        key: const Key(
                          'user_settings_screen-notifications-secret-tap',
                        ),
                        onTap: () => _handleSecretTap('notifications'),
                        child: Text(
                          'Notifications',
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                      ),
                      const SizedBox(height: 16),
                      _buildNotificationSettings(context, ref),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 16),

              // Suggestions/Feedback button
              Align(
                alignment: Alignment.center,
                child: OutlinedButton.icon(
                  key: const Key('settings-feedback-button'),
                  icon: const Icon(Icons.feedback_outlined),
                  label: const Text('Suggestions/Feedback'),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(
                      vertical: 16,
                      horizontal: 16,
                    ),
                    visualDensity: VisualDensity.compact,
                    minimumSize: const Size(0, 32),
                  ),
                  onPressed: () async {
                    final router = GoRouter.maybeOf(context);
                    final messenger = ScaffoldMessenger.of(context);
                    final successColor = Theme.of(context).colorScheme.primary;

                    Future<bool?> navigationFuture;
                    if (router != null) {
                      navigationFuture = router.pushNamed<bool>(
                        RouteNames.feedback,
                      );
                    } else {
                      navigationFuture = Navigator.of(context).push<bool>(
                        MaterialPageRoute(
                          builder: (_) => const UserFeedbackScreen(),
                        ),
                      );
                    }

                    final result = await navigationFuture;
                    if (!context.mounted || result != true) {
                      return;
                    }

                    messenger.showSnackBar(
                      SnackBar(
                        content: const Text('Thanks for your feedback!'),
                        backgroundColor: successColor,
                      ),
                    );
                  },
                ),
              ),

              // Developer mode sections (only show when unlocked)
              if (_developerModeEnabled) ...[
                const SizedBox(height: 16),

                // User Info Section
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'User Information',
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                        const SizedBox(height: 8),
                        if (currentUser != null) ...[
                          _buildInfoRow(
                            'Status',
                            currentUser.isAnonymous
                                ? 'Guest User'
                                : 'Signed In',
                          ),
                          if (!currentUser.isAnonymous) ...[
                            _buildInfoRow(
                              'Email',
                              currentUser.email ?? 'Not provided',
                            ),
                            _buildInfoRow(
                              'Display Name',
                              currentUser.displayName ?? 'Not set',
                            ),
                          ],
                          _buildInfoRow(
                            'Role',
                            _getRoleDisplay(currentUser.role),
                          ),
                          _buildInfoRow('User ID', currentUser.id),
                        ] else
                          const Text('No user information available'),

                        const SizedBox(height: 12),
                        Consumer(
                          builder: (context, ref, _) {
                            // Rebuild usage metrics when app usage changes
                            ref.watch(appUsageEventsProvider);
                            return FutureBuilder<_UsageMetrics>(
                              future: _fetchUsageMetrics(ref),
                              initialData: _cachedUsageMetrics,
                              builder: (context, snapshot) {
                                if (snapshot.hasData && snapshot.data != null) {
                                  _cachedUsageMetrics = snapshot.data;
                                }
                                final metrics =
                                    snapshot.data ?? _cachedUsageMetrics;
                                if (metrics == null) {
                                  return const SizedBox.shrink();
                                }
                                final firstValue = metrics.firstUsedDate ?? '';
                                final lastValue = metrics.lastUsedDate ?? '';
                                final days = metrics.numDaysUsed;
                                return Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    _buildInfoRowButton(
                                      label: 'First Used Date',
                                      buttonLabel: firstValue.isEmpty
                                          ? '—'
                                          : firstValue,
                                      buttonKey: const Key(
                                        'user_settings_screen-first-used-date-button',
                                      ),
                                      onPressed: () =>
                                          _showEditableUsageValueDialog(
                                            context: context,
                                            ref: ref,
                                            keyPrefix: 'first-used-date',
                                            title: 'First Used Date',
                                            initialValue: firstValue,
                                            onSubmit: (usage, value) async {
                                              final sanitized = value.trim();
                                              await usage.setFirstUsedDate(
                                                sanitized.isEmpty
                                                    ? null
                                                    : sanitized,
                                              );
                                            },
                                          ),
                                    ),
                                    _buildInfoRowButton(
                                      label: 'Last Used Date',
                                      buttonLabel: lastValue.isEmpty
                                          ? '—'
                                          : lastValue,
                                      buttonKey: const Key(
                                        'user_settings_screen-last-used-date-button',
                                      ),
                                      onPressed: () =>
                                          _showEditableUsageValueDialog(
                                            context: context,
                                            ref: ref,
                                            keyPrefix: 'last-used-date',
                                            title: 'Last Used Date',
                                            initialValue: lastValue,
                                            onSubmit: (usage, value) async {
                                              final sanitized = value.trim();
                                              await usage.setLastUsedDate(
                                                sanitized.isEmpty
                                                    ? null
                                                    : sanitized,
                                              );
                                            },
                                          ),
                                    ),
                                    _buildInfoRowButton(
                                      label: 'Days Used',
                                      buttonLabel: days.toString(),
                                      buttonKey: const Key(
                                        'user_settings_screen-num-days-used-button',
                                      ),
                                      onPressed: () =>
                                          _showEditableUsageValueDialog(
                                            context: context,
                                            ref: ref,
                                            keyPrefix: 'num-days-used',
                                            title: 'Days Used',
                                            initialValue: days.toString(),
                                            validator: (value) {
                                              final trimmed = value.trim();
                                              if (trimmed.isEmpty) {
                                                return 'Please enter a value.';
                                              }
                                              final parsed = int.tryParse(
                                                trimmed,
                                              );
                                              if (parsed == null) {
                                                return 'Enter a whole number.';
                                              }
                                              if (parsed < 0) {
                                                return 'Value cannot be negative.';
                                              }
                                              return null;
                                            },
                                            onSubmit: (usage, value) async {
                                              final parsed = int.parse(
                                                value.trim(),
                                              );
                                              await usage.setNumDaysUsed(
                                                parsed,
                                              );
                                            },
                                          ),
                                    ),
                                    const SizedBox(height: 8),
                                    Wrap(
                                      spacing: 8,
                                      runSpacing: 8,
                                      children: [
                                        _buildStatusToggleButton(
                                          context: context,
                                          buttonKey: const Key(
                                            'user_settings_screen-review-toggle-button',
                                          ),
                                          label: 'Review',
                                          isActive:
                                              metrics.reviewPromptRequested,
                                          isEnabled: true,
                                          onPressed: () async {
                                            final store = ref.read(
                                              reviewPromptStateStoreProvider,
                                            );
                                            await store.setRequested(
                                              !metrics.reviewPromptRequested,
                                            );
                                            if (!mounted) return;
                                            setState(() {});
                                          },
                                        ),
                                        _buildStatusToggleButton(
                                          context: context,
                                          buttonKey: const Key(
                                            'user_settings_screen-feedback-toggle-button',
                                          ),
                                          label: 'Feedback',
                                          isActive:
                                              metrics.feedbackDialogViewed,
                                          isEnabled: true,
                                          onPressed: () async {
                                            final store = ref.read(
                                              feedbackPromptStateStoreProvider,
                                            );
                                            await store.setViewed(
                                              !metrics.feedbackDialogViewed,
                                            );
                                            if (!mounted) return;
                                            setState(() {});
                                          },
                                        ),
                                        _buildStatusToggleButton(
                                          context: context,
                                          buttonKey: const Key(
                                            'user_settings_screen-subscribe-toggle-button',
                                          ),
                                          label: 'Subscribe',
                                          isActive:
                                              metrics.subscriptionChoiceMade,
                                          isEnabled:
                                              metrics.subscriptionChoiceMade,
                                          onPressed: () async {
                                            final promptNotifier = ref.read(
                                              subscriptionPromptProvider
                                                  .notifier,
                                            );
                                            await promptNotifier
                                                .resetUserChoice();
                                            if (!mounted) return;
                                            setState(() {});
                                          },
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 8),
                                    const SizedBox(height: 8),
                                    Table(
                                      columnWidths: const {
                                        0: FlexColumnWidth(),
                                        1: FlexColumnWidth(),
                                        2: FlexColumnWidth(),
                                        3: FlexColumnWidth(),
                                      },
                                      defaultVerticalAlignment:
                                          TableCellVerticalAlignment.middle,
                                      children: [
                                        TableRow(
                                          children: [
                                            _buildMetricsHeaderCell(
                                              context,
                                              'Navigated',
                                            ),
                                            _buildMetricsHeaderCell(
                                              context,
                                              'Viewed',
                                            ),
                                            _buildMetricsHeaderCell(
                                              context,
                                              'Saved',
                                            ),
                                            _buildMetricsHeaderCell(
                                              context,
                                              'Shared',
                                            ),
                                          ],
                                        ),
                                        TableRow(
                                          children: [
                                            _buildMetricsCountCell(
                                              context: context,
                                              buttonKey: const Key(
                                                'user_settings_screen-navigated-jokes-button',
                                              ),
                                              value: metrics.numJokesNavigated
                                                  .toString(),
                                              onPressed: () =>
                                                  _handleJokeIdsDialog(
                                                    context: context,
                                                    ref: ref,
                                                    title: 'Navigated Jokes',
                                                    loadJokeIds: (usage) => usage
                                                        .getNavigatedJokeIds(),
                                                  ),
                                            ),
                                            _buildMetricsCountCell(
                                              context: context,
                                              buttonKey: const Key(
                                                'user_settings_screen-viewed-jokes-button',
                                              ),
                                              value: metrics.numJokesViewed
                                                  .toString(),
                                              onPressed: () =>
                                                  _handleJokeIdsDialog(
                                                    context: context,
                                                    ref: ref,
                                                    title: 'Viewed Jokes',
                                                    loadJokeIds: (usage) =>
                                                        usage
                                                            .getViewedJokeIds(),
                                                  ),
                                            ),
                                            _buildMetricsCountCell(
                                              context: context,
                                              buttonKey: const Key(
                                                'user_settings_screen-saved-jokes-button',
                                              ),
                                              value: metrics.numJokesSaved
                                                  .toString(),
                                              onPressed: () =>
                                                  _handleJokeIdsDialog(
                                                    context: context,
                                                    ref: ref,
                                                    title: 'Saved Jokes',
                                                    loadJokeIds: (usage) =>
                                                        usage.getSavedJokeIds(),
                                                  ),
                                            ),
                                            _buildMetricsCountCell(
                                              context: context,
                                              buttonKey: const Key(
                                                'user_settings_screen-shared-jokes-button',
                                              ),
                                              value: metrics.numJokesShared
                                                  .toString(),
                                              onPressed: () =>
                                                  _handleJokeIdsDialog(
                                                    context: context,
                                                    ref: ref,
                                                    title: 'Shared Jokes',
                                                    loadJokeIds: (usage) =>
                                                        usage
                                                            .getSharedJokeIds(),
                                                  ),
                                            ),
                                          ],
                                        ),
                                      ],
                                    ),
                                  ],
                                );
                              },
                            );
                          },
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Admin Settings Section
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Admin Settings',
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                        const SizedBox(height: 16),
                        // Force Show Banner Ads
                        Consumer(
                          builder: (context, ref, _) {
                            final adminSettingsService = ref.read(
                              adminSettingsServiceProvider,
                            );
                            final adminOverride = adminSettingsService
                                .getAdminOverrideShowBannerAd();

                            return Row(
                              children: [
                                Icon(
                                  Icons.ads_click,
                                  color: adminOverride
                                      ? Theme.of(context).colorScheme.primary
                                      : Theme.of(context).colorScheme.onSurface
                                            .withValues(alpha: 0.6),
                                ),
                                const SizedBox(width: 16),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'Force Show Banner Ads',
                                        style: menuTitleTextStyle(context),
                                      ),
                                      const SizedBox(height: 2),
                                      Text(
                                        adminOverride
                                            ? 'Banner ads will show regardless of remote config'
                                            : 'Banner ads follow remote config settings',
                                        style: menuSubtitleTextStyle(context),
                                      ),
                                    ],
                                  ),
                                ),
                                Switch(
                                  key: const Key(
                                    'user_settings_screen-admin-override-banner-ads-toggle',
                                  ),
                                  value: adminOverride,
                                  onChanged: (value) async {
                                    await adminSettingsService
                                        .setAdminOverrideShowBannerAd(value);
                                    if (!mounted) return;
                                    setState(() {});
                                  },
                                ),
                              ],
                            );
                          },
                        ),
                        const SizedBox(height: 16),
                        // Onboarding Tour Completion
                        Consumer(
                          builder: (context, ref, _) {
                            final store = ref.read(
                              onboardingTourStateStoreProvider,
                            );
                            return FutureBuilder<bool>(
                              future: store.hasCompleted(),
                              builder: (context, snapshot) {
                                final completed = snapshot.data ?? true;
                                final loading =
                                    snapshot.connectionState !=
                                    ConnectionState.done;

                                return Row(
                                  children: [
                                    Icon(
                                      Icons.tour,
                                      color: completed
                                          ? Theme.of(
                                              context,
                                            ).colorScheme.primary
                                          : Theme.of(context)
                                                .colorScheme
                                                .onSurface
                                                .withValues(alpha: 0.6),
                                    ),
                                    const SizedBox(width: 16),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            'Onboarding Tour Completed',
                                            style: menuTitleTextStyle(context),
                                          ),
                                          const SizedBox(height: 2),
                                          Text(
                                            completed
                                                ? 'Tour is marked complete; it will stay hidden until reset.'
                                                : 'Tour is marked incomplete; it will show the next time it runs.',
                                            style: menuSubtitleTextStyle(
                                              context,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                    loading
                                        ? const SizedBox(
                                            width: 24,
                                            height: 24,
                                            child: CircularProgressIndicator(
                                              strokeWidth: 2,
                                            ),
                                          )
                                        : Switch(
                                            key: const Key(
                                              'user_settings_screen-onboarding-complete-toggle',
                                            ),
                                            value: completed,
                                            onChanged: (value) async {
                                              await store.setCompleted(value);
                                              if (!mounted) return;
                                              setState(() {});
                                            },
                                          ),
                                  ],
                                );
                              },
                            );
                          },
                        ),
                        const SizedBox(height: 16),
                        // Show Joke Data Source
                        Consumer(
                          builder: (context, ref, _) {
                            final adminSettings = ref.read(
                              adminSettingsServiceProvider,
                            );
                            final showDataSource = adminSettings
                                .getAdminShowJokeDataSource();

                            return Row(
                              children: [
                                Icon(
                                  Icons.source,
                                  color: showDataSource
                                      ? Theme.of(context).colorScheme.primary
                                      : Theme.of(context).colorScheme.onSurface
                                            .withValues(alpha: 0.6),
                                ),
                                const SizedBox(width: 16),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'Show Joke Data Source',
                                        style: menuTitleTextStyle(context),
                                      ),
                                      const SizedBox(height: 2),
                                      Text(
                                        'Display source ID in joke carousel',
                                        style: menuSubtitleTextStyle(context),
                                      ),
                                    ],
                                  ),
                                ),
                                Switch(
                                  key: const Key(
                                    'user_settings_screen-show-data-source-toggle',
                                  ),
                                  value: showDataSource,
                                  onChanged: (value) async {
                                    await adminSettings
                                        .setAdminShowJokeDataSource(value);
                                    if (!mounted) return;
                                    setState(() {});
                                  },
                                ),
                              ],
                            );
                          },
                        ),
                        const SizedBox(height: 16),
                        Consumer(
                          builder: (context, ref, _) {
                            final adminSettings = ref.read(
                              adminSettingsServiceProvider,
                            );
                            final showProposed = adminSettings
                                .getAdminShowProposedCategories();

                            return Row(
                              children: [
                                Icon(
                                  Icons.category,
                                  color: showProposed
                                      ? Theme.of(context).colorScheme.primary
                                      : Theme.of(context).colorScheme.onSurface
                                            .withValues(alpha: 0.6),
                                ),
                                const SizedBox(width: 16),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'Show Proposed Categories',
                                        style: menuTitleTextStyle(context),
                                      ),
                                      const SizedBox(height: 2),
                                      Text(
                                        'Include proposed Discover categories',
                                        style: menuSubtitleTextStyle(context),
                                      ),
                                    ],
                                  ),
                                ),
                                Switch(
                                  key: const Key(
                                    'user_settings_screen-show-proposed-categories-toggle',
                                  ),
                                  value: showProposed,
                                  onChanged: (value) async {
                                    await adminSettings
                                        .setAdminShowProposedCategories(value);
                                    ref.invalidate(discoverCategoriesProvider);
                                    if (!mounted) return;
                                    setState(() {});
                                  },
                                ),
                              ],
                            );
                          },
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Authentication Actions Section
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Authentication',
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                        const SizedBox(height: 16),

                        if (currentUser?.isAnonymous == true) ...[
                          // Show Google sign-in option for anonymous users
                          BouncingButton(
                            buttonKey: const Key(
                              'user_settings_screen-google-sign-in-button',
                            ),
                            isPositive: true,
                            onPressed: () =>
                                _signInWithGoogle(context, authController),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Theme.of(
                                context,
                              ).appColors.googleBlue,
                              foregroundColor: Colors.white,
                            ),
                            icon: const Icon(Icons.login),
                            child: const Text('Sign in with Google'),
                          ),
                        ] else ...[
                          // Show sign out option for authenticated users
                          BouncingButton(
                            buttonKey: const Key(
                              'user_settings_screen-switch-to-guest-button',
                            ),
                            isPositive: true,
                            onPressed: () =>
                                _confirmSignOut(context, authController),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Theme.of(
                                context,
                              ).appColors.authError,
                              foregroundColor: Colors.white,
                            ),
                            icon: const Icon(Icons.logout),
                            child: const Text('Switch to Guest Mode'),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Testing Section
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Testing',
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                        const SizedBox(height: 16),

                        BouncingButton(
                          buttonKey: const Key(
                            'user_settings_screen-test-subscribe-prompt-button',
                          ),
                          isPositive: true,
                          onPressed: () => _testSubscribePrompt(context),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Theme.of(
                              context,
                            ).colorScheme.tertiary,
                            foregroundColor: Colors.white,
                          ),
                          icon: const Icon(Icons.notifications),
                          child: const Text('Test Subscribe Prompt'),
                        ),
                        const SizedBox(height: 12),
                        BouncingButton(
                          buttonKey: const Key('settings-review-button'),
                          isPositive: true,
                          onPressed: () => _testReviewPrompt(context),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Theme.of(
                              context,
                            ).colorScheme.secondary,
                            foregroundColor: Colors.white,
                          ),
                          icon: const Icon(Icons.rate_review),
                          child: const Text('Test Review Prompt'),
                        ),
                        const SizedBox(height: 12),
                        BouncingButton(
                          buttonKey: const Key('settings-remote-config-button'),
                          isPositive: true,
                          onPressed: () => _showRemoteConfigDialog(context),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Theme.of(
                              context,
                            ).colorScheme.primaryContainer,
                            foregroundColor: Theme.of(
                              context,
                            ).colorScheme.onPrimaryContainer,
                          ),
                          icon: const Icon(Icons.tune),
                          child: const Text('See Remote Config'),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 16),

              Center(
                child: TextButton(
                  key: const Key('user_settings_screen-privacy-policy-button'),
                  onPressed: _openPrivacyPolicy,
                  style: Theme.of(context).textButtonTheme.style?.copyWith(
                    foregroundColor: WidgetStateProperty.all(
                      Theme.of(
                        context,
                      ).colorScheme.onSurface.withValues(alpha: 0.8),
                    ),
                  ),
                  child: const Text('Privacy Policy'),
                ),
              ),

              // Version text (for secret sequence)
              Center(
                child: GestureDetector(
                  key: const Key('user_settings_screen-version-secret-tap'),
                  onTap: () => _handleSecretTap('version'),
                  child: Container(
                    padding: const EdgeInsets.symmetric(vertical: 16.0),
                    child: Consumer(
                      builder: (context, ref, child) {
                        final appVersionAsync = ref.watch(appVersionProvider);
                        return Text(
                          appVersionAsync.when(
                            data: (version) => version,
                            loading: () => 'Loading version...',
                            error: (error, stack) => 'Snickerdoodle Jokes',
                          ),
                          style: Theme.of(context).textTheme.labelMedium
                              ?.copyWith(
                                color: Theme.of(
                                  context,
                                ).colorScheme.onSurface.withValues(alpha: 0.5),
                              ),
                        );
                      },
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildThemeSettings(BuildContext context, WidgetRef ref) {
    final currentThemeMode = ref.watch(themeModeProvider);
    final themeModeNotifier = ref.read(themeModeProvider.notifier);

    return RadioGroup(
      groupValue: currentThemeMode,
      onChanged: (ThemeMode? value) {
        if (value != null) {
          themeModeNotifier.setThemeMode(value);
        }
      },
      child: Column(
        children: [
          _buildThemeOption(
            context,
            ThemeMode.system,
            currentThemeMode,
            Icons.brightness_auto,
            'Use System Setting',
            'Automatically switch between light and dark themes based on your device settings',
            () => themeModeNotifier.setThemeMode(ThemeMode.system),
          ),
          _buildThemeOption(
            context,
            ThemeMode.light,
            currentThemeMode,
            Icons.light_mode,
            'Always Light',
            'Use light theme regardless of system settings',
            () => themeModeNotifier.setThemeMode(ThemeMode.light),
          ),
          _buildThemeOption(
            context,
            ThemeMode.dark,
            currentThemeMode,
            Icons.dark_mode,
            'Always Dark',
            'Use dark theme regardless of system settings',
            () => themeModeNotifier.setThemeMode(ThemeMode.dark),
          ),
        ],
      ),
    );
  }

  Widget _buildNotificationSettings(BuildContext context, WidgetRef ref) {
    // Watch the reactive subscription state
    final subscriptionState = ref.watch(subscriptionProvider);
    final isSubscribed = subscriptionState.isSubscribed;

    return Column(
      children: [
        Row(
          children: [
            Icon(
              Icons.notifications,
              color: isSubscribed
                  ? Theme.of(context).colorScheme.primary
                  : Theme.of(
                      context,
                    ).colorScheme.onSurface.withValues(alpha: 0.6),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Daily Joke Notifications',
                    style: menuTitleTextStyle(context),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    isSubscribed
                        ? 'Receive daily joke notifications'
                        : 'Get notified when new jokes are available',
                    style: menuSubtitleTextStyle(context),
                  ),
                ],
              ),
            ),
            Switch(
              key: const Key('user_settings_screen-notifications-toggle'),
              value: isSubscribed,
              onChanged: (value) => _toggleNotifications(context, ref, value),
            ),
          ],
        ),
        if (isSubscribed) ...[
          const SizedBox(height: 16),
          const HourDisplayWidget(),
        ],
      ],
    );
  }

  Widget _buildThemeOption(
    BuildContext context,
    ThemeMode themeMode,
    ThemeMode currentThemeMode,
    IconData icon,
    String title,
    String subtitle,
    VoidCallback onTap,
  ) {
    final isSelected = themeMode == currentThemeMode;

    return RadioListTile<ThemeMode>(
      key: Key(
        'user_settings_screen-theme-option-${title.toLowerCase().replaceAll(' ', '-')}',
      ),
      value: themeMode,
      title: Text(title, style: menuTitleTextStyle(context)),
      subtitle: Text(subtitle, style: menuSubtitleTextStyle(context)),
      secondary: Icon(
        icon,
        color: isSelected
            ? Theme.of(context).colorScheme.primary
            : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
      ),
      selected: isSelected,
    );
  }

  Widget _buildInfoRowButton({
    required String label,
    required String buttonLabel,
    required Key buttonKey,
    required VoidCallback onPressed,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          SizedBox(
            width: 100,
            child: Text(
              '$label:',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
          TextButton(
            key: buttonKey,
            onPressed: onPressed,
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              minimumSize: const Size(0, 32),
              visualDensity: VisualDensity.compact,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: Text(buttonLabel),
          ),
        ],
      ),
    );
  }

  Widget _buildMetricsHeaderCell(BuildContext context, String label) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Text(
        label,
        style: Theme.of(
          context,
        ).textTheme.labelMedium?.copyWith(fontWeight: FontWeight.bold),
        textAlign: TextAlign.center,
      ),
    );
  }

  Widget _buildMetricsCountCell({
    required BuildContext context,
    required Key buttonKey,
    required String value,
    required VoidCallback onPressed,
  }) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: TextButton(
        key: buttonKey,
        onPressed: onPressed,
        style: TextButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
          minimumSize: const Size(0, 36),
          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
          foregroundColor: theme.colorScheme.primary,
        ),
        child: Text(
          value,
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: theme.colorScheme.primary,
          ),
        ),
      ),
    );
  }

  Widget _buildStatusToggleButton({
    required BuildContext context,
    required Key buttonKey,
    required String label,
    required bool isActive,
    Future<void> Function()? onPressed,
    bool isEnabled = true,
  }) {
    final successColor = Theme.of(context).appColors.success;
    final inactiveColor = Theme.of(context).colorScheme.surfaceContainerHighest;
    final disabledColor = Theme.of(context).colorScheme.surfaceContainerHighest;
    final textColor = !isEnabled
        ? Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.3)
        : isActive
        ? Theme.of(context).colorScheme.onPrimary
        : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5);
    final backgroundColor = !isEnabled
        ? disabledColor
        : isActive
        ? successColor
        : inactiveColor;

    return TextButton(
      key: buttonKey,
      onPressed: !isEnabled || onPressed == null
          ? null
          : () async {
              await onPressed();
            },
      style: TextButton.styleFrom(
        backgroundColor: backgroundColor,
        foregroundColor: textColor,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        minimumSize: const Size(80, 36),
        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      ),
      child: Text(label),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(
              '$label:',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }

  Future<void> _showEditableUsageValueDialog({
    required BuildContext context,
    required WidgetRef ref,
    required String keyPrefix,
    required String title,
    required String initialValue,
    required Future<void> Function(AppUsageService usageService, String value)
    onSubmit,
    String? Function(String value)? validator,
    String? successMessage,
  }) async {
    final usageService = ref.read(appUsageServiceProvider);

    await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return _EditableValueDialog(
          keyPrefix: keyPrefix,
          title: title,
          initialValue: initialValue,
          validator: validator,
          successMessage: successMessage,
          rootContext: context,
          onSubmit: (value) => onSubmit(usageService, value),
        );
      },
    );
  }

  Future<void> _handleJokeIdsDialog({
    required BuildContext context,
    required WidgetRef ref,
    required String title,
    required Future<List<String>> Function(AppUsageService usage) loadJokeIds,
  }) async {
    final usageService = ref.read(appUsageServiceProvider);
    List<String> jokeIds;
    try {
      jokeIds = await loadJokeIds(usageService);
    } catch (error, stackTrace) {
      AppLogger.warn(
        'DEBUG: Settings screen - failed to load joke IDs for $title: $error',
      );
      AppLogger.debug('STACKTRACE: $stackTrace');
      if (!context.mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('Unable to load joke IDs right now.'),
          backgroundColor: Theme.of(context).appColors.authError,
        ),
      );
      return;
    }

    if (!context.mounted) {
      return;
    }

    await showDialog<void>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: Text('$title (${jokeIds.length})'),
          content: SizedBox(
            width: double.maxFinite,
            child: jokeIds.isEmpty
                ? const Text('No jokes recorded yet.')
                : SizedBox(
                    height: 240,
                    child: Scrollbar(
                      thumbVisibility: true,
                      child: ListView.separated(
                        itemCount: jokeIds.length,
                        itemBuilder: (context, index) {
                          final id = jokeIds[index];
                          return ListTile(
                            contentPadding: EdgeInsets.zero,
                            dense: true,
                            visualDensity: VisualDensity.compact,
                            leading: Text('${index + 1}.'),
                            title: SelectableText(id),
                          );
                        },
                        separatorBuilder: (context, _) =>
                            const Divider(height: 1),
                      ),
                    ),
                  ),
          ),
          actions: [
            TextButton(
              key: const Key(
                'user_settings_screen-joke-ids-dialog-close-button',
              ),
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('Close'),
            ),
          ],
        );
      },
    );
  }

  String _getRoleDisplay(UserRole role) {
    switch (role) {
      case UserRole.admin:
        return 'Administrator';
      case UserRole.user:
        return 'User';
      case UserRole.anonymous:
        return 'Anonymous';
    }
  }

  Future<_UsageMetrics> _fetchUsageMetrics(WidgetRef ref) async {
    final usage = ref.read(appUsageServiceProvider);
    final reviewStore = ref.read(reviewPromptStateStoreProvider);
    final feedbackStore = ref.read(feedbackPromptStateStoreProvider);
    final subscriptionPrompt = ref.read(subscriptionPromptProvider);
    final firstUsed = await usage.getFirstUsedDate();
    final lastUsed = await usage.getLastUsedDate();
    final daysUsed = await usage.getNumDaysUsed();
    final jokesViewed = await usage.getNumJokesViewed();
    final jokesNavigated = await usage.getNumJokesNavigated();
    final jokesSaved = await usage.getNumSavedJokes();
    final jokesShared = await usage.getNumSharedJokes();
    final reviewRequested = reviewStore.hasRequested();
    final feedbackViewed = await feedbackStore.hasViewed();

    return _UsageMetrics(
      firstUsedDate: firstUsed,
      lastUsedDate: lastUsed,
      numDaysUsed: daysUsed,
      numJokesNavigated: jokesNavigated,
      numJokesViewed: jokesViewed,
      numJokesSaved: jokesSaved,
      numJokesShared: jokesShared,
      reviewPromptRequested: reviewRequested,
      feedbackDialogViewed: feedbackViewed,
      subscriptionChoiceMade: subscriptionPrompt.hasUserMadeChoice,
    );
  }

  Future<void> _signInWithGoogle(
    BuildContext context,
    AuthController authController,
  ) async {
    try {
      AppLogger.debug('DEBUG: Settings screen - starting Google sign-in...');
      await authController.signInWithGoogle();
      AppLogger.debug(
        'DEBUG: Settings screen - Google sign-in completed successfully',
      );
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Successfully signed in with Google!'),
            backgroundColor: Theme.of(context).appColors.success,
            duration: const Duration(seconds: 4),
          ),
        );
      }
    } catch (e) {
      AppLogger.warn('DEBUG: Settings screen - Google sign-in failed: $e');
      // Log analytics/crash for sign-in failure
      try {
        final analytics = ref.read(analyticsServiceProvider);
        analytics.logErrorAuthSignIn(
          source: 'user_settings_screen',
          errorMessage: 'google_sign_in_failed',
        );
      } catch (_) {}
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to sign in: ${e.toString()}'),
            backgroundColor: Theme.of(context).appColors.authError,
            duration: const Duration(seconds: 8), // Longer duration for errors
            action: SnackBarAction(
              label: 'Details',
              textColor: Colors.white,
              onPressed: () {
                AppLogger.debug('ERROR DETAILS: $e');
                // Show dialog with full error
                showDialog(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Sign-in Error'),
                    content: SingleChildScrollView(child: Text(e.toString())),
                    actions: [
                      TextButton(
                        key: const Key(
                          'user_settings_screen-error-dialog-ok-button',
                        ),
                        onPressed: () => Navigator.of(context).pop(),
                        child: const Text('OK'),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        );
      }
    }
  }

  void _confirmSignOut(BuildContext context, AuthController authController) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Switch to Guest Mode'),
        content: const Text(
          'Are you sure you want to switch to guest mode? You will still be able to view jokes, but you\'ll lose access to your personalized features.',
        ),
        actions: [
          TextButton(
            key: const Key('user_settings_screen-sign-out-cancel-button'),
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            key: const Key('user_settings_screen-sign-out-confirm-button'),
            onPressed: () async {
              Navigator.of(context).pop();
              try {
                await authController.signOut();
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: const Text('Switched to guest mode'),
                      backgroundColor: Theme.of(context).appColors.success,
                      duration: const Duration(seconds: 3),
                    ),
                  );
                }
              } catch (e) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('Failed to switch to guest mode: $e'),
                      backgroundColor: Theme.of(context).appColors.authError,
                      duration: const Duration(seconds: 5),
                    ),
                  );
                }
              }
            },
            child: const Text('Switch to Guest'),
          ),
        ],
      ),
    );
  }

  Future<void> _toggleNotifications(
    BuildContext context,
    WidgetRef ref,
    bool enable,
  ) async {
    final subscriptionNotifier = ref.read(subscriptionProvider.notifier);

    try {
      bool success;

      if (enable) {
        // Subscribe with notification permission (uses existing hour or default)
        success = await subscriptionNotifier.subscribeWithPermission();
      } else {
        // Unsubscribe (no permission needed)
        await subscriptionNotifier.unsubscribe();
        success = true;
      }

      // Track analytics for subscription toggle (fire-and-forget)
      final analyticsService = ref.read(analyticsServiceProvider);
      if (success) {
        if (enable) {
          analyticsService.logSubscriptionOnSettings();
        } else {
          analyticsService.logSubscriptionOffSettings();
        }
      } else if (enable) {
        // Track failed subscription attempt
        analyticsService.logSubscriptionDeclinedPermissionsInSettings();
      }

      // Show appropriate message based on result
      if (!success && enable) {
        // Subscription failed (likely permission denied)
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: const Text(
                'Notification permission is required for daily jokes.',
              ),
              backgroundColor: Theme.of(context).colorScheme.secondary,
              duration: const Duration(seconds: 4),
            ),
          );
        }
      }
    } catch (e) {
      AppLogger.warn('ERROR: _toggleNotifications: $e');
      // Log analytics/crash for notification toggle failure (fire-and-forget)
      final analytics = ref.read(analyticsServiceProvider);
      analytics.logErrorSubscriptionToggle(
        source: 'user_settings_screen',
        errorMessage: 'notifications_toggle_failed',
      );
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error updating notification settings'),
            backgroundColor: Theme.of(context).appColors.authError,
            duration: const Duration(seconds: 5),
          ),
        );
      }
    }
  }

  void _testSubscribePrompt(BuildContext context) {
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (context) => const SubscriptionPromptDialog(),
    );
  }

  Future<void> _testReviewPrompt(BuildContext context) async {
    final reviewService = ref.read(appReviewServiceProvider);
    final result = await reviewService.requestReview(
      source: ReviewRequestSource.adminTest,
      context: context,
      force: true,
    );

    if (!context.mounted) return;

    String message;
    Color bg = Theme.of(context).colorScheme.primary;
    switch (result) {
      case ReviewRequestResult.shown:
        message = 'Review prompt shown (if allowed by the OS).';
        break;
      case ReviewRequestResult.notAvailable:
        message = 'In-app review not available on this device.';
        bg = Theme.of(context).colorScheme.secondary;
        break;
      case ReviewRequestResult.dismissed:
        message = 'Review prompt dismissed.';
        bg = Theme.of(context).colorScheme.secondary;
        break;
      case ReviewRequestResult.error:
        message = 'Error requesting review prompt.';
        bg = Theme.of(context).appColors.authError;
        break;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: bg,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  void _showRemoteConfigDialog(BuildContext context) {
    final rc = ref.read(remoteConfigValuesProvider);
    showDialog<void>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Remote Config'),
          content: SingleChildScrollView(
            child: SizedBox(
              width: double.maxFinite,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ...RemoteParam.values.map((param) {
                    final descriptor = remoteParams[param]!;
                    final label = descriptor.key;
                    String valueString;
                    switch (descriptor.type) {
                      case RemoteParamType.intType:
                        valueString = rc.getInt(param).toString();
                        break;
                      case RemoteParamType.boolType:
                        valueString = rc.getBool(param).toString();
                        break;
                      case RemoteParamType.doubleType:
                        valueString = rc.getDouble(param).toString();
                        break;
                      case RemoteParamType.stringType:
                        valueString = rc.getString(param);
                        break;
                      case RemoteParamType.enumType:
                        valueString = rc.getString(param);
                        break;
                    }
                    return Text(
                      '$label: $valueString',
                      style: Theme.of(
                        context,
                      ).textTheme.bodyMedium?.copyWith(fontSize: 13),
                      softWrap: true,
                    );
                  }),
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
        );
      },
    );
  }
}

class _UsageMetrics {
  final String? firstUsedDate;
  final String? lastUsedDate;
  final int numDaysUsed;
  final int numJokesNavigated;
  final int numJokesViewed;
  final int numJokesSaved;
  final int numJokesShared;
  final bool reviewPromptRequested;
  final bool feedbackDialogViewed;
  final bool subscriptionChoiceMade;

  const _UsageMetrics({
    required this.firstUsedDate,
    required this.lastUsedDate,
    required this.numDaysUsed,
    required this.numJokesNavigated,
    required this.numJokesViewed,
    required this.numJokesSaved,
    required this.numJokesShared,
    required this.reviewPromptRequested,
    required this.feedbackDialogViewed,
    required this.subscriptionChoiceMade,
  });
}

class _EditableValueDialog extends StatefulWidget {
  const _EditableValueDialog({
    required this.keyPrefix,
    required this.title,
    required this.initialValue,
    required this.onSubmit,
    required this.rootContext,
    this.validator,
    this.successMessage,
  });

  final String keyPrefix;
  final String title;
  final String initialValue;
  final Future<void> Function(String value) onSubmit;
  final BuildContext rootContext;
  final String? Function(String value)? validator;
  final String? successMessage;

  @override
  State<_EditableValueDialog> createState() => _EditableValueDialogState();
}

class _EditableValueDialogState extends State<_EditableValueDialog> {
  late final TextEditingController _controller;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialValue);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _handleSubmit() async {
    if (_isSubmitting) return;
    final value = _controller.text;
    final validationMessage = widget.validator?.call(value);
    if (validationMessage != null) {
      ScaffoldMessenger.of(widget.rootContext).showSnackBar(
        SnackBar(
          content: Text(validationMessage),
          backgroundColor: Theme.of(widget.rootContext).appColors.authError,
        ),
      );
      return;
    }

    setState(() {
      _isSubmitting = true;
    });

    try {
      await widget.onSubmit(value);
      if (!mounted || !context.mounted) return;
      Navigator.of(context).pop(true);
      if (widget.successMessage != null) {
        ScaffoldMessenger.of(widget.rootContext).showSnackBar(
          SnackBar(
            content: Text(widget.successMessage!),
            backgroundColor: Theme.of(widget.rootContext).colorScheme.primary,
          ),
        );
      }
    } catch (error) {
      AppLogger.warn(
        'DEBUG: Settings screen - failed to update ${widget.title}: $error',
      );
      AppLogger.debug('STACKTRACE: ${StackTrace.current}');
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
      });
      ScaffoldMessenger.of(widget.rootContext).showSnackBar(
        SnackBar(
          content: Text('Unable to update ${widget.title}.'),
          backgroundColor: Theme.of(widget.rootContext).appColors.authError,
        ),
      );
      return;
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.title),
      content: TextField(
        key: Key('user_settings_screen-${widget.keyPrefix}-text-field'),
        controller: _controller,
        decoration: const InputDecoration(labelText: 'Value'),
      ),
      actions: [
        TextButton(
          key: Key('user_settings_screen-${widget.keyPrefix}-cancel-button'),
          onPressed: () {
            FocusScope.of(context).unfocus();
            Navigator.of(context).pop();
          },
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          key: Key('user_settings_screen-${widget.keyPrefix}-submit-button'),
          onPressed: _isSubmitting ? null : _handleSubmit,
          child: _isSubmitting
              ? const SizedBox(
                  height: 16,
                  width: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Submit'),
        ),
      ],
    );
  }
}
