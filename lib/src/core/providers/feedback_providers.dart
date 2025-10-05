import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/feedback_service.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
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

/// Stream provider for all feedback entries ordered by creation_time desc
final allFeedbackProvider = StreamProvider<List<FeedbackEntry>>((ref) {
  return ref.watch(feedbackRepositoryProvider).watchAllFeedback().map((
    entries,
  ) {
    final sortedEntries = [...entries];
    sortedEntries.sort((a, b) {
      final aTime = a.lastUserMessageTime;
      final bTime = b.lastUserMessageTime;
      if (aTime == null && bTime == null) return 0;
      // Put entries without user messages at the end
      if (aTime == null) return 1;
      if (bTime == null) return -1;
      return bTime.compareTo(aTime); // Sort by most recent user message
    });
    return sortedEntries;
  });
});

/// Stream provider for a single feedback entry
final feedbackProvider = StreamProvider.family<FeedbackEntry?, String>((
  ref,
  id,
) {
  return ref.watch(feedbackRepositoryProvider).watchAllFeedback().map((list) {
    for (final item in list) {
      if (item.id == id) return item;
    }
    return null;
  });
});

/// Model for joke user usage counters
class JokeUserUsage {
  final int? clientNumDaysUsed;
  final int? clientNumSaved;
  final int? clientNumViewed;
  final int? clientNumShared;
  final DateTime? lastLoginAt;
  final DateTime? createdAt;

  const JokeUserUsage({
    this.clientNumDaysUsed,
    this.clientNumSaved,
    this.clientNumViewed,
    this.clientNumShared,
    this.lastLoginAt,
    this.createdAt,
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

    DateTime? parseDate(dynamic value) {
      if (value is Timestamp) return value.toDate();
      if (value is DateTime) return value;
      return null;
    }

    final lastLogin = parseDate(data['last_login_at']);
    final createdAt = parseDate(data['created_at']);

    return JokeUserUsage(
      clientNumDaysUsed: (data['client_num_days_used'] as num?)?.toInt(),
      clientNumSaved: (data['client_num_saved'] as num?)?.toInt(),
      clientNumViewed: (data['client_num_viewed'] as num?)?.toInt(),
      clientNumShared: (data['client_num_shared'] as num?)?.toInt(),
      lastLoginAt: lastLogin,
      createdAt: createdAt,
    );
  });
});

/// Stream provider of feedback entries for the current user
final userFeedbackProvider = StreamProvider.autoDispose<List<FeedbackEntry>>((
  ref,
) {
  final feedbackRepository = ref.watch(feedbackRepositoryProvider);
  final user = ref.watch(currentUserProvider);
  if (user == null) {
    return Stream.value([]);
  }
  return feedbackRepository.watchAllFeedbackForUser(user.id).map((entries) {
    // Sort client-side by creation_time descending (newest first)
    final list = [...entries];
    list.sort((a, b) {
      final aTime = a.creationTime;
      final bTime = b.creationTime;
      if (aTime == null && bTime == null) return 0;
      if (aTime == null) return 1; // nulls last
      if (bTime == null) return -1;
      return bTime.compareTo(aTime);
    });
    return list;
  });
});

/// Derived provider computing unread feedback for the current user
final unreadFeedbackProvider = Provider.autoDispose<List<FeedbackEntry>>((ref) {
  final userFeedbackAsyncValue = ref.watch(userFeedbackProvider);
  return userFeedbackAsyncValue.when(
    data: (feedbackEntries) {
      final unread = feedbackEntries.where((entry) {
        if (entry.conversation.isEmpty) {
          return false;
        }
        final lastEntry = entry.conversation.last;
        if (lastEntry.speaker != SpeakerType.admin) {
          return false;
        }
        if (entry.lastUserViewTime == null) {
          return true;
        }
        return entry.lastUserViewTime!.isBefore(lastEntry.timestamp);
      }).toList();

      // Sort by creation time, oldest first
      unread.sort((a, b) {
        if (a.creationTime == null && b.creationTime == null) return 0;
        if (a.creationTime == null) return 1;
        if (b.creationTime == null) return -1;
        return a.creationTime!.compareTo(b.creationTime!);
      });

      return unread;
    },
    loading: () => [],
    error: (_, _) => [],
  );
});
