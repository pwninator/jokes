import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';

/// A screen wrapper that provides AppBar configuration to the ShellRoute.
/// The ShellRoute reads [appBarConfigProvider] to construct the actual AppBar.
class AppBarConfiguredScreen extends ConsumerStatefulWidget {
  const AppBarConfiguredScreen({
    super.key,
    required this.title,
    required this.body,
    this.leading,
    this.actions,
    this.automaticallyImplyLeading = true,
    this.floatingActionButton,
  });

  final String title;
  final Widget body;
  final Widget? leading;
  final List<Widget>? actions;
  final bool automaticallyImplyLeading;
  final Widget? floatingActionButton;

  @override
  ConsumerState<AppBarConfiguredScreen> createState() =>
      _AppBarConfiguredScreenState();
}

class _AppBarConfiguredScreenState
    extends ConsumerState<AppBarConfiguredScreen> {
  void _applyConfig() {
    Widget? resolvedLeading = widget.leading;

    if (resolvedLeading == null && widget.automaticallyImplyLeading) {
      final goRouter = GoRouter.maybeOf(context);
      VoidCallback? onBackPressed;

      bool canPopViaGoRouter = false;
      if (goRouter != null) {
        try {
          canPopViaGoRouter = goRouter.canPop();
        } catch (_) {
          canPopViaGoRouter = false;
        }
      }

      if (canPopViaGoRouter && goRouter != null) {
        onBackPressed = goRouter.pop;
      } else {
        final navigator = Navigator.maybeOf(context);
        if (navigator != null && navigator.canPop()) {
          onBackPressed = () => navigator.pop();
        }
      }

      if (onBackPressed != null) {
        resolvedLeading = IconButton(
          key: const Key('app_bar_configured_screen-back-button'),
          icon: const Icon(Icons.arrow_back),
          onPressed: onBackPressed,
        );
      }
    }

    ref.read(appBarConfigProvider.notifier).state = AppBarConfigData(
      title: widget.title,
      leading: resolvedLeading,
      actions: widget.actions,
      automaticallyImplyLeading: widget.automaticallyImplyLeading,
    );
    ref.read(floatingActionButtonProvider.notifier).state =
        widget.floatingActionButton;
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _applyConfig();
    });
  }

  @override
  void didUpdateWidget(covariant AppBarConfiguredScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.title != widget.title ||
        oldWidget.leading != widget.leading ||
        oldWidget.actions != widget.actions ||
        oldWidget.automaticallyImplyLeading !=
            widget.automaticallyImplyLeading ||
        oldWidget.floatingActionButton != widget.floatingActionButton) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        _applyConfig();
      });
    }
  }

  @override
  void dispose() {
    // Do not read providers here; the next screen will override config as needed.
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return widget.body;
  }
}
