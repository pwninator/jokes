import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';

part 'reviews_repository.g.dart';

@Riverpod(keepAlive: true)
ReviewsRepository reviewsRepository(Ref ref) {
  final firestore = ref.watch(firebaseFirestoreProvider);
  return FirestoreReviewsRepository(firestore: firestore, ref: ref);
}

/// Repository to record app review events to Firestore
abstract class ReviewsRepository {
  Future<void> recordAppReview();
}

class FirestoreReviewsRepository implements ReviewsRepository {
  FirestoreReviewsRepository({
    required FirebaseFirestore firestore,
    required Ref ref,
  }) : _firestore = firestore,
       _ref = ref;

  final FirebaseFirestore _firestore;
  final Ref _ref;

  static const String _collection = 'joke_app_reviews';

  @override
  Future<void> recordAppReview() async {
    try {
      final user = _ref.read(currentUserProvider);
      if (user == null) {
        AppLogger.warn('REVIEWS_REPO recordAppReview skipped: no user');
        return;
      }

      // Build doc id: YYYYMMDD_HHMM_[user_id]
      final now = DateTime.now();
      String p2(int n) => n.toString().padLeft(2, '0');
      final id =
          '${now.year}${p2(now.month)}${p2(now.day)}_${p2(now.hour)}${p2(now.minute)}_${user.id}';

      // Gather metrics from AppUsageService
      final usage = _ref.read(appUsageServiceProvider);
      final numDaysUsed = await usage.getNumDaysUsed();
      final numViewed = await usage.getNumJokesViewed();
      final numSaved = await usage.getNumSavedJokes();
      final numShared = await usage.getNumSharedJokes();

      // Subscription state
      final isSubscribed = _ref.read(isSubscribedProvider);

      final data = <String, dynamic>{
        'user_id': user.id,
        'num_days_used': numDaysUsed,
        'num_jokes_viewed': numViewed,
        'num_jokes_saved': numSaved,
        'num_jokes_shared': numShared,
        'is_subscribed': isSubscribed,
        'timestamp': FieldValue.serverTimestamp(),
      };

      await _firestore
          .collection(_collection)
          .doc(id)
          .set(data, SetOptions(merge: true));
      AppLogger.debug('REVIEWS_REPO recorded app review for ${user.id} -> $id');
    } catch (e) {
      AppLogger.warn('REVIEWS_REPO recordAppReview error: $e');
    }
  }
}
