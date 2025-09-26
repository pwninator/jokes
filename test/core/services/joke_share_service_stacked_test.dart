import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
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
  group('JokeShareService with stacked images', () {
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
      registerFallbackValue(FakeXFile());
      registerFallbackValue(ReviewRequestSource.jokeShared);
      registerFallbackValue(JokeReactionType.share);
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

      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      appUsageService = AppUsageService(prefs: prefs);

      service = JokeShareServiceImpl(
        imageService: mockImageService,
        analyticsService: mockAnalyticsService,
        reactionsService: mockJokeReactionsService,
        platformShareService: mockPlatformShareService,
        appUsageService: appUsageService,
        reviewPromptCoordinator: mockCoordinator,
        performanceService: mockPerformanceService,
        remoteConfigValues: mockRemoteConfigValues,
        getRevealModeEnabled: () => true,
      );

      when(() => mockImageService.addWatermarkToFiles(any())).thenAnswer(
        (invocation) async => List<XFile>.from(
          invocation.positionalArguments.first as List<XFile>,
        ),
      );
      when(() => mockImageService.addWatermarkToFile(any())).thenAnswer(
        (invocation) async => invocation.positionalArguments.first as XFile,
      );
      when(
        () => mockImageService.stackImages(any()),
      ).thenAnswer((invocation) async => XFile('stacked.jpg'));
    });

    test(
      'shareJoke should call stackImages when remote config is true',
      () async {
        when(
          () => mockRemoteConfigValues.getEnum<ShareImagesMode>(
            RemoteParam.shareImagesMode,
          ),
        ).thenReturn(ShareImagesMode.stacked);

        const joke = Joke(
          id: 'test-joke-id',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
        );

        final mockFiles = [XFile('setup.jpg'), XFile('punchline.jpg')];

        when(
          () => mockImageService.getProcessedJokeImageUrl(
            any(),
            width: any(named: 'width'),
          ),
        ).thenAnswer(
          (invocation) => invocation.positionalArguments.first as String?,
        );

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

        await service.shareJoke(joke, jokeContext: 'test-context');

        verify(() => mockImageService.stackImages(any())).called(1);
        verify(() => mockImageService.addWatermarkToFiles(any())).called(1);
        verifyNever(() => mockImageService.addWatermarkToFile(any()));
      },
    );

    test(
      'shareJoke should not call stackImages when remote config is false',
      () async {
        when(
          () => mockRemoteConfigValues.getEnum<ShareImagesMode>(
            RemoteParam.shareImagesMode,
          ),
        ).thenReturn(ShareImagesMode.separate);

        const joke = Joke(
          id: 'test-joke-id',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
        );

        final mockFiles = [XFile('setup.jpg'), XFile('punchline.jpg')];

        when(
          () => mockImageService.getProcessedJokeImageUrl(
            any(),
            width: any(named: 'width'),
          ),
        ).thenAnswer(
          (invocation) => invocation.positionalArguments.first as String?,
        );

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

        await service.shareJoke(joke, jokeContext: 'test-context');

        verifyNever(() => mockImageService.stackImages(any()));
        verifyNever(() => mockImageService.addWatermarkToFile(any()));
        verify(() => mockImageService.addWatermarkToFiles(any())).called(1);
      },
    );
  });
}
