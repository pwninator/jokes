import 'package:cloud_functions/cloud_functions.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';

class BookRepository {
  BookRepository({
    FirebaseFunctions? functions,
    required JokeRepository jokeRepository,
  }) : _functions = functions ?? FirebaseFunctions.instance,
       _jokeRepository = jokeRepository;

  final FirebaseFunctions _functions;
  final JokeRepository _jokeRepository;

  Future<List<Joke>> searchJokes(String query) async {
    if (query.isEmpty) {
      return [];
    }
    try {
      final callable = _functions.httpsCallable('search_jokes');
      final result = await callable.call({
        'search_query': query,
        'max_results': 20,
        'public_only': true,
        'match_mode': 'TIGHT',
        'label': 'book_creator_search',
      });

      final data = result.data;
      final List<dynamic>? resultsList = (data is Map && data['jokes'] is List)
          ? (data['jokes'] as List)
          : (data is List)
          ? data
          : null;

      if (resultsList == null) {
        AppLogger.warn('Unexpected search_jokes response: $data');
        return [];
      }

      final jokeIds = resultsList
          .whereType<Map>()
          .map((e) => e['joke_id'] as String?)
          .where((id) => id != null)
          .cast<String>()
          .toList();

      if (jokeIds.isEmpty) {
        return [];
      }

      final jokes = await _jokeRepository.getJokesByIds(jokeIds);

      // Sort jokes by popularity score (saves + shares) in descending order
      jokes.sort((a, b) {
        final popularityA = a.numSaves + a.numShares;
        final popularityB = b.numSaves + b.numShares;
        return popularityB.compareTo(popularityA);
      });

      return jokes;
    } on FirebaseFunctionsException catch (e) {
      AppLogger.warn(
        'Firebase Functions error (search_jokes): ${e.code} - ${e.message}',
      );
      return [];
    } catch (e) {
      AppLogger.warn('Error calling search_jokes: $e');
      return [];
    }
  }

  Future<void> createBook(String title, List<String> jokeIds) async {
    try {
      final callable = _functions.httpsCallable('create_book');
      await callable.call({'book_name': title, 'joke_ids': jokeIds});
    } on FirebaseFunctionsException catch (e) {
      AppLogger.warn('Failed to create book: ${e.code} - ${e.message}');
      rethrow;
    } catch (e) {
      AppLogger.warn('Failed to create book: $e');
      rethrow;
    }
  }
}
