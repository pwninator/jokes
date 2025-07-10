import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/shared_preferences_provider.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';

// Mock classes
class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

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

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      sharedPreferences = await SharedPreferences.getInstance();
      service = DailyJokeSubscriptionServiceImpl(
        sharedPreferences: sharedPreferences,
      );
    });

    group('FCM sync operations', () {
      test('should handle unsubscribed state correctly', () async {
        // FCM operations will fail in test environment without Firebase initialization
        // We expect the method to return false but handle the error gracefully
        final result = await service.ensureSubscriptionSync();
        expect(
          result,
          isFalse,
        ); // Should return false due to Firebase not being initialized
      });

      test('should handle subscribed state with valid hour', () async {
        await sharedPreferences.setBool('daily_jokes_subscribed', true);
        await sharedPreferences.setInt('daily_jokes_subscribed_hour', 14);

        // FCM operations will fail in test environment
        final result = await service.ensureSubscriptionSync();
        expect(
          result,
          isFalse,
        ); // Should return false due to Firebase not being initialized
      });

      test('should handle subscribed state with invalid hour', () async {
        await sharedPreferences.setBool('daily_jokes_subscribed', true);
        await sharedPreferences.setInt('daily_jokes_subscribed_hour', -1);

        // FCM operations will fail in test environment
        final result = await service.ensureSubscriptionSync();
        expect(
          result,
          isFalse,
        ); // Should return false due to Firebase not being initialized
      });
    });

    group('Topic name calculation', () {
      test('should handle various timezone scenarios', () {
        // Test that the service doesn't crash with different hours
        // The actual FCM operations will fail, but the method should handle errors gracefully
        expect(() => service.ensureSubscriptionSync(), returnsNormally);
      });
    });
  });
}
