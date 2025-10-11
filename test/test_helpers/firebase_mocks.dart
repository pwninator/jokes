// ignore_for_file: subtype_of_sealed_class
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_population_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_search_result.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

import 'core_mocks.dart';

// Mock classes for Firebase services
class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class MockFirebaseAnalytics extends Mock implements FirebaseAnalytics {}

class MockFirebaseFirestore extends Mock implements FirebaseFirestore {}

class MockCollectionReference extends Mock
    implements CollectionReference<Map<String, dynamic>> {}

class MockDocumentReference extends Mock
    implements DocumentReference<Map<String, dynamic>> {}

class MockQuery<T> extends Mock implements Query<T> {}

class MockQueryDocumentSnapshot<T extends Object?> extends Mock
    implements QueryDocumentSnapshot<T> {}

class MockDocumentSnapshot extends Mock
    implements DocumentSnapshot<Map<String, dynamic>> {}

class MockFirebaseMessaging extends Mock implements FirebaseMessaging {}

/// Firebase-specific service mocks for unit tests
class FirebaseMocks {
  static MockJokeCloudFunctionService? _mockCloudFunctionService;
  static MockFirebaseAnalytics? _mockFirebaseAnalytics;
  static MockFirebaseFirestore? _mockFirebaseFirestore;
  static MockFirebaseMessaging? _mockFirebaseMessaging;

  /// Get or create mock cloud function service
  static MockJokeCloudFunctionService get mockCloudFunctionService {
    _mockCloudFunctionService ??= MockJokeCloudFunctionService();
    _setupCloudFunctionServiceDefaults(_mockCloudFunctionService!);
    return _mockCloudFunctionService!;
  }

  /// Get or create mock Firebase Analytics
  static MockFirebaseAnalytics get mockFirebaseAnalytics {
    _mockFirebaseAnalytics ??= MockFirebaseAnalytics();
    _setupFirebaseAnalyticsDefaults(_mockFirebaseAnalytics!);
    return _mockFirebaseAnalytics!;
  }

  /// Get or create mock Firebase Firestore
  static MockFirebaseFirestore get mockFirebaseFirestore {
    _mockFirebaseFirestore ??= MockFirebaseFirestore();
    _setupFirebaseFirestoreDefaults(_mockFirebaseFirestore!);
    return _mockFirebaseFirestore!;
  }

  /// Get or create mock Firebase Messaging
  static MockFirebaseMessaging get mockFirebaseMessaging {
    _mockFirebaseMessaging ??= MockFirebaseMessaging();
    _setupFirebaseMessagingDefaults(_mockFirebaseMessaging!);
    return _mockFirebaseMessaging!;
  }

  /// Reset all Firebase mocks (call this in setUp if needed)
  static void reset() {
    _mockCloudFunctionService = null;
    _mockFirebaseAnalytics = null;
    _mockFirebaseFirestore = null;
    _mockFirebaseMessaging = null;
  }

  /// Get Firebase-specific provider overrides
  static List<Override> getFirebaseProviderOverrides({
    List<Override> additionalOverrides = const [],
  }) {
    return [
      // Mock settings service to satisfy synchronous SettingsService consumers
      settingsServiceProvider.overrideWithValue(CoreMocks.mockSettingsService),
      // Mock Firestore
      firebaseFirestoreProvider.overrideWithValue(mockFirebaseFirestore),

      // Force connectivity to "online" in tests to avoid platform plugin calls
      isOnlineProvider.overrideWith((ref) async* {
        yield true;
      }),

      // Mock cloud function service
      jokeCloudFunctionServiceProvider.overrideWithValue(
        mockCloudFunctionService,
      ),

      // Mock Firebase Analytics
      firebaseAnalyticsProvider.overrideWithValue(mockFirebaseAnalytics),

      // Mock joke population provider to avoid Firebase calls
      jokePopulationProvider.overrideWith(
        (ref) => TestJokePopulationNotifier(),
      ),

      // Add any additional overrides
      // Remote Config: override values to avoid platform calls in tests
      remoteConfigValuesProvider.overrideWithValue(_TestRemoteConfigValues()),

      // No-op performance service to avoid calling Firebase in tests
      performanceServiceProvider.overrideWithValue(
        _TestNoopPerformanceService(),
      ),
      // Additional overrides after base ones so tests can replace any of these
      ...additionalOverrides,
    ];
  }

  /// Get or create mock SettingsService (use CoreMocks)
  static MockSettingsService get mockSettingsService =>
      CoreMocks.mockSettingsService;

  static void _setupFirebaseAnalyticsDefaults(MockFirebaseAnalytics mock) {
    // Setup default behaviors that won't throw
    when(() => mock.setDefaultEventParameters(any())).thenAnswer((_) async {});
    when(() => mock.setUserId(id: any(named: 'id'))).thenAnswer((_) async {});
    when(
      () => mock.setUserProperty(
        name: any(named: 'name'),
        value: any(named: 'value'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => mock.logEvent(
        name: any(named: 'name'),
        parameters: any(named: 'parameters'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => mock.logScreenView(
        screenName: any(named: 'screenName'),
        screenClass: any(named: 'screenClass'),
        parameters: any(named: 'parameters'),
      ),
    ).thenAnswer((_) async {});
  }

  static void _setupCloudFunctionServiceDefaults(
    MockJokeCloudFunctionService mock,
  ) {
    // Needed for mocktail when matching named args of type MatchMode
    registerFallbackValue(MatchMode.tight);
    // Needed for mocktail when matching named args of type SearchScope
    registerFallbackValue(SearchScope.userJokeSearch);
    // Needed for mocktail when matching named args of type SearchLabel
    registerFallbackValue(SearchLabel.none);
    // Setup default behaviors that won't throw
    when(
      () => mock.createJokeWithResponse(
        setupText: any(named: 'setupText'),
        punchlineText: any(named: 'punchlineText'),
        adminOwned: any(named: 'adminOwned'),
        setupImageUrl: any(named: 'setupImageUrl'),
        punchlineImageUrl: any(named: 'punchlineImageUrl'),
      ),
    ).thenAnswer((_) async => {'success': true, 'joke_id': 'test-id'});

    when(
      () => mock.populateJoke(
        any(),
        imagesOnly: any(named: 'imagesOnly'),
        additionalParams: any(named: 'additionalParams'),
      ),
    ).thenAnswer((_) async => {'success': true, 'data': 'populated'});

    when(
      () => mock.critiqueJokes(
        instructions: any(named: 'instructions'),
        additionalParameters: any(named: 'additionalParameters'),
      ),
    ).thenAnswer(
      (_) async => {
        'success': true,
        'data': {'jokes': []},
      },
    );

    // Default searchJokes returns empty list to avoid network calls during tests
    when(
      () => mock.searchJokes(
        searchQuery: any(named: 'searchQuery'),
        maxResults: any(named: 'maxResults'),
        publicOnly: any(named: 'publicOnly'),
        matchMode: any(named: 'matchMode'),
        scope: any(named: 'scope'),
        label: any(named: 'label'),
      ),
    ).thenAnswer((_) async => <JokeSearchResult>[]);
  }

  static void _setupFirebaseFirestoreDefaults(MockFirebaseFirestore mock) {
    final mockCollection = MockCollectionReference();
    when(() => mock.collection('jokes')).thenReturn(mockCollection);

    final mockQuery = MockQuery<Map<String, dynamic>>();
    when(
      () => mockCollection.where(any, whereIn: any(named: 'whereIn')),
    ).thenReturn(mockQuery);

    final mockQuerySnapshot = MockQuerySnapshot();
    when(() => mockQuery.get(any())).thenAnswer((_) async => mockQuerySnapshot);

    when(
      () => mockCollection.get(any()),
    ).thenAnswer((_) async => MockQuerySnapshot());

    final mockDocRef = MockDocumentReference();
    when(() => mockCollection.doc(any())).thenReturn(mockDocRef);
    final mockDocSnapshot = MockDocumentSnapshot();
    when(() => mockDocRef.get(any())).thenAnswer((_) async => mockDocSnapshot);
    when(() => mockDocSnapshot.exists).thenReturn(false);
  }

  static void _setupFirebaseMessagingDefaults(MockFirebaseMessaging mock) {
    // Setup default behaviors for Firebase Messaging
    when(() => mock.subscribeToTopic(any())).thenAnswer((_) async {});
    when(() => mock.unsubscribeFromTopic(any())).thenAnswer((_) async {});
    when(() => mock.getToken()).thenAnswer((_) async => 'mock_fcm_token');
    when(() => mock.requestPermission()).thenAnswer(
      (_) async => const NotificationSettings(
        authorizationStatus: AuthorizationStatus.authorized,
        alert: AppleNotificationSetting.enabled,
        announcement: AppleNotificationSetting.enabled,
        badge: AppleNotificationSetting.enabled,
        carPlay: AppleNotificationSetting.enabled,
        criticalAlert: AppleNotificationSetting.enabled,
        lockScreen: AppleNotificationSetting.enabled,
        notificationCenter: AppleNotificationSetting.enabled,
        showPreviews: AppleShowPreviewSetting.always,
        sound: AppleNotificationSetting.enabled,
        timeSensitive: AppleNotificationSetting.enabled,
        providesAppNotificationSettings: AppleNotificationSetting.enabled,
      ),
    );
  }
}

class MockQuerySnapshot extends Mock
    implements QuerySnapshot<Map<String, dynamic>> {
  @override
  List<QueryDocumentSnapshot<Map<String, dynamic>>> get docs => [];
}

class _TestNoopPerformanceService implements PerformanceService {
  @override
  void startNamedTrace({
    required TraceName name,
    String? key,
    Map<String, String>? attributes,
  }) {}

  @override
  void putNamedTraceAttributes({
    required TraceName name,
    String? key,
    required Map<String, String> attributes,
  }) {}

  @override
  void stopNamedTrace({required TraceName name, String? key}) {}

  @override
  void dropNamedTrace({required TraceName name, String? key}) {}
}

class _TestRemoteConfigValues implements RemoteConfigValues {
  @override
  bool getBool(RemoteParam param) {
    if (param == RemoteParam.defaultJokeViewerReveal) {
      return true;
    }
    return false;
  }

  @override
  double getDouble(RemoteParam param) => 0;

  @override
  int getInt(RemoteParam param) {
    final descriptor = remoteParams[param]!;
    return descriptor.defaultInt ?? 0;
  }

  @override
  String getString(RemoteParam param) => '';

  @override
  T getEnum<T>(RemoteParam param) {
    final descriptor = remoteParams[param]!;
    return (descriptor.enumDefault ?? '') as T;
  }
}

/// Test joke population notifier that doesn't require Firebase
/// Maintains stable state for testing - doesn't actually populate
class TestJokePopulationNotifier extends JokePopulationNotifier {
  TestJokePopulationNotifier() : super(FirebaseMocks.mockCloudFunctionService);

  @override
  Future<bool> populateJoke(
    String jokeId, {
    bool imagesOnly = false,
    Map<String, dynamic>? additionalParams,
  }) async {
    // Don't change state to avoid timing issues in tests
    // Just return success
    return true;
  }

  @override
  void clearError() {
    state = state.copyWith(error: null);
  }

  @override
  bool isJokePopulating(String jokeId) {
    // Always return false for stable testing
    return false;
  }
}
