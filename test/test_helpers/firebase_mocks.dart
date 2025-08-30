// ignore_for_file: subtype_of_sealed_class
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

// Mock classes for Firebase services
class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class MockFirebaseAnalytics extends Mock implements FirebaseAnalytics {}

class MockFirebaseFirestore extends Mock implements FirebaseFirestore {}

class MockCollectionReference extends Mock implements CollectionReference {}

class MockDocumentReference extends Mock implements DocumentReference {}

/// Firebase-specific service mocks for unit tests
class FirebaseMocks {
  static MockJokeCloudFunctionService? _mockCloudFunctionService;
  static MockFirebaseAnalytics? _mockFirebaseAnalytics;
  static MockFirebaseFirestore? _mockFirebaseFirestore;

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

  /// Reset all Firebase mocks (call this in setUp if needed)
  static void reset() {
    _mockCloudFunctionService = null;
    _mockFirebaseAnalytics = null;
    _mockFirebaseFirestore = null;
  }

  /// Get Firebase-specific provider overrides
  static List<Override> getFirebaseProviderOverrides({
    List<Override> additionalOverrides = const [],
  }) {
    return [
      // Mock Firestore
      firebaseFirestoreProvider.overrideWithValue(mockFirebaseFirestore),

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
      ...additionalOverrides,
    ];
  }

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
  }

  static void _setupCloudFunctionServiceDefaults(
    MockJokeCloudFunctionService mock,
  ) {
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
  }

  static void _setupFirebaseFirestoreDefaults(MockFirebaseFirestore mock) {
    // Basic mock setup - methods will be mocked as needed in individual tests
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
