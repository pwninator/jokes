import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';
import 'package:snickerdoodle/src/features/settings/application/settings_service.dart';

class MockJokeListDataSource extends Mock implements JokeListDataSource {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockSettingsService extends Mock implements SettingsService {}

class _TestJokeViewerRevealNotifier extends JokeViewerRevealNotifier {
  _TestJokeViewerRevealNotifier(bool initialValue)
    : super(_TestJokeViewerSettingsService()) {
    state = initialValue;
  }
}

class _TestJokeViewerSettingsService extends JokeViewerSettingsService {
  _TestJokeViewerSettingsService()
    : super(
        settingsService: _MockSettingsService(),
        remoteConfigValues: _TestRemoteConfigValues(),
        analyticsService: _MockAnalyticsService(),
      );
}

class _TestRemoteConfigValues implements RemoteConfigValues {
  @override
  bool getBool(RemoteParam param) => false;
  @override
  double getDouble(RemoteParam param) => 0;
  @override
  int getInt(RemoteParam param) => 0;
  @override
  String getString(RemoteParam param) => '';
  @override
  T getEnum<T>(RemoteParam param) => '' as T;
}

class _MockAnalyticsService extends Mock implements AnalyticsService {}

class _MockSettingsService extends Mock implements SettingsService {}

void main() {
  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(JokeViewerMode.reveal);
    registerFallbackValue(Brightness.light);
  });

  group('JokeListViewer Paging', () {
    late MockJokeListDataSource mockDataSource;
    late MockAnalyticsService mockAnalyticsService;

    setUp(() {
      mockDataSource = MockJokeListDataSource();
      mockAnalyticsService = MockAnalyticsService();

      // Stub default behavior to avoid errors
      when(() => mockDataSource.loadMore()).thenAnswer((_) async {});
      when(() => mockDataSource.loadFirstPage()).thenAnswer((_) async {});
      when(
        () => mockDataSource.updateViewingIndex(any()),
      ).thenAnswer((_) async {});

      // Setup analytics service defaults
      when(
        () => mockAnalyticsService.logJokeNavigation(
          any(),
          any(),
          method: any(named: 'method'),
          jokeContext: any(named: 'jokeContext'),
          jokeViewerMode: any(named: 'jokeViewerMode'),
          brightness: any(named: 'brightness'),
        ),
      ).thenAnswer((_) async {});

      when(
        () => mockAnalyticsService.logErrorJokesLoad(
          source: any(named: 'source'),
          errorMessage: any(named: 'errorMessage'),
        ),
      ).thenAnswer((_) async {});
    });

    testWidgets('displays loading indicator when data is loading', (
      tester,
    ) async {
      // Arrange: Mock data source in loading state
      when(() => mockDataSource.items).thenReturn(
        Provider<AsyncValue<List<JokeWithDate>>>(
          (ref) => const AsyncValue<List<JokeWithDate>>.loading(),
        ),
      );
      when(
        () => mockDataSource.isDataPending,
      ).thenReturn(Provider<bool>((ref) => true));

      // Act: Build widget with ProviderScope
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
            jokeViewerRevealProvider.overrideWith(
              (ref) => _TestJokeViewerRevealNotifier(false),
            ),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: JokeListViewer(
                key: const Key('joke_list_viewer_paging_test-loading'),
                viewerId: 'test-viewer',
                jokeContext: 'test',
                dataSource: mockDataSource,
              ),
            ),
          ),
        ),
      );

      await tester.pump();

      // Assert: Loading indicator is shown
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('displays empty state when no jokes and not loading', (
      tester,
    ) async {
      // Arrange: Mock data source with empty list (not loading)
      when(() => mockDataSource.items).thenReturn(
        Provider<AsyncValue<List<JokeWithDate>>>(
          (ref) => const AsyncValue.data([]),
        ),
      );
      when(
        () => mockDataSource.isDataPending,
      ).thenReturn(Provider<bool>((ref) => false));

      // Act: Build widget
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
            jokeViewerRevealProvider.overrideWith(
              (ref) => _TestJokeViewerRevealNotifier(false),
            ),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: JokeListViewer(
                key: const Key('joke_list_viewer_paging_test-empty'),
                viewerId: 'test-viewer',
                jokeContext: 'test',
                dataSource: mockDataSource,
              ),
            ),
          ),
        ),
      );

      await tester.pump();

      // Assert: Empty state message is shown
      expect(find.text('No jokes found! Try adding some.'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets('displays error state when data loading fails', (tester) async {
      // Arrange: Mock data source with error state
      when(() => mockDataSource.items).thenReturn(
        Provider<AsyncValue<List<JokeWithDate>>>(
          (ref) => AsyncValue<List<JokeWithDate>>.error(
            Exception('Network error'),
            StackTrace.current,
          ),
        ),
      );

      // Act: Build widget
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
            jokeViewerRevealProvider.overrideWith(
              (ref) => _TestJokeViewerRevealNotifier(false),
            ),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: JokeListViewer(
                key: const Key('joke_list_viewer_paging_test-error'),
                viewerId: 'test-viewer',
                jokeContext: 'test',
                dataSource: mockDataSource,
              ),
            ),
          ),
        ),
      );

      await tester.pump();

      // Assert: Error message is shown
      expect(find.textContaining('Error loading jokes'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });
  });
}
