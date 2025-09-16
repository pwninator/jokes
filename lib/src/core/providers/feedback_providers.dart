import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/feedback_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:cloud_firestore/cloud_firestore.dart';

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

/// Stream provider for all feedback entries ordered by creation_time desc
final allFeedbackProvider = StreamProvider<List<FeedbackEntry>>((ref) {
  return ref.watch(feedbackRepositoryProvider).watchAllFeedback();
});

/// Stream provider for unread feedback count
final unreadFeedbackCountProvider = StreamProvider<int>((ref) {
  return ref.watch(feedbackRepositoryProvider).watchUnreadCount();
});

/// Model for joke user usage counters
class JokeUserUsage {
  final int? clientNumDaysUsed;
  final int? clientNumSaved;
  final int? clientNumViewed;
  final int? clientNumShared;
  final DateTime? lastLoginAt;

  const JokeUserUsage({
    this.clientNumDaysUsed,
    this.clientNumSaved,
    this.clientNumViewed,
    this.clientNumShared,
    this.lastLoginAt,
  });
}

/// Provider to stream a single user's usage counters from 'joke_users/{userId}'
final jokeUserUsageProvider = StreamProvider.family<JokeUserUsage?, String>((
  ref,
  userId,
) {
  final firestore = ref.watch(firebaseFirestoreProvider);
  return firestore.collection('joke_users').doc(userId).snapshots().map((d) {
    if (!d.exists) return null;
    final data = d.data() ?? <String, dynamic>{};
    final ts = data['last_login_at'];
    DateTime? lastLogin;
    if (ts is Timestamp) {
      lastLogin = ts.toDate();
    } else if (ts is DateTime) {
      lastLogin = ts;
    }
    return JokeUserUsage(
      clientNumDaysUsed: (data['client_num_days_used'] as num?)?.toInt(),
      clientNumSaved: (data['client_num_saved'] as num?)?.toInt(),
      clientNumViewed: (data['client_num_viewed'] as num?)?.toInt(),
      clientNumShared: (data['client_num_shared'] as num?)?.toInt(),
      lastLoginAt: lastLogin,
    );
  });
});
