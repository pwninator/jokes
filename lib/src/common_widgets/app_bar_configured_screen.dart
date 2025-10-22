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
  Listenable? _routerListenable;
  bool _applyScheduled = false;

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

  void _scheduleApply() {
    if (!mounted || _applyScheduled) return;
    _applyScheduled = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _applyScheduled = false;
      if (!mounted) return;
      final route = ModalRoute.of(context);
      if (route == null || route.isCurrent) {
        _applyConfig();
      }
    });
  }

  void _handleRouterChange() {
    _scheduleApply();
  }

  void _subscribeRouter() {
    final router = GoRouter.maybeOf(context);
    Listenable? nextListenable;
    if (router != null) {
      try {
        nextListenable = router.routerDelegate;
      } catch (_) {
        nextListenable = null;
      }
    }
    if (nextListenable == _routerListenable) return;
    _routerListenable?.removeListener(_handleRouterChange);
    _routerListenable = nextListenable;
    _routerListenable?.addListener(_handleRouterChange);
  }

  @override
  void initState() {
    super.initState();
    _scheduleApply();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _subscribeRouter();
    _scheduleApply();
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
      _scheduleApply();
    }
  }

  @override
  void dispose() {
    _routerListenable?.removeListener(_handleRouterChange);
    _routerListenable = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return widget.body;
  }
}
