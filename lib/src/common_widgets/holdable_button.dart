import 'package:flutter/material.dart';

class HoldableButton extends StatefulWidget {
  final VoidCallback onTap;
  final VoidCallback onHoldComplete;
  final bool isEnabled;
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
  }

  @override
  void dispose() {
    _animationController.removeStatusListener(_onAnimationStatusChanged);
    _animationController.dispose();
    super.dispose();
  }

  void _onAnimationStatusChanged(AnimationStatus status) {
    if (status == AnimationStatus.completed && _isHolding) {
      // Animation completed while still holding - trigger hold action
      widget.onHoldComplete();
      _resetHold();
    }
  }

  void _onTapDown(TapDownDetails details) {
    if (!widget.isEnabled) return;

    setState(() {
      _isHolding = true;
    });
    _animationController.forward();
  }

  void _onTapUp(TapUpDetails details) {
    if (!widget.isEnabled) return;

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
    if (!widget.isEnabled) return;
    _resetHold();
  }

  void _resetHold() {
    setState(() {
      _isHolding = false;
    });
    _animationController.reset();
  }

  Color _getBaseColor() {
    final baseColor =
        widget.color ?? widget.theme.colorScheme.tertiaryContainer;
    if (!widget.isEnabled) {
      return baseColor.withValues(alpha: 0.5);
    }
    return baseColor.withValues(alpha: 0.8);
  }

  Color _getFillColor() {
    final baseColor =
        widget.color ?? widget.theme.colorScheme.tertiaryContainer;
    if (!widget.isEnabled) {
      return baseColor.withValues(alpha: 0.5);
    }
    return baseColor.withValues(alpha: 1.0);
  }

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
                    // Show spinner when disabled (processing)
                    if (!widget.isEnabled) {
                      return SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            widget.theme.colorScheme.onTertiaryContainer
                                .withValues(alpha: 0.6),
                          ),
                        ),
                      );
                    }

                    // Show appropriate icon based on animation state
                    return Icon(
                      _fillAnimation.value >= 1.0
                          ? (widget.holdCompleteIcon ?? Icons.refresh)
                          : widget.icon,
                      color: widget.theme.colorScheme.onTertiaryContainer,
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
