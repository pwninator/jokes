import 'package:flutter/material.dart';

/// ElevatedButton wrapper that plays a squash-and-bounce animation with
/// coordinated elevation changes whenever the button is pressed.
class BouncingButton extends StatefulWidget {
  const BouncingButton({
    super.key,
    required this.buttonKey,
    required this.isPositive,
    required this.child,
    this.icon,
    this.onPressed,
    this.style,
    this.focusNode,
    this.autofocus = false,
    this.clipBehavior = Clip.none,
    this.totalDuration = const Duration(milliseconds: 300),
    this.squishScale = 0.97,
    this.overshootScale = 1.02,
    this.baseElevation = 2.0,
    this.squishElevation = 1.0,
    this.overshootElevation = 2.2,
  }) : assert(squishScale > 0 && overshootScale > 0),
       assert(squishElevation >= 0);

  final Key buttonKey;
  final Widget child;
  final Widget? icon;
  final bool isPositive;
  final VoidCallback? onPressed;
  final ButtonStyle? style;
  final FocusNode? focusNode;
  final bool autofocus;
  final Clip clipBehavior;
  final Duration totalDuration;
  final double squishScale;
  final double overshootScale;
  final double baseElevation;
  final double squishElevation;
  final double overshootElevation;

  @override
  State<BouncingButton> createState() => _BouncingButtonState();
}

class _BouncingButtonState extends State<BouncingButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late Animation<double> _scaleAnimation;
  late Animation<double> _elevationAnimation;
  bool _animationsConfigured = false;

  static const double _squishProgress = 0.4;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: widget.totalDuration,
      vsync: this,
    );
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _configureAnimation();
  }

  @override
  void didUpdateWidget(covariant BouncingButton oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.totalDuration != widget.totalDuration) {
      _controller.duration = widget.totalDuration;
    }
    _configureAnimation();
    if (widget.onPressed == null && _controller.isAnimating) {
      _controller.stop();
      _controller.reset();
    }
  }

  void _configureAnimation() {
    _scaleAnimation = _buildAnimation(
      1.0,
      widget.squishScale,
      widget.overshootScale,
      _controller,
    );

    _elevationAnimation = _buildAnimation(
      widget.baseElevation,
      widget.squishElevation,
      widget.overshootElevation,
      _controller,
    );

    _animationsConfigured = true;
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  bool get _isEnabled => widget.onPressed != null;

  Duration _durationForRange(double from, double to) {
    final double distance = (to - from).abs().clamp(0.0, 1.0);
    if (distance == 0.0) {
      return Duration.zero;
    }
    int micros = (widget.totalDuration.inMicroseconds * distance).round();
    if (micros == 0) {
      micros = 1;
    }
    return Duration(microseconds: micros);
  }

  void _animateTo(double target) {
    if (!_isEnabled) return;
    final double clampedTarget = target.clamp(0.0, 1.0);
    _controller.animateTo(
      clampedTarget,
      duration: _durationForRange(_controller.value, clampedTarget),
      curve: Curves.easeOut,
    );
  }

  void _handlePointerDown(PointerDownEvent event) {
    if (!_isEnabled) return;
    _controller.stop();
    _controller.value = 0.0;
    _animateTo(_squishProgress);
  }

  void _handlePointerUp(PointerUpEvent event) {
    if (!_isEnabled) return;
    _animateTo(1.0);
  }

  void _handlePointerCancel(PointerCancelEvent event) {
    if (!_isEnabled) return;
    _controller.animateBack(
      0.0,
      duration: _durationForRange(_controller.value, 0.0),
      curve: Curves.easeOut,
    );
  }

  void _handlePressed() {
    final VoidCallback? handler = widget.onPressed;
    if (handler == null) {
      return;
    }
    handler();
  }

  @override
  Widget build(BuildContext context) {
    if (!_animationsConfigured) {
      _configureAnimation();
    }

    final bool enabled = _isEnabled;
    final Animation<double> scaleAnimation = enabled
        ? _scaleAnimation
        : const AlwaysStoppedAnimation<double>(1.0);
    final Animation<double> elevationAnimation = enabled
        ? _elevationAnimation
        : AlwaysStoppedAnimation<double>(widget.baseElevation);

    final colorScheme = Theme.of(context).colorScheme;

    return Listener(
      onPointerDown: _handlePointerDown,
      onPointerUp: _handlePointerUp,
      onPointerCancel: _handlePointerCancel,
      behavior: HitTestBehavior.translucent,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, child) {
          final ButtonStyle dynamicStyle = ButtonStyle(
            elevation: WidgetStateProperty.resolveWith((states) {
              if (states.contains(WidgetState.disabled)) {
                return 0.0;
              }
              return elevationAnimation.value;
            }),
            backgroundColor: WidgetStateProperty.resolveWith((states) {
              if (states.contains(WidgetState.disabled)) {
                return colorScheme.surfaceDim;
              }
              return widget.isPositive
                  ? colorScheme.primaryContainer
                  : colorScheme.secondaryContainer;
              ;
            }),
            foregroundColor: WidgetStateProperty.resolveWith((states) {
              if (states.contains(WidgetState.disabled)) {
                return colorScheme.onPrimaryContainer.withValues(alpha: 0.5);
              }
              return widget.isPositive
                  ? colorScheme.onPrimaryContainer
                  : colorScheme.onSecondaryContainer;
              ;
            }),
            animationDuration: Duration.zero,
          );
          final ButtonStyle mergedStyle = (widget.style ?? const ButtonStyle())
              .merge(dynamicStyle);
          final button = widget.icon != null
              ? ElevatedButton.icon(
                  key: widget.buttonKey,
                  style: mergedStyle,
                  focusNode: widget.focusNode,
                  autofocus: widget.autofocus,
                  clipBehavior: widget.clipBehavior,
                  onPressed: enabled ? _handlePressed : null,
                  icon: widget.icon!,
                  label: widget.child,
                )
              : ElevatedButton(
                  key: widget.buttonKey,
                  style: mergedStyle,
                  focusNode: widget.focusNode,
                  autofocus: widget.autofocus,
                  clipBehavior: widget.clipBehavior,
                  onPressed: enabled ? _handlePressed : null,
                  child: widget.child,
                );
          return ScaleTransition(scale: scaleAnimation, child: button);
        },
      ),
    );
  }
}

Animation<double> _buildAnimation(
  double baseValue,
  double squishValue,
  double overshootValue,
  AnimationController controller,
) {
  return TweenSequence<double>([
    TweenSequenceItem(
      tween: Tween<double>(
        begin: baseValue,
        end: squishValue,
      ).chain(CurveTween(curve: Curves.easeOut)),
      weight: 40,
    ),
    TweenSequenceItem(
      tween: Tween<double>(
        begin: squishValue,
        end: overshootValue,
      ).chain(CurveTween(curve: Curves.easeIn)),
      weight: 40,
    ),
    TweenSequenceItem(
      tween: Tween<double>(
        begin: overshootValue,
        end: baseValue,
      ).chain(CurveTween(curve: Curves.easeOut)),
      weight: 20,
    ),
  ]).animate(controller);
}
