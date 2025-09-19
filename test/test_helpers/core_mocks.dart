import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/providers/app_version_provider.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/providers/shared_preferences_provider.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/feedback_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

// Mock classes for core services
class MockImageService extends Mock implements ImageService {}

class MockSettingsService extends Mock implements SettingsService {}

class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

class MockFeedbackService extends Mock implements FeedbackService {}

class MockSharedPreferences extends Mock implements SharedPreferences {}

/// Core service mocks for unit tests
class CoreMocks {
  static MockImageService? _mockImageService;
  static MockSettingsService? _mockSettingsService;
  static MockDailyJokeSubscriptionService? _mockSubscriptionService;
  static SharedPreferences? _mockSharedPreferences;

  /// Get or create mock image service
  static MockImageService get mockImageService {
    _mockImageService ??= MockImageService();
    _setupImageServiceDefaults(_mockImageService!);
    return _mockImageService!;
  }

  /// Get or create mock settings service
  static MockSettingsService get mockSettingsService {
    _mockSettingsService ??= MockSettingsService();
    _setupSettingsServiceDefaults(_mockSettingsService!);
    return _mockSettingsService!;
  }

  /// Get or create mock subscription service (FCM sync only)
  static MockDailyJokeSubscriptionService get mockSubscriptionService {
    _mockSubscriptionService ??= MockDailyJokeSubscriptionService();
    _setupSubscriptionServiceDefaults(_mockSubscriptionService!);
    return _mockSubscriptionService!;
  }

  /// Get or create mock SharedPreferences
  static Future<SharedPreferences> get mockSharedPreferences async {
    if (_mockSharedPreferences == null) {
      SharedPreferences.setMockInitialValues({});
      _mockSharedPreferences = await SharedPreferences.getInstance();
    }
    return _mockSharedPreferences!;
  }

  /// Reset all core mocks (call this in setUp if needed)
  static void reset() {
    _mockImageService = null;
    _mockSettingsService = null;
    _mockSubscriptionService = null;
    _mockSharedPreferences = null;
  }

  /// Get core service provider overrides (synchronous version for simple tests)
  static List<Override> getCoreProviderOverrides({
    List<Override> additionalOverrides = const [],
  }) {
    // For synchronous tests, we need to provide a mock SharedPreferences directly
    // to avoid the async loading issue
    final mockSharedPrefs = MockSharedPreferences();

    // Set up basic mock behavior
    when(
      () => mockSharedPrefs.getBool('daily_jokes_subscribed'),
    ).thenReturn(false);
    when(
      () => mockSharedPrefs.getInt('daily_jokes_subscribed_hour'),
    ).thenReturn(9);
    when(
      () => mockSharedPrefs.containsKey('daily_jokes_subscribed'),
    ).thenReturn(false);
    when(
      () => mockSharedPrefs.setBool(any(), any()),
    ).thenAnswer((_) async => true);
    when(
      () => mockSharedPrefs.setInt(any(), any()),
    ).thenAnswer((_) async => true);

    return [
      // Mock image service
      imageServiceProvider.overrideWithValue(mockImageService),

      // Mock settings service
      settingsServiceProvider.overrideWithValue(mockSettingsService),

      // Mock subscription service (FCM sync only)
      dailyJokeSubscriptionServiceProvider.overrideWithValue(
        mockSubscriptionService,
      ),

      // Override SharedPreferences providers directly
      sharedPreferencesInstanceProvider.overrideWithValue(mockSharedPrefs),
      sharedPreferencesProvider.overrideWith((_) async => mockSharedPrefs),

      // Mock app version provider
      appVersionProvider.overrideWith((_) async => 'Snickerdoodle v0.0.1+1'),

      // Include additional overrides
      ...additionalOverrides,
    ];
  }

  /// Get core service provider overrides (async version for complex tests)
  static Future<List<Override>> getCoreProviderOverridesAsync({
    List<Override> additionalOverrides = const [],
  }) async {
    // Set up mock SharedPreferences with proper async loading
    SharedPreferences.setMockInitialValues({
      'daily_jokes_subscribed': false,
      'daily_jokes_subscribed_hour': 9,
    });
    final sharedPreferences = await SharedPreferences.getInstance();

    return [
      // Mock image service
      imageServiceProvider.overrideWithValue(mockImageService),

      // Mock settings service
      settingsServiceProvider.overrideWithValue(mockSettingsService),

      // Mock subscription service (FCM sync only)
      dailyJokeSubscriptionServiceProvider.overrideWithValue(
        mockSubscriptionService,
      ),

      // Override SharedPreferences providers with real instances
      sharedPreferencesInstanceProvider.overrideWithValue(sharedPreferences),
      sharedPreferencesProvider.overrideWith((_) async => sharedPreferences),

      // Mock app version provider
      appVersionProvider.overrideWith((_) async => 'Test App v1.0.0'),

      // Include additional overrides
      ...additionalOverrides,
    ];
  }

  /// Set up mock SharedPreferences with initial values
  static void setupMockSharedPreferences([Map<String, Object>? values]) {
    SharedPreferences.setMockInitialValues(values ?? {});
    _mockSharedPreferences = null; // Reset to force recreation
  }

  /// Create optimized image URLs for testing
  static const String transparentImageDataUrl =
      'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';

  static void _setupImageServiceDefaults(MockImageService mock) {
    // Setup default behaviors that won't throw
    when(() => mock.isValidImageUrl(any())).thenReturn(true);
    when(() => mock.processImageUrl(any())).thenAnswer((invocation) {
      final url = invocation.positionalArguments[0] as String?;
      return url ?? transparentImageDataUrl;
    });
    when(
      () => mock.processImageUrl(
        any(),
        width: any(named: 'width'),
        height: any(named: 'height'),
        quality: any(named: 'quality'),
      ),
    ).thenAnswer((invocation) {
      final url = invocation.positionalArguments[0] as String?;
      return url ?? transparentImageDataUrl;
    });
    when(() => mock.getThumbnailUrl(any())).thenAnswer((invocation) {
      final url = invocation.positionalArguments[0] as String?;
      return url ?? transparentImageDataUrl;
    });
    when(
      () => mock.getThumbnailUrl(any(), size: any(named: 'size')),
    ).thenAnswer((invocation) {
      final url = invocation.positionalArguments[0] as String?;
      return url ?? transparentImageDataUrl;
    });
    when(() => mock.getFullSizeUrl(any())).thenAnswer((invocation) {
      final url = invocation.positionalArguments[0] as String?;
      return url ?? transparentImageDataUrl;
    });
    when(() => mock.clearCache()).thenAnswer((_) async {});
  }

  static void _setupSettingsServiceDefaults(MockSettingsService mock) {
    // Setup default behaviors for settings
    when(() => mock.getString(any())).thenAnswer((_) async => null);
    when(() => mock.setString(any(), any())).thenAnswer((_) async => {});
    when(() => mock.getBool(any())).thenAnswer((_) async => null);
    when(() => mock.setBool(any(), any())).thenAnswer((_) async => {});
    when(() => mock.getInt(any())).thenAnswer((_) async => null);
    when(() => mock.setInt(any(), any())).thenAnswer((_) async => {});
    when(() => mock.getDouble(any())).thenAnswer((_) async => null);
    when(() => mock.setDouble(any(), any())).thenAnswer((_) async => {});
  }

  static void _setupSubscriptionServiceDefaults(
    MockDailyJokeSubscriptionService mock,
  ) {
    // Setup default behaviors for FCM sync service
    when(() => mock.ensureSubscriptionSync()).thenAnswer((_) async => true);
  }
}
