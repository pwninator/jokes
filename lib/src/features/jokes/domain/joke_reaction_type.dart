import 'package:flutter/material.dart';

enum JokeReactionType {
  save('num_saves', Icons.favorite, Icons.favorite_border, Colors.red),
  share('num_shares', Icons.share, Icons.share_outlined, Colors.blue);

  const JokeReactionType(
    this.firestoreField,
    this.activeIcon,
    this.inactiveIcon,
    this.activeColor,
  );

  /// The Firestore field name for this reaction count
  final String firestoreField;

  /// Icon to show when reaction is active/selected
  final IconData activeIcon;

  /// Icon to show when reaction is inactive/not selected
  final IconData inactiveIcon;

  /// Color to use when reaction is active
  final Color activeColor;

  /// SharedPreferences key for storing this reaction type
  String get prefsKey => 'user_reactions_$name';

  /// Human-readable label for this reaction type
  String get label {
    switch (this) {
      case JokeReactionType.save:
        return 'Save';
      case JokeReactionType.share:
        return 'Share';
    }
  }
}
