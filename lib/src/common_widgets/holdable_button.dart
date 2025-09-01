import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:vibration/vibration.dart';

class HoldableButton extends StatefulWidget {
  final VoidCallback onTap;
  final VoidCallback onHoldComplete;
  final bool isEnabled;
  final bool isLoading;
  final ThemeData theme;
  final String? tooltip;
  final IconData icon;
  final IconData? holdCompleteIcon;
  final Duration holdDuration;
  final Color? color;

  const HoldableButton({
    super.key,
    required this.onTap,
    required this.onHoldComplete,
    required this.theme,
    required this.icon,
    this.isEnabled = true,
    this.isLoading = false,
    this.tooltip,
    this.holdCompleteIcon,
    this.holdDuration = const Duration(seconds: 2),
    this.color,
  });

  @override
  State<HoldableButton> createState() => _HoldableButtonState();
}

class _HoldableButtonState extends State<HoldableButton>
    with TickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _fillAnimation;
  bool _isHolding = false;
  bool? _hasVibrator;
  bool? _hasAmplitudeControl;
  Timer? _vibrationTimer;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: widget.holdDuration,
      vsync: this,
    );
    _fillAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.linear),
    );

    // Listen for animation completion
    _animationController.addStatusListener(_onAnimationStatusChanged);

    // Initialize vibration capabilities
    _initVibration();
  }

  Future<void> _initVibration() async {
    _hasVibrator = await Vibration.hasVibrator();
    _hasAmplitudeControl = await Vibration.hasAmplitudeControl();
  }

  @override
  void dispose() {
    _animationController.removeStatusListener(_onAnimationStatusChanged);
    _animationController.dispose();
    _vibrationTimer?.cancel();
    super.dispose();
  }

  void _onAnimationStatusChanged(AnimationStatus status) {
    if (status == AnimationStatus.completed && _isHolding) {
      // Animation completed while still holding - trigger hold action
      _triggerFinalVibration();
      widget.onHoldComplete();
      _resetHold();
    }
  }

  void _startVibration() {
    if (_hasVibrator != true) return;

    // Start continuous vibration with increasing intensity
    _vibrationTimer = Timer.periodic(const Duration(milliseconds: 50), (timer) {
      if (!_isHolding) {
        timer.cancel();
        return;
      }

      final progress = _fillAnimation.value;
      if (_hasAmplitudeControl == true) {
        // Android: Use amplitude control for smooth intensity ramp
        final amplitude = (progress * 255).toInt().clamp(1, 255);
        Vibration.vibrate(duration: 50, amplitude: amplitude);
      } else {
        // iOS or fallback: Use haptic feedback patterns
        _triggerHapticFeedback(progress);
      }
    });
  }

  void _stopVibration() {
    _vibrationTimer?.cancel();
    _vibrationTimer = null;
  }

  void _triggerHapticFeedback(double progress) {
    // Note: iOS haptic feedback doesn't have direct amplitude control
    // We use timing and pattern selection instead
    if (progress < 0.3) {
      // Light feedback at start - subtle indication
      HapticFeedback.lightImpact();
    } else if (progress < 0.7) {
      // Medium feedback in middle - building intensity
      HapticFeedback.mediumImpact();
    } else {
      // Stronger feedback near end - clear escalation
      HapticFeedback.heavyImpact();
    }
  }

  void _triggerFinalVibration() {
    if (_hasVibrator != true) return;

    if (_hasAmplitudeControl == true) {
      // Android: Strong final vibration
      Vibration.vibrate(duration: 100, amplitude: 255);
    } else {
      // iOS: Use system vibration
      Vibration.vibrate(duration: 200);
    }
  }

  void _onTapDown(TapDownDetails details) {
    final blocked = _isBlocked;
    if (blocked) return;

    setState(() {
      _isHolding = true;
    });
    _animationController.forward();
    _startVibration();
  }

  void _onTapUp(TapUpDetails details) {
    final blocked = _isBlocked;
    if (blocked) return;

    _stopVibration();

    if (_animationController.isCompleted) {
      // Already completed - do nothing (onHoldComplete already called)
      _resetHold();
    } else if (_animationController.value > 0.0) {
      // Released after holding started - just reset, don't trigger tap
      _resetHold();
    } else {
      // Quick tap without holding - treat as normal tap
      widget.onTap();
      _resetHold();
    }
  }

  void _onTapCancel() {
    final blocked = _isBlocked;
    if (blocked) return;
    _stopVibration();
    _resetHold();
  }

  void _resetHold() {
    setState(() {
      _isHolding = false;
    });
    _animationController.reset();
  }

  Color _getBaseColor() {
    final disabled = _isDisabled;
    final loading = widget.isLoading;
    if (disabled) {
      return widget.theme.disabledColor;
    }
    final baseColor =
        widget.color ?? widget.theme.colorScheme.tertiaryContainer;
    if (loading) {
      return baseColor.withValues(alpha: 0.5);
    }
    return baseColor.withValues(alpha: 0.8);
  }

  Color _getFillColor() {
    final disabled = _isDisabled;
    final loading = widget.isLoading;
    if (disabled) {
      return widget.theme.disabledColor;
    }
    final baseColor =
        widget.color ?? widget.theme.colorScheme.tertiaryContainer;
    if (loading) {
      return baseColor.withValues(alpha: 0.8);
    }
    return baseColor.withValues(alpha: 1.0);
  }

  bool get _isDisabled => !widget.isEnabled;
  bool get _isBlocked => _isDisabled || widget.isLoading;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: _onTapDown,
      onTapUp: _onTapUp,
      onTapCancel: _onTapCancel,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(
          20,
        ), // Apply curved border to outer container
        child: SizedBox(
          width: 40, // Default width when not expanded
          height: 40, // Match ElevatedButton height
          child: Stack(
            children: [
              // Base button (rectangular, no border radius, no icon)
              Container(
                width: double.infinity,
                height: 40,
                color: _getBaseColor(),
              ),

              // Animated fill overlay (fills from bottom to top, no icon)
              AnimatedBuilder(
                animation: _fillAnimation,
                builder: (context, child) {
                  return Align(
                    alignment: Alignment.bottomCenter,
                    child: Container(
                      width: double.infinity,
                      height:
                          40 *
                          _fillAnimation.value, // Height grows from 0 to 40
                      color: _getFillColor(),
                    ),
                  );
                },
              ),

              // Icon hovering above everything
              Center(
                child: AnimatedBuilder(
                  animation: _fillAnimation,
                  builder: (context, child) {
                    // Show spinner when loading (optionally greyed if also disabled)
                    if (widget.isLoading) {
                      final spinnerColor = _isDisabled
                          ? widget.theme.disabledColor
                          : widget.theme.colorScheme.onTertiaryContainer
                                .withValues(alpha: 0.6);
                      return SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            spinnerColor,
                          ),
                        ),
                      );
                    }

                    // Show appropriate icon based on animation state
                    return Icon(
                      _fillAnimation.value >= 1.0
                          ? (widget.holdCompleteIcon ?? Icons.refresh)
                          : widget.icon,
                      color: _isDisabled
                          ? widget.theme.disabledColor
                          : widget.theme.colorScheme.onTertiaryContainer,
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
