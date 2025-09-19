import 'package:flutter/foundation.dart';

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
  final String id;
  final String displayName;
  final String jokeDescriptionQuery;
  final String? imageUrl;
  final String? imageDescription;
  final JokeCategoryState state;

  const JokeCategory({
    required this.id,
    required this.displayName,
    required this.jokeDescriptionQuery,
    this.imageUrl,
    this.imageDescription,
    this.state = JokeCategoryState.proposed,
  });

  factory JokeCategory.fromMap(Map<String, dynamic> map, String id) {
    return JokeCategory(
      id: id,
      displayName: (map['display_name'] as String?)?.trim() ?? '',
      jokeDescriptionQuery:
          (map['joke_description_query'] as String?)?.trim() ?? '',
      imageUrl: (map['image_url'] as String?)?.trim(),
      imageDescription: (map['image_description'] as String?)?.trim(),
      state:
          JokeCategoryState.fromString(map['state'] as String?) ??
          JokeCategoryState.proposed,
    );
  }
}
