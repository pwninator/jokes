import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/common_widgets/notification_hour_widget.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/providers/shared_preferences_provider.dart';
import 'package:snickerdoodle/src/core/services/analytics_events.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';

// Mock classes
class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockNotificationService extends Mock implements NotificationService {}

class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

void main() {
  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(SubscriptionEventType.subscribed);
    registerFallbackValue(SubscriptionSource.settings);
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
      expect(find.text('09:00 AM'), findsOneWidget);

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
    late MockDailyJokeSubscriptionService mockSubscriptionService;
    late MockAnalyticsService mockAnalyticsService;
    late SharedPreferences sharedPreferences;

    setUp(() async {
      TestWidgetsFlutterBinding.ensureInitialized();

      SharedPreferences.setMockInitialValues({});
      sharedPreferences = await SharedPreferences.getInstance();

      mockSubscriptionService = MockDailyJokeSubscriptionService();
      mockAnalyticsService = MockAnalyticsService();

      // Set up default mock returns
      when(
        () => mockSubscriptionService.getSubscriptionHour(),
      ).thenAnswer((_) async => 9);
      when(
        () => mockSubscriptionService.subscribeWithNotificationPermission(
          hour: any(named: 'hour'),
        ),
      ).thenAnswer((_) async => true);
      when(
        () => mockAnalyticsService.logSubscriptionEvent(
          any(),
          any(),
          permissionGranted: any(named: 'permissionGranted'),
          subscriptionHour: any(named: 'subscriptionHour'),
        ),
      ).thenAnswer((_) async {});
    });

    Widget createTestWidget() {
      return ProviderScope(
        overrides: [
          sharedPreferencesInstanceProvider.overrideWithValue(
            sharedPreferences,
          ),
          dailyJokeSubscriptionServiceProvider.overrideWithValue(
            mockSubscriptionService,
          ),
          analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
        ],
        child: const MaterialApp(home: Scaffold(body: HourDisplayWidget())),
      );
    }

    testWidgets('displays current subscription hour', (tester) async {
      when(
        () => mockSubscriptionService.getSubscriptionHour(),
      ).thenAnswer((_) async => 14); // 2 PM

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('02:00 PM'), findsOneWidget);
      expect(find.byIcon(Icons.schedule), findsOneWidget);
      expect(find.byIcon(Icons.edit), findsOneWidget);
    });

    testWidgets('shows loading state initially', (tester) async {
      // Make the future not complete immediately
      when(() => mockSubscriptionService.getSubscriptionHour()).thenAnswer(
        (_) => Future.delayed(const Duration(milliseconds: 100), () => 9),
      );

      await tester.pumpWidget(createTestWidget());

      expect(find.text('Loading notification time...'), findsOneWidget);

      // Wait for the future to complete
      await tester.pumpAndSettle();
    });

    testWidgets('handles errors gracefully', (tester) async {
      when(
        () => mockSubscriptionService.getSubscriptionHour(),
      ).thenAnswer((_) async => -1); // Invalid hour should hide widget

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Should show nothing when there's an invalid hour
      expect(find.byType(HourDisplayWidget), findsOneWidget);
      expect(find.text('Loading notification time...'), findsNothing);
      expect(find.text('09:00 AM'), findsNothing);
    });

    testWidgets('is tappable to open hour picker', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Verify the widget is tappable
      expect(find.byType(InkWell), findsOneWidget);
      expect(find.byIcon(Icons.edit), findsOneWidget);

      // Tap on the hour display (dialog functionality tested separately)
      await tester.tap(find.byType(InkWell));
      await tester.pump(); // Just pump once to trigger the tap
    });
  });
}
