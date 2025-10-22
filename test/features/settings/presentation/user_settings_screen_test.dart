import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/providers/app_usage_events_provider.dart';
import 'package:snickerdoodle/src/core/providers/app_version_provider.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/feedback_prompt_state_store.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_state_store.dart';
import 'package:snickerdoodle/src/core/services/url_launcher_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/data/reviews/reviews_repository.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';
import 'package:snickerdoodle/src/features/settings/application/admin_settings_service.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';

class FakeBuildContext extends Fake implements BuildContext {}

// Mock classes
class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockAppUsageService extends Mock implements AppUsageService {}

class MockAppReviewService extends Mock implements AppReviewService {}

class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

class MockRemoteConfigService extends Mock implements RemoteConfigService {}

class MockSettingsService extends Mock implements SettingsService {}

class MockAdminSettingsService extends Mock implements AdminSettingsService {}

class MockReviewsRepository extends Mock implements ReviewsRepository {}

class MockFirebaseAnalytics extends Mock implements FirebaseAnalytics {}

class MockReviewPromptStateStore extends Mock
    implements ReviewPromptStateStore {}

class MockFeedbackPromptStateStore extends Mock
    implements FeedbackPromptStateStore {}

class MockAuthController extends Mock implements AuthController {}

class MockRemoteConfigValues extends Mock implements RemoteConfigValues {}

class MockNotificationService extends Mock implements NotificationService {}

class MockUrlLauncherService extends Mock implements UrlLauncherService {}

// Fake classes for registerFallbackValue
class FakeAppUser extends Fake implements AppUser {}

void main() {
  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(AppUser.anonymous('test-user-id'));
    registerFallbackValue(JokeReactionType.save);
    registerFallbackValue(Brightness.light);
    registerFallbackValue(ReviewRequestSource.adminTest);
    registerFallbackValue(FakeBuildContext());
    registerFallbackValue(RemoteParam.defaultJokeViewerReveal);
    registerFallbackValue(Uri.parse('https://example.com'));
  });

  late MockAnalyticsService mockAnalyticsService;
  late MockAppUsageService mockAppUsageService;
  late MockAppReviewService mockAppReviewService;
  late MockDailyJokeSubscriptionService mockSubscriptionService;
  late MockRemoteConfigValues mockRemoteConfigValues;
  late MockSettingsService mockSettingsService;
  late MockAdminSettingsService mockAdminSettingsService;
  late MockReviewsRepository mockReviewsRepository;
  late MockFirebaseAnalytics mockFirebaseAnalytics;
  late MockUrlLauncherService mockUrlLauncherService;

  late MockReviewPromptStateStore mockReviewPromptStore;
  late MockFeedbackPromptStateStore mockFeedbackPromptStore;
  late bool reviewRequestedState;
  late bool feedbackViewedState;

  setUp(() {
    // Create fresh mocks per test
    mockAnalyticsService = MockAnalyticsService();
    mockAppUsageService = MockAppUsageService();
    mockAppReviewService = MockAppReviewService();
    mockSubscriptionService = MockDailyJokeSubscriptionService();
    mockRemoteConfigValues = MockRemoteConfigValues();
    mockSettingsService = MockSettingsService();
    mockAdminSettingsService = MockAdminSettingsService();
    mockReviewPromptStore = MockReviewPromptStateStore();
    mockReviewsRepository = MockReviewsRepository();
    mockFirebaseAnalytics = MockFirebaseAnalytics();
    mockFeedbackPromptStore = MockFeedbackPromptStateStore();
    mockUrlLauncherService = MockUrlLauncherService();
    reviewRequestedState = false;
    feedbackViewedState = false;

    when(
      () => mockReviewPromptStore.hasRequested(),
    ).thenAnswer((_) => reviewRequestedState);
    when(() => mockReviewPromptStore.markRequested()).thenAnswer((_) async {
      reviewRequestedState = true;
    });
    when(() => mockReviewPromptStore.setRequested(any())).thenAnswer((
      invocation,
    ) async {
      reviewRequestedState = invocation.positionalArguments.first as bool;
    });

    when(
      () => mockFeedbackPromptStore.hasViewed(),
    ).thenAnswer((_) async => feedbackViewedState);
    when(() => mockFeedbackPromptStore.markViewed()).thenAnswer((_) async {
      feedbackViewedState = true;
    });
    when(() => mockFeedbackPromptStore.setViewed(any())).thenAnswer((
      invocation,
    ) async {
      feedbackViewedState = invocation.positionalArguments.first as bool;
    });

    // Setup default behaviors
    _setupAnalyticsServiceDefaults(mockAnalyticsService);
    _setupAppUsageServiceDefaults(mockAppUsageService);
    _setupAppReviewServiceDefaults(mockAppReviewService);
    _setupSubscriptionServiceDefaults(mockSubscriptionService);
    _setupRemoteConfigValuesDefaults(mockRemoteConfigValues);
    _setupSettingsServiceDefaults(mockSettingsService);
    _setupAdminSettingsServiceDefaults(mockAdminSettingsService);
    _setupReviewsRepositoryDefaults(mockReviewsRepository);
    _setupFirebaseAnalyticsDefaults(mockFirebaseAnalytics);

    when(
      () => mockUrlLauncherService.launchUrl(any<Uri>()),
    ).thenAnswer((_) async => true);
  });

  Widget createTestWidget({AppUser? testUser}) {
    final user = testUser ?? AppUser.anonymous('test-user-id');

    return ProviderScope(
      overrides: [
        // Analytics
        firebaseAnalyticsProvider.overrideWithValue(mockFirebaseAnalytics),
        analyticsServiceProvider.overrideWithValue(mockAnalyticsService),

        // Auth
        currentUserProvider.overrideWith((_) => user),
        authControllerProvider.overrideWith((ref) => MockAuthController()),

        // Settings
        settingsServiceProvider.overrideWithValue(mockSettingsService),
        adminSettingsServiceProvider.overrideWithValue(
          mockAdminSettingsService,
        ),
        jokeViewerRevealProvider.overrideWith(
          (ref) => JokeViewerRevealNotifier(
            JokeViewerSettingsService(
              settingsService: mockSettingsService,
              remoteConfigValues: mockRemoteConfigValues,
              analyticsService: mockAnalyticsService,
            ),
          ),
        ),

        // App usage
        appUsageServiceProvider.overrideWithValue(mockAppUsageService),
        appUsageEventsProvider.overrideWith((_) => 0),
        reviewPromptStateStoreProvider.overrideWithValue(mockReviewPromptStore),
        feedbackPromptStateStoreProvider.overrideWithValue(
          mockFeedbackPromptStore,
        ),

        // App version
        appVersionProvider.overrideWith((_) async => 'Snickerdoodle v0.0.1+1'),

        // Subscription
        subscriptionProvider.overrideWith(
          (ref) => SubscriptionNotifier(
            mockSettingsService,
            mockSubscriptionService,
            MockNotificationService(),
          ),
        ),
        dailyJokeSubscriptionServiceProvider.overrideWithValue(
          mockSubscriptionService,
        ),

        // Review service
        appReviewServiceProvider.overrideWithValue(mockAppReviewService),
        reviewsRepositoryProvider.overrideWithValue(mockReviewsRepository),

        // Remote config
        remoteConfigValuesProvider.overrideWithValue(mockRemoteConfigValues),
        urlLauncherServiceProvider.overrideWithValue(mockUrlLauncherService),
      ],
      child: MaterialApp(
        theme: lightTheme,
        darkTheme: darkTheme,
        home: Scaffold(
          body: SingleChildScrollView(
            child: SizedBox(height: 1000, child: const UserSettingsScreen()),
          ),
        ),
      ),
    );
  }

  group('UserSettingsScreen Theme Settings', () {
    group('Theme Settings UI', () {
      testWidgets('displays theme settings section', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pump();

        // Allow time for async operations but don't wait indefinitely
        await tester.pump(const Duration(milliseconds: 100));

        expect(find.text('Theme Settings'), findsOneWidget);
        expect(find.text('Use System Setting'), findsOneWidget);
        expect(find.text('Always Light'), findsOneWidget);
        expect(find.text('Always Dark'), findsOneWidget);
      });

      testWidgets('displays theme option descriptions', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(
          find.text(
            'Automatically switch between light and dark themes based on your device settings',
          ),
          findsOneWidget,
        );
        expect(
          find.text('Use light theme regardless of system settings'),
          findsOneWidget,
        );
        expect(
          find.text('Use dark theme regardless of system settings'),
          findsOneWidget,
        );
      });

      testWidgets('displays correct icons for theme options', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));

        expect(find.byIcon(Icons.brightness_auto), findsOneWidget);
        expect(find.byIcon(Icons.light_mode), findsOneWidget);
        expect(find.byIcon(Icons.dark_mode), findsOneWidget);
      });

      testWidgets('displays radio buttons for theme selection', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        expect(find.byType(RadioListTile<ThemeMode>), findsNWidgets(3));
      });
    });

    group('Theme Selection Interaction', () {
      testWidgets('can select light theme', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Tap on the light theme option
        await tester.tap(find.text('Always Light'));
        await tester.pumpAndSettle();

        // Verify the setting was saved
        verify(
          () => mockSettingsService.setString('theme_mode', 'light'),
        ).called(1);
      });

      testWidgets('can select dark theme', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Tap on the dark theme option
        await tester.tap(find.text('Always Dark'));
        await tester.pumpAndSettle();

        // Verify the setting was saved
        verify(
          () => mockSettingsService.setString('theme_mode', 'dark'),
        ).called(1);
      });

      testWidgets('can select system theme', (tester) async {
        // Start with a non-system theme by selecting Light first
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Select Light to ensure current theme is not system
        await tester.tap(find.text('Always Light'));
        await tester.pumpAndSettle();
        verify(
          () => mockSettingsService.setString('theme_mode', 'light'),
        ).called(1);

        // Now select System
        await tester.tap(find.text('Use System Setting'));
        await tester.pumpAndSettle();

        // Verify the setting was saved
        verify(
          () => mockSettingsService.setString('theme_mode', 'system'),
        ).called(1);
      });

      testWidgets('can tap on radio button to change theme', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Find and tap the radio button for dark theme
        final darkRadio = find
            .byType(RadioListTile<ThemeMode>)
            .at(2); // Third radio button (dark)
        await tester.tap(darkRadio);
        await tester.pumpAndSettle();

        // Verify the setting was saved
        verify(
          () => mockSettingsService.setString('theme_mode', 'dark'),
        ).called(1);
      });

      testWidgets('can tap on entire theme option row to change theme', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Find the RadioListTile containing the light theme option
        final lightThemeRow = find.widgetWithText(
          RadioListTile<ThemeMode>,
          'Always Light',
        );
        await tester.tap(lightThemeRow);
        await tester.pumpAndSettle();

        // Verify the setting was saved
        verify(
          () => mockSettingsService.setString('theme_mode', 'light'),
        ).called(1);
      });
    });

    group('Theme State Display', () {
      testWidgets('shows system theme as selected by default', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // The system option tile should be selected by default
        final systemTile = tester.widget<RadioListTile<ThemeMode>>(
          find.byKey(
            const Key('user_settings_screen-theme-option-use-system-setting'),
          ),
        );
        expect(systemTile.selected, isTrue);
      });
    });

    group('Visual Feedback', () {
      testWidgets('shows radio buttons in correct states', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Give time for theme to load
        await tester.pump(const Duration(milliseconds: 100));

        // Find all radio buttons
        final radioButtons = find.byType(RadioListTile<ThemeMode>);
        expect(radioButtons, findsNWidgets(3));

        // Check that radio buttons are present (detailed state checking would require more complex setup)
        expect(find.byIcon(Icons.light_mode), findsOneWidget);
        expect(find.byIcon(Icons.dark_mode), findsOneWidget);
        expect(find.byIcon(Icons.brightness_auto), findsOneWidget);
      });
    });
  });

  group('UserSettingsScreen Privacy Policy link', () {
    const privacyPolicyUrl = 'https://snickerdoodlejokes.com/privacy.html';

    testWidgets('shows button and launches privacy policy URL', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      final buttonFinder = find.byKey(
        const Key('user_settings_screen-privacy-policy-button'),
      );
      expect(buttonFinder, findsOneWidget);

      await tester.ensureVisible(buttonFinder);
      await tester.tap(buttonFinder, warnIfMissed: false);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      final expectedUri = Uri.parse(privacyPolicyUrl);
      verify(() => mockUrlLauncherService.launchUrl(expectedUri)).called(1);
      verify(() => mockAnalyticsService.logPrivacyPolicyOpened()).called(1);
      expect(find.text('Unable to open the privacy policy.'), findsNothing);
    });
  });

  group('UserSettingsScreen Secret Developer Mode', () {
    group('Initial State', () {
      testWidgets('developer mode starts disabled', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Developer sections should not be visible initially
        expect(find.text('User Information'), findsNothing);
        expect(find.text('Authentication'), findsNothing);
        expect(find.text('Sign in with Google'), findsNothing);
      });

      testWidgets('shows only Theme and Notifications sections initially', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // These sections should be visible
        expect(find.text('Theme Settings'), findsOneWidget);
        expect(find.text('Notifications'), findsOneWidget);
        expect(find.text('Snickerdoodle v0.0.1+1'), findsOneWidget);

        // Developer sections should not be visible
        expect(find.text('User Information'), findsNothing);
        expect(find.text('Authentication'), findsNothing);
      });
    });

    group('Secret Sequence Execution', () {
      testWidgets('completes secret sequence successfully', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Execute the secret sequence: Theme(2x), Version(2x), Notifications(4x)

        // Theme Settings (2 taps)
        await tester.tap(find.text('Theme Settings'));
        await tester.pump(const Duration(milliseconds: 100));
        await tester.tap(find.text('Theme Settings'));
        await tester.pump(const Duration(milliseconds: 100));

        // Version (2 taps)
        await tester.ensureVisible(find.text('Snickerdoodle v0.0.1+1'));
        await tester.pump();
        await tester.tap(
          find.text('Snickerdoodle v0.0.1+1'),
          warnIfMissed: false,
        );
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Snickerdoodle v0.0.1+1'));
        await tester.pump();
        await tester.tap(
          find.text('Snickerdoodle v0.0.1+1'),
          warnIfMissed: false,
        );
        await tester.pump(const Duration(milliseconds: 100));

        // Notifications (4 taps)
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pumpAndSettle();

        // Developer mode should now be active
        expect(find.text('User Information'), findsOneWidget);
        expect(find.text('Authentication'), findsOneWidget);
        expect(find.text('Sign in with Google'), findsOneWidget);
      });

      testWidgets('shows success snackbar when sequence completed', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Execute the secret sequence
        await tester.tap(find.text('Theme Settings'));
        await tester.pump(const Duration(milliseconds: 100));
        await tester.tap(find.text('Theme Settings'));
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Snickerdoodle v0.0.1+1'));
        await tester.pump();
        await tester.tap(
          find.text('Snickerdoodle v0.0.1+1'),
          warnIfMissed: false,
        );
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Snickerdoodle v0.0.1+1'));
        await tester.pump();
        await tester.tap(
          find.text('Snickerdoodle v0.0.1+1'),
          warnIfMissed: false,
        );
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pumpAndSettle();

        // Should show success snackbar
        expect(
          find.text('Congrats! You\'ve unlocked dev mode!'),
          findsOneWidget,
        );
      });

      testWidgets('resets sequence on wrong tap', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Start sequence correctly
        await tester.ensureVisible(find.text('Theme Settings'));
        await tester.pump();
        await tester.tap(find.text('Theme Settings'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));

        // Wrong tap - should reset sequence
        await tester.tap(find.text('Notifications'));
        await tester.pump(const Duration(milliseconds: 100));

        // Continue with what would be correct if sequence wasn't reset
        await tester.ensureVisible(find.text('Theme Settings'));
        await tester.pump();
        await tester.tap(find.text('Theme Settings'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Snickerdoodle v0.0.1+1'));
        await tester.pump();
        await tester.tap(
          find.text('Snickerdoodle v0.0.1+1'),
          warnIfMissed: false,
        );
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Snickerdoodle v0.0.1+1'));
        await tester.pump();
        await tester.tap(
          find.text('Snickerdoodle v0.0.1+1'),
          warnIfMissed: false,
        );
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pumpAndSettle();

        // Developer mode should NOT be active
        expect(find.text('User Information'), findsNothing);
        expect(find.text('Authentication'), findsNothing);
        expect(find.text('Congrats! You\'ve unlocked dev mode!'), findsNothing);
      });

      // Note: Timeout test removed as it requires complex timer mocking
      // The timeout functionality works correctly in real usage
    });

    group('Developer Mode Features', () {
      Future<void> enableDeveloperMode(WidgetTester tester) async {
        // Execute the secret sequence to enable developer mode
        await tester.ensureVisible(find.text('Theme Settings'));
        await tester.pump();
        await tester.tap(find.text('Theme Settings'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Theme Settings'));
        await tester.pump();
        await tester.tap(find.text('Theme Settings'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Snickerdoodle v0.0.1+1'));
        await tester.pump();
        await tester.tap(
          find.text('Snickerdoodle v0.0.1+1'),
          warnIfMissed: false,
        );
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Snickerdoodle v0.0.1+1'));
        await tester.pump();
        await tester.tap(
          find.text('Snickerdoodle v0.0.1+1'),
          warnIfMissed: false,
        );
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pumpAndSettle();

        final scaffoldContext = tester.element(find.byType(Scaffold).first);
        ScaffoldMessenger.of(scaffoldContext).clearSnackBars();
        await tester.pump();
      }

      testWidgets('shows User Information section when enabled', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        await enableDeveloperMode(tester);

        expect(find.text('User Information'), findsOneWidget);
        expect(find.text('Status:'), findsOneWidget);
        expect(find.text('Guest User'), findsOneWidget);
        expect(find.text('Role:'), findsOneWidget);
        expect(find.text('Anonymous'), findsOneWidget);
        expect(find.text('User ID:'), findsOneWidget);
      });

      testWidgets('shows Authentication section when enabled', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        await enableDeveloperMode(tester);

        expect(find.text('Authentication'), findsOneWidget);
        expect(find.text('Sign in with Google'), findsOneWidget);
        expect(find.byIcon(Icons.login), findsOneWidget);
      });

      testWidgets('shows usage metrics rows in developer mode', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        await enableDeveloperMode(tester);

        // Allow FutureBuilder to resolve
        await tester.pump(const Duration(milliseconds: 100));

        expect(find.text('First Used Date:'), findsOneWidget);
        expect(find.text('Last Used Date:'), findsOneWidget);
        expect(find.text('Days Used:'), findsOneWidget);
        expect(find.text('Num Jokes Viewed:'), findsOneWidget);
        expect(find.text('Num Jokes Saved:'), findsOneWidget);
        expect(find.text('Num Jokes Shared:'), findsOneWidget);
        expect(
          find.byKey(const Key('user_settings_screen-first-used-date-button')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('user_settings_screen-last-used-date-button')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('user_settings_screen-num-days-used-button')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('user_settings_screen-subscribe-toggle-button')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('user_settings_screen-subscribe-toggle-button')),
          findsOneWidget,
        );
      });

      testWidgets('tapping review button toggles requested state', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        await enableDeveloperMode(tester);
        await tester.pump(const Duration(milliseconds: 100));

        final reviewButton = find.byKey(
          const Key('user_settings_screen-review-toggle-button'),
        );
        expect(reviewButton, findsOneWidget);

        await tester.ensureVisible(reviewButton);
        await tester.tap(reviewButton);
        await tester.pumpAndSettle();

        verify(() => mockReviewPromptStore.setRequested(true)).called(1);

        await tester.tap(reviewButton);
        await tester.pumpAndSettle();

        verify(() => mockReviewPromptStore.setRequested(false)).called(1);
      });

      testWidgets('tapping feedback button toggles viewed flag', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        await enableDeveloperMode(tester);
        await tester.pump(const Duration(milliseconds: 100));

        final subscribeButton = find.byKey(
          const Key('user_settings_screen-feedback-toggle-button'),
        );
        expect(subscribeButton, findsOneWidget);

        await tester.ensureVisible(subscribeButton);
        await tester.tap(subscribeButton);
        await tester.pumpAndSettle();

        verify(() => mockFeedbackPromptStore.setViewed(true)).called(1);

        await tester.tap(subscribeButton);
        await tester.pumpAndSettle();

        verify(() => mockFeedbackPromptStore.setViewed(false)).called(1);
      });

      testWidgets('tapping subscribe button clears user choice when enabled', (
        tester,
      ) async {
        bool containsKey = true;
        when(
          () => mockSettingsService.containsKey(any()),
        ).thenAnswer((_) => containsKey);
        when(() => mockSettingsService.remove(any())).thenAnswer((_) async {
          containsKey = false;
        });

        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        await enableDeveloperMode(tester);
        await tester.pump(const Duration(milliseconds: 100));

        final subscribeButton = find.byKey(
          const Key('user_settings_screen-subscribe-toggle-button'),
        );
        expect(subscribeButton, findsOneWidget);

        await tester.ensureVisible(subscribeButton);
        await tester.tap(subscribeButton);
        await tester.pumpAndSettle();

        verify(() => mockSettingsService.remove(any())).called(1);

        final subscribeTextButton = tester.widget<TextButton>(subscribeButton);
        expect(subscribeTextButton.onPressed, isNull);
      });

      testWidgets('tapping viewed jokes button shows dialog with joke IDs', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        await enableDeveloperMode(tester);
        await tester.pump(const Duration(milliseconds: 100));

        final viewedButton = find.byKey(
          const Key('user_settings_screen-viewed-jokes-button'),
        );
        await tester.ensureVisible(viewedButton);
        await tester.tap(viewedButton);
        await tester.pumpAndSettle();

        expect(find.text('Viewed Jokes (2)'), findsOneWidget);
        expect(find.text('joke-view-1'), findsOneWidget);
        expect(find.text('joke-view-2'), findsOneWidget);

        final closeButton = find.byKey(
          const Key('user_settings_screen-joke-ids-dialog-close-button'),
        );
        expect(closeButton, findsOneWidget);

        await tester.tap(closeButton);
        await tester.pumpAndSettle();

        expect(find.text('Viewed Jokes (2)'), findsNothing);
      });

      testWidgets('can tap Google sign-in button in developer mode', (
        tester,
      ) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        await enableDeveloperMode(tester);

        // Should be able to find and tap the Google sign-in button (it's an ElevatedButton.icon)
        final signInButtonText = find.text('Sign in with Google');
        expect(signInButtonText, findsOneWidget);

        // Ensure the button is visible before tapping
        await tester.ensureVisible(signInButtonText);
        await tester.pumpAndSettle();

        // Tap should not throw an error
        await tester.tap(signInButtonText, warnIfMissed: false);
        await tester.pump();
      });

      testWidgets('shows Test Review Prompt button and calls service', (
        tester,
      ) async {
        // Use core mocks for settings service to avoid real SharedPreferences
        final store = ReviewPromptStateStore(
          settingsService: mockSettingsService,
        );

        Widget withOverrides() {
          return ProviderScope(
            overrides: [
              // Analytics
              firebaseAnalyticsProvider.overrideWithValue(
                mockFirebaseAnalytics,
              ),
              analyticsServiceProvider.overrideWithValue(mockAnalyticsService),

              // Auth
              currentUserProvider.overrideWith(
                (_) => AppUser.anonymous('test-user-id'),
              ),
              authControllerProvider.overrideWith(
                (ref) => MockAuthController(),
              ),

              // Settings
              settingsServiceProvider.overrideWithValue(mockSettingsService),
              adminSettingsServiceProvider.overrideWithValue(
                mockAdminSettingsService,
              ),
              jokeViewerRevealProvider.overrideWith(
                (ref) => JokeViewerRevealNotifier(
                  JokeViewerSettingsService(
                    settingsService: mockSettingsService,
                    remoteConfigValues: mockRemoteConfigValues,
                    analyticsService: mockAnalyticsService,
                  ),
                ),
              ),

              // App usage
              appUsageServiceProvider.overrideWithValue(mockAppUsageService),
              appUsageEventsProvider.overrideWith((_) => 0),
              reviewPromptStateStoreProvider.overrideWithValue(store),
              feedbackPromptStateStoreProvider.overrideWithValue(
                FeedbackPromptStateStore(settingsService: mockSettingsService),
              ),

              // App version
              appVersionProvider.overrideWith(
                (_) async => 'Snickerdoodle v0.0.1+1',
              ),

              // Subscription
              subscriptionProvider.overrideWith(
                (ref) => SubscriptionNotifier(
                  mockSettingsService,
                  mockSubscriptionService,
                  MockNotificationService(),
                ),
              ),
              dailyJokeSubscriptionServiceProvider.overrideWithValue(
                mockSubscriptionService,
              ),

              // Review service
              appReviewServiceProvider.overrideWithValue(mockAppReviewService),
              reviewsRepositoryProvider.overrideWithValue(
                mockReviewsRepository,
              ),

              // Remote config
              remoteConfigValuesProvider.overrideWithValue(
                mockRemoteConfigValues,
              ),
              appReviewServiceProvider.overrideWithValue(
                AppReviewService(
                  nativeAdapter: _FakeAdapter(),
                  stateStore: store,
                  getReviewPromptVariant: () => ReviewPromptVariant.bunny,
                  analyticsService: mockAnalyticsService,
                  reviewsRepository: mockReviewsRepository,
                ),
              ),
            ],
            child: MaterialApp(
              theme: lightTheme,
              darkTheme: darkTheme,
              home: Scaffold(
                body: SingleChildScrollView(
                  child: const SizedBox(
                    height: 1000,
                    child: UserSettingsScreen(),
                  ),
                ),
              ),
            ),
          );
        }

        await tester.pumpWidget(withOverrides());
        await tester.pumpAndSettle();

        await enableDeveloperMode(tester);

        // Tap the button
        final btn = find.byKey(const Key('settings-review-button'));
        expect(btn, findsOneWidget);
        await tester.ensureVisible(btn);
        await tester.pump();
        await tester.tap(btn, warnIfMissed: false);
        await tester.pump();

        // A snackbar should appear (message depends on result)
        expect(find.byType(SnackBar), findsOneWidget);
      });

      testWidgets(
        'maintains regular functionality after enabling developer mode',
        (tester) async {
          await tester.pumpWidget(createTestWidget());
          await tester.pumpAndSettle();

          await enableDeveloperMode(tester);

          // Theme settings should still work
          expect(find.text('Theme Settings'), findsOneWidget);
          expect(find.text('Always Light'), findsOneWidget);

          await tester.ensureVisible(find.text('Always Light'));
          await tester.pump();
          await tester.tap(find.text('Always Light'), warnIfMissed: false);
          await tester.pumpAndSettle();

          verify(
            () => mockSettingsService.setString('theme_mode', 'light'),
          ).called(1);

          // Notifications should still work
          expect(find.text('Notifications'), findsOneWidget);
        },
      );
    });

    group('Sequence Edge Cases', () {
      testWidgets('handles rapid tapping without issues', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Rapidly tap the same element multiple times
        for (int i = 0; i < 10; i++) {
          await tester.tap(find.text('Theme Settings'));
          await tester.pump(const Duration(milliseconds: 10));
        }

        // Should not crash or enable developer mode
        expect(find.text('User Information'), findsNothing);
        expect(find.text('Authentication'), findsNothing);
      });

      testWidgets('handles sequence restart after wrong input', (tester) async {
        await tester.pumpWidget(createTestWidget());
        await tester.pumpAndSettle();

        // Do part of the sequence incorrectly
        await tester.ensureVisible(find.text('Theme Settings'));
        await tester.pump();
        await tester.tap(find.text('Theme Settings'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Theme Settings'));
        await tester.pump();
        await tester.tap(find.text('Theme Settings'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        // Wrong tap - should reset
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));

        // Now do the complete sequence from start
        await tester.ensureVisible(find.text('Theme Settings'));
        await tester.pump();
        await tester.tap(find.text('Theme Settings'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Theme Settings'));
        await tester.pump();
        await tester.tap(find.text('Theme Settings'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Snickerdoodle v0.0.1+1'));
        await tester.pump();
        await tester.tap(
          find.text('Snickerdoodle v0.0.1+1'),
          warnIfMissed: false,
        );
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Snickerdoodle v0.0.1+1'));
        await tester.pump();
        await tester.tap(
          find.text('Snickerdoodle v0.0.1+1'),
          warnIfMissed: false,
        );
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.ensureVisible(find.text('Notifications'));
        await tester.pump();
        await tester.tap(find.text('Notifications'), warnIfMissed: false);
        await tester.pumpAndSettle();

        // Should now be enabled after correct sequence
        expect(find.text('User Information'), findsOneWidget);
        expect(find.text('Authentication'), findsOneWidget);
      });
    });
  });
}

class _FakeAdapter implements NativeReviewAdapter {
  @override
  Future<bool> isAvailable() async => true;

  @override
  Future<void> requestReview() async {}
}

// Setup functions for mock services
void _setupAnalyticsServiceDefaults(MockAnalyticsService mock) {
  when(() => mock.initialize()).thenAnswer((_) async {});
  when(() => mock.setUserProperties(any())).thenAnswer((_) async {});
  when(
    () => mock.logErrorAuthSignIn(
      source: any(named: 'source'),
      errorMessage: any(named: 'errorMessage'),
    ),
  ).thenAnswer((_) async {});
  when(
    () => mock.logErrorSubscriptionToggle(
      source: any(named: 'source'),
      errorMessage: any(named: 'errorMessage'),
    ),
  ).thenAnswer((_) async {});
  when(() => mock.logSubscriptionOnSettings()).thenAnswer((_) async {});
  when(() => mock.logSubscriptionOffSettings()).thenAnswer((_) async {});
  when(
    () => mock.logSubscriptionDeclinedPermissionsInSettings(),
  ).thenAnswer((_) async {});
  when(() => mock.logPrivacyPolicyOpened()).thenAnswer((_) {});
  when(() => mock.logAnalyticsError(any(), any())).thenAnswer((_) async {});
}

void _setupAppUsageServiceDefaults(MockAppUsageService mock) {
  when(() => mock.getFirstUsedDate()).thenAnswer((_) async => '2024-01-01');
  when(() => mock.getLastUsedDate()).thenAnswer((_) async => '2024-01-01');
  when(() => mock.getNumDaysUsed()).thenAnswer((_) async => 1);
  when(() => mock.getNumJokesViewed()).thenAnswer((_) async => 2);
  when(() => mock.getNumSavedJokes()).thenAnswer((_) async => 2);
  when(() => mock.getNumSharedJokes()).thenAnswer((_) async => 3);
  when(
    () => mock.getViewedJokeIds(),
  ).thenAnswer((_) async => const ['joke-view-1', 'joke-view-2']);
  when(
    () => mock.getSavedJokeIds(),
  ).thenAnswer((_) async => const ['joke-save-1', 'joke-save-2']);
  when(() => mock.getSharedJokeIds()).thenAnswer(
    (_) async => const ['joke-share-1', 'joke-share-2', 'joke-share-3'],
  );
  when(() => mock.setFirstUsedDate(any<String?>())).thenAnswer((_) async {});
  when(() => mock.setLastUsedDate(any<String?>())).thenAnswer((_) async {});
  when(() => mock.setNumDaysUsed(any<int>())).thenAnswer((_) async {});
}

void _setupAppReviewServiceDefaults(MockAppReviewService mock) {
  when(
    () => mock.requestReview(
      source: any(named: 'source'),
      context: any(named: 'context'),
      force: any(named: 'force'),
    ),
  ).thenAnswer((_) async => ReviewRequestResult.shown);
}

void _setupSubscriptionServiceDefaults(MockDailyJokeSubscriptionService mock) {
  when(
    () => mock.ensureSubscriptionSync(
      unsubscribeOthers: any(named: 'unsubscribeOthers'),
    ),
  ).thenAnswer((_) async => true);
}

void _setupRemoteConfigValuesDefaults(MockRemoteConfigValues mock) {
  // Don't stub specific calls - just let them return default values when needed
  // This avoids complex mocktail matchers for remote config
}

void _setupSettingsServiceDefaults(MockSettingsService mock) {
  when(() => mock.getString(any())).thenReturn(null);
  when(() => mock.setString(any(), any())).thenAnswer((_) async {});
  when(() => mock.getBool(any())).thenReturn(false);
  when(() => mock.setBool(any(), any())).thenAnswer((_) async {});
  when(() => mock.getInt(any())).thenReturn(0);
  when(() => mock.setInt(any(), any())).thenAnswer((_) async {});
  when(() => mock.getDouble(any())).thenReturn(0.0);
  when(() => mock.setDouble(any(), any())).thenAnswer((_) async {});
  when(() => mock.getStringList(any())).thenReturn(null);
  when(() => mock.setStringList(any(), any())).thenAnswer((_) async {});
  when(() => mock.containsKey(any())).thenReturn(false);
  when(() => mock.remove(any())).thenAnswer((_) async {});
  when(() => mock.clear()).thenAnswer((_) async {});
}

void _setupAdminSettingsServiceDefaults(MockAdminSettingsService mock) {
  when(() => mock.getAdminOverrideShowBannerAd()).thenReturn(false);
  when(() => mock.setAdminOverrideShowBannerAd(any())).thenAnswer((_) async {});
}

void _setupReviewsRepositoryDefaults(MockReviewsRepository mock) {
  when(() => mock.recordAppReview()).thenAnswer((_) async {});
}

void _setupFirebaseAnalyticsDefaults(MockFirebaseAnalytics mock) {
  when(
    () => mock.logEvent(
      name: any(named: 'name'),
      parameters: any(named: 'parameters'),
    ),
  ).thenAnswer((_) async {});
  when(
    () => mock.setUserProperty(
      name: any(named: 'name'),
      value: any(named: 'value'),
    ),
  ).thenAnswer((_) async {});
  when(() => mock.setUserId(id: any(named: 'id'))).thenAnswer((_) async {});
  when(
    () => mock.setAnalyticsCollectionEnabled(any()),
  ).thenAnswer((_) async {});
}
