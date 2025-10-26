import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/titled_screen.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_feed_screen.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';

import '../../../helpers/joke_viewer_test_utils.dart';

class MockAnalyticsService extends Mock implements AnalyticsService {}

class FakeSettingsService implements SettingsService {
  FakeSettingsService(Map<String, Object> initial) : _store = {...initial};

  final Map<String, Object> _store;
  final List<String> getKeys = [];
  final List<MapEntry<String, String>> setEntries = [];

  @override
  bool? getBool(String key) => _store[key] as bool?;

  @override
  Future<void> setBool(String key, bool value) async {
    _store[key] = value;
  }

  @override
  String? getString(String key) {
    getKeys.add(key);
    return _store[key] as String?;
  }

  @override
  Future<void> setString(String key, String value) async {
    setEntries.add(MapEntry(key, value));
    _store[key] = value;
  }

  @override
  int? getInt(String key) => _store[key] as int?;

  @override
  Future<void> setInt(String key, int value) async {
    _store[key] = value;
  }

  @override
  double? getDouble(String key) => _store[key] as double?;

  @override
  Future<void> setDouble(String key, double value) async {
    _store[key] = value;
  }

  @override
  List<String>? getStringList(String key) => _store[key] as List<String>?;

  @override
  Future<void> setStringList(String key, List<String> value) async {
    _store[key] = value;
  }

  @override
  bool containsKey(String key) => _store.containsKey(key);

  @override
  Future<void> remove(String key) async {
    _store.remove(key);
  }

  @override
  Future<void> clear() async {
    _store.clear();
  }
}

void main() {
  setUpAll(() {
    registerFallbackValue(JokeViewerMode.reveal);
    registerFallbackValue(Brightness.light);
    registerFallbackValue(JokeField.state);
    registerFallbackValue(
      JokeFilter(field: JokeField.state, isEqualTo: 'test'),
    );
    registerFallbackValue(OrderDirection.ascending);
    registerFallbackValue(
      const JokeListPageCursor(orderValue: 0, docId: 'cursor'),
    );
  });

  test('JokeFeedScreen exposes expected title', () {
    const screen = JokeFeedScreen();
    expect(screen, isA<TitledScreen>());
    expect(screen.title, 'Joke Feed');
  });

  testWidgets('JokeFeedScreen creates JokeListViewer with correct parameters', (
    tester,
  ) async {
    // Arrange
    final mockAnalyticsService = MockAnalyticsService();
    when(
      () => mockAnalyticsService.logJokeNavigation(
        any(),
        any(),
        method: any(named: 'method'),
        jokeContext: any(named: 'jokeContext'),
        jokeViewerMode: any(named: 'jokeViewerMode'),
        brightness: any(named: 'brightness'),
        screenOrientation: any(named: 'screenOrientation'),
      ),
    ).thenAnswer((_) {});
    when(
      () => mockAnalyticsService.logErrorJokesLoad(
        source: any(named: 'source'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) {});

    final fakeSettings = FakeSettingsService({});

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          ...buildJokeViewerOverrides(
            analyticsService: mockAnalyticsService,
            isOnline: false,
          ),
          settingsServiceProvider.overrideWithValue(fakeSettings),
        ],
        child: const MaterialApp(home: JokeFeedScreen()),
      ),
    );

    await tester.pump();
    await tester.pump();

    // Assert
    final viewer = tester.widget<JokeListViewer>(find.byType(JokeListViewer));
    expect(viewer.jokeContext, 'joke_feed');
    expect(viewer.viewerId, 'joke_feed');
    expect(viewer.dataSource, isNotNull);
  });
}
