import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:share_plus/share_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_review_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/joke_share_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/services/review_prompt_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

class MockImageService extends Mock implements ImageService {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockJokeReactionsService extends Mock implements JokeReactionsService {}

class MockPlatformShareService extends Mock implements PlatformShareService {}

class MockReviewPromptCoordinator extends Mock
    implements ReviewPromptCoordinator {}

class MockPerformanceService extends Mock implements PerformanceService {}

class MockRemoteConfigValues extends Mock implements RemoteConfigValues {}

class FakeJoke extends Fake implements Joke {}

class FakeXFile extends Fake implements XFile {}

void main() {
  group('JokeShareService', () {
    late JokeShareService service;
    late MockImageService mockImageService;
    late MockAnalyticsService mockAnalyticsService;
    late MockJokeReactionsService mockJokeReactionsService;
    late MockPlatformShareService mockPlatformShareService;
    late MockPerformanceService mockPerformanceService;
    late AppUsageService appUsageService;
    late ReviewPromptCoordinator mockCoordinator;
    late MockRemoteConfigValues mockRemoteConfigValues;

    setUpAll(() {
      registerFallbackValue(FakeJoke());
      registerFallbackValue(JokeReactionType.share);
      registerFallbackValue(FakeXFile());
      registerFallbackValue(ReviewRequestSource.jokeShared);
    });

    setUp(() async {
      mockImageService = MockImageService();
      mockAnalyticsService = MockAnalyticsService();
      mockJokeReactionsService = MockJokeReactionsService();
      mockPlatformShareService = MockPlatformShareService();
      mockCoordinator = MockReviewPromptCoordinator();
      mockPerformanceService = MockPerformanceService();
      mockRemoteConfigValues = MockRemoteConfigValues();
      when(
        () =>
            mockCoordinator.maybePromptForReview(source: any(named: 'source')),
      ).thenAnswer((_) async {});
      // Real AppUsageService with mock SharedPreferences
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      appUsageService = AppUsageService(prefs: prefs);

      when(
        () => mockRemoteConfigValues.getEnum<ShareImagesMode>(
          RemoteParam.shareImagesMode,
        ),
      ).thenReturn(ShareImagesMode.separate);

      service = JokeShareServiceImpl(
        imageService: mockImageService,
        analyticsService: mockAnalyticsService,
        reactionsService: mockJokeReactionsService,
        platformShareService: mockPlatformShareService,
        appUsageService: appUsageService,
        reviewPromptCoordinator: mockCoordinator,
        performanceService: mockPerformanceService,
        remoteConfigValues: mockRemoteConfigValues,
      );

      // Default watermark behavior: passthrough original files
      when(() => mockImageService.addWatermarkToFiles(any())).thenAnswer(
        (invocation) async => List<XFile>.from(
          invocation.positionalArguments.first as List<XFile>,
        ),
      );
    });

    test(
      'shareJoke should save joke and log analytics when sharing succeeds',
      () async {
        // Arrange
        const joke = Joke(
          id: 'test-joke-id',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
          numThumbsUp: 0,
          numThumbsDown: 0,
          adminRating: null,
        );

        final mockFiles = [XFile('setup.jpg'), XFile('punchline.jpg')];

        when(
          () => mockImageService.getProcessedJokeImageUrl(
            any(),
            width: any(named: 'width'),
          ),
        ).thenAnswer((invocation) {
          final arg = invocation.positionalArguments.first as String?;
          return arg; // passthrough
        });

        when(
          () => mockImageService.getCachedFileFromUrl(
            'https://example.com/setup.jpg',
          ),
        ).thenAnswer((_) async => mockFiles[0]);

        when(
          () => mockImageService.getCachedFileFromUrl(
            'https://example.com/punchline.jpg',
          ),
        ).thenAnswer((_) async => mockFiles[1]);

        when(
          () => mockPlatformShareService.shareFiles(
            any(),
            subject: any(named: 'subject'),
            text: any(named: 'text'),
          ),
        ).thenAnswer(
          (_) async => const ShareResult('', ShareResultStatus.success),
        );

        when(
          () => mockJokeReactionsService.addUserReaction(any(), any()),
        ).thenAnswer((_) async {});

        when(
          () => mockAnalyticsService.logJokeShareInitiated(
            any(),
            jokeContext: any(named: 'jokeContext'),
          ),
        ).thenAnswer((_) async {});
        when(
          () => mockAnalyticsService.logJokeShareSuccess(
            any(),
            jokeContext: any(named: 'jokeContext'),
            shareDestination: any(named: 'shareDestination'),
            totalJokesShared: any(named: 'totalJokesShared'),
          ),
        ).thenAnswer((_) async {});

        // Act
        final result = await service.shareJoke(
          joke,
          jokeContext: 'test-context',
        );

        // Assert
        expect(result, isTrue);

        // Verify performance trace start/stop
        verify(
          () => mockPerformanceService.startNamedTrace(
            name: TraceName.sharePreparation,
            key: 'images:test-joke-id',
            attributes: any(named: 'attributes'),
          ),
        ).called(1);
        verify(
          () => mockPerformanceService.stopNamedTrace(
            name: TraceName.sharePreparation,
            key: 'images:test-joke-id',
          ),
        ).called(1);

        verify(
          () => mockJokeReactionsService.addUserReaction(
            'test-joke-id',
            JokeReactionType.share,
          ),
        ).called(1);

        verify(
          () => mockAnalyticsService.logJokeShareInitiated(
            'test-joke-id',
            jokeContext: 'test-context',
          ),
        ).called(1);
        verify(
          () => mockAnalyticsService.logJokeShareSuccess(
            'test-joke-id',
            jokeContext: 'test-context',
            shareDestination: any(named: 'shareDestination'),
            totalJokesShared: any(named: 'totalJokesShared'),
          ),
        ).called(1);
        expect(await appUsageService.getNumSharedJokes(), 1);
      },
    );
    test(
      'shareJoke should not increment shared counter when sharing fails',
      () async {
        // Arrange
        const joke = Joke(
          id: 'test-joke-id',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
          numThumbsUp: 0,
          numThumbsDown: 0,
          adminRating: null,
        );

        final mockFiles = [XFile('setup.jpg'), XFile('punchline.jpg')];

        when(
          () => mockImageService.getProcessedJokeImageUrl(
            any(),
            width: any(named: 'width'),
          ),
        ).thenAnswer((invocation) {
          final arg = invocation.positionalArguments.first as String?;
          return arg; // passthrough
        });

        when(
          () => mockImageService.getCachedFileFromUrl(
            'https://example.com/setup.jpg',
          ),
        ).thenAnswer((_) async => mockFiles[0]);

        when(
          () => mockImageService.getCachedFileFromUrl(
            'https://example.com/punchline.jpg',
          ),
        ).thenAnswer((_) async => mockFiles[1]);

        when(
          () => mockPlatformShareService.shareFiles(
            any(),
            subject: any(named: 'subject'),
            text: any(named: 'text'),
          ),
        ).thenAnswer(
          (_) async => const ShareResult('', ShareResultStatus.unavailable),
        );

        when(
          () => mockAnalyticsService.logJokeShareInitiated(
            any(),
            jokeContext: any(named: 'jokeContext'),
          ),
        ).thenAnswer((_) async {});
        when(
          () => mockAnalyticsService.logJokeShareCanceled(
            any(),
            jokeContext: any(named: 'jokeContext'),
            shareDestination: any(named: 'shareDestination'),
          ),
        ).thenAnswer((_) async {});

        // Act
        final result = await service.shareJoke(
          joke,
          jokeContext: 'test-context',
        );

        // Assert
        expect(result, isFalse);
        expect(await appUsageService.getNumSharedJokes(), 0);

        // Verify performance trace start/stop
        verify(
          () => mockPerformanceService.startNamedTrace(
            name: TraceName.sharePreparation,
            key: 'images:test-joke-id',
            attributes: any(named: 'attributes'),
          ),
        ).called(1);
        verify(
          () => mockPerformanceService.stopNamedTrace(
            name: TraceName.sharePreparation,
            key: 'images:test-joke-id',
          ),
        ).called(1);

        verify(
          () => mockAnalyticsService.logJokeShareInitiated(
            'test-joke-id',
            jokeContext: 'test-context',
          ),
        ).called(1);
        verify(
          () => mockAnalyticsService.logJokeShareCanceled(
            'test-joke-id',
            jokeContext: 'test-context',
            shareDestination: any(named: 'shareDestination'),
          ),
        ).called(1);
      },
    );

    test(
      'shareJoke should pass correct text parameter to platform share service',
      () async {
        // Arrange
        const joke = Joke(
          id: 'test-joke-id',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
          numThumbsUp: 0,
          numThumbsDown: 0,
          adminRating: null,
        );

        final mockFiles = [XFile('setup.jpg'), XFile('punchline.jpg')];

        when(
          () => mockImageService.getProcessedJokeImageUrl(
            any(),
            width: any(named: 'width'),
          ),
        ).thenAnswer((invocation) {
          final arg = invocation.positionalArguments.first as String?;
          return arg; // passthrough
        });

        when(
          () => mockImageService.getCachedFileFromUrl(
            'https://example.com/setup.jpg',
          ),
        ).thenAnswer((_) async => mockFiles[0]);

        when(
          () => mockImageService.getCachedFileFromUrl(
            'https://example.com/punchline.jpg',
          ),
        ).thenAnswer((_) async => mockFiles[1]);

        when(
          () => mockPlatformShareService.shareFiles(
            any(),
            subject: any(named: 'subject'),
            text: any(named: 'text'),
          ),
        ).thenAnswer(
          (_) async => const ShareResult('', ShareResultStatus.success),
        );

        when(
          () => mockJokeReactionsService.addUserReaction(any(), any()),
        ).thenAnswer((_) async {});

        when(
          () => mockAnalyticsService.logJokeShareInitiated(
            any(),
            jokeContext: any(named: 'jokeContext'),
          ),
        ).thenAnswer((_) async {});
        when(
          () => mockAnalyticsService.logJokeShareSuccess(
            any(),
            jokeContext: any(named: 'jokeContext'),
            shareDestination: any(named: 'shareDestination'),
            totalJokesShared: any(named: 'totalJokesShared'),
          ),
        ).thenAnswer((_) async {});

        // Act
        await service.shareJoke(
          joke,
          jokeContext: 'test-context',
          subject: 'Test subject',
          text: 'Test text',
        );

        // Assert
        verify(
          () => mockPlatformShareService.shareFiles(
            any(),
            subject: 'Test subject',
            text: 'Test text',
          ),
        ).called(1);
      },
    );
  });
}
