import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

part 'book_repository.g.dart';

@Riverpod(keepAlive: true)
BookRepository bookRepository(Ref ref) {
  final jokeRepository = ref.watch(jokeRepositoryProvider);
  final jokeCloudFunctionService = ref.watch(jokeCloudFunctionServiceProvider);
  return BookRepository(
    jokeRepository: jokeRepository,
    jokeCloudFunctionService: jokeCloudFunctionService,
  );
}

class BookRepository {
  BookRepository({
    required JokeRepository jokeRepository,
    required JokeCloudFunctionService jokeCloudFunctionService,
  }) : _jokeRepository = jokeRepository,
       _jokeCloudFunctionService = jokeCloudFunctionService;

  final JokeRepository _jokeRepository;
  final JokeCloudFunctionService _jokeCloudFunctionService;

  Future<List<Joke>> searchJokes(String query, {bool isCategory = false}) async {
    if (query.isEmpty) {
      return [];
    }
    try {
      final searchResults = await _jokeCloudFunctionService.searchJokes(
        searchQuery: query,
        category: isCategory ? query : null,
        maxResults: 20,
        publicOnly: false,
        matchMode: MatchMode.loose,
        scope: SearchScope
            .jokeManagementSearch, // Using appropriate scope for book creator
        label: SearchLabel.none,
      );

      if (searchResults.isEmpty) {
        AppLogger.warn('search_jokes result: No search results found');
        return [];
      }

      final jokeIds = searchResults.map((result) => result.id).toList();

      AppLogger.debug('search_jokes result: $searchResults');

      final jokes = await _jokeRepository.getJokesByIds(jokeIds);

      // Sort jokes by popularity score (saves + shares) in descending order
      jokes.sort((a, b) {
        final popularityA = a.numSaves + a.numShares;
        final popularityB = b.numSaves + b.numShares;
        return popularityB.compareTo(popularityA);
      });

      return jokes;
    } catch (e) {
      AppLogger.warn('Error searching jokes: $e');
      return [];
    }
  }

  Future<void> createBook(String title, List<String> jokeIds) async {
    try {
      final result = await _jokeCloudFunctionService.createBook(
        title: title,
        jokeIds: jokeIds,
      );

      if (result == null || result['success'] != true) {
        final error = result?['error'] ?? 'Unknown error';
        AppLogger.warn('Failed to create book: $error');
        throw Exception('Failed to create book: $error');
      }
    } catch (e) {
      AppLogger.warn('Failed to create book: $e');
      rethrow;
    }
  }
}
