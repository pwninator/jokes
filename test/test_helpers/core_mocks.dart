import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/providers/app_version_provider.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

// Mock classes for core services
class MockImageService extends Mock implements ImageService {}

class MockSettingsService extends Mock implements SettingsService {}

class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

/// Core service mocks for unit tests
class CoreMocks {
  static MockImageService? _mockImageService;
  static MockSettingsService? _mockSettingsService;
  static MockDailyJokeSubscriptionService? _mockSubscriptionService;

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

  /// Get or create mock subscription service
  static MockDailyJokeSubscriptionService get mockSubscriptionService {
    _mockSubscriptionService ??= MockDailyJokeSubscriptionService();
    _setupSubscriptionServiceDefaults(_mockSubscriptionService!);
    return _mockSubscriptionService!;
  }

  /// Reset all core mocks (call this in setUp if needed)
  static void reset() {
    _mockImageService = null;
    _mockSettingsService = null;
    _mockSubscriptionService = null;
  }

  /// Get core service provider overrides
  static List<Override> getCoreProviderOverrides({
    List<Override> additionalOverrides = const [],
  }) {
    return [
      // Mock image service
      imageServiceProvider.overrideWithValue(mockImageService),

      // Mock settings service
      settingsServiceProvider.overrideWithValue(mockSettingsService),

      // Mock subscription service
      dailyJokeSubscriptionServiceProvider.overrideWithValue(
        mockSubscriptionService,
      ),

      // Mock subscription status provider
      subscriptionStatusProvider.overrideWith((ref) => const AsyncValue.data(false)),

      // Mock app version provider with test data
      appVersionProvider.overrideWith((ref) => Future.value('Snickerdoodle v0.0.1+1')),

      // Add any additional overrides
      ...additionalOverrides,
    ];
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
    when(() => mock.processImageUrl(
      any(),
      width: any(named: 'width'),
      height: any(named: 'height'),
      quality: any(named: 'quality'),
    )).thenAnswer((invocation) {
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
    // Setup default behaviors for subscription service
    when(() => mock.isSubscribed()).thenAnswer((_) async => false);
    when(() => mock.ensureSubscriptionSync()).thenAnswer((_) async => true);
    when(() => mock.setSubscriptionPreference(any())).thenAnswer((_) async => true);
    when(() => mock.hasBeenPromptedForSubscription()).thenAnswer((_) async => false);
    when(() => mock.markUserPromptedForSubscription()).thenAnswer((_) async => true);
  }
}
