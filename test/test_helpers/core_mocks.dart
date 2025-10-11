import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/providers/app_version_provider.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/feedback_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/notification_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/data/core/database/app_database.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

// Mock classes for core services
class MockImageService extends Mock implements ImageService {}

class MockSettingsService extends Mock implements SettingsService {}

class MockDailyJokeSubscriptionService extends Mock
    implements DailyJokeSubscriptionService {}

class MockFeedbackService extends Mock implements FeedbackService {}

class MockPerformanceService extends Mock implements PerformanceService {}

class MockNotificationService extends Mock implements NotificationService {}

/// Core service mocks for unit tests
class CoreMocks {
  static MockImageService? _mockImageService;
  static MockSettingsService? _mockSettingsService;
  static MockDailyJokeSubscriptionService? _mockSubscriptionService;
  static MockPerformanceService? _mockPerformanceService;
  static MockNotificationService? _mockNotificationService;
  static AppDatabase? _mockAppDatabase;

  // Shared storage for settings service across all instances
  static final Map<String, dynamic> _sharedStorage = {};

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

  /// Get or create mock notification service
  static MockNotificationService get mockNotificationService {
    _mockNotificationService ??= MockNotificationService();
    _setupNotificationServiceDefaults(_mockNotificationService!);
    return _mockNotificationService!;
  }

  /// Get or create in-memory AppDatabase for tests
  static AppDatabase get mockAppDatabase {
    _mockAppDatabase ??= AppDatabase.inMemory();
    return _mockAppDatabase!;
  }

  /// Reset all core mocks (call this in setUp if needed)
  static void reset() {
    _mockImageService = null;
    _mockSettingsService = null;
    _mockSubscriptionService = null;
    _mockPerformanceService = null;
    _mockNotificationService = null;
    _mockAppDatabase = null;
    _sharedStorage.clear();
  }

  /// Get core service provider overrides (synchronous version for simple tests)
  static List<Override> getCoreProviderOverrides({
    List<Override> additionalOverrides = const [],
  }) {
    return [
      // Mock image service
      imageServiceProvider.overrideWithValue(mockImageService),

      // Mock settings service
      settingsServiceProvider.overrideWithValue(mockSettingsService),

      // Mock notification service
      notificationServiceProvider.overrideWithValue(mockNotificationService),

      // Mock subscription service (FCM sync only)
      dailyJokeSubscriptionServiceProvider.overrideWithValue(
        mockSubscriptionService,
      ),

      // Mock app version provider
      appVersionProvider.overrideWith((_) async => 'Snickerdoodle v0.0.1+1'),

      // Mock performance service (Firebase Performance)
      performanceServiceProvider.overrideWithValue(
        _mockPerformanceService ??= MockPerformanceService(),
      ),

      // In-memory Drift database
      appDatabaseProvider.overrideWithValue(mockAppDatabase),

      // Include additional overrides
      ...additionalOverrides,
    ];
  }

  /// Get core service provider overrides (async version for complex tests)
  static Future<List<Override>> getCoreProviderOverridesAsync({
    List<Override> additionalOverrides = const [],
  }) async {
    return [
      // Mock image service
      imageServiceProvider.overrideWithValue(mockImageService),

      // Mock settings service
      settingsServiceProvider.overrideWithValue(mockSettingsService),

      // Mock notification service
      notificationServiceProvider.overrideWithValue(mockNotificationService),

      // Mock subscription service (FCM sync only)
      dailyJokeSubscriptionServiceProvider.overrideWithValue(
        mockSubscriptionService,
      ),

      // Mock app version provider
      appVersionProvider.overrideWith((_) async => 'Test App v1.0.0'),

      // Mock performance service (Firebase Performance)
      performanceServiceProvider.overrideWithValue(
        _mockPerformanceService ??= MockPerformanceService(),
      ),

      // In-memory Drift database
      appDatabaseProvider.overrideWithValue(mockAppDatabase),

      // Include additional overrides
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
    // Setup default behaviors for settings that use shared storage
    when(() => mock.getString(any())).thenAnswer((invocation) {
      final key = invocation.positionalArguments[0] as String;
      return _sharedStorage[key] as String?;
    });
    when(() => mock.setString(any(), any())).thenAnswer((invocation) async {
      final key = invocation.positionalArguments[0] as String;
      final value = invocation.positionalArguments[1] as String;
      _sharedStorage[key] = value;
    });
    when(() => mock.getBool(any())).thenAnswer((invocation) {
      final key = invocation.positionalArguments[0] as String;
      return _sharedStorage[key] as bool?;
    });
    when(() => mock.setBool(any(), any())).thenAnswer((invocation) async {
      final key = invocation.positionalArguments[0] as String;
      final value = invocation.positionalArguments[1] as bool;
      _sharedStorage[key] = value;
    });
    when(() => mock.getInt(any())).thenAnswer((invocation) {
      final key = invocation.positionalArguments[0] as String;
      return _sharedStorage[key] as int?;
    });
    when(() => mock.setInt(any(), any())).thenAnswer((invocation) async {
      final key = invocation.positionalArguments[0] as String;
      final value = invocation.positionalArguments[1] as int;
      _sharedStorage[key] = value;
    });
    when(() => mock.getDouble(any())).thenAnswer((invocation) {
      final key = invocation.positionalArguments[0] as String;
      return _sharedStorage[key] as double?;
    });
    when(() => mock.setDouble(any(), any())).thenAnswer((invocation) async {
      final key = invocation.positionalArguments[0] as String;
      final value = invocation.positionalArguments[1] as double;
      _sharedStorage[key] = value;
    });
    when(() => mock.getStringList(any())).thenAnswer((invocation) {
      final key = invocation.positionalArguments[0] as String;
      return _sharedStorage[key] as List<String>?;
    });
    when(() => mock.setStringList(any(), any())).thenAnswer((invocation) async {
      final key = invocation.positionalArguments[0] as String;
      final value = invocation.positionalArguments[1] as List<String>;
      _sharedStorage[key] = value;
    });
    when(() => mock.containsKey(any())).thenAnswer((invocation) {
      final key = invocation.positionalArguments[0] as String;
      return _sharedStorage.containsKey(key);
    });
    when(() => mock.remove(any())).thenAnswer((invocation) async {
      final key = invocation.positionalArguments[0] as String;
      _sharedStorage.remove(key);
    });
    when(() => mock.clear()).thenAnswer((_) async {
      _sharedStorage.clear();
    });
  }

  static void _setupSubscriptionServiceDefaults(
    MockDailyJokeSubscriptionService mock,
  ) {
    // Setup default behaviors for FCM sync service
    when(
      () => mock.ensureSubscriptionSync(
        unsubscribeOthers: any(named: 'unsubscribeOthers'),
      ),
    ).thenAnswer((_) async => true);
  }

  static void _setupNotificationServiceDefaults(MockNotificationService mock) {
    // Setup default behaviors for notification service
    when(() => mock.initialize()).thenAnswer((_) async {});
    when(
      () => mock.requestNotificationPermissions(),
    ).thenAnswer((_) async => true);
    when(() => mock.getFCMToken()).thenAnswer((_) async => 'mock_fcm_token');
  }
}
