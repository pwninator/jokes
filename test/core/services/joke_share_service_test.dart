import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:share_plus/share_plus.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/joke_share_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

class MockImageService extends Mock implements ImageService {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockPlatformShareService extends Mock implements PlatformShareService {}

class MockAppUsageService extends Mock implements AppUsageService {}

class MockPerformanceService extends Mock implements PerformanceService {}

class MockRemoteConfigValues extends Mock implements RemoteConfigValues {}

class FakeJoke extends Fake implements Joke {}

class FakeXFile extends Fake implements XFile {}

class FakeBuildContext extends Fake implements BuildContext {}

void main() {
  group('JokeShareService', () {
    late JokeShareService service;
    late MockImageService mockImageService;
    late MockAnalyticsService mockAnalyticsService;
    late MockPlatformShareService mockPlatformShareService;
    late MockPerformanceService mockPerformanceService;
    late MockAppUsageService appUsageService;
    late MockRemoteConfigValues mockRemoteConfigValues;
    late BuildContext fakeContext;
    late Future<Set<String>> Function() getAssetManifest;

    setUpAll(() {
      registerFallbackValue(FakeJoke());
      registerFallbackValue(JokeReactionType.share);
      registerFallbackValue(FakeXFile());
      registerFallbackValue(FakeBuildContext());
      registerFallbackValue(Uint8List(0));
    });

    setUp(() async {
      mockImageService = MockImageService();
      mockAnalyticsService = MockAnalyticsService();
      mockPlatformShareService = MockPlatformShareService();
      mockPerformanceService = MockPerformanceService();
      mockRemoteConfigValues = MockRemoteConfigValues();
      fakeContext = FakeBuildContext();
      appUsageService = MockAppUsageService();
      when(
        () => mockRemoteConfigValues.getEnum<ShareImagesMode>(
          RemoteParam.shareImagesMode,
        ),
      ).thenReturn(ShareImagesMode.separate);

      getAssetManifest = () async => <String>{};

      service = JokeShareServiceImpl(
        imageService: mockImageService,
        analyticsService: mockAnalyticsService,
        platformShareService: mockPlatformShareService,
        appUsageService: appUsageService,
        performanceService: mockPerformanceService,
        remoteConfigValues: mockRemoteConfigValues,
        getRevealModeEnabled: () => true,
        getAssetManifest: getAssetManifest,
      );

      // Default watermark behavior: passthrough original files
      when(() => mockImageService.addWatermarkToFiles(any())).thenAnswer(
        (invocation) async => List<XFile>.from(
          invocation.positionalArguments.first as List<XFile>,
        ),
      );
      when(
        () => mockImageService.getAssetPathForUrl(any(), any()),
      ).thenReturn(null);
      when(
        () => mockImageService.loadAssetBytes(any()),
      ).thenAnswer((_) async => null);
      when(
        () => mockImageService.createTempXFileFromBytes(
          any(),
          fileName: any(named: 'fileName'),
          prefix: any(named: 'prefix'),
        ),
      ).thenAnswer((_) async => XFile('temp.png'));
    });

    test('shareJoke uses bundled assets when manifest contains tails', () async {
      const joke = Joke(
        id: 'asset-joke-id',
        setupText: 'Test setup',
        punchlineText: 'Test punchline',
        setupImageUrl:
            'https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/pun_agent_image.png',
        punchlineImageUrl:
            'https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/some_dir/file_name.png',
        adminRating: null,
      );

      final assetBytes = Uint8List.fromList([0, 1, 2, 3]);
      when(
        () => mockPlatformShareService.shareFiles(
          any(),
          subject: any(named: 'subject'),
        ),
      ).thenAnswer(
        (_) async => const ShareResult('', ShareResultStatus.success),
      );
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
      when(
        () => appUsageService.shareJoke(any(), context: any(named: 'context')),
      ).thenAnswer((_) async {});
      when(
        () => appUsageService.getNumSharedJokes(),
      ).thenAnswer((_) async => 1);

      final manifestTails = <String>{
        'pun_agent_image.png',
        'some_dir/file_name.png',
      };
      final assetAwareService = JokeShareServiceImpl(
        imageService: mockImageService,
        analyticsService: mockAnalyticsService,
        platformShareService: mockPlatformShareService,
        appUsageService: appUsageService,
        performanceService: mockPerformanceService,
        remoteConfigValues: mockRemoteConfigValues,
        getRevealModeEnabled: () => true,
        getAssetManifest: () async => manifestTails,
      );

      when(
        () => mockImageService.getProcessedJokeImageUrl(
          any(),
          width: any(named: 'width'),
        ),
      ).thenAnswer(
        (invocation) => invocation.positionalArguments.first as String,
      );
      when(
        () => mockImageService.getCachedFileFromUrl(any()),
      ).thenAnswer((_) async => null);
      when(
        () => mockImageService.getAssetPathForUrl(
          joke.setupImageUrl,
          manifestTails,
        ),
      ).thenReturn('assets/data_bundles/images/pun_agent_image.png');
      when(
        () => mockImageService.getAssetPathForUrl(
          joke.punchlineImageUrl,
          manifestTails,
        ),
      ).thenReturn('assets/data_bundles/images/some_dir/file_name.png');
      when(
        () => mockImageService.loadAssetBytes(any()),
      ).thenAnswer((_) async => assetBytes);
      when(
        () => mockImageService.createTempXFileFromBytes(
          assetBytes,
          fileName: any(named: 'fileName'),
          prefix: any(named: 'prefix'),
        ),
      ).thenAnswer(
        (invocation) async =>
            XFile('temp_${invocation.namedArguments[#fileName] as String}'),
      );

      final result = await assetAwareService.shareJoke(
        joke,
        jokeContext: 'test-context',
        context: fakeContext,
      );

      expect(result, isTrue);
      verify(
        () => mockImageService.getProcessedJokeImageUrl(
          joke.setupImageUrl,
          width: any(named: 'width'),
        ),
      ).called(1);
      verify(
        () => mockImageService.getProcessedJokeImageUrl(
          joke.punchlineImageUrl,
          width: any(named: 'width'),
        ),
      ).called(1);
      verify(
        () => mockImageService.getCachedFileFromUrl(joke.setupImageUrl!),
      ).called(1);
      verify(
        () => mockImageService.getCachedFileFromUrl(joke.punchlineImageUrl!),
      ).called(1);
      verify(
        () => mockImageService.getAssetPathForUrl(
          joke.setupImageUrl,
          manifestTails,
        ),
      ).called(1);
      verify(
        () => mockImageService.getAssetPathForUrl(
          joke.punchlineImageUrl,
          manifestTails,
        ),
      ).called(1);
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
          ),
        ).thenAnswer(
          (_) async => const ShareResult('', ShareResultStatus.success),
        );

        when(
          () =>
              appUsageService.shareJoke(any(), context: any(named: 'context')),
        ).thenAnswer((_) async {});
        when(
          () => appUsageService.getNumSharedJokes(),
        ).thenAnswer((_) async => 1);

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
          context: fakeContext,
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
        ).called(2);

        verify(
          () => appUsageService.shareJoke(
            'test-joke-id',
            context: any(named: 'context'),
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
      'shareJoke should allow user abort during preparation and log aborted',
      () async {
        // Arrange
        const joke = Joke(
          id: 'test-joke-id',
          setupText: 'Test setup',
          punchlineText: 'Test punchline',
          setupImageUrl: 'https://example.com/setup.jpg',
          punchlineImageUrl: 'https://example.com/punchline.jpg',
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

        // Platform share should never be called when aborted pre-share
        when(
          () => mockPlatformShareService.shareFiles(
            any(),
            subject: any(named: 'subject'),
          ),
        ).thenThrow(Exception('Should not be called'));

        when(
          () => mockAnalyticsService.logJokeShareInitiated(
            any(),
            jokeContext: any(named: 'jokeContext'),
          ),
        ).thenAnswer((_) async {});
        when(
          () => mockAnalyticsService.logJokeShareAborted(
            any(),
            jokeContext: any(named: 'jokeContext'),
          ),
        ).thenAnswer((_) async {});

        final controller = SharePreparationController();

        // Act - cancel immediately after downloads (simulate UI cancel early)
        controller.cancel();
        final result = await service.shareJoke(
          joke,
          jokeContext: 'test-context',
          controller: controller,
          context: fakeContext,
        );

        // Assert
        expect(result, isFalse);
        verify(
          () => mockAnalyticsService.logJokeShareInitiated(
            'test-joke-id',
            jokeContext: 'test-context',
          ),
        ).called(1);
        verify(
          () => mockAnalyticsService.logJokeShareAborted(
            'test-joke-id',
            jokeContext: 'test-context',
          ),
        ).called(1);
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
          ),
        ).thenAnswer(
          (_) async => const ShareResult('', ShareResultStatus.dismissed),
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
          ),
        ).thenAnswer((_) async {});

        // Act
        final result = await service.shareJoke(
          joke,
          jokeContext: 'test-context',
          context: fakeContext,
        );

        // Assert
        when(
          () => appUsageService.getNumSharedJokes(),
        ).thenAnswer((_) async => 0);
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
        ).called(2);

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
          ),
        ).thenAnswer(
          (_) async => const ShareResult('', ShareResultStatus.success),
        );

        when(
          () =>
              appUsageService.shareJoke(any(), context: any(named: 'context')),
        ).thenAnswer((_) async {});

        when(
          () => appUsageService.getNumSharedJokes(),
        ).thenAnswer((_) async => 1);

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
          context: fakeContext,
        );

        // Assert
        verify(
          () => mockPlatformShareService.shareFiles(
            any(),
            subject: 'Test subject',
          ),
        ).called(1);
      },
    );
  });
}
