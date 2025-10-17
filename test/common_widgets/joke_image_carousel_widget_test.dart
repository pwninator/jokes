import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:smooth_page_indicator/smooth_page_indicator.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_schedule_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_schedule_repository.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

import '../common/test_utils/joke_carousel_test_utils.dart';

class MockImageService extends Mock implements ImageService {}

class MockJokeRepository extends Mock implements JokeRepository {}

class _FakeJoke extends Fake implements Joke {}

// Mock performance service to avoid Firebase initialization
class _MockPerformanceService extends Mock implements PerformanceService {}

// Mock analytics service to avoid Firebase initialization
class _MockAnalyticsService extends Mock implements AnalyticsService {}

// Simple spy service to capture calls triggered by the dialog
class _SpyScheduleService extends JokeScheduleAutoFillService {
  _SpyScheduleService()
    : super(
        jokeRepository: _NoopJokeRepository(),
        scheduleRepository: _NoopJokeScheduleRepository(),
      );

  String? lastJokeId;
  DateTime? lastDate;
  String lastScheduleId = '';

  @override
  Future<void> scheduleJokeToDate({
    required String jokeId,
    required DateTime date,
    required String scheduleId,
  }) async {
    lastJokeId = jokeId;
    lastDate = date;
    lastScheduleId = scheduleId;
  }
}

class _NoopJokeRepository extends Mock implements JokeRepository {}

class _NoopJokeScheduleRepository extends Mock
    implements JokeScheduleRepository {}

// Lifecycle/Dispose test
class _MockAppUsageService extends Mock implements AppUsageService {}

class Host extends StatefulWidget {
  const Host({super.key, required this.child});
  final Widget child;

  @override
  State<Host> createState() => _HostState();
}

class _HostState extends State<Host> {
  bool showChild = true;

  @override
  Widget build(BuildContext context) {
    return showChild ? widget.child : const SizedBox.shrink();
  }
}

void main() {
  setUpAll(() {
    registerCarouselTestFallbacks();
    registerFallbackValue(_FakeJoke());
  });

  late MockImageService mockImageService;
  late MockJokeRepository mockJokeRepository;
  late _MockPerformanceService mockPerformanceService;
  late _MockAnalyticsService mockAnalyticsService;
  late _MockAppUsageService mockAppUsageService;

  setUp(() {
    mockImageService = MockImageService();
    mockJokeRepository = MockJokeRepository();
    mockPerformanceService = _MockPerformanceService();
    mockAnalyticsService = _MockAnalyticsService();
    mockAppUsageService = _MockAppUsageService();

    stubImageServiceHappyPath(
      mockImageService,
      dataUrl: transparentImageDataUrl,
    );
    stubPerformanceNoOps(mockPerformanceService);
    stubAppUsageViewed(mockAppUsageService, viewedCount: 0);
  });

  group('Widget rendering', () {
    testWidgets('displays correctly with valid image URLs', (tester) async {
      // arrange
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      const widget = JokeImageCarousel(joke: joke, jokeContext: 'test');

      // act
      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
          extraOverrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        ),
      );
      await tester.pump(); // Let the widget build
      await tester.pump(const Duration(milliseconds: 100)); // Let images load

      // assert
      expect(find.byType(JokeImageCarousel), findsOneWidget);
      expect(find.byType(PageView), findsOneWidget);
    });

    testWidgets('page indicators work correctly', (tester) async {
      // arrange
      const joke = Joke(
        id: 'test-joke-1',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: 'https://example.com/setup.jpg',
        punchlineImageUrl: 'https://example.com/punchline.jpg',
      );

      const widget = JokeImageCarousel(joke: joke, jokeContext: 'test');

      // act
      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
          extraOverrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        ),
      );
      await tester.pump();

      // assert - should have 1 smooth page indicator
      final pageIndicator = find.byType(SmoothPageIndicator);
      expect(pageIndicator, findsOneWidget);
    });

    testWidgets('handles null image URLs gracefully', (tester) async {
      // arrange
      const jokeWithNullImages = Joke(
        id: 'test-joke-null',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: null,
        punchlineImageUrl: null,
      );

      const widget = JokeImageCarousel(
        joke: jokeWithNullImages,
        jokeContext: 'test',
      );

      // act
      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
          extraOverrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        ),
      );
      await tester.pump();

      // assert
      expect(find.byType(JokeImageCarousel), findsOneWidget);
      // Verify no errors are thrown
    });

    testWidgets('handles empty image URLs gracefully', (tester) async {
      // arrange
      const jokeWithEmptyUrls = Joke(
        id: 'test-joke-empty',
        setupText: 'Setup text',
        punchlineText: 'Punchline text',
        setupImageUrl: '',
        punchlineImageUrl: '',
      );

      const widget = JokeImageCarousel(
        joke: jokeWithEmptyUrls,
        jokeContext: 'test',
      );

      // act
      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          widget,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
          extraOverrides: [
            jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          ],
        ),
      );
      await tester.pump();

      // assert
      expect(find.byType(JokeImageCarousel), findsOneWidget);
    });
  });

  group('Reschedule badge flow', () {
    testWidgets('tapping future DAILY badge opens dialog and calls service', (
      tester,
    ) async {
      // arrange: DAILY with future timestamp
      final future = DateTime.now().add(const Duration(days: 10));
      final joke = Joke(
        id: 'daily-future-1',
        setupText: 'Setup',
        punchlineText: 'Punch',
        setupImageUrl: 'https://example.com/a.jpg',
        punchlineImageUrl: 'https://example.com/b.jpg',
        state: JokeState.daily,
        publicTimestamp: future,
      );

      // Spy service
      final spyService = _SpyScheduleService();

      final widget = wrapWithCarouselOverrides(
        JokeImageCarousel(joke: joke, isAdminMode: true, jokeContext: 'test'),
        imageService: mockImageService,
        appUsageService: mockAppUsageService,
        analyticsService: mockAnalyticsService,
        performanceService: mockPerformanceService,
        extraOverrides: [
          jokeRepositoryProvider.overrideWithValue(mockJokeRepository),
          jokeScheduleAutoFillServiceProvider.overrideWithValue(spyService),
        ],
      );

      // act
      await tester.pumpWidget(widget);
      await tester.pump();

      // Tap the state badge
      expect(find.byKey(const Key('daily-state-badge')), findsOneWidget);
      await tester.tap(find.byKey(const Key('daily-state-badge')));
      await tester.pump(const Duration(milliseconds: 100));

      // Dialog should appear with Change date button
      expect(find.text('Change scheduled date'), findsOneWidget);
      expect(
        find.byKey(const Key('reschedule_dialog-change-date-button')),
        findsOneWidget,
      );

      // Tap change date
      await tester.tap(
        find.byKey(const Key('reschedule_dialog-change-date-button')),
      );
      await tester.pump();

      // assert - service called
      expect(spyService.lastJokeId, equals('daily-future-1'));
      expect(spyService.lastScheduleId, isNotEmpty);
      expect(spyService.lastDate, isNotNull);
    });
  });

  group('Lifecycle/Dispose', () {
    const joke = Joke(
      id: 'jX',
      setupText: 's',
      punchlineText: 'p',
      setupImageUrl: 'https://example.com/a.jpg',
      punchlineImageUrl: 'https://example.com/b.jpg',
    );

    testWidgets('does not access ref after dispose during view logging', (
      tester,
    ) async {
      // Arrange delayed usage calls to simulate in-flight awaits
      when(
        () => mockAppUsageService.logJokeViewed(
          any(),
          context: any(named: 'context'),
        ),
      ).thenAnswer((_) async {
        await Future<void>.delayed(const Duration(milliseconds: 100));
      });
      when(() => mockAppUsageService.getNumJokesViewed()).thenAnswer((_) async {
        await Future<int>.delayed(const Duration(milliseconds: 500));
        return 7;
      });

      // Host widget that can remove the carousel from the tree
      final hostKey = GlobalKey<_HostState>();
      final host = Host(
        key: hostKey,
        child: const JokeImageCarousel(joke: joke, jokeContext: 'test'),
      );

      await tester.pumpWidget(
        wrapWithCarouselOverrides(
          host,
          imageService: mockImageService,
          appUsageService: mockAppUsageService,
          analyticsService: mockAnalyticsService,
          performanceService: mockPerformanceService,
        ),
      );
      await tester.pump();

      // Wait >2s to mark setup viewed
      await tester.pump(const Duration(milliseconds: 2100));

      // Navigate to punchline by tap, then complete page animation
      await tester.tap(find.byType(JokeImageCarousel));
      await tester.pump(const Duration(milliseconds: 350));

      // Wait >2s to trigger punchline viewed and start logging flow
      await tester.pump(const Duration(milliseconds: 2100));

      // While logging is in-flight, remove the widget from the tree
      await tester.pump(const Duration(milliseconds: 50)); // within first await
      hostKey.currentState!.showChild = false;
      await tester.pump();

      // Advance time to allow all delayed futures to complete
      await tester.pump(const Duration(seconds: 1));

      // If ref.read after dispose occurs, the test will throw. Reaching here means success.
      expect(true, isTrue);
    });
  });
}
