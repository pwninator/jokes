import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

// Mock classes using mocktail
class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

class MockImageService extends Mock implements ImageService {}

/// Common Firebase service mocks for all unit tests
class FirebaseMocks {
  static MockJokeCloudFunctionService? _mockCloudFunctionService;
  static MockImageService? _mockImageService;

  /// Get or create mock cloud function service
  static MockJokeCloudFunctionService get mockCloudFunctionService {
    _mockCloudFunctionService ??= MockJokeCloudFunctionService();
    _setupCloudFunctionServiceDefaults(_mockCloudFunctionService!);
    return _mockCloudFunctionService!;
  }

  /// Get or create mock image service
  static MockImageService get mockImageService {
    _mockImageService ??= MockImageService();
    _setupImageServiceDefaults(_mockImageService!);
    return _mockImageService!;
  }

  /// Reset all mocks (call this in setUp if needed)
  static void reset() {
    _mockCloudFunctionService = null;
    _mockImageService = null;
  }

  /// Get standard provider overrides for Firebase services
  static List<Override> getFirebaseProviderOverrides({
    List<Override> additionalOverrides = const [],
  }) {
    return [
      // Mock cloud function service
      jokeCloudFunctionServiceProvider.overrideWithValue(
        mockCloudFunctionService,
      ),

      // Mock image service
      imageServiceProvider.overrideWithValue(mockImageService),

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

  static void _setupImageServiceDefaults(MockImageService mock) {
    // Setup default behaviors that won't throw
    when(() => mock.isValidImageUrl(any())).thenReturn(true);
    when(() => mock.processImageUrl(any())).thenAnswer((invocation) {
      final url = invocation.positionalArguments[0] as String?;
      return url ?? 'https://example.com/default.jpg';
    });
    when(() => mock.getThumbnailUrl(any())).thenAnswer((invocation) {
      final url = invocation.positionalArguments[0] as String?;
      return url ?? 'https://example.com/default-thumb.jpg';
    });
    when(() => mock.getFullSizeUrl(any())).thenAnswer((invocation) {
      final url = invocation.positionalArguments[0] as String?;
      return url ?? 'https://example.com/default-full.jpg';
    });
    when(() => mock.clearCache()).thenAnswer((_) async {});
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
