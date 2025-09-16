import 'package:flutter/foundation.dart';

@immutable
class JokeCategory {
  final String id;
  final String displayName;
  final String jokeDescriptionQuery;
  final String? imageUrl;

  const JokeCategory({
    required this.id,
    required this.displayName,
    required this.jokeDescriptionQuery,
    this.imageUrl,
  });

  factory JokeCategory.fromMap(Map<String, dynamic> map, String id) {
    return JokeCategory(
      id: id,
      displayName: (map['display_name'] as String?)?.trim() ?? '',
      jokeDescriptionQuery:
          (map['joke_description_query'] as String?)?.trim() ?? '',
      imageUrl: (map['image_url'] as String?)?.trim(),
    );
  }
}
