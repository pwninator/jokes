import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/subscription_prompt_dialog.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/core/providers/app_version_provider.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
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
                            onPressed:
                                () =>
                                    _signInWithGoogle(context, authController),
                            icon: const Icon(Icons.login),
                            label: const Text('Sign in with Google'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor:
                                  Theme.of(context).appColors.googleBlue,
                              foregroundColor: Colors.white,
                            ),
                          ),
                        ] else ...[
                          // Show sign out option for authenticated users
                          ElevatedButton.icon(
                            onPressed:
                                () => _confirmSignOut(context, authController),
                            icon: const Icon(Icons.logout),
                            label: const Text('Switch to Guest Mode'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor:
                                  Theme.of(context).appColors.authError,
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
                            backgroundColor:
                                Theme.of(context).colorScheme.tertiary,
                            foregroundColor: Colors.white,
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
                  child: Padding(
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
    // Initialize subscription status on first build
    ref.read(subscriptionRefreshProvider);

    final subscriptionState = ref.watch(subscriptionStatusProvider);

    return subscriptionState.when(
      data:
          (isSubscribed) => Column(
            children: [
              Row(
                children: [
                  Icon(
                    Icons.notifications,
                    color:
                        isSubscribed
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
                            color:
                                isSubscribed
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
                    onChanged:
                        (value) => _toggleNotifications(context, ref, value),
                    activeColor: Theme.of(context).colorScheme.primary,
                  ),
                ],
              ),
            ],
          ),
      loading:
          () => Column(
            children: [
              Row(
                children: [
                  Icon(
                    Icons.notifications,
                    color: Theme.of(
                      context,
                    ).colorScheme.onSurface.withValues(alpha: 0.6),
                  ),
                  const SizedBox(width: 16),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Daily Joke Notifications',
                          style: TextStyle(fontWeight: FontWeight.w500),
                        ),
                        SizedBox(height: 2),
                        Text(
                          'Loading notification settings...',
                          style: TextStyle(fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ],
              ),
            ],
          ),
      error:
          (error, stackTrace) => Column(
            children: [
              Row(
                children: [
                  Icon(Icons.error, color: Theme.of(context).colorScheme.error),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Notification Settings',
                          style: TextStyle(
                            fontWeight: FontWeight.w500,
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'Error loading settings: ${error.toString()}',
                          style: TextStyle(
                            fontSize: 12,
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
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
              color:
                  isSelected
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
                      color:
                          isSelected
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
                  builder:
                      (context) => AlertDialog(
                        title: const Text('Sign-in Error'),
                        content: SingleChildScrollView(
                          child: Text(e.toString()),
                        ),
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
      builder:
          (context) => AlertDialog(
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
                          backgroundColor:
                              Theme.of(context).appColors.authError,
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
    final subscriptionService = ref.read(dailyJokeSubscriptionServiceProvider);
    final statusNotifier = ref.read(subscriptionStatusProvider.notifier);

    try {
      bool success;
      if (enable) {
        // Subscribe with notification permission
        success =
            await subscriptionService.subscribeWithNotificationPermission();
      } else {
        // Unsubscribe (no permission needed)
        success = await subscriptionService.unsubscribe();
      }

      // Update UI state based on the operation result
      if (success) {
        statusNotifier.state = AsyncValue.data(enable);

        // Show success message
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                enable
                    ? 'Successfully subscribed to daily jokes! 🎉'
                    : 'Successfully unsubscribed from daily jokes',
              ),
              backgroundColor: Theme.of(context).colorScheme.primary,
              duration: const Duration(seconds: 3),
            ),
          );
        }
      } else {
        // Operation failed
        if (enable) {
          // Subscription failed (likely permission denied)
          statusNotifier.state = AsyncValue.data(false); // Keep toggle off
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
        } else {
          // Unsubscription failed
          statusNotifier.state = AsyncValue.data(true); // Keep toggle on
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: const Text('Failed to unsubscribe. Please try again.'),
                backgroundColor: Theme.of(context).appColors.authError,
                duration: const Duration(seconds: 3),
              ),
            );
          }
        }
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error updating notification settings: $e'),
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
}
