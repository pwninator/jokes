import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';

class DeviceUtils {
  static final DeviceInfoPlugin _deviceInfo = DeviceInfoPlugin();
  static bool? _isPhysicalDevice;

  /// Returns whether the app is running on a physical device.
  ///
  /// This is determined once and cached for subsequent calls.
  /// Returns true for desktop platforms by default.
  static Future<bool> get isPhysicalDevice async {
    if (_isPhysicalDevice != null) {
      return _isPhysicalDevice!;
    }

    _isPhysicalDevice = switch (defaultTargetPlatform) {
      TargetPlatform.android =>
        (await _deviceInfo.androidInfo).isPhysicalDevice,
      TargetPlatform.iOS => (await _deviceInfo.iosInfo).isPhysicalDevice,
      _ => true,
    };

    return _isPhysicalDevice!;
  }
}