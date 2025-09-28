import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/book_creator/data/repositories/book_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

final bookRepositoryProvider = Provider<BookRepository>((ref) {
  final jokeRepository = ref.watch(jokeRepositoryProvider);
  return BookRepository(jokeRepository: jokeRepository);
});
