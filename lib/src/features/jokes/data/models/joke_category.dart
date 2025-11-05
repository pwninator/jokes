import 'package:flutter/material.dart';

/// Type of category behavior used by Discover tiles
enum CategoryType {
  /// Firestore-based category
  firestore,

  /// Programmatic category for most popular jokes
  popular,

  /// Programmatic daily jokes category using scheduled joke batches
  daily,
}

/// Joke category state values stored in Firestore as uppercase strings
enum JokeCategoryState {
  proposed('PROPOSED'),
  approved('APPROVED'),
  rejected('REJECTED');

  const JokeCategoryState(this.value);

  final String value;

  static JokeCategoryState? fromString(String? value) {
    if (value == null) return null;
    for (final s in JokeCategoryState.values) {
      if (s.value == value) return s;
    }
    return null;
  }
}

@immutable
class JokeCategory {
  static const String firestorePrefix = 'firestore:';

  final String id;
  final String displayName;
  final String?
  jokeDescriptionQuery; // When type == firestore and not seasonal, this must be non-empty
  final String? imageUrl;
  final String? imageDescription;
  final JokeCategoryState state;
  final CategoryType type;
  final String?
  seasonalValue; // When type == firestore and seasonal, this must be non-empty
  final Color? borderColor;

  const JokeCategory({
    required this.id,
    required this.displayName,
    this.jokeDescriptionQuery,
    this.imageUrl,
    this.imageDescription,
    this.state = JokeCategoryState.proposed,
    required this.type,
    this.seasonalValue,
    this.borderColor,
  });

  factory JokeCategory.fromMap(Map<String, dynamic> map, String id) {
    final displayName = (map['display_name'] as String?)?.trim() ?? '';
    final searchQuery = (map['joke_description_query'] as String?)?.trim();
    final seasonalName = (map['seasonal_name'] as String?)?.trim();
    final imageUrl = (map['image_url'] as String?)?.trim();
    final imageDescription = (map['image_description'] as String?)?.trim();
    final state =
        JokeCategoryState.fromString(map['state'] as String?) ??
        JokeCategoryState.proposed;

    final isSeasonal = seasonalName != null && seasonalName.isNotEmpty;

    return JokeCategory(
      id: '$firestorePrefix$id',
      displayName: displayName,
      jokeDescriptionQuery: isSeasonal ? null : searchQuery,
      imageUrl: imageUrl,
      imageDescription: imageDescription,
      state: state,
      type: CategoryType.firestore,
      seasonalValue: isSeasonal ? seasonalName : null,
    );
  }

  bool get isFirestoreCategory => id.startsWith(firestorePrefix);

  /// Returns the Firestore document id, without the prefix, for persistence.
  String get firestoreDocumentId {
    if (!isFirestoreCategory) {
      return id;
    }
    return id.substring(firestorePrefix.length);
  }
}
