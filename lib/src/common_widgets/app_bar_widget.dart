import 'package:flutter/material.dart';

/// A custom AppBar widget that provides consistent styling across the app
/// while allowing for flexible customization when needed.
class AppBarWidget extends StatelessWidget implements PreferredSizeWidget {
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
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return AppBar(
      title: Text(title),
      leading: leading,
      actions: actions,
      backgroundColor: backgroundColor ?? theme.colorScheme.surface,
      foregroundColor: foregroundColor,
      elevation: elevation,
      centerTitle: centerTitle,
      automaticallyImplyLeading: automaticallyImplyLeading,
    );
  }

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);
}
