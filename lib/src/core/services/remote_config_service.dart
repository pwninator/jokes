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
    isValid: _validatePositiveInt,
  ),
};

enum RemoteParam { subscriptionPromptMinJokesViewed }

enum RemoteParamType { intType, boolType, doubleType, stringType }

class RemoteParamDescriptor {
  final String key;
  final RemoteParamType type;
  final int? defaultInt;
  final bool? defaultBool;
  final double? defaultDouble;
  final String? defaultString;
  final bool Function(Object value)? isValid;

  const RemoteParamDescriptor({
    required this.key,
    required this.type,
    this.defaultInt,
    this.defaultBool,
    this.defaultDouble,
    this.defaultString,
    this.isValid,
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
    }
  }
}

// Validation helpers
bool _validatePositiveInt(Object value) {
  return value is int && value > 0;
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
        await _analyticsService.logErrorRemoteConfig(
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
    if (!_isInitialized) return d.defaultString!;
    try {
      final value = _client.getString(d.key);
      if (d.isValid != null && !d.isValid!(value)) return d.defaultString!;
      return value;
    } catch (_) {
      return d.defaultString!;
    }
  }
}

/// Lightweight, generic values wrapper (minimize per-param code)
abstract class RemoteConfigValues {
  int getInt(RemoteParam param);
  bool getBool(RemoteParam param);
  double getDouble(RemoteParam param);
  String getString(RemoteParam param);
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
