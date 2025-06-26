import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

// Mock classes for Firebase services
class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

/// Firebase-specific service mocks for unit tests
class FirebaseMocks {
  static MockJokeCloudFunctionService? _mockCloudFunctionService;

  /// Get or create mock cloud function service
  static MockJokeCloudFunctionService get mockCloudFunctionService {
    _mockCloudFunctionService ??= MockJokeCloudFunctionService();
    _setupCloudFunctionServiceDefaults(_mockCloudFunctionService!);
    return _mockCloudFunctionService!;
  }

  /// Reset all Firebase mocks (call this in setUp if needed)
  static void reset() {
    _mockCloudFunctionService = null;
  }

  /// Get Firebase-specific provider overrides
  static List<Override> getFirebaseProviderOverrides({
    List<Override> additionalOverrides = const [],
  }) {
    return [
      // Mock cloud function service
      jokeCloudFunctionServiceProvider.overrideWithValue(
        mockCloudFunctionService,
      ),

      // Mock joke population provider to avoid Firebase calls
      jokePopulationProvider.overrideWith(
        (ref) => TestJokePopulationNotifier(),
      ),

      // Add any additional overrides
      ...additionalOverrides,
    ];
  }

  static void _setupCloudFunctionServiceDefaults(
    MockJokeCloudFunctionService mock,
  ) {
    // Setup default behaviors that won't throw
    when(
      () => mock.createJoke(
        setupText: any(named: 'setupText'),
        punchlineText: any(named: 'punchlineText'),
        setupImageUrl: any(named: 'setupImageUrl'),
        punchlineImageUrl: any(named: 'punchlineImageUrl'),
      ),
    ).thenAnswer((_) async => true);

    when(
      () => mock.createJokeWithResponse(
        setupText: any(named: 'setupText'),
        punchlineText: any(named: 'punchlineText'),
        setupImageUrl: any(named: 'setupImageUrl'),
        punchlineImageUrl: any(named: 'punchlineImageUrl'),
      ),
    ).thenAnswer((_) async => {'success': true, 'joke_id': 'test-id'});

    when(
      () => mock.populateJoke(any()),
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
}

/// Test joke population notifier that doesn't require Firebase
/// Maintains stable state for testing - doesn't actually populate
class TestJokePopulationNotifier extends JokePopulationNotifier {
  TestJokePopulationNotifier() : super(FirebaseMocks.mockCloudFunctionService);

  @override
  Future<bool> populateJoke(String jokeId) async {
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
