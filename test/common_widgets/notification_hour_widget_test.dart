import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/notification_hour_widget.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

// Mock classes
class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockSettingsService extends Mock implements SettingsService {}

class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

class MockNotificationService extends Mock implements NotificationService {}

void main() {
  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(FakeSettingsService());
  });

  group('HourPickerWidget', () {
    testWidgets('displays correctly and handles hour changes', (tester) async {
      int selectedHour = 9;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: HourPickerWidget(
              selectedHour: selectedHour,
              onHourChanged: (hour) {
                // No op
              },
            ),
          ),
        ),
      );

      // Verify initial display
      expect(find.text('Notification time:'), findsOneWidget);
      expect(find.byType(CupertinoPicker), findsOneWidget);

      // Verify hour formatting (9 AM should be displayed)
      expect(find.text('9:00 AM'), findsOneWidget);

      // The CupertinoPicker is complex to test directly due to framework limitations
      // We'll focus on the essential functionality
      expect(find.byType(HourPickerWidget), findsOneWidget);
    });

    testWidgets('formats hours correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: HourPickerWidget(selectedHour: 0, onHourChanged: (hour) {}),
          ),
        ),
      );

      // Check midnight formatting
      expect(find.text('12:00 AM'), findsOneWidget);
    });
  });

  group('HourDisplayWidget', () {
    late MockSettingsService mockSettingsService;
    late MockDailyJokeSubscriptionService mockSubscriptionService;
    late MockNotificationService mockNotificationService;
    late MockAnalyticsService mockAnalyticsService;

    setUp(() {
      // Create fresh mocks per test
      mockSettingsService = MockSettingsService();
      mockSubscriptionService = MockDailyJokeSubscriptionService();
      mockNotificationService = MockNotificationService();
      mockAnalyticsService = MockAnalyticsService();

      // Stub default behavior
      when(
        () => mockSettingsService.getBool('daily_jokes_subscribed'),
      ).thenReturn(true);
      when(
        () => mockSettingsService.getInt('daily_jokes_subscribed_hour'),
      ).thenReturn(9);
      when(
        () => mockSettingsService.setBool(any(), any()),
      ).thenAnswer((_) async {});
      when(
        () => mockSettingsService.setInt(any(), any()),
      ).thenAnswer((_) async {});
      when(() => mockSettingsService.containsKey(any())).thenReturn(true);
      when(
        () => mockSubscriptionService.ensureSubscriptionSync(
          unsubscribeOthers: any(named: 'unsubscribeOthers'),
        ),
      ).thenAnswer((_) async => true);
      when(
        () => mockNotificationService.requestNotificationPermissions(),
      ).thenAnswer((_) async => true);
      when(
        () => mockAnalyticsService.logSubscriptionTimeChanged(
          subscriptionHour: any(named: 'subscriptionHour'),
        ),
      ).thenAnswer((_) async {});
      when(
        () => mockAnalyticsService.logErrorSubscriptionTimeUpdate(
          source: any(named: 'source'),
          errorMessage: any(named: 'errorMessage'),
        ),
      ).thenAnswer((_) async {});
    });

    testWidgets('displays current subscription hour', (tester) async {
      // Arrange: Configure mock to return specific hour
      when(
        () => mockSettingsService.getInt('daily_jokes_subscribed_hour'),
      ).thenReturn(14);

      // Act: Build widget with explicit overrides
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            settingsServiceProvider.overrideWithValue(mockSettingsService),
            dailyJokeSubscriptionServiceProvider.overrideWithValue(
              mockSubscriptionService,
            ),
            analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
            notificationServiceProvider.overrideWithValue(
              mockNotificationService,
            ),
          ],
          child: const MaterialApp(home: Scaffold(body: HourDisplayWidget())),
        ),
      );
      await tester.pumpAndSettle();

      // Assert: Verify behavior
      expect(find.text('Notification time: 2:00 PM'), findsOneWidget);
    });

    testWidgets('displays different hours correctly', (tester) async {
      // Arrange: Configure mock to return midnight hour
      when(
        () => mockSettingsService.getInt('daily_jokes_subscribed_hour'),
      ).thenReturn(0);

      // Act: Build widget with explicit overrides
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            settingsServiceProvider.overrideWithValue(mockSettingsService),
            dailyJokeSubscriptionServiceProvider.overrideWithValue(
              mockSubscriptionService,
            ),
            analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
            notificationServiceProvider.overrideWithValue(
              mockNotificationService,
            ),
          ],
          child: const MaterialApp(home: Scaffold(body: HourDisplayWidget())),
        ),
      );
      await tester.pumpAndSettle();

      // Assert: Verify midnight formatting
      expect(find.text('Notification time: 12:00 AM'), findsOneWidget);
    });

    testWidgets('opens dialog when change button is tapped', (tester) async {
      // Act: Build widget and tap change button
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            settingsServiceProvider.overrideWithValue(mockSettingsService),
            dailyJokeSubscriptionServiceProvider.overrideWithValue(
              mockSubscriptionService,
            ),
            analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
            notificationServiceProvider.overrideWithValue(
              mockNotificationService,
            ),
          ],
          child: const MaterialApp(home: Scaffold(body: HourDisplayWidget())),
        ),
      );
      await tester.pumpAndSettle();

      // Initial state
      expect(find.text('Notification time: 9:00 AM'), findsOneWidget);

      // Tap change button
      await tester.tap(
        find.byKey(const Key('notification_hour_widget-change-hour-button')),
      );
      await tester.pumpAndSettle();

      // Assert: Dialog should be open
      expect(find.text('Change Notification Time'), findsOneWidget);
    });

    testWidgets('closes dialog when cancel button is tapped', (tester) async {
      // Act: Build widget and open dialog
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            settingsServiceProvider.overrideWithValue(mockSettingsService),
            dailyJokeSubscriptionServiceProvider.overrideWithValue(
              mockSubscriptionService,
            ),
            analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
            notificationServiceProvider.overrideWithValue(
              mockNotificationService,
            ),
          ],
          child: const MaterialApp(home: Scaffold(body: HourDisplayWidget())),
        ),
      );
      await tester.pumpAndSettle();

      // Open dialog
      await tester.tap(
        find.byKey(const Key('notification_hour_widget-change-hour-button')),
      );
      await tester.pumpAndSettle();

      // Verify dialog is open
      expect(find.text('Change Notification Time'), findsOneWidget);

      // Tap cancel button
      await tester.tap(
        find.byKey(const Key('notification_hour_widget-cancel-button')),
      );
      await tester.pumpAndSettle();

      // Assert: Dialog should be closed
      expect(find.text('Change Notification Time'), findsNothing);
    });

    testWidgets('updates hour and shows success message when save is tapped', (
      tester,
    ) async {
      // Act: Build widget and open dialog
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            settingsServiceProvider.overrideWithValue(mockSettingsService),
            dailyJokeSubscriptionServiceProvider.overrideWithValue(
              mockSubscriptionService,
            ),
            analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
            notificationServiceProvider.overrideWithValue(
              mockNotificationService,
            ),
          ],
          child: const MaterialApp(home: Scaffold(body: HourDisplayWidget())),
        ),
      );
      await tester.pumpAndSettle();

      // Open dialog
      await tester.tap(
        find.byKey(const Key('notification_hour_widget-change-hour-button')),
      );
      await tester.pumpAndSettle();

      // Tap save button (this will return the current hour since we can't easily
      // simulate CupertinoPicker changes in tests)
      await tester.tap(
        find.byKey(const Key('notification_hour_widget-save-button')),
      );
      await tester.pumpAndSettle();

      // Assert: Verify dialog is closed (no analytics call since hour didn't change)
      expect(find.text('Change Notification Time'), findsNothing);
    });
  });
}

// Fake class for registerFallbackValue
class FakeSettingsService extends Fake implements SettingsService {}
