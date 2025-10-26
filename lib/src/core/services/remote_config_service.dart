import 'package:firebase_remote_config/firebase_remote_config.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/data/core/app/firebase_providers.dart';

part 'remote_config_service.g.dart';

const Map<RemoteParam, RemoteParamDescriptor> remoteParams = {
  //////////////
  // Feedback //
  //////////////
  RemoteParam.feedbackMinJokesViewed: IntRemoteParamDescriptor(
    key: 'feedback_min_jokes_viewed',
    defaultInt: 10,
    isValid: validateNonNegativeInt,
  ),

  /////////////////////////
  // Subscription Prompt //
  /////////////////////////
  RemoteParam.subscriptionPromptMinJokesViewed: IntRemoteParamDescriptor(
    key: 'subscription_prompt_min_jokes_viewed',
    defaultInt: 5,
    isValid: validateNonNegativeInt,
  ),

  ////////////////////
  // Review Request //
  ////////////////////
  RemoteParam.reviewMinDaysUsed: IntRemoteParamDescriptor(
    key: 'review_min_days_used',
    // Default to never show review prompt
    defaultInt: 14,
    isValid: validateNonNegativeInt,
  ),
  RemoteParam.reviewMinViewedJokes: IntRemoteParamDescriptor(
    key: 'review_min_viewed_jokes',
    defaultInt: 100,
    isValid: validateNonNegativeInt,
  ),
  RemoteParam.reviewMinSavedJokes: IntRemoteParamDescriptor(
    key: 'review_min_saved_jokes',
    defaultInt: 1,
    isValid: validateNonNegativeInt,
  ),
  RemoteParam.reviewMinSharedJokes: IntRemoteParamDescriptor(
    key: 'review_min_shared_jokes',
    defaultInt: 0,
    isValid: validateNonNegativeInt,
  ),
  // Gate requesting a review from a joke viewed event
  RemoteParam.reviewRequestFromJokeViewed: BoolRemoteParamDescriptor(
    key: 'review_request_from_joke_viewed',
    defaultBool: true,
  ),
  // Gate review prompt behind user's daily subscription preference
  RemoteParam.reviewRequireDailySubscription: BoolRemoteParamDescriptor(
    key: 'review_require_daily_subscription',
    defaultBool: false,
  ),
  // Review prompt variant (which image/message to show)
  RemoteParam.reviewPromptVariant: EnumRemoteParamDescriptor(
    key: 'review_prompt_variant',
    enumValues: ReviewPromptVariant.values,
    enumDefault: ReviewPromptVariant.kitten,
  ),

  /////////////////
  // Joke Viewer //
  /////////////////
  // Controls the default for the Joke Viewer setting when no local pref exists
  RemoteParam.defaultJokeViewerReveal: BoolRemoteParamDescriptor(
    key: 'default_joke_viewer_reveal',
    defaultBool: true,
  ),

  //////////////////
  // Joke Sharing //
  //////////////////
  // Enum-based param for share images mode (enum-like)
  RemoteParam.shareImagesMode: EnumRemoteParamDescriptor(
    key: 'share_images_mode',
    enumValues: ShareImagesMode.values,
    enumDefault: ShareImagesMode.stacked,
  ),

  //////////////////
  // Advertisements //
  //////////////////
  RemoteParam.adDisplayMode: EnumRemoteParamDescriptor(
    key: 'ad_display_mode',
    enumValues: AdDisplayMode.values,
    enumDefault: AdDisplayMode.none,
  ),
  RemoteParam.bannerAdPosition: EnumRemoteParamDescriptor(
    key: 'banner_ad_position',
    enumValues: BannerAdPosition.values,
    enumDefault: BannerAdPosition.top,
  ),
};

enum RemoteParam {
  subscriptionPromptMinJokesViewed,
  feedbackMinJokesViewed,
  reviewMinDaysUsed,
  reviewMinSavedJokes,
  reviewMinSharedJokes,
  reviewMinViewedJokes,
  reviewRequestFromJokeViewed,
  reviewRequireDailySubscription,
  reviewPromptVariant,
  defaultJokeViewerReveal,
  shareImagesMode,
  adDisplayMode,
  bannerAdPosition,
}

// Enum used by share images mode configuration
enum ShareImagesMode { auto, separate, stacked }

// Enum for review prompt variants
enum ReviewPromptVariant { none, bunny, kitten }

// Enum for Ad display configuration
enum AdDisplayMode { none, banner }

// Enum for banner ad placement configuration
enum BannerAdPosition { top, bottom }

enum RemoteParamType { intType, boolType, doubleType, stringType, enumType }

class RemoteParamDescriptor {
  final String key;
  final RemoteParamType type;
  final int? defaultInt;
  final bool? defaultBool;
  final double? defaultDouble;
  final String? defaultString;
  final bool Function(Object value)? isValid;
  // Enum-like support for string params
  final List<Object>? enumValues;
  final Object? enumDefault;

  const RemoteParamDescriptor({
    required this.key,
    required this.type,
    this.defaultInt,
    this.defaultBool,
    this.defaultDouble,
    this.defaultString,
    this.isValid,
    this.enumValues,
    this.enumDefault,
  });

  Object get defaultValue {
    switch (type) {
      case RemoteParamType.intType:
        return defaultInt!;
      case RemoteParamType.boolType:
        return defaultBool!;
      case RemoteParamType.doubleType:
        return defaultDouble!;
      case RemoteParamType.stringType:
        return defaultString!;
      case RemoteParamType.enumType:
        return _enumName(enumDefault!);
    }
  }
}

/// Type-safe descriptor for integer parameters
class IntRemoteParamDescriptor extends RemoteParamDescriptor {
  const IntRemoteParamDescriptor({
    required super.key,
    required super.defaultInt,
    super.isValid,
  }) : super(
         type: RemoteParamType.intType,
         defaultBool: null,
         defaultDouble: null,
         defaultString: null,
         enumValues: null,
         enumDefault: null,
       );
}

/// Type-safe descriptor for boolean parameters
class BoolRemoteParamDescriptor extends RemoteParamDescriptor {
  const BoolRemoteParamDescriptor({
    required super.key,
    required super.defaultBool,
  }) : super(
         type: RemoteParamType.boolType,
         defaultInt: null,
         defaultDouble: null,
         defaultString: null,
         isValid: null,
         enumValues: null,
         enumDefault: null,
       );
}

/// Type-safe descriptor for double parameters
class DoubleRemoteParamDescriptor extends RemoteParamDescriptor {
  const DoubleRemoteParamDescriptor({
    required super.key,
    required super.defaultDouble,
    super.isValid,
  }) : super(
         type: RemoteParamType.doubleType,
         defaultInt: null,
         defaultBool: null,
         defaultString: null,
         enumValues: null,
         enumDefault: null,
       );
}

/// Type-safe descriptor for string parameters
class StringRemoteParamDescriptor extends RemoteParamDescriptor {
  const StringRemoteParamDescriptor({
    required super.key,
    required super.defaultString,
    super.isValid,
  }) : super(
         type: RemoteParamType.stringType,
         defaultInt: null,
         defaultBool: null,
         defaultDouble: null,
         enumValues: null,
         enumDefault: null,
       );
}

/// Type-safe descriptor for enum parameters
class EnumRemoteParamDescriptor extends RemoteParamDescriptor {
  const EnumRemoteParamDescriptor({
    required super.key,
    required super.enumValues,
    required super.enumDefault,
  }) : super(
         type: RemoteParamType.enumType,
         defaultInt: null,
         defaultBool: null,
         defaultDouble: null,
         defaultString: null,
         isValid: null,
       );
}

// Validation helpers
bool validateNonNegativeInt(Object value) {
  return value is int && value >= 0;
}

/// Abstraction over Firebase Remote Config for testability
abstract class RemoteConfigClient {
  Future<bool> fetchAndActivate();
  Future<void> setConfigSettings(RemoteConfigSettings settings);
  Future<void> setDefaults(Map<String, Object> defaults);
  RemoteConfigValue getValue(String key);
}

class FirebaseRemoteConfigClient implements RemoteConfigClient {
  FirebaseRemoteConfigClient(this._inner);

  final FirebaseRemoteConfig _inner;

  @override
  Future<bool> fetchAndActivate() => _inner.fetchAndActivate();

  @override
  Future<void> setConfigSettings(RemoteConfigSettings settings) =>
      _inner.setConfigSettings(settings);

  @override
  Future<void> setDefaults(Map<String, Object> defaults) =>
      _inner.setDefaults(defaults);

  @override
  RemoteConfigValue getValue(String key) => _inner.getValue(key);
}

/// Service responsible for initializing and exposing Remote Config values
class RemoteConfigService {
  RemoteConfigService({
    required RemoteConfigClient client,
    required AnalyticsService analyticsService,
    Map<RemoteParam, RemoteParamDescriptor>? parameters,
  }) : _client = client,
       _analyticsService = analyticsService,
       _parameters = parameters ?? remoteParams;

  final RemoteConfigClient _client;
  final AnalyticsService _analyticsService;
  final Map<RemoteParam, RemoteParamDescriptor> _parameters;
  bool _isInitialized = false;

  /// Initialize Remote Config with sane defaults and attempt fetch/activate
  Future<void> initialize() async {
    // Validate descriptor configuration up-front (fail fast on misconfiguration)
    validateRemoteParams(_parameters);
    try {
      // Configure fetch behavior (shorter in debug builds)
      await _client.setConfigSettings(
        RemoteConfigSettings(
          fetchTimeout: const Duration(seconds: 10),
          minimumFetchInterval: kDebugMode
              ? const Duration(minutes: 1)
              : const Duration(hours: 12),
        ),
      );

      // Set in-app defaults
      final defaults = <String, Object>{};
      _parameters.forEach((param, descriptor) {
        defaults[descriptor.key] = descriptor.defaultValue;
      });
      await _client.setDefaults(defaults);

      // As soon as defaults are applied, expose client reads
      _isInitialized = true;

      // Try to fetch fresh values
      await _client.fetchAndActivate();
    } catch (e) {
      // Log analytics + crashlytics on error per project policy
      try {
        _analyticsService.logErrorRemoteConfig(
          phase: 'initialize',
          errorMessage: e.toString(),
        );
      } catch (_) {
        // Swallow secondary errors
      }
      // Even on error, mark initialized so defaults are used without hitting platform again
      _isInitialized = true;
    }
  }

  /// Refresh Remote Config by fetching latest values from server.
  /// Safe to call frequently; Firebase SDK handles throttling based on minimumFetchInterval.
  /// Returns true if new values were activated, false if using cached/throttled values.
  Future<bool> refresh() async {
    if (!_isInitialized) {
      // Not initialized yet, do full initialization
      await initialize();
      return _isInitialized;
    }

    try {
      final activated = await _client.fetchAndActivate();
      return activated;
    } catch (e) {
      // Log error but don't crash - continue using current values
      try {
        _analyticsService.logErrorRemoteConfig(
          phase: 'refresh',
          errorMessage: e.toString(),
        );
      } catch (_) {
        // Swallow secondary errors
      }
      return false;
    }
  }

  /// Expose a typed values reader (no per-param fields)
  RemoteConfigValues get currentValues => _RemoteConfigValues(this);

  T _readParamValue<T>(
    RemoteParamDescriptor descriptor, {
    required T localDefaultValue,
    required T Function(RemoteConfigValue value) convert,
    bool Function(Object value)? validator,
  }) {
    final key = descriptor.key;
    final localDefaultLogValue = localDefaultValue.toString();
    if (!_isInitialized) {
      _analyticsService.logRemoteConfigUsedLocal(
        paramName: key,
        value: localDefaultLogValue,
      );
      return localDefaultValue;
    }

    RemoteConfigValue value;
    try {
      value = _client.getValue(key);
    } catch (e) {
      _analyticsService.logErrorRemoteConfig(
        phase: 'readParamValue',
        errorMessage: 'Failed to get value for key: $key: $e',
      );
      return localDefaultValue;
    }

    try {
      final result = convert(value);
      final logValue = result.toString();
      final isValid = validator == null ? true : validator(result as Object);
      if (!isValid) {
        _analyticsService.logErrorRemoteConfig(
          phase: 'readParamValue',
          errorMessage: 'Invalid value for key: $key: $result',
        );
        return localDefaultValue;
      }

      if (value.source == ValueSource.valueStatic) {
        _analyticsService.logRemoteConfigUsedError(
          paramName: key,
          value: logValue,
        );
        return result;
      }

      if (value.source == ValueSource.valueDefault) {
        _analyticsService.logRemoteConfigUsedDefault(
          paramName: key,
          value: logValue,
        );
        return result;
      }

      _analyticsService.logRemoteConfigUsedRemote(
        paramName: key,
        value: logValue,
      );
      return result;
    } catch (e) {
      _analyticsService.logErrorRemoteConfig(
        phase: 'readParamValue',
        errorMessage: 'Error when reading value for key: $key: $e',
      );
      return localDefaultValue;
    }
  }

  // Typed readers used by the values wrapper
  int readInt(RemoteParam param) {
    final descriptor = _parameters[param]!;
    return _readParamValue<int>(
      descriptor,
      localDefaultValue: descriptor.defaultInt!,
      convert: (value) => value.asInt(),
      validator: descriptor.isValid,
    );
  }

  bool readBool(RemoteParam param) {
    final descriptor = _parameters[param]!;
    return _readParamValue<bool>(
      descriptor,
      localDefaultValue: descriptor.defaultBool!,
      convert: (value) => value.asBool(),
    );
  }

  double readDouble(RemoteParam param) {
    final descriptor = _parameters[param]!;
    return _readParamValue<double>(
      descriptor,
      localDefaultValue: descriptor.defaultDouble!,
      convert: (value) => value.asDouble(),
      validator: descriptor.isValid,
    );
  }

  String readString(RemoteParam param) {
    final descriptor = _parameters[param]!;
    return _readParamValue<String>(
      descriptor,
      localDefaultValue: descriptor.defaultValue.toString(),
      convert: (value) => value.asString(),
      validator: descriptor.isValid,
    );
  }

  /// Generic: normalize an enum-like string param
  T readEnum<T>(RemoteParam param) {
    final d = _parameters[param]!;
    // Read primary string value
    final raw = readString(param).trim().toLowerCase();
    if (d.enumValues != null && d.enumValues!.isNotEmpty) {
      for (final value in d.enumValues!) {
        final name = _enumName(value);
        if (name.toLowerCase() == raw) {
          return value as T;
        }
      }
      return d.enumDefault as T;
    }
    throw StateError('Param $param is not configured as enum');
  }
}

/// Validates that all RemoteParam descriptors are correctly configured.
/// Throws StateError with details if any validation fails.
void validateRemoteParams(Map<RemoteParam, RemoteParamDescriptor> params) {
  // Ensure unique, non-empty keys
  final seenKeys = <String>{};
  for (final entry in params.entries) {
    final param = entry.key;
    final d = entry.value;
    if (d.key.isEmpty) {
      throw StateError('RemoteParam $param has empty key');
    }
    if (!seenKeys.add(d.key)) {
      throw StateError('Duplicate Remote Config key detected: ${d.key}');
    }

    switch (d.type) {
      case RemoteParamType.intType:
        if (d.defaultInt == null) {
          throw StateError('RemoteParam $param (int) missing defaultInt');
        }
        break;
      case RemoteParamType.boolType:
        if (d.defaultBool == null) {
          throw StateError('RemoteParam $param (bool) missing defaultBool');
        }
        break;
      case RemoteParamType.doubleType:
        if (d.defaultDouble == null) {
          throw StateError('RemoteParam $param (double) missing defaultDouble');
        }
        break;
      case RemoteParamType.stringType:
        if (d.defaultString == null) {
          throw StateError('RemoteParam $param (string) missing defaultString');
        }
        break;
      case RemoteParamType.enumType:
        if (d.enumValues == null || d.enumValues!.isEmpty) {
          throw StateError('RemoteParam $param (enum) missing enumValues');
        }
        if (d.enumDefault == null) {
          throw StateError('RemoteParam $param (enum) missing enumDefault');
        }
        // Ensure default is one of the enum values
        final names = d.enumValues!.map(_enumName).toSet();
        final defName = _enumName(d.enumDefault!);
        if (!names.contains(defName)) {
          throw StateError(
            'RemoteParam $param (enum) default not in enumValues: $defName',
          );
        }
        break;
    }
  }
}

String _enumName(Object value) {
  final s = value.toString();
  final idx = s.indexOf('.');
  return idx == -1 ? s : s.substring(idx + 1);
}

/// Lightweight, generic values wrapper (minimize per-param code)
abstract class RemoteConfigValues {
  int getInt(RemoteParam param);
  bool getBool(RemoteParam param);
  double getDouble(RemoteParam param);
  String getString(RemoteParam param);
  T getEnum<T>(RemoteParam param);
}

class _RemoteConfigValues implements RemoteConfigValues {
  _RemoteConfigValues(this._service);
  final RemoteConfigService _service;

  @override
  int getInt(RemoteParam param) => _service.readInt(param);

  @override
  bool getBool(RemoteParam param) => _service.readBool(param);

  @override
  double getDouble(RemoteParam param) => _service.readDouble(param);

  @override
  String getString(RemoteParam param) => _service.readString(param);

  @override
  T getEnum<T>(RemoteParam param) => _service.readEnum<T>(param);
}

@Riverpod(keepAlive: true)
RemoteConfigService remoteConfigService(Ref ref) {
  final analytics = ref.watch(analyticsServiceProvider);
  final firebaseRemoteConfig = ref.watch(firebaseRemoteConfigProvider);
  final client = FirebaseRemoteConfigClient(firebaseRemoteConfig);
  return RemoteConfigService(client: client, analyticsService: analytics);
}

/// Exposes typed Remote Config values to the app
final remoteConfigValuesProvider = Provider<RemoteConfigValues>((ref) {
  final service = ref.watch(remoteConfigServiceProvider);
  return service.currentValues;
});
