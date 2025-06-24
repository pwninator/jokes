import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

void main() {
  group('SettingsService', () {
    late SettingsService settingsService;

    setUp(() async {
      // Set up SharedPreferences for testing
      SharedPreferences.setMockInitialValues({});
      settingsService = SettingsService();
    });

    test('setString and getString', () async {
      const key = 'testStringKey';
      const value = 'testStringValue';
      await settingsService.setString(key, value);
      final retrievedValue = await settingsService.getString(key);
      expect(retrievedValue, value);
    });

    test('setInt and getInt', () async {
      const key = 'testIntKey';
      const value = 123;
      await settingsService.setInt(key, value);
      final retrievedValue = await settingsService.getInt(key);
      expect(retrievedValue, value);
    });

    test('setBool and getBool', () async {
      const key = 'testBoolKey';
      const value = true;
      await settingsService.setBool(key, value);
      final retrievedValue = await settingsService.getBool(key);
      expect(retrievedValue, value);
    });

    test('setDouble and getDouble', () async {
      const key = 'testDoubleKey';
      const value = 123.456;
      await settingsService.setDouble(key, value);
      final retrievedValue = await settingsService.getDouble(key);
      expect(retrievedValue, value);
    });

    test('setStringList and getStringList', () async {
      const key = 'testStringListKey';
      final value = ['a', 'b', 'c'];
      await settingsService.setStringList(key, value);
      final retrievedValue = await settingsService.getStringList(key);
      expect(retrievedValue, value);
    });

    test('containsKey', () async {
      const key = 'testContainsKey';
      const value = 'testValue';
      await settingsService.setString(key, value);
      expect(await settingsService.containsKey(key), isTrue);
      expect(await settingsService.containsKey('nonExistentKey'), isFalse);
    });

    test('remove', () async {
      const key = 'testRemoveKey';
      const value = 'testValue';
      await settingsService.setString(key, value);
      expect(await settingsService.containsKey(key), isTrue);
      await settingsService.remove(key);
      expect(await settingsService.containsKey(key), isFalse);
    });

    test('clear', () async {
      await settingsService.setString('key1', 'value1');
      await settingsService.setInt('key2', 123);
      await settingsService.clear();
      expect(await settingsService.containsKey('key1'), isFalse);
      expect(await settingsService.containsKey('key2'), isFalse);
    });

    test('getString returns null for non-existent key', () async {
      final retrievedValue = await settingsService.getString('nonExistentKey');
      expect(retrievedValue, isNull);
    });

    test('getInt returns null for non-existent key', () async {
      final retrievedValue = await settingsService.getInt('nonExistentKey');
      expect(retrievedValue, isNull);
    });

    test('getBool returns null for non-existent key', () async {
      final retrievedValue = await settingsService.getBool('nonExistentKey');
      expect(retrievedValue, isNull);
    });

    test('getDouble returns null for non-existent key', () async {
      final retrievedValue = await settingsService.getDouble('nonExistentKey');
      expect(retrievedValue, isNull);
    });

    test('getStringList returns null for non-existent key', () async {
      final retrievedValue = await settingsService.getStringList('nonExistentKey');
      expect(retrievedValue, isNull);
    });
  });
}
