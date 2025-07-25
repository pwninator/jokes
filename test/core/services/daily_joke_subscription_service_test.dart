import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/shared_preferences_provider.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';

// Mock classes
class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

class MockFirebaseMessaging extends Mock implements FirebaseMessaging {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('SubscriptionState', () {
    test('should have correct equality and hashCode', () {
      const state1 = SubscriptionState(isSubscribed: true, hour: 9);
      const state2 = SubscriptionState(isSubscribed: true, hour: 9);
      const state3 = SubscriptionState(isSubscribed: false, hour: 9);

      expect(state1, equals(state2));
      expect(state1.hashCode, equals(state2.hashCode));
      expect(state1, isNot(equals(state3)));
    });

    test('should copy with new values', () {
      const original = SubscriptionState(isSubscribed: false, hour: 9);
      final copied = original.copyWith(isSubscribed: true, hour: 14);

      expect(copied.isSubscribed, isTrue);
      expect(copied.hour, equals(14));
      expect(original.isSubscribed, isFalse);
      expect(original.hour, equals(9));
    });
  });

  group('SubscriptionNotifier', () {
    late ProviderContainer container;
    late MockDailyJokeSubscriptionService mockSyncService;
    late SharedPreferences sharedPreferences;

    setUp(() async {
      // Set up mock SharedPreferences
      SharedPreferences.setMockInitialValues({});
      sharedPreferences = await SharedPreferences.getInstance();

      // Set up mock sync service
      mockSyncService = MockDailyJokeSubscriptionService();
      when(
        () => mockSyncService.ensureSubscriptionSync(),
      ).thenAnswer((_) async => true);

      // Create container with overrides
      container = ProviderContainer(
        overrides: [
          sharedPreferencesInstanceProvider.overrideWithValue(
            sharedPreferences,
          ),
          dailyJokeSubscriptionServiceProvider.overrideWithValue(
            mockSyncService,
          ),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    group('Initial state', () {
      test('should load default state when no preferences exist', () {
        final notifier = container.read(subscriptionProvider.notifier);
        final state = container.read(subscriptionProvider);

        expect(state.isSubscribed, isFalse);
        expect(state.hour, equals(9)); // Default hour
        expect(notifier.hasUserMadeChoice(), isFalse);
      });

      test('should load existing preferences', () async {
        // Set up existing preferences
        await sharedPreferences.setBool('daily_jokes_subscribed', true);
        await sharedPreferences.setInt('daily_jokes_subscribed_hour', 14);

        // Create new container to reload state
        final newContainer = ProviderContainer(
          overrides: [
            sharedPreferencesInstanceProvider.overrideWithValue(
              sharedPreferences,
            ),
            dailyJokeSubscriptionServiceProvider.overrideWithValue(
              mockSyncService,
            ),
          ],
        );

        final state = newContainer.read(subscriptionProvider);
        final notifier = newContainer.read(subscriptionProvider.notifier);

        expect(state.isSubscribed, isTrue);
        expect(state.hour, equals(14));
        expect(notifier.hasUserMadeChoice(), isTrue);

        newContainer.dispose();
      });

      test('should apply default hour for invalid stored hour', () async {
        // Set up invalid hour
        await sharedPreferences.setBool('daily_jokes_subscribed', true);
        await sharedPreferences.setInt('daily_jokes_subscribed_hour', -1);

        // Create new container to reload state
        final newContainer = ProviderContainer(
          overrides: [
            sharedPreferencesInstanceProvider.overrideWithValue(
              sharedPreferences,
            ),
            dailyJokeSubscriptionServiceProvider.overrideWithValue(
              mockSyncService,
            ),
          ],
        );

        final state = newContainer.read(subscriptionProvider);

        expect(state.isSubscribed, isTrue);
        expect(state.hour, equals(9)); // Should default to 9

        newContainer.dispose();
      });
    });

    group('State mutations', () {
      test('should update subscription status and trigger sync', () async {
        final notifier = container.read(subscriptionProvider.notifier);

        // Initially false
        expect(container.read(subscriptionProvider).isSubscribed, isFalse);

        // Set to true
        await notifier.setSubscribed(true);

        expect(container.read(subscriptionProvider).isSubscribed, isTrue);
        expect(sharedPreferences.getBool('daily_jokes_subscribed'), isTrue);
        verify(
          () => mockSyncService.ensureSubscriptionSync(),
        ).called(2); // Once on init, once on change
      });

      test('should update hour and trigger sync', () async {
        final notifier = container.read(subscriptionProvider.notifier);

        // Initially default hour
        expect(container.read(subscriptionProvider).hour, equals(9));

        // Set to 14
        await notifier.setHour(14);

        expect(container.read(subscriptionProvider).hour, equals(14));
        expect(
          sharedPreferences.getInt('daily_jokes_subscribed_hour'),
          equals(14),
        );
        verify(
          () => mockSyncService.ensureSubscriptionSync(),
        ).called(2); // Once on init, once on change
      });

      test('should reject invalid hours', () async {
        final notifier = container.read(subscriptionProvider.notifier);
        final originalHour = container.read(subscriptionProvider).hour;

        // Try invalid hours
        await notifier.setHour(-1);
        expect(container.read(subscriptionProvider).hour, equals(originalHour));

        await notifier.setHour(24);
        expect(container.read(subscriptionProvider).hour, equals(originalHour));

        await notifier.setHour(25);
        expect(container.read(subscriptionProvider).hour, equals(originalHour));
      });

      test('should unsubscribe correctly', () async {
        final notifier = container.read(subscriptionProvider.notifier);

        // First subscribe
        await notifier.setSubscribed(true);
        expect(container.read(subscriptionProvider).isSubscribed, isTrue);

        // Then unsubscribe
        await notifier.unsubscribe();
        expect(container.read(subscriptionProvider).isSubscribed, isFalse);
        expect(sharedPreferences.getBool('daily_jokes_subscribed'), isFalse);
      });
    });

    group('Permission handling', () {
      test('should handle successful subscription with permission', () async {
        final notifier = container.read(subscriptionProvider.notifier);

        // Mock successful permission
        // Note: We can't easily mock NotificationService here since it's created internally
        // In a real implementation, you'd inject NotificationService as a dependency

        // For now, we'll test the state changes that should happen
        await notifier.setSubscribed(true);
        expect(container.read(subscriptionProvider).isSubscribed, isTrue);
      });

      test('should set hour during subscription with permission', () async {
        final notifier = container.read(subscriptionProvider.notifier);

        // Set hour first
        await notifier.setHour(15);
        expect(container.read(subscriptionProvider).hour, equals(15));

        // Subscribe
        await notifier.setSubscribed(true);
        expect(container.read(subscriptionProvider).isSubscribed, isTrue);
        expect(
          container.read(subscriptionProvider).hour,
          equals(15),
        ); // Hour should be preserved
      });
    });

    group('Convenience providers', () {
      test('isSubscribedProvider should return correct value', () async {
        expect(container.read(isSubscribedProvider), isFalse);

        await container.read(subscriptionProvider.notifier).setSubscribed(true);
        expect(container.read(isSubscribedProvider), isTrue);
      });

      test('subscriptionHourProvider should return correct value', () async {
        expect(container.read(subscriptionHourProvider), equals(9));

        await container.read(subscriptionProvider.notifier).setHour(14);
        expect(container.read(subscriptionHourProvider), equals(14));
      });
    });
  });

  group('DailyJokeSubscriptionServiceImpl', () {
    late DailyJokeSubscriptionServiceImpl service;
    late SharedPreferences sharedPreferences;
    late MockFirebaseMessaging mockFirebaseMessaging;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      sharedPreferences = await SharedPreferences.getInstance();

      // Set up mock Firebase Messaging
      mockFirebaseMessaging = MockFirebaseMessaging();
      when(
        () => mockFirebaseMessaging.subscribeToTopic(any()),
      ).thenAnswer((_) async {});
      when(
        () => mockFirebaseMessaging.unsubscribeFromTopic(any()),
      ).thenAnswer((_) async {});

      service = DailyJokeSubscriptionServiceImpl(
        sharedPreferences: sharedPreferences,
        firebaseMessaging: mockFirebaseMessaging,
      );
    });

    group('FCM sync operations', () {
      test('should handle unsubscribed state correctly', () async {
        // Should succeed with mocked Firebase operations
        final result = await service.ensureSubscriptionSync();
        expect(result, isTrue);

        // Verify no subscribe calls (not subscribed)
        verifyNever(() => mockFirebaseMessaging.subscribeToTopic(any()));
        // Should still unsubscribe from all topics to clean up
        verify(
          () => mockFirebaseMessaging.unsubscribeFromTopic(any()),
        ).called(greaterThan(0));
      });

      test('should handle subscribed state with valid hour', () async {
        await sharedPreferences.setBool('daily_jokes_subscribed', true);
        await sharedPreferences.setInt('daily_jokes_subscribed_hour', 14);

        final result = await service.ensureSubscriptionSync();
        expect(result, isTrue);

        // Should subscribe to the correct topic
        verify(() => mockFirebaseMessaging.subscribeToTopic(any())).called(1);
        // Should unsubscribe from other topics
        verify(
          () => mockFirebaseMessaging.unsubscribeFromTopic(any()),
        ).called(greaterThan(0));
      });

      test('should handle subscribed state with invalid hour', () async {
        await sharedPreferences.setBool('daily_jokes_subscribed', true);
        await sharedPreferences.setInt('daily_jokes_subscribed_hour', -1);

        final result = await service.ensureSubscriptionSync();
        expect(result, isTrue);

        // Should subscribe with default hour (9)
        verify(() => mockFirebaseMessaging.subscribeToTopic(any())).called(1);
      });
    });

    group('Topic name calculation', () {
      test('should handle various timezone scenarios', () {
        // Test that the service doesn't crash with different hours
        // The actual FCM operations will fail, but the method should handle errors gracefully
        expect(() => service.ensureSubscriptionSync(), returnsNormally);
      });
    });

    group('Debouncing and cancellation', () {
      test(
        'should debounce rapid calls and cancel previous operations',
        () async {
          // Set up subscription to trigger sync operations
          await sharedPreferences.setBool('daily_jokes_subscribed', true);
          await sharedPreferences.setInt('daily_jokes_subscribed_hour', 14);

          // Start operations in rapid succession
          final future1 = service.ensureSubscriptionSync();
          final future2 = service.ensureSubscriptionSync();
          final future3 = service.ensureSubscriptionSync();

          // Wait for all operations to complete
          final results = await Future.wait([future1, future2, future3]);

          // The first two operations should be cancelled (return false)
          // The third operation should succeed (return true)
          expect(results[0], isFalse); // Cancelled
          expect(results[1], isFalse); // Cancelled
          expect(results[2], isTrue); // Executed successfully

          // Verify Firebase operations were called only once (for the successful operation)
          verify(() => mockFirebaseMessaging.subscribeToTopic(any())).called(1);
          verify(
            () => mockFirebaseMessaging.unsubscribeFromTopic(any()),
          ).called(greaterThan(0));
        },
      );

      test('should debounce rapid calls with proper timing', () async {
        // Set up subscription
        await sharedPreferences.setBool('daily_jokes_subscribed', true);
        await sharedPreferences.setInt('daily_jokes_subscribed_hour', 14);

        final stopwatch = Stopwatch()..start();

        // Start multiple operations in rapid succession
        service.ensureSubscriptionSync();
        service.ensureSubscriptionSync();
        final finalFuture = service.ensureSubscriptionSync();

        // Wait for the final operation to complete
        final result = await finalFuture;

        stopwatch.stop();

        // Should take at least 500ms due to debouncing
        expect(stopwatch.elapsedMilliseconds, greaterThan(450));

        // But shouldn't take too long (indicating operations were cancelled properly)
        expect(stopwatch.elapsedMilliseconds, lessThan(2000));

        // Should return true since Firebase operations are properly mocked
        expect(result, isTrue);
      });

      test('should handle cancellation during different phases', () async {
        // Test that operations can be cancelled at various points
        await sharedPreferences.setBool('daily_jokes_subscribed', true);
        await sharedPreferences.setInt('daily_jokes_subscribed_hour', 14);

        // Start operations with small delays to test cancellation at different phases
        service.ensureSubscriptionSync();

        // Wait a bit, then start another (should cancel first)
        await Future.delayed(const Duration(milliseconds: 100));
        service.ensureSubscriptionSync();

        // Wait a bit more, then start final one
        await Future.delayed(const Duration(milliseconds: 200));
        final finalFuture = service.ensureSubscriptionSync();

        final result = await finalFuture;

        // Should complete successfully with mocked Firebase operations
        expect(result, isTrue);

        // This test mainly ensures the cancellation logic works without deadlocks
      });
    });
  });
}
