import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_category_repository.dart';

class JokeCategoryService {
  final JokeCategoryRepository _repository;

  const JokeCategoryService(this._repository);

  Stream<List<JokeCategory>> watchCategories() {
    return _repository.watchCategories();
  }
}
