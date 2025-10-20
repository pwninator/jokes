import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/features/settings/presentation/user_settings_screen.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';
import 'package:snickerdoodle/src/features/auth/data/models/app_user.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/auth/application/auth_providers.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:mocktail/mocktail.dart';

// Mock classes
class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockSettingsService extends Mock implements SettingsService {}

class MockFirebaseAuth extends Mock implements FirebaseAuth {}

class MockGoogleSignIn extends Mock implements GoogleSignIn {}

class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

class MockNotificationService extends Mock implements NotificationService {}

// Test implementations
class _FakeRemoteValues implements RemoteConfigValues {
  final Map<RemoteParam, Object> _map;
  _FakeRemoteValues(this._map);
  @override
  int getInt(RemoteParam param) => _map[param] as int;
  @override
  bool getBool(RemoteParam param) => _map[param] as bool;
  @override
  double getDouble(RemoteParam param) => _map[param] as double;
  @override
  String getString(RemoteParam param) => _map[param] as String;
  @override
  T getEnum<T>(RemoteParam param) {
    final descriptor = remoteParams[param]!;
    return (descriptor.enumDefault ?? '') as T;
  }
}

// Helper methods
AppUser get anonymousUser => AppUser.anonymous('anonymous_user_id');

List<Override> getAllMockOverrides({AppUser? testUser}) {
  final mockAnalyticsService = MockAnalyticsService();
  final mockSettingsService = MockSettingsService();
  final mockFirebaseAuth = MockFirebaseAuth();
  final mockGoogleSignIn = MockGoogleSignIn();
  final mockSubscriptionService = MockDailyJokeSubscriptionService();
  final mockNotificationService = MockNotificationService();

  // Setup default behaviors for mocks
  when(() => mockAnalyticsService.initialize()).thenAnswer((_) async {});
  when(
    () => mockAnalyticsService.setUserProperties(any()),
  ).thenAnswer((_) async {});

  when(() => mockSettingsService.getBool(any())).thenReturn(null);
  when(
    () => mockSettingsService.setBool(any(), any()),
  ).thenAnswer((_) async {});
  when(() => mockSettingsService.getString(any())).thenReturn(null);
  when(
    () => mockSettingsService.setString(any(), any()),
  ).thenAnswer((_) async {});
  when(() => mockSettingsService.getInt(any())).thenReturn(null);
  when(() => mockSettingsService.setInt(any(), any())).thenAnswer((_) async {});
  when(() => mockSettingsService.getDouble(any())).thenReturn(null);
  when(
    () => mockSettingsService.setDouble(any(), any()),
  ).thenAnswer((_) async {});
  when(() => mockSettingsService.getStringList(any())).thenReturn(null);
  when(
    () => mockSettingsService.setStringList(any(), any()),
  ).thenAnswer((_) async {});
  when(() => mockSettingsService.containsKey(any())).thenReturn(false);
  when(() => mockSettingsService.remove(any())).thenAnswer((_) async {});
  when(() => mockSettingsService.clear()).thenAnswer((_) async {});

  when(
    () => mockFirebaseAuth.authStateChanges(),
  ).thenAnswer((_) => Stream<User?>.value(null));
  when(() => mockGoogleSignIn.signIn()).thenAnswer((_) async => null);

  when(
    () => mockSubscriptionService.ensureSubscriptionSync(
      unsubscribeOthers: any(named: 'unsubscribeOthers'),
    ),
  ).thenAnswer((_) async => true);
  when(() => mockNotificationService.initialize()).thenAnswer((_) async {});

  return [
    analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
    settingsServiceProvider.overrideWithValue(mockSettingsService),
    firebaseAuthProvider.overrideWithValue(mockFirebaseAuth),
    googleSignInProvider.overrideWithValue(mockGoogleSignIn),
    currentUserProvider.overrideWith((ref) => testUser ?? anonymousUser),
    dailyJokeSubscriptionServiceProvider.overrideWithValue(
      mockSubscriptionService,
    ),
    notificationServiceProvider.overrideWithValue(mockNotificationService),
  ];
}

void registerAnalyticsFallbackValues() {
  registerFallbackValue(JokeViewerMode.reveal);
  registerFallbackValue(Brightness.light);
  registerFallbackValue(RemoteParam.defaultJokeViewerReveal);
}

Widget _wrap(Widget child, {required RemoteConfigValues rcValues}) {
  return ProviderScope(
    overrides: [
      ...getAllMockOverrides(testUser: anonymousUser),
      remoteConfigValuesProvider.overrideWithValue(rcValues),
    ],
    child: MaterialApp(home: Scaffold(body: child)),
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() {
    registerAnalyticsFallbackValues();
  });

  group('Joke Viewer setting UI', () {
    testWidgets('defaults from RC=false to show both (toggle off)', (
      tester,
    ) async {
      SharedPreferences.setMockInitialValues({});

      await tester.pumpWidget(
        _wrap(
          const UserSettingsScreen(),
          rcValues: _FakeRemoteValues({
            RemoteParam.defaultJokeViewerReveal: false,
          }),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Joke Viewer'), findsOneWidget);
      expect(find.text('Always show both images'), findsOneWidget);

      // Toggle on -> reveal
      await tester.tap(find.byKey(const Key('joke-viewer-toggle')));
      await tester.pumpAndSettle();
      expect(find.text('Hide punchline image for a surprise!'), findsOneWidget);
    });

    testWidgets('defaults from RC=true to reveal (toggle on)', (tester) async {
      SharedPreferences.setMockInitialValues({});

      await tester.pumpWidget(
        _wrap(
          const UserSettingsScreen(),
          rcValues: _FakeRemoteValues({
            RemoteParam.defaultJokeViewerReveal: true,
          }),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Hide punchline image for a surprise!'), findsOneWidget);

      // Toggle off -> both
      await tester.tap(find.byKey(const Key('joke-viewer-toggle')));
      await tester.pumpAndSettle();
      expect(find.text('Always show both images'), findsOneWidget);
    });
  });
}
