import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

final settingsServiceProvider = Provider<SettingsService>((ref) {
  throw UnimplementedError(
    'settingsServiceProvider must be overridden with a concrete SettingsService that has a SharedPreferences instance.',
  );
});

class SettingsService {
  SettingsService(this._prefs);

  final SharedPreferences _prefs;

  String? getString(String key) {
    return _prefs.getString(key);
  }

  Future<void> setString(String key, String value) async {
    await _prefs.setString(key, value);
  }

  int? getInt(String key) {
    return _prefs.getInt(key);
  }

  Future<void> setInt(String key, int value) async {
    await _prefs.setInt(key, value);
  }

  bool? getBool(String key) {
    return _prefs.getBool(key);
  }

  Future<void> setBool(String key, bool value) async {
    await _prefs.setBool(key, value);
  }

  double? getDouble(String key) {
    return _prefs.getDouble(key);
  }

  Future<void> setDouble(String key, double value) async {
    await _prefs.setDouble(key, value);
  }

  List<String>? getStringList(String key) {
    return _prefs.getStringList(key);
  }

  Future<void> setStringList(String key, List<String> value) async {
    await _prefs.setStringList(key, value);
  }

  bool containsKey(String key) {
    return _prefs.containsKey(key);
  }

  Future<void> remove(String key) async {
    await _prefs.remove(key);
  }

  Future<void> clear() async {
    await _prefs.clear();
  }
}
