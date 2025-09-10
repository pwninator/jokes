import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/feedback_dialog.dart';
import 'package:snickerdoodle/src/common_widgets/notification_hour_widget.dart';
import 'package:snickerdoodle/src/common_widgets/subscription_prompt_dialog.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/app_version_provider.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
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

  void _handleSecretTap(String tapType) {
    final now = DateTime.now();

    // Reset sequence if more than 2 seconds passed since last tap
    if (_lastTap != null && now.difference(_lastTap!).inSeconds > 2) {
      debugPrint('DEBUG: Settings screen - sequence reset due to timeout');
      _tapSequence.clear();
    }

    debugPrint('DEBUG: Settings screen - adding tap: $tapType');
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
      debugPrint('DEBUG: Settings screen - sequence invalid');
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

  @override
  Widget build(BuildContext context) {
    final currentUser = ref.watch(currentUserProvider);
    final authController = ref.watch(authControllerProvider);

    return AdaptiveAppBarScreen(
      title: 'Settings',
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Theme Settings Section
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      GestureDetector(
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
              const SizedBox(height: 16),

              // Notification Settings Section
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      GestureDetector(
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

              // Suggestions/Feedback button
              const SizedBox(height: 16),
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
                  onPressed: () {
                    showDialog<bool>(
                      context: context,
                      builder: (context) => const FeedbackDialog(),
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
                        FutureBuilder<_UsageMetrics>(
                          future: _fetchUsageMetrics(ref),
                          builder: (context, snapshot) {
                            if (snapshot.connectionState ==
                                ConnectionState.waiting) {
                              return const SizedBox.shrink();
                            }
                            if (!snapshot.hasData) {
                              return const SizedBox.shrink();
                            }
                            final metrics = snapshot.data!;
                            final first = metrics.firstUsedDate ?? '—';
                            final last = metrics.lastUsedDate ?? '—';
                            final days = metrics.numDaysUsed;
                            final summary = '$first - $last ($days)';
                            return Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                _buildInfoRow('Usage', summary),
                                _buildInfoRow(
                                  'Num Jokes Viewed',
                                  metrics.numJokesViewed.toString(),
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
                          ElevatedButton.icon(
                            onPressed: () =>
                                _signInWithGoogle(context, authController),
                            icon: const Icon(Icons.login),
                            label: const Text('Sign in with Google'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Theme.of(
                                context,
                              ).appColors.googleBlue,
                              foregroundColor: Colors.white,
                            ),
                          ),
                        ] else ...[
                          // Show sign out option for authenticated users
                          ElevatedButton.icon(
                            onPressed: () =>
                                _confirmSignOut(context, authController),
                            icon: const Icon(Icons.logout),
                            label: const Text('Switch to Guest Mode'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Theme.of(
                                context,
                              ).appColors.authError,
                              foregroundColor: Colors.white,
                            ),
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

                        ElevatedButton.icon(
                          onPressed: () => _testSubscribePrompt(context),
                          icon: const Icon(Icons.notifications),
                          label: const Text('Test Subscribe Prompt'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Theme.of(
                              context,
                            ).colorScheme.tertiary,
                            foregroundColor: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 12),
                        ElevatedButton.icon(
                          key: const Key('settings-review-button'),
                          onPressed: () => _testReviewPrompt(context),
                          icon: const Icon(Icons.rate_review),
                          label: const Text('Test Review Prompt'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Theme.of(
                              context,
                            ).colorScheme.secondary,
                            foregroundColor: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 12),
                        ElevatedButton.icon(
                          key: const Key('settings-remote-config-button'),
                          onPressed: () => _showRemoteConfigDialog(context),
                          icon: const Icon(Icons.tune),
                          label: const Text('See Remote Config'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Theme.of(
                              context,
                            ).colorScheme.primaryContainer,
                            foregroundColor: Theme.of(
                              context,
                            ).colorScheme.onPrimaryContainer,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 16),

              // Version text (for secret sequence)
              Center(
                child: GestureDetector(
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
                          style: TextStyle(
                            fontSize: 12,
                            color: Theme.of(
                              context,
                            ).colorScheme.onSurface.withValues(alpha: 0.6),
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

    return Column(
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
                    style: TextStyle(
                      fontWeight: FontWeight.w500,
                      color: isSubscribed
                          ? Theme.of(context).colorScheme.primary
                          : Theme.of(context).colorScheme.onSurface,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    isSubscribed
                        ? 'Receive daily joke notifications'
                        : 'Get notified when new jokes are available',
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(
                        context,
                      ).colorScheme.onSurface.withValues(alpha: 0.6),
                    ),
                  ),
                ],
              ),
            ),
            Switch(
              value: isSubscribed,
              onChanged: (value) => _toggleNotifications(context, ref, value),
              activeColor: Theme.of(context).colorScheme.primary,
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

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 4.0),
        child: Row(
          children: [
            Icon(
              icon,
              color: isSelected
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
                    title,
                    style: TextStyle(
                      fontWeight: FontWeight.w500,
                      color: isSelected
                          ? Theme.of(context).colorScheme.primary
                          : Theme.of(context).colorScheme.onSurface,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(
                        context,
                      ).colorScheme.onSurface.withValues(alpha: 0.6),
                    ),
                  ),
                ],
              ),
            ),
            Radio<ThemeMode>(
              value: themeMode,
              groupValue: currentThemeMode,
              onChanged: (value) => onTap(),
              activeColor: Theme.of(context).colorScheme.primary,
            ),
          ],
        ),
      ),
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
    final firstUsed = await usage.getFirstUsedDate();
    final lastUsed = await usage.getLastUsedDate();
    final daysUsed = await usage.getNumDaysUsed();
    final jokesViewed = await usage.getNumJokesViewed();
    return _UsageMetrics(
      firstUsedDate: firstUsed,
      lastUsedDate: lastUsed,
      numDaysUsed: daysUsed,
      numJokesViewed: jokesViewed,
    );
  }

  Future<void> _signInWithGoogle(
    BuildContext context,
    AuthController authController,
  ) async {
    try {
      debugPrint('DEBUG: Settings screen - starting Google sign-in...');
      await authController.signInWithGoogle();
      debugPrint(
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
      debugPrint('DEBUG: Settings screen - Google sign-in failed: $e');
      // Log analytics/crash for sign-in failure
      try {
        final analytics = ref.read(analyticsServiceProvider);
        await analytics.logErrorAuthSignIn(
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
                debugPrint('ERROR DETAILS: $e');
                // Show dialog with full error
                showDialog(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Sign-in Error'),
                    content: SingleChildScrollView(child: Text(e.toString())),
                    actions: [
                      TextButton(
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
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
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

      // Track analytics for subscription toggle
      final analyticsService = ref.read(analyticsServiceProvider);
      if (success) {
        if (enable) {
          await analyticsService.logSubscriptionOnSettings();
        } else {
          await analyticsService.logSubscriptionOffSettings();
        }
      } else if (enable) {
        // Track failed subscription attempt
        await analyticsService.logSubscriptionDeclinedPermissionsInSettings();
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
      debugPrint('ERROR: _toggleNotifications: $e');
      // Log analytics/crash for notification toggle failure
      try {
        final analytics = ref.read(analyticsServiceProvider);
        await analytics.logErrorSubscriptionToggle(
          source: 'user_settings_screen',
          errorMessage: 'notifications_toggle_failed',
        );
      } catch (_) {}
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
    final response = await reviewService.requestReview(
      source: ReviewRequestSource.adminTest,
      force: true,
    );

    if (!context.mounted) return;

    String message;
    Color bg = Theme.of(context).colorScheme.primary;
    switch (response.result) {
      case ReviewRequestResult.shown:
        message = 'Review prompt shown (if allowed by the OS).';
        break;
      case ReviewRequestResult.notAvailable:
        message = 'In-app review not available on this device.';
        bg = Theme.of(context).colorScheme.secondary;
        break;
      case ReviewRequestResult.throttledOrNoop:
        message = 'Review prompt throttled (no UI shown).';
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
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
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
                }
                return _buildInfoRow(label, valueString);
              }),
            ],
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
  final int numJokesViewed;

  const _UsageMetrics({
    required this.firstUsedDate,
    required this.lastUsedDate,
    required this.numDaysUsed,
    required this.numJokesViewed,
  });
}
