import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:fake_cloud_firestore/fake_cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/data/reviews/reviews_repository.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';

void main() {
  group('FirestoreReviewsRepository', () {
    test(
      'recordAppReview writes expected document with correct ID and fields',
      () async {
        final fakeFs = FakeFirebaseFirestore();
        final container = ProviderContainer(
          overrides: [
            firebaseFirestoreProvider.overrideWithValue(
              fakeFs as FirebaseFirestore,
            ),
            // Provide a fake current user
            currentUserProvider.overrideWith(
              (ref) => AppUser.authenticated(id: 'user123'),
            ),
            // Provide deterministic usage values
            appUsageServiceProvider.overrideWithValue(
              _FakeUsageService(days: 5, viewed: 10, saved: 3, shared: 2),
            ),
            // Subscription state
            isSubscribedProvider.overrideWith((ref) => true),
          ],
        );

        final repo = container.read(reviewsRepositoryProvider);

        await repo.recordAppReview();

        final now = DateTime.now();
        String p2(int n) => n.toString().padLeft(2, '0');
        final id =
            '${now.year}${p2(now.month)}${p2(now.day)}_${p2(now.hour)}${p2(now.minute)}_user123';

        final snap = await fakeFs.collection('joke_app_reviews').doc(id).get();
        expect(snap.exists, true);
        final data = snap.data()!;
        expect(data['user_id'], 'user123');
        expect((data['num_days_used'] as num).toInt(), 5);
        expect((data['num_jokes_viewed'] as num).toInt(), 10);
        expect((data['num_jokes_saved'] as num).toInt(), 3);
        expect((data['num_jokes_shared'] as num).toInt(), 2);
        expect(data['is_subscribed'], true);
        expect(data['timestamp'], isA<Timestamp>());
      },
    );
  });
}

class _FakeUsageService implements AppUsageService {
  _FakeUsageService({
    required this.days,
    required this.viewed,
    required this.saved,
    required this.shared,
  });

  final int days;
  final int viewed;
  final int saved;
  final int shared;

  @override
  noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);

  @override
  Future<int> getNumDaysUsed() async => days;

  @override
  Future<int> getNumJokesViewed() async => viewed;

  @override
  Future<int> getNumSavedJokes() async => saved;

  @override
  Future<int> getNumSharedJokes() async => shared;
}
