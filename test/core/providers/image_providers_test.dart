import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';

void main() {
  group('Image Providers', () {
    late ProviderContainer container;

    setUp(() {
      container = ProviderContainer();
    });

    tearDown(() {
      container.dispose();
    });

    group('imageServiceProvider', () {
      test('should provide an ImageService instance', () {
        // act
        final imageService = container.read(imageServiceProvider);

        // assert
        expect(imageService, isA<ImageService>());
      });

      test('should provide the same instance on multiple reads', () {
        // act
        final imageService1 = container.read(imageServiceProvider);
        final imageService2 = container.read(imageServiceProvider);

        // assert
        expect(imageService1, same(imageService2));
      });
    });

    group('imageCacheConfigProvider', () {
      test('should provide cache configuration map', () {
        // act
        final config = container.read(imageCacheConfigProvider);

        // assert
        expect(config, isA<Map<String, dynamic>>());
        expect(config.containsKey('cacheDuration'), true);
        expect(config.containsKey('maxCacheSize'), true);
      });

      test('should provide correct cache duration', () {
        // act
        final config = container.read(imageCacheConfigProvider);

        // assert
        expect(config['cacheDuration'], equals(ImageService.defaultCacheDuration));
      });

      test('should provide correct max cache size', () {
        // act
        final config = container.read(imageCacheConfigProvider);

        // assert
        expect(config['maxCacheSize'], equals(ImageService.maxCacheSize));
      });

      test('should provide the same configuration on multiple reads', () {
        // act
        final config1 = container.read(imageCacheConfigProvider);
        final config2 = container.read(imageCacheConfigProvider);

        // assert
        expect(config1, equals(config2));
      });
    });
  });
} 