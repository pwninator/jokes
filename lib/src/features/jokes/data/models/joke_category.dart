import 'package:flutter/foundation.dart';

enum JokeCategoryState {
  PROPOSED,
  APPROVED,
  REJECTED,
}

@immutable
class JokeCategory {
  final String id;
  final String displayName;
  final String jokeDescriptionQuery;
  final String? imageUrl;
  final JokeCategoryState state;

  const JokeCategory({
    required this.id,
    required this.displayName,
    required this.jokeDescriptionQuery,
    this.imageUrl,
    this.state = JokeCategoryState.PROPOSED,
  });

  factory JokeCategory.fromMap(Map<String, dynamic> map, String id) {
    return JokeCategory(
      id: id,
      displayName: (map['display_name'] as String?)?.trim() ?? '',
      jokeDescriptionQuery:
          (map['joke_description_query'] as String?)?.trim() ?? '',
      imageUrl: (map['image_url'] as String?)?.trim(),
      state: JokeCategoryState.values.firstWhere(
        (e) => e.name == map['state'],
        orElse: () => JokeCategoryState.PROPOSED,
      ),
    );
  }
}
