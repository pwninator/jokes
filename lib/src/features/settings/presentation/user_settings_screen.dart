import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_widget.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/settings/application/theme_settings_service.dart';

class UserSettingsScreen extends ConsumerWidget implements TitledScreen {
  const UserSettingsScreen({super.key});

  @override
  String get title => 'Settings';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentUser = ref.watch(currentUserProvider);
    final authController = ref.watch(authControllerProvider);

    return Scaffold(
      appBar: const AppBarWidget(title: 'Settings'),
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
                      Text(
                        'Theme Settings',
                        style: Theme.of(context).textTheme.headlineSmall,
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
                      Text(
                        'Notifications',
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 16),
                      _buildNotificationSettings(context, ref),
                    ],
                  ),
                ),
              ),
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
                          currentUser.isAnonymous ? 'Guest User' : 'Signed In',
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
                              () => _signInWithGoogle(context, authController),
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
    final subscriptionService = ref.watch(dailyJokeSubscriptionServiceProvider);
    
    return FutureBuilder<bool>(
      future: subscriptionService.isSubscribed(),
      builder: (context, snapshot) {
        final isSubscribed = snapshot.data ?? false;
        final isLoading = snapshot.connectionState == ConnectionState.waiting;

        return Column(
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
                if (isLoading)
                  const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                else
                  Switch(
                    value: isSubscribed,
                                         onChanged: (value) => _toggleNotifications(context, ref, value),
                    activeColor: Theme.of(context).colorScheme.primary,
                  ),
              ],
            ),
            const SizedBox(height: 16),
            // Test notification button
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                                 onPressed: () => _testNotification(context, ref),
                icon: const Icon(Icons.send),
                label: const Text('Test Notification'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Theme.of(context).colorScheme.primary,
                ),
              ),
            ),
          ],
        );
      },
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

  Future<void> _toggleNotifications(BuildContext context, WidgetRef ref, bool enable) async {
    final subscriptionService = ref.read(dailyJokeSubscriptionServiceProvider);
    
    try {
      bool success;
      if (enable) {
        success = await subscriptionService.subscribe();
      } else {
        success = await subscriptionService.unsubscribe();
      }

      if (context.mounted) {
        if (success) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                enable
                    ? 'Successfully subscribed to daily jokes!'
                    : 'Successfully unsubscribed from daily jokes',
              ),
              backgroundColor: Theme.of(context).appColors.success,
              duration: const Duration(seconds: 3),
            ),
          );
          // Widget will rebuild automatically when user returns to this screen
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                enable
                    ? 'Failed to subscribe to notifications'
                    : 'Failed to unsubscribe from notifications',
              ),
              backgroundColor: Theme.of(context).appColors.authError,
              duration: const Duration(seconds: 3),
            ),
          );
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

  Future<void> _testNotification(BuildContext context, WidgetRef ref) async {
    final subscriptionService = ref.read(dailyJokeSubscriptionServiceProvider);
    
    try {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('Sending test notification...'),
          backgroundColor: Theme.of(context).colorScheme.primary,
          duration: const Duration(seconds: 2),
        ),
      );

      final success = await subscriptionService.testDailyJoke();

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              success
                  ? 'Test notification sent! Check your notifications.'
                  : 'Failed to send test notification',
            ),
            backgroundColor:
                success
                    ? Theme.of(context).appColors.success
                    : Theme.of(context).appColors.authError,
            duration: const Duration(seconds: 4),
          ),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error sending test notification: $e'),
            backgroundColor: Theme.of(context).appColors.authError,
            duration: const Duration(seconds: 5),
          ),
        );
      }
    }
  }
}
