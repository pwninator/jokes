import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/feedback_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

/// Provider for FeedbackRepository
final feedbackRepositoryProvider = Provider<FeedbackRepository>((ref) {
  final firestore = ref.watch(firebaseFirestoreProvider);
  return FirestoreFeedbackRepository(firestore: firestore);
});

/// Provider for FeedbackService
final feedbackServiceProvider = Provider<FeedbackService>((ref) {
  final repository = ref.watch(feedbackRepositoryProvider);
  final analytics = ref.watch(analyticsServiceProvider);
  return FeedbackServiceImpl(
    feedbackRepository: repository,
    analyticsService: analytics,
  );
});
