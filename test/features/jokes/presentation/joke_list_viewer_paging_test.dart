import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/analytics_parameters.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/services/crash_reporting_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_list_data_source.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_viewer_mode.dart';
import 'package:snickerdoodle/src/features/jokes/presentation/joke_list_viewer.dart';
import 'package:snickerdoodle/src/features/settings/application/joke_viewer_settings_service.dart';

class MockJokeListDataSource extends Mock implements JokeListDataSource {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockCrashReportingService extends Mock implements CrashReportingService {}

class MockJokeViewerSettingsService extends Mock
    implements JokeViewerSettingsService {}

void main() {
  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(JokeViewerMode.reveal);
    registerFallbackValue(Brightness.light);
    registerFallbackValue(StackTrace.empty);
  });

  group('JokeListViewer Paging', () {
    late MockJokeListDataSource mockDataSource;
    late MockAnalyticsService mockAnalyticsService;
    late MockJokeViewerSettingsService mockViewerSettingsService;

    setUp(() {
      mockDataSource = MockJokeListDataSource();
      mockAnalyticsService = MockAnalyticsService();
      mockViewerSettingsService = MockJokeViewerSettingsService();
      when(
        () => mockViewerSettingsService.getReveal(),
      ).thenAnswer((_) async => false);
      when(
        () => mockViewerSettingsService.setReveal(any()),
      ).thenAnswer((_) async {});

      // Stub default behavior to avoid errors
      when(() => mockDataSource.loadMore()).thenAnswer((_) async {});
      when(() => mockDataSource.loadFirstPage()).thenAnswer((_) async {});
      when(
        () => mockDataSource.updateViewingIndex(any()),
      ).thenAnswer((_) async {});
      when(
        () => mockDataSource.hasMore,
      ).thenReturn(Provider<bool>((ref) => false));
      when(
        () => mockDataSource.isLoading,
      ).thenReturn(Provider<bool>((ref) => false));
      when(
        () => mockDataSource.isDataPending,
      ).thenReturn(Provider<bool>((ref) => false));
      when(() => mockDataSource.resultCount).thenReturn(
        Provider<({int count, bool hasMore})>(
          (ref) => (count: 0, hasMore: false),
        ),
      );

      // Setup analytics service defaults
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
      ).thenAnswer((_) async {});

      when(
        () => mockAnalyticsService.logErrorJokesLoad(
          source: any(named: 'source'),
          errorMessage: any(named: 'errorMessage'),
        ),
      ).thenAnswer((_) async {});
      when(
        () => mockAnalyticsService.logJokeFeedEndEmptyViewed(
          jokeContext: any(named: 'jokeContext'),
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
      when(
        () => mockDataSource.isLoading,
      ).thenReturn(Provider<bool>((ref) => true));

      // Act: Build widget with ProviderScope
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
            jokeViewerRevealProvider.overrideWith(
              (ref) => JokeViewerRevealNotifier(mockViewerSettingsService),
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
              (ref) => JokeViewerRevealNotifier(mockViewerSettingsService),
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
              (ref) => JokeViewerRevealNotifier(mockViewerSettingsService),
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

    testWidgets('logs analytics and error when feed viewer shows empty state', (
      tester,
    ) async {
      // Arrange: feed viewer with empty data
      final mockCrashService = MockCrashReportingService();
      when(
        () => mockCrashService.recordNonFatal(
          any(),
          stackTrace: any(named: 'stackTrace'),
          keys: any(named: 'keys'),
        ),
      ).thenAnswer((_) async {});
      when(
        () => mockCrashService.recordFatal(
          any(),
          any(),
          keys: any(named: 'keys'),
        ),
      ).thenAnswer((_) async {});
      when(() => mockCrashService.log(any())).thenAnswer((_) async {});
      when(() => mockCrashService.setKeys(any())).thenAnswer((_) async {});
      AppLogger.setInstanceForTesting(
        AppLogger.createForTesting(crashReportingService: mockCrashService),
      );
      addTearDown(() {
        AppLogger.setInstanceForTesting(
          AppLogger.createForTesting(
            crashReportingService: NoopCrashReportingService(),
          ),
        );
      });

      when(() => mockDataSource.items).thenReturn(
        Provider<AsyncValue<List<JokeWithDate>>>(
          (ref) => const AsyncValue.data([]),
        ),
      );
      when(
        () => mockDataSource.isDataPending,
      ).thenReturn(Provider<bool>((ref) => false));
      when(() => mockDataSource.resultCount).thenReturn(
        Provider<({int count, bool hasMore})>(
          (ref) => (count: 0, hasMore: false),
        ),
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
            jokeViewerRevealProvider.overrideWith(
              (ref) => JokeViewerRevealNotifier(mockViewerSettingsService),
            ),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: JokeListViewer(
                key: Key('joke_list_viewer_paging_test-feed-empty'),
                viewerId: 'joke_feed',
                jokeContext: AnalyticsJokeContext.jokeFeed,
                dataSource: mockDataSource,
              ),
            ),
          ),
        ),
      );

      await tester.pump();

      verify(
        () => mockAnalyticsService.logJokeFeedEndEmptyViewed(
          jokeContext: AnalyticsJokeContext.jokeFeed,
        ),
      ).called(1);

      final verificationResult = verify(
        () => mockCrashService.recordNonFatal(
          captureAny(),
          stackTrace: any(named: 'stackTrace'),
          keys: any(named: 'keys'),
        ),
      );
      final loggedError = verificationResult.captured.first.toString();
      expect(loggedError, contains('Empty feed state shown'));
    });
  });
}
