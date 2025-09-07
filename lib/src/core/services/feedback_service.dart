import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';

/// Abstract interface for submitting user feedback
abstract class FeedbackService {
  /// Submit freeform user feedback to Firestore and log analytics
  Future<void> submitFeedback(String feedbackText, AppUser? currentUser);
}

class FeedbackServiceImpl implements FeedbackService {
  final FeedbackRepository _feedbackRepository;
  final AnalyticsService _analyticsService;

  FeedbackServiceImpl({
    required FeedbackRepository feedbackRepository,
    required AnalyticsService analyticsService,
  }) : _feedbackRepository = feedbackRepository,
       _analyticsService = analyticsService;

  @override
  Future<void> submitFeedback(String feedbackText, AppUser? currentUser) async {
    final userId = currentUser?.id ?? 'anonymous';
    await _feedbackRepository.submitFeedback(feedbackText, userId);
    await _analyticsService.logFeedbackSubmitted();
  }
}
