import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:share_plus/share_plus.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/joke_share_service.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_reactions_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_reaction_type.dart';

class MockImageService extends Mock implements ImageService {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockJokeReactionsService extends Mock implements JokeReactionsService {}

class MockPlatformShareService extends Mock implements PlatformShareService {}

class FakeJoke extends Fake implements Joke {}

class FakeXFile extends Fake implements XFile {}

void main() {
  group('JokeShareService', () {
    late JokeShareService service;
    late MockImageService mockImageService;
    late MockAnalyticsService mockAnalyticsService;
    late MockJokeReactionsService mockJokeReactionsService;
    late MockPlatformShareService mockPlatformShareService;

    setUpAll(() {
      registerFallbackValue(FakeJoke());
      registerFallbackValue(JokeReactionType.share);
      registerFallbackValue(FakeXFile());
    });

    setUp(() {
      mockImageService = MockImageService();
      mockAnalyticsService = MockAnalyticsService();
      mockJokeReactionsService = MockJokeReactionsService();
      mockPlatformShareService = MockPlatformShareService();

      service = JokeShareServiceImpl(
        imageService: mockImageService,
        analyticsService: mockAnalyticsService,
        reactionsService: mockJokeReactionsService,
        platformShareService: mockPlatformShareService,
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

        when(() => mockImageService.precacheJokeImages(any())).thenAnswer(
          (_) async => (
            setupUrl: 'https://example.com/setup.jpg',
            punchlineUrl: 'https://example.com/punchline.jpg',
          ),
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
          ),
        ).thenAnswer(
          (_) async => const ShareResult('', ShareResultStatus.success),
        );

        when(
          () => mockJokeReactionsService.addUserReaction(
            any(),
            any(),
            jokeContext: any(named: 'jokeContext'),
          ),
        ).thenAnswer((_) async {});

        when(
          () => mockAnalyticsService.logJokeShared(
            any(),
            jokeContext: any(named: 'jokeContext'),
            shareMethod: any(named: 'shareMethod'),
            shareSuccess: any(named: 'shareSuccess'),
          ),
        ).thenAnswer((_) async {});

        // Act
        final result = await service.shareJoke(
          joke,
          jokeContext: 'test-context',
        );

        // Assert
        expect(result, isTrue);

        verify(
          () => mockJokeReactionsService.addUserReaction(
            'test-joke-id',
            JokeReactionType.share,
            jokeContext: 'test-context',
          ),
        ).called(1);

        verify(
          () => mockAnalyticsService.logJokeShared(
            'test-joke-id',
            jokeContext: 'test-context',
            shareMethod: 'images',
            shareSuccess: true,
          ),
        ).called(1);
      },
    );
  });
}
