import 'package:flutter/material.dart';

/// Type of category behavior used by Discover tiles
enum CategoryType {
  /// Search-based category using cloud function search
  search,

  /// Firestore-based category for most popular jokes
  popular,

  /// Firestore-based category filtered by a seasonal field
  seasonal,

  /// Composite feed that stitches together multiple sources (e.g., All jokes)
  composite,

  /// Daily jokes category using scheduled joke batches
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
  jokeDescriptionQuery; // When type == search, this must be non-empty
  final String? imageUrl;
  final String? imageDescription;
  final JokeCategoryState state;
  final CategoryType type;
  final String? seasonalValue; // When type == seasonal, this must be non-empty
  final Color? borderColor;

  JokeCategory({
    required this.id,
    required this.displayName,
    this.jokeDescriptionQuery,
    this.imageUrl,
    this.imageDescription,
    this.state = JokeCategoryState.proposed,
    required this.type,
    this.seasonalValue,
    this.borderColor,
  }) : // Search-specific validation
       assert(
         type != CategoryType.search ||
             (jokeDescriptionQuery != null &&
                 jokeDescriptionQuery.trim().isNotEmpty),
         'For search, provide non-empty jokeDescriptionQuery.',
       ),
       // Seasonal-specific validation: no search query allowed
       assert(
         type != CategoryType.seasonal ||
             (jokeDescriptionQuery == null ||
                 jokeDescriptionQuery.trim().isEmpty),
         'For seasonal, do not provide jokeDescriptionQuery.',
       ),
       // Seasonal-specific validation: require non-empty seasonalValue
       assert(
         type != CategoryType.seasonal ||
             (seasonalValue != null && seasonalValue.trim().isNotEmpty),
         'For seasonal, provide non-empty seasonalValue.',
       ),
       // Other types: must not provide search query
       assert(
         type == CategoryType.search ||
             type == CategoryType.seasonal ||
             (jokeDescriptionQuery == null ||
                 jokeDescriptionQuery.trim().isEmpty),
         'For non-search, non-seasonal types, jokeDescriptionQuery must be null/empty.',
       );

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
      type: isSeasonal ? CategoryType.seasonal : CategoryType.search,
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
