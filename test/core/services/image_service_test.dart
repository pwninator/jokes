import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

// Mock classes for testing
class MockJoke extends Mock implements Joke {}

void main() {
  group('ImageService', () {
    late ImageService imageService;

    setUpAll(() {
      // Initialize Flutter binding for tests that need it
      TestWidgetsFlutterBinding.ensureInitialized();
    });

    setUp(() {
      imageService = ImageService();
    });

    group('isValidImageUrl', () {
      test('should return true for valid HTTP image URLs', () {
        // arrange
        const validUrls = [
          'https://example.com/image.jpg',
          'http://example.com/photo.png',
          'https://example.com/pic.jpeg',
          'https://example.com/graphic.gif',
          'https://example.com/image.webp',
          'https://example.com/picture.bmp',
        ];

        // act & assert
        for (final url in validUrls) {
          expect(
            imageService.isValidImageUrl(url),
            true,
            reason: 'URL: $url should be valid',
          );
        }
      });

      test(
        'should return true for dynamic image URLs with query parameters',
        () {
          // arrange
          const dynamicUrls = [
            'https://example.com/api/image?id=123&format=jpg',
            'https://example.com/images/dynamic-image?size=large',
            'https://example.com/cdn/image/12345',
          ];

          // act & assert
          for (final url in dynamicUrls) {
            expect(
              imageService.isValidImageUrl(url),
              true,
              reason: 'URL: $url should be valid',
            );
          }
        },
      );

      test('should return false for null or empty URLs', () {
        // act & assert
        expect(imageService.isValidImageUrl(null), false);
        expect(imageService.isValidImageUrl(''), false);
        expect(imageService.isValidImageUrl('   '), false);
      });

      test('should return false for invalid URLs', () {
        // arrange
        const invalidUrls = [
          'not-a-url',
          'ftp://example.com/image.jpg',
          'file:///local/image.jpg',
          'https://example.com/document.pdf',
          'https://example.com/text.txt',
          'invalid-url-format',
        ];

        // act & assert
        for (final url in invalidUrls) {
          expect(
            imageService.isValidImageUrl(url),
            false,
            reason: 'URL: $url should be invalid',
          );
        }
      });

      test('should return false for malformed URLs', () {
        // arrange
        const malformedUrls = [
          'https://',
          'http://',
          'https:///',
          'not valid url',
        ];

        // act & assert
        for (final url in malformedUrls) {
          expect(
            imageService.isValidImageUrl(url),
            false,
            reason: 'URL: $url should be invalid',
          );
        }
      });
    });

    group('processImageUrl', () {
      test('should return the same URL for valid URLs', () {
        // arrange
        const validUrl = 'https://example.com/image.jpg';

        // act
        final result = imageService.processImageUrl(validUrl);

        // assert
        expect(result, equals(validUrl));
      });

      test('should throw ArgumentError for invalid URLs', () {
        // arrange
        const invalidUrl = 'not-a-valid-url';

        // act & assert
        expect(
          () => imageService.processImageUrl(invalidUrl),
          throwsA(isA<ArgumentError>()),
        );
      });

      test('should process URLs with optional parameters', () {
        // arrange
        const validUrl = 'https://example.com/image.jpg';

        // act
        final result = imageService.processImageUrl(
          validUrl,
          width: 200,
          height: 150,
          quality: 'high',
        );

        // assert
        expect(result, equals(validUrl)); // Currently returns the same URL
      });
    });

    group('getThumbnailUrl', () {
      test('should return processed URL for thumbnails', () {
        // arrange
        const validUrl = 'https://example.com/image.jpg';

        // act
        final result = imageService.getThumbnailUrl(validUrl);

        // assert
        expect(result, equals(validUrl)); // Currently returns the same URL
      });

      test('should accept custom thumbnail size', () {
        // arrange
        const validUrl = 'https://example.com/image.jpg';
        const customSize = 200;

        // act
        final result = imageService.getThumbnailUrl(validUrl, size: customSize);

        // assert
        expect(result, equals(validUrl)); // Currently returns the same URL
      });
    });

    group('getFullSizeUrl', () {
      test('should return processed URL for full size images', () {
        // arrange
        const validUrl = 'https://example.com/image.jpg';

        // act
        final result = imageService.getFullSizeUrl(validUrl);

        // assert
        expect(result, equals(validUrl)); // Currently returns the same URL
      });
    });

    group('cache management', () {
      test('cache constants should be defined correctly', () {
        // assert
        expect(ImageService.defaultCacheDuration, isA<Duration>());
        expect(ImageService.maxCacheSize, isA<int>());
        expect(ImageService.maxCacheSize, greaterThan(0));
      });
    });

    group('constants', () {
      test('should have correct default cache duration', () {
        // assert
        expect(
          ImageService.defaultCacheDuration,
          equals(const Duration(days: 30)),
        );
      });

      test('should have correct max cache size', () {
        // assert
        expect(ImageService.maxCacheSize, equals(100 * 1024 * 1024)); // 100MB
      });
    });

    group('Joke image methods', () {
      group('constants', () {
        test('should have correct joke image quality', () {
          // assert
          expect(ImageService.jokeImageQuality, equals(50));
        });

        test('should have correct joke image HTTP headers', () {
          // assert
          expect(ImageService.jokeImageHttpHeaders, isA<Map<String, String>>());
          expect(
            ImageService.jokeImageHttpHeaders['Accept'],
            contains('image/webp'),
          );
          expect(
            ImageService.jokeImageHttpHeaders['Accept-Encoding'],
            contains('gzip'),
          );
        });
      });

      group('getProcessedJokeImageUrl', () {
        test('should return processed URL for valid joke image', () {
          // arrange
          const validUrl = 'https://example.com/joke.jpg';

          // act
          final result = imageService.getProcessedJokeImageUrl(validUrl);

          // assert
          expect(result, equals(validUrl)); // Currently returns same URL
        });

        test('should forward width hint to processImageUrl', () {
          // arrange
          const validUrl = 'https://example.com/joke.jpg';

          // act
          final result = imageService.getProcessedJokeImageUrl(
            validUrl,
            width: 200,
          );

          // assert
          expect(result, equals(validUrl));
        });

        test('should return null for invalid URL', () {
          // arrange
          const invalidUrl = 'not-a-url';

          // act
          final result = imageService.getProcessedJokeImageUrl(invalidUrl);

          // assert
          expect(result, isNull);
        });

        test('should return null for null URL', () {
          // act
          final result = imageService.getProcessedJokeImageUrl(null);

          // assert
          expect(result, isNull);
        });
      });

      group('precacheJokeImage', () {
        test('should return null for invalid URL', () async {
          // arrange
          const invalidUrl = 'not-a-url';

          // act
          final result = await imageService.precacheJokeImage(invalidUrl);

          // assert
          expect(result, isNull);
        });

        test('should return null for null URL', () async {
          // act
          final result = await imageService.precacheJokeImage(null);

          // assert
          expect(result, isNull);
        });
      });

      group('precacheJokeImages', () {
        test('should handle joke with null image URLs', () async {
          // arrange
          const joke = Joke(
            id: 'test-joke',
            setupText: 'Setup',
            punchlineText: 'Punchline',
            setupImageUrl: null,
            punchlineImageUrl: null,
          );

          // act
          final result = await imageService.precacheJokeImages(joke);

          // assert
          expect(result, isNotNull);
          expect(result.setupUrl, isNull);
          expect(result.punchlineUrl, isNull);
        });
      });

      group('precacheMultipleJokeImages', () {
        test('should handle empty joke list', () async {
          // arrange
          final jokes = <Joke>[];

          // act & assert (should not throw)
          await expectLater(
            imageService.precacheMultipleJokeImages(jokes, width: 200),
            completes,
          );
        });
      });
    });

    group('Cloudflare URL optimization', () {
      test(
        'should optimize Cloudflare Images URL with webp format and quality',
        () {
          // arrange
          const cloudflareUrl =
              'https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto/pun_agent_image_20250623_014533_483036.png';

          // act
          final result = imageService.processImageUrl(cloudflareUrl);

          // assert
          expect(result, contains('format=webp'));
          expect(
            result,
            contains('quality=${ImageService.defaultFullSizeQuality}'),
          );
          expect(result, contains('width=1024'));
        },
      );

      test('should handle Cloudflare URLs with custom quality', () {
        // arrange
        const cloudflareUrl =
            'https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto/test.png';

        // act
        final result = imageService.processImageUrl(
          cloudflareUrl,
          quality: '70',
        );

        // assert
        expect(result, contains('format=webp'));
        expect(result, contains('quality=70'));
      });

      test('should add dimensions to Cloudflare URLs', () {
        // arrange
        const cloudflareUrl =
            'https://images.quillsstorybook.com/cdn-cgi/image/format=auto/test.png';

        // act
        final result = imageService.processImageUrl(
          cloudflareUrl,
          width: 512,
          height: 384,
        );

        // assert
        expect(result, contains('width=512'));
        expect(result, contains('height=384'));
        expect(result, contains('format=webp'));
      });

      test('should return original URL if not Cloudflare Images', () {
        // arrange
        const regularUrl = 'https://example.com/image.jpg';

        // act
        final result = imageService.processImageUrl(regularUrl);

        // assert
        expect(result, equals(regularUrl));
      });
    });

    group('getThumbnailUrl with quality', () {
      test('should return Cloudflare URL with thumbnail size and quality', () {
        // arrange
        const cloudflareUrl =
            'https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto/test.png';

        // act
        final result = imageService.getThumbnailUrl(cloudflareUrl, size: 200);

        // assert
        expect(result, contains('width=200'));
        expect(result, contains('height=200'));
        expect(
          result,
          contains('quality=${ImageService.defaultThumbnailQuality}'),
        );
        expect(result, contains('format=webp'));
      });
    });

    group('getFullSizeUrl with quality', () {
      test('should return Cloudflare URL with quality optimization', () {
        // arrange
        const cloudflareUrl =
            'https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto/test.png';

        // act
        final result = imageService.getFullSizeUrl(cloudflareUrl);

        // assert
        expect(
          result,
          contains('quality=${ImageService.defaultFullSizeQuality}'),
        );
        expect(result, contains('format=webp'));
      });
    });

    group('getAssetPathForUrl', () {
      test('returns asset path when URL tail is in manifest', () {
        const url =
            'https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/path/to/file.png';

        final result = imageService.getAssetPathForUrl(url, {
          'path/to/file.png',
        });

        expect(
          result,
          equals('${ImageService.assetImageBasePath}path/to/file.png'),
        );
      });

      test('returns null for URLs not using the expected CDN prefix', () {
        const url = 'https://example.com/path/to/file.png';

        final result = imageService.getAssetPathForUrl(url, {
          'path/to/file.png',
        });

        expect(result, isNull);
      });

      test('returns null when tail is missing from manifest', () {
        const url =
            'https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/path/to/file.png';

        final result = imageService.getAssetPathForUrl(url, {'other.png'});

        expect(result, isNull);
      });
    });
  });
}
