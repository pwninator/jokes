import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/app_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

// Provider for getting a specific joke by ID
final jokeStreamByIdProvider = StreamProvider.family<Joke?, String>((
  ref,
  jokeId,
) {
  final repository = ref.watch(jokeRepositoryProvider);
  return repository.getJokeByIdStream(jokeId);
});

// Provider for JokeCloudFunctionService
final jokeCloudFunctionServiceProvider = Provider<JokeCloudFunctionService>((
  ref,
) {
  final perf = ref.read(performanceServiceProvider);
  return JokeCloudFunctionService(perf: perf);
});

// Data class to hold a joke with its associated date
class JokeWithDate {
  final Joke joke;
  final DateTime? date;

  const JokeWithDate({required this.joke, this.date});
}
