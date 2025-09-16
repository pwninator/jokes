import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';

abstract class JokeCategoryRepository {
  /// Stream of all joke categories ordered by display_name
  Stream<List<JokeCategory>> watchCategories();
}
