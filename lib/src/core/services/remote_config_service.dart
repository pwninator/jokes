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
  RemoteParam.feedbackMinJokesViewed: RemoteParamDescriptor(
    key: 'feedback_min_jokes_viewed',
    type: RemoteParamType.intType,
    defaultInt: 10,
    isValid: _validateNonNegativeInt,
  ),

  /////////////////////////
  // Subscription Prompt //
  /////////////////////////
  RemoteParam.subscriptionPromptMinJokesViewed: RemoteParamDescriptor(
    key: 'subscription_prompt_min_jokes_viewed',
    type: RemoteParamType.intType,
    defaultInt: 5,
    isValid: _validateNonNegativeInt,
  ),

  ////////////////////
  // Review Request //
  ////////////////////
  RemoteParam.reviewMinDaysUsed: RemoteParamDescriptor(
    key: 'review_min_days_used',
    type: RemoteParamType.intType,
    // Default to never show review prompt
    defaultInt: 10000,
    isValid: _validateNonNegativeInt,
  ),
  RemoteParam.reviewMinViewedJokes: RemoteParamDescriptor(
    key: 'review_min_viewed_jokes',
    type: RemoteParamType.intType,
    defaultInt: 30,
    isValid: _validateNonNegativeInt,
  ),
  RemoteParam.reviewMinSavedJokes: RemoteParamDescriptor(
    key: 'review_min_saved_jokes',
    type: RemoteParamType.intType,
    defaultInt: 3,
    isValid: _validateNonNegativeInt,
  ),
  RemoteParam.reviewMinSharedJokes: RemoteParamDescriptor(
    key: 'review_min_shared_jokes',
    type: RemoteParamType.intType,
    defaultInt: 1,
    isValid: _validateNonNegativeInt,
  ),
  // Gate requesting a review from a joke viewed event
  RemoteParam.reviewRequestFromJokeViewed: RemoteParamDescriptor(
    key: 'review_request_from_joke_viewed',
    type: RemoteParamType.boolType,
    defaultBool: false,
  ),
  // Gate review prompt behind user's daily subscription preference
  RemoteParam.reviewRequireDailySubscription: RemoteParamDescriptor(
    key: 'review_require_daily_subscription',
    type: RemoteParamType.boolType,
    defaultBool: true,
  ),
  // Review prompt variant (which image/message to show)
  RemoteParam.reviewPromptVariant: RemoteParamDescriptor(
    key: 'review_prompt_variant',
    type: RemoteParamType.enumType,
    enumValues: ReviewPromptVariant.values,
    enumDefault: ReviewPromptVariant.kitten,
  ),

  /////////////////
  // Joke Viewer //
  /////////////////
  // Controls the default for the Joke Viewer setting when no local pref exists
  RemoteParam.defaultJokeViewerReveal: RemoteParamDescriptor(
    key: 'default_joke_viewer_reveal',
    type: RemoteParamType.boolType,
    defaultBool: true,
  ),

  //////////////////
  // Joke Sharing //
  //////////////////
  // Enum-based param for share images mode (enum-like)
  RemoteParam.shareImagesMode: RemoteParamDescriptor(
    key: 'share_images_mode',
    type: RemoteParamType.enumType,
    enumValues: ShareImagesMode.values,
    enumDefault: ShareImagesMode.stacked,
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
}

// Enum used by share images mode configuration
enum ShareImagesMode { auto, separate, stacked }

// Enum for review prompt variants
enum ReviewPromptVariant { none, bunny, kitten }

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

// Validation helpers
bool _validateNonNegativeInt(Object value) {
  return value is int && value >= 0;
}

/// Abstraction over Firebase Remote Config for testability
abstract class RemoteConfigClient {
  Future<bool> fetchAndActivate();
  Future<void> setConfigSettings(RemoteConfigSettings settings);
  Future<void> setDefaults(Map<String, Object> defaults);
  int getInt(String key);
  bool getBool(String key);
  double getDouble(String key);
  String getString(String key);
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
  int getInt(String key) => _inner.getInt(key);

  @override
  bool getBool(String key) => _inner.getBool(key);

  @override
  double getDouble(String key) => _inner.getDouble(key);

  @override
  String getString(String key) => _inner.getString(key);
}

/// Service responsible for initializing and exposing Remote Config values
class RemoteConfigService {
  RemoteConfigService({
    required RemoteConfigClient client,
    required AnalyticsService analyticsService,
  }) : _client = client,
       _analyticsService = analyticsService;

  final RemoteConfigClient _client;
  final AnalyticsService _analyticsService;
  bool _isInitialized = false;

  /// Initialize Remote Config with sane defaults and attempt fetch/activate
  Future<void> initialize() async {
    // Validate descriptor configuration up-front (fail fast on misconfiguration)
    validateRemoteParams(remoteParams);
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
      remoteParams.forEach((param, descriptor) {
        defaults[descriptor.key] = descriptor.defaultValue;
      });
      await _client.setDefaults(defaults);

      // Try to fetch fresh values
      await _client.fetchAndActivate();
      _isInitialized = true;
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

  // Typed readers used by the values wrapper
  int readInt(RemoteParam param) {
    final d = remoteParams[param]!;
    if (!_isInitialized) return d.defaultInt!;
    try {
      final value = _client.getInt(d.key);
      if (d.isValid != null && !d.isValid!(value)) return d.defaultInt!;
      return value;
    } catch (_) {
      return d.defaultInt!;
    }
  }

  bool readBool(RemoteParam param) {
    final d = remoteParams[param]!;
    if (!_isInitialized) return d.defaultBool!;
    try {
      final value = _client.getBool(d.key);
      if (d.isValid != null && !d.isValid!(value)) return d.defaultBool!;
      return value;
    } catch (_) {
      return d.defaultBool!;
    }
  }

  double readDouble(RemoteParam param) {
    final d = remoteParams[param]!;
    if (!_isInitialized) return d.defaultDouble!;
    try {
      final value = _client.getDouble(d.key);
      if (d.isValid != null && !d.isValid!(value)) return d.defaultDouble!;
      return value;
    } catch (_) {
      return d.defaultDouble!;
    }
  }

  String readString(RemoteParam param) {
    final d = remoteParams[param]!;
    if (!_isInitialized) {
      if (d.type == RemoteParamType.enumType) return _enumName(d.enumDefault!);
      return d.defaultString!;
    }
    try {
      final value = _client.getString(d.key);
      if (d.isValid != null && !d.isValid!(value)) {
        return d.type == RemoteParamType.enumType
            ? _enumName(d.enumDefault!)
            : d.defaultString!;
      }
      return value;
    } catch (_) {
      return d.type == RemoteParamType.enumType
          ? _enumName(d.enumDefault!)
          : d.defaultString!;
    }
  }

  /// Generic: normalize an enum-like string param
  T readEnum<T>(RemoteParam param) {
    final d = remoteParams[param]!;
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
