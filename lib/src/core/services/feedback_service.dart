import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';

/// Abstract interface for submitting user feedback
abstract class FeedbackService {
  /// Submit freeform user feedback to Firestore and log analytics
  Future<void> submitFeedback(String feedbackText, AppUser? currentUser);

  /// Add a message to a feedback conversation
  Future<void> addConversationMessage(
    String docId,
    String text,
    SpeakerType speaker,
  );

  /// Update last user view time to server time
  Future<void> updateLastUserViewTime(String docId);
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
    await _feedbackRepository.submitFeedback(feedbackText, currentUser?.id);
    _analyticsService.logFeedbackSubmitted();
  }

  @override
  Future<void> addConversationMessage(
    String docId,
    String text,
    SpeakerType speaker,
  ) async {
    await _feedbackRepository.addConversationMessage(docId, text, speaker);
    if (speaker == SpeakerType.user) {
      _analyticsService.logFeedbackSubmitted();
    }
  }

  @override
  Future<void> updateLastUserViewTime(String docId) async {
    await _feedbackRepository.updateLastUserViewTime(docId);
  }
}
