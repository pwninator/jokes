import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';

// Provider for JokeRepository
final jokeRepositoryProvider = Provider<JokeRepository>((ref) {
  final firestore = ref.watch(firebaseFirestoreProvider);
  final perf = ref.read(performanceServiceProvider);
  return JokeRepository(firestore: firestore, perf: perf);
});
