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
}
