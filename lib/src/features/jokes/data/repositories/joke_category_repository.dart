import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';

abstract class JokeCategoryRepository {
  /// Stream of all joke categories ordered by display_name
  Stream<List<JokeCategory>> watchCategories();

  /// Stream a single joke category by ID
  Stream<JokeCategory?> watchCategory(String categoryId);

  /// Upsert a joke category
  Future<void> upsertCategory(JokeCategory category);

  /// Delete a joke category
  Future<void> deleteCategory(String categoryId);

  /// Stream of all images for a joke category
  Stream<List<String>> watchCategoryImages(String categoryId);

  /// Add an image to a joke category
  Future<void> addImageToCategory(String categoryId, String imageUrl);

  /// Delete an image from a joke category
  Future<void> deleteImageFromCategory(String categoryId, String imageUrl);

  /// Get cached joke results for a category from subcollection
  Future<List<CategoryCachedJoke>> getCachedCategoryJokes(String categoryId);
}

class CategoryCachedJoke {
  final String jokeId;
  final String setupText;
  final String punchlineText;
  final String? setupImageUrl;
  final String? punchlineImageUrl;

  const CategoryCachedJoke({
    required this.jokeId,
    required this.setupText,
    required this.punchlineText,
    this.setupImageUrl,
    this.punchlineImageUrl,
  });

  factory CategoryCachedJoke.fromMap(Map<String, dynamic> map) {
    return CategoryCachedJoke(
      jokeId: (map['key'] as String?)?.trim() ?? '',
      setupText: (map['setup_text'] as String?)?.trim() ?? '',
      punchlineText: (map['punchline_text'] as String?)?.trim() ?? '',
      setupImageUrl: (map['setup_image_url'] as String?)?.trim(),
      punchlineImageUrl: (map['punchline_image_url'] as String?)?.trim(),
    );
  }
}
