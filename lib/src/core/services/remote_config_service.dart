import 'package:firebase_remote_config/firebase_remote_config.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';

const Map<RemoteParam, RemoteParamDescriptor> remoteParams = {
  RemoteParam.subscriptionPromptMinJokesViewed: RemoteParamDescriptor(
    key: 'subscription_prompt_min_jokes_viewed',
    type: RemoteParamType.intType,
    defaultInt: 5,
    isValid: _validateNonNegativeInt,
  ),
  RemoteParam.feedbackMinJokesViewed: RemoteParamDescriptor(
    key: 'feedback_min_jokes_viewed',
    type: RemoteParamType.intType,
    defaultInt: 10,
    isValid: _validateNonNegativeInt,
  ),
  RemoteParam.reviewMinDaysUsed: RemoteParamDescriptor(
    key: 'review_min_days_used',
    type: RemoteParamType.intType,
    // Default to never show review prompt
    defaultInt: 10000,
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
  RemoteParam.reviewMinViewedJokes: RemoteParamDescriptor(
    key: 'review_min_viewed_jokes',
    type: RemoteParamType.intType,
    defaultInt: 30,
    isValid: _validateNonNegativeInt,
  ),
  // Controls the default for the Joke Viewer setting when no local pref exists
  RemoteParam.defaultJokeViewerReveal: RemoteParamDescriptor(
    key: 'default_joke_viewer_reveal',
    type: RemoteParamType.boolType,
    defaultBool: false,
  ),
  // Enum-based param for share images mode (enum-like)
  RemoteParam.shareImagesMode: RemoteParamDescriptor(
    key: 'share_images_mode',
    type: RemoteParamType.enumType,
    enumValues: ShareImagesMode.values,
    enumDefault: ShareImagesMode.separate,
  ),
};

enum RemoteParam {
  subscriptionPromptMinJokesViewed,
  feedbackMinJokesViewed,
  reviewMinDaysUsed,
  reviewMinSavedJokes,
  reviewMinSharedJokes,
  reviewMinViewedJokes,
  defaultJokeViewerReveal,
  shareImagesMode,
}

// Enum used by share images mode configuration
enum ShareImagesMode { separate, stacked }

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
        final name = (value as dynamic).name as String?;
        if (name != null && name.toLowerCase() == raw) {
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

/// Provider for RemoteConfigService
final remoteConfigServiceProvider = Provider<RemoteConfigService>((ref) {
  final analytics = ref.watch(analyticsServiceProvider);
  final client = FirebaseRemoteConfigClient(FirebaseRemoteConfig.instance);
  return RemoteConfigService(client: client, analyticsService: analytics);
});

/// Kicks off Remote Config initialization once per app launch
final remoteConfigInitializationProvider = FutureProvider<void>((ref) async {
  final service = ref.read(remoteConfigServiceProvider);
  await service.initialize();
});

/// Exposes typed Remote Config values to the app
final remoteConfigValuesProvider = Provider<RemoteConfigValues>((ref) {
  final service = ref.watch(remoteConfigServiceProvider);
  return service.currentValues;
});
