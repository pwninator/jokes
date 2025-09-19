import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/feedback_notification_icon.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';

/// A custom AppBar widget that provides consistent styling across the app
/// while allowing for flexible customization when needed.
class AppBarWidget extends ConsumerWidget implements PreferredSizeWidget {
  const AppBarWidget({
    super.key,
    required this.title,
    this.leading,
    this.actions,
    this.backgroundColor,
    this.foregroundColor,
    this.elevation,
    this.centerTitle = true,
    this.automaticallyImplyLeading = true,
  });

  /// The title to display in the AppBar
  final String title;

  /// Optional leading widget (back button, drawer button, etc.)
  final Widget? leading;

  /// Optional list of action widgets
  final List<Widget>? actions;

  /// Background color of the AppBar. Defaults to theme's inversePrimary
  final Color? backgroundColor;

  /// Foreground color (text and icons). Defaults to theme's onSurface
  final Color? foregroundColor;

  /// Elevation of the AppBar. Defaults to null (uses theme default)
  final double? elevation;

  /// Whether to center the title. Defaults to null (uses theme default)
  final bool? centerTitle;

  /// Whether to automatically imply leading widget
  final bool automaticallyImplyLeading;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final unreadFeedback = ref.watch(unreadFeedbackProvider);

    final allActions = <Widget>[
      ...?actions,
      if (unreadFeedback.isNotEmpty)
        const FeedbackNotificationIcon(key: Key('feedback-notification-icon')),
    ];

    return AppBar(
      title: Text(title),
      leading: leading,
      actions: allActions,
      backgroundColor: backgroundColor ?? theme.colorScheme.surface,
      foregroundColor: foregroundColor,
      elevation: elevation ?? 0,
      centerTitle: centerTitle,
      automaticallyImplyLeading: automaticallyImplyLeading,
      scrolledUnderElevation: 0,
    );
  }

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);
}
