import 'package:flutter/material.dart';

class BadgedIcon extends StatelessWidget {
  const BadgedIcon({
    super.key,
    required this.icon,
    this.iconColor,
    this.iconSize,
    required this.iconSemanticLabel,
    required this.showBadge,
    this.badgeColor,
    required this.badgeSemanticLabel,
  });

  final IconData icon;
  final bool showBadge;
  final Color? badgeColor;
  final String badgeSemanticLabel;
  final Color? iconColor;
  final String iconSemanticLabel;
  final double? iconSize;

  @override
  Widget build(BuildContext context) {
    final Color resolvedBadgeColor =
        badgeColor ?? Theme.of(context).colorScheme.error;

    return Stack(
      clipBehavior: Clip.none,
      children: [
        Icon(
          icon,
          color: iconColor,
          semanticLabel: iconSemanticLabel,
          size: iconSize,
        ),
        if (showBadge)
          Positioned(
            right: -3,
            top: -3,
            child: Semantics(
              label: badgeSemanticLabel,
              container: true,
              child: Container(
                width: 10,
                height: 10,
                decoration: BoxDecoration(
                  color: resolvedBadgeColor,
                  borderRadius: BorderRadius.circular(6),
                ),
              ),
            ),
          ),
      ],
    );
  }
}
