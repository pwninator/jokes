import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

// Mock classes
class MockSettingsService extends Mock implements SettingsService {}

class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

class MockNotificationService extends Mock implements NotificationService {}

class MockRemoteConfigValues extends Mock implements RemoteConfigValues {}

void main() {
  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(RemoteParam.subscriptionPromptMinJokesViewed);
  });

  late MockSettingsService mockSettingsService;
  late MockDailyJokeSubscriptionService mockSubscriptionService;
  late MockNotificationService mockNotificationService;
  late MockRemoteConfigValues mockRemoteConfigValues;

  setUp(() {
    // Create fresh mocks per test
    mockSettingsService = MockSettingsService();
    mockSubscriptionService = MockDailyJokeSubscriptionService();
    mockNotificationService = MockNotificationService();
    mockRemoteConfigValues = MockRemoteConfigValues();

    // Setup default behavior for settings service
    when(() => mockSettingsService.getBool(any())).thenReturn(false);
    when(() => mockSettingsService.getInt(any())).thenReturn(-1);
    when(() => mockSettingsService.containsKey(any())).thenReturn(false);
    when(
      () => mockSettingsService.setBool(any(), any()),
    ).thenAnswer((_) async {});
    when(
      () => mockSettingsService.setInt(any(), any()),
    ).thenAnswer((_) async {});

    // Setup default behavior for subscription service
    when(
      () => mockSubscriptionService.ensureSubscriptionSync(
        unsubscribeOthers: any(named: 'unsubscribeOthers'),
      ),
    ).thenAnswer((_) async => true);

    // Setup default behavior for notification service
    when(
      () => mockNotificationService.requestNotificationPermissions(),
    ).thenAnswer((_) async => true);

    // Setup default behavior for remote config
    when(() => mockRemoteConfigValues.getInt(any())).thenReturn(5);
    when(() => mockRemoteConfigValues.getBool(any())).thenReturn(false);
    when(() => mockRemoteConfigValues.getDouble(any())).thenReturn(0.0);
    when(() => mockRemoteConfigValues.getString(any())).thenReturn('');
    when(() => mockRemoteConfigValues.getEnum(any())).thenReturn('');
  });

  group('SubscriptionPromptNotifier', () {
    test('does not show prompt when jokes viewed below threshold', () {
      // Arrange
      when(
        () => mockRemoteConfigValues.getInt(
          RemoteParam.subscriptionPromptMinJokesViewed,
        ),
      ).thenReturn(7);

      final subscriptionNotifier = SubscriptionNotifier(
        mockSettingsService,
        mockSubscriptionService,
        mockNotificationService,
      );
      final promptNotifier = SubscriptionPromptNotifier(
        subscriptionNotifier,
        remoteConfigValues: mockRemoteConfigValues,
      );

      // Act
      final shown = promptNotifier.maybePromptAfterJokeViewed(5);

      // Assert
      expect(shown, isFalse);
      expect(promptNotifier.state.shouldShowPrompt, isFalse);
    });

    test('shows prompt when jokes viewed meets threshold', () {
      // Arrange
      when(
        () => mockRemoteConfigValues.getInt(
          RemoteParam.subscriptionPromptMinJokesViewed,
        ),
      ).thenReturn(5);

      final subscriptionNotifier = SubscriptionNotifier(
        mockSettingsService,
        mockSubscriptionService,
        mockNotificationService,
      );
      final promptNotifier = SubscriptionPromptNotifier(
        subscriptionNotifier,
        remoteConfigValues: mockRemoteConfigValues,
      );

      // Act
      final shown = promptNotifier.maybePromptAfterJokeViewed(5);

      // Assert
      expect(shown, isTrue);
      expect(promptNotifier.state.shouldShowPrompt, isTrue);
    });

    test('shows prompt when jokes viewed exceeds threshold', () {
      // Arrange
      when(
        () => mockRemoteConfigValues.getInt(
          RemoteParam.subscriptionPromptMinJokesViewed,
        ),
      ).thenReturn(3);

      final subscriptionNotifier = SubscriptionNotifier(
        mockSettingsService,
        mockSubscriptionService,
        mockNotificationService,
      );
      final promptNotifier = SubscriptionPromptNotifier(
        subscriptionNotifier,
        remoteConfigValues: mockRemoteConfigValues,
      );

      // Act
      final shown = promptNotifier.maybePromptAfterJokeViewed(5);

      // Assert
      expect(shown, isTrue);
      expect(promptNotifier.state.shouldShowPrompt, isTrue);
    });

    test('does not show prompt when user has already made choice', () {
      // Arrange
      when(
        () => mockSettingsService.containsKey('daily_jokes_subscribed'),
      ).thenReturn(true);
      when(
        () => mockSettingsService.getBool('daily_jokes_subscribed'),
      ).thenReturn(false);

      when(
        () => mockRemoteConfigValues.getInt(
          RemoteParam.subscriptionPromptMinJokesViewed,
        ),
      ).thenReturn(5);

      final subscriptionNotifier = SubscriptionNotifier(
        mockSettingsService,
        mockSubscriptionService,
        mockNotificationService,
      );
      final promptNotifier = SubscriptionPromptNotifier(
        subscriptionNotifier,
        remoteConfigValues: mockRemoteConfigValues,
      );

      // Act
      final shown = promptNotifier.maybePromptAfterJokeViewed(5);

      // Assert
      expect(shown, isFalse);
      expect(promptNotifier.state.shouldShowPrompt, isFalse);
      expect(promptNotifier.state.hasUserMadeChoice, isTrue);
    });

    test('does not show prompt when user is already subscribed', () {
      // Arrange
      when(
        () => mockSettingsService.containsKey('daily_jokes_subscribed'),
      ).thenReturn(true);
      when(
        () => mockSettingsService.getBool('daily_jokes_subscribed'),
      ).thenReturn(true);

      when(
        () => mockRemoteConfigValues.getInt(
          RemoteParam.subscriptionPromptMinJokesViewed,
        ),
      ).thenReturn(5);

      final subscriptionNotifier = SubscriptionNotifier(
        mockSettingsService,
        mockSubscriptionService,
        mockNotificationService,
      );
      final promptNotifier = SubscriptionPromptNotifier(
        subscriptionNotifier,
        remoteConfigValues: mockRemoteConfigValues,
      );

      // Act
      final shown = promptNotifier.maybePromptAfterJokeViewed(5);

      // Assert
      expect(shown, isFalse);
      expect(promptNotifier.state.shouldShowPrompt, isFalse);
      expect(promptNotifier.state.isSubscribed, isTrue);
    });

    test('does not show prompt again if already shown', () {
      // Arrange
      when(
        () => mockRemoteConfigValues.getInt(
          RemoteParam.subscriptionPromptMinJokesViewed,
        ),
      ).thenReturn(5);

      final subscriptionNotifier = SubscriptionNotifier(
        mockSettingsService,
        mockSubscriptionService,
        mockNotificationService,
      );
      final promptNotifier = SubscriptionPromptNotifier(
        subscriptionNotifier,
        remoteConfigValues: mockRemoteConfigValues,
      );

      // Act - first call shows prompt
      final firstShown = promptNotifier.maybePromptAfterJokeViewed(5);
      expect(promptNotifier.state.shouldShowPrompt, isTrue);

      // Second call should not show prompt again
      final secondShown = promptNotifier.maybePromptAfterJokeViewed(6);

      // Assert
      expect(firstShown, isTrue);
      expect(secondShown, isFalse);
      expect(
        promptNotifier.state.shouldShowPrompt,
        isTrue,
      ); // Still true, not changed
    });

    test('updates subscription state from underlying notifier', () {
      // Arrange
      when(
        () => mockSettingsService.containsKey('daily_jokes_subscribed'),
      ).thenReturn(true);
      when(
        () => mockSettingsService.getBool('daily_jokes_subscribed'),
      ).thenReturn(true);

      when(
        () => mockRemoteConfigValues.getInt(
          RemoteParam.subscriptionPromptMinJokesViewed,
        ),
      ).thenReturn(5);

      final subscriptionNotifier = SubscriptionNotifier(
        mockSettingsService,
        mockSubscriptionService,
        mockNotificationService,
      );
      final promptNotifier = SubscriptionPromptNotifier(
        subscriptionNotifier,
        remoteConfigValues: mockRemoteConfigValues,
      );

      // Act
      final shown = promptNotifier.maybePromptAfterJokeViewed(5);

      // Assert
      expect(shown, isFalse);
      expect(promptNotifier.state.isSubscribed, isTrue);
      expect(promptNotifier.state.hasUserMadeChoice, isTrue);
      expect(promptNotifier.state.shouldShowPrompt, isFalse);
    });
  });
}
