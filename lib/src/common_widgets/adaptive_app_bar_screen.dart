import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_widget.dart';

/// A base screen widget that adapts its app bar based on orientation.
/// In portrait mode, shows a normal app bar with the provided title.
/// In landscape mode, shows an empty app bar with 8px height for consistent spacing.
class AdaptiveAppBarScreen extends StatelessWidget {
  const AdaptiveAppBarScreen({
    super.key,
    required this.title,
    required this.body,
    this.floatingActionButton,
  });

  /// The title to display in the app bar when in portrait mode
  final String title;

  /// The body content of the screen
  final Widget body;

  /// Optional floating action button
  final Widget? floatingActionButton;

  @override
  Widget build(BuildContext context) {
    final isLandscape =
        MediaQuery.of(context).orientation == Orientation.landscape;

    return Scaffold(
      appBar:
          isLandscape
              ? PreferredSize(
                preferredSize: const Size.fromHeight(8.0),
                child: AppBar(
                  backgroundColor: Theme.of(context).colorScheme.surface,
                  elevation: 0,
                  automaticallyImplyLeading: false,
                  scrolledUnderElevation: 0,
                ),
              )
              : AppBarWidget(title: title),
      body: body,
      floatingActionButton: floatingActionButton,
    );
  }
}
