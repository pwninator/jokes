import 'dart:async';

import 'dart:convert';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/providers/connectivity_providers.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';

class _MockImageService extends Mock implements ImageService {}

class _MockAnalyticsService extends Mock implements AnalyticsService {}

class _MockPerformanceService extends Mock implements PerformanceService {}

class _FakeAssetBundle extends CachingAssetBundle {
  _FakeAssetBundle(this.assets);

  final Map<String, Uint8List> assets;

  Map<String, List<Map<String, Object?>>> get _manifestMap => {
    for (final key in assets.keys)
      key: [
        {'asset': key, 'dpr': 1.0},
      ],
  };

  @override
  Future<ByteData> load(String key) async {
    if (key == 'AssetManifest.bin') {
      final encoded = const StandardMessageCodec().encodeMessage(_manifestMap);
      if (encoded != null) {
        return encoded;
      }
    }
    if (key == 'AssetManifest.json') {
      final manifestJson = jsonEncode(_manifestMap);
      final jsonBytes = Uint8List.fromList(utf8.encode(manifestJson));
      return ByteData.view(jsonBytes.buffer);
    }
    final bytes = assets[key];
    if (bytes == null) {
      throw FlutterError('Asset not found: $key');
    }
    return ByteData.view(bytes.buffer);
  }
}

const _sampleImage =
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
const _onePixelPngBase64 =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() {
    registerFallbackValue(TraceName.imageDownload);
  });

  late _MockImageService imageService;
  late _MockAnalyticsService analytics;
  late _MockPerformanceService performance;

  ProviderScope wrap(
    Widget child, {
    Stream<int>? offlineStream,
    Set<String>? manifestSet,
    AssetBundle? assetBundle,
  }) {
    return ProviderScope(
      overrides: [
        imageServiceProvider.overrideWithValue(imageService),
        analyticsServiceProvider.overrideWithValue(analytics),
        performanceServiceProvider.overrideWithValue(performance),
        offlineToOnlineProvider.overrideWith(
          (ref) => offlineStream ?? const Stream<int>.empty(),
        ),
        imageAssetManifestProvider.overrideWith(
          (ref) async => manifestSet ?? <String>{},
        ),
      ],
      child: DefaultAssetBundle(
        bundle: assetBundle ?? rootBundle,
        child: MaterialApp(home: Scaffold(body: child)),
      ),
    );
  }

  setUp(() {
    imageService = _MockImageService();
    analytics = _MockAnalyticsService();
    performance = _MockPerformanceService();

    when(
      () => performance.startNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
        attributes: any(named: 'attributes'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => performance.stopNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => performance.dropNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
      ),
    ).thenAnswer((_) async {});

    when(
      () => analytics.logErrorImageLoad(
        jokeId: any(named: 'jokeId'),
        imageType: any(named: 'imageType'),
        imageUrlHash: any(named: 'imageUrlHash'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});

    when(() => imageService.processImageUrl(any())).thenReturn(_sampleImage);
    when(
      () => imageService.processImageUrl(
        any(),
        width: any(named: 'width'),
        height: any(named: 'height'),
        quality: any(named: 'quality'),
      ),
    ).thenReturn(_sampleImage);
    when(() => imageService.getAssetPathForUrl(any(), any())).thenReturn(null);
  });

  group('CachedJokeImage', () {
    testWidgets('renders error widget when processed URL is null', (
      tester,
    ) async {
      when(() => imageService.isValidImageUrl(null)).thenReturn(false);
      when(
        () => imageService.getProcessedJokeImageUrl(
          null,
          width: any(named: 'width'),
        ),
      ).thenReturn(null);

      await tester.pumpWidget(wrap(const CachedJokeImage(imageUrlOrAssetPath: null)));
      await tester.pump();

      expect(find.byIcon(Icons.image_not_supported_outlined), findsOneWidget);
    });

    testWidgets('uses asset path when manifest contains tail', (tester) async {
      const url =
          'https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/local.png';
      final assetBytes = base64Decode(_onePixelPngBase64);
      when(
        () => imageService.getAssetPathForUrl(url, any()),
      ).thenReturn('assets/data_bundles/images/local.png');

      await tester.pumpWidget(
        wrap(
          const CachedJokeImage(imageUrlOrAssetPath: url, width: 50, height: 50),
          manifestSet: {'local.png'},
          assetBundle: _FakeAssetBundle({
            'assets/data_bundles/images/local.png': assetBytes,
          }),
        ),
      );
      await tester.pump();
      await tester.pump();

      expect(find.byType(CachedNetworkImage), findsNothing);
      expect(find.byType(Image), findsOneWidget);
      verifyNever(
        () => imageService.getProcessedJokeImageUrl(
          any(),
          width: any(named: 'width'),
        ),
      );
    });

    testWidgets('uses direct asset path when provided', (tester) async {
      const assetPath = 'assets/images/local.png';
      final assetBytes = base64Decode(_onePixelPngBase64);

      await tester.pumpWidget(
        wrap(
          const CachedJokeImage(imageUrlOrAssetPath: assetPath, width: 50, height: 50),
          assetBundle: _FakeAssetBundle({assetPath: assetBytes}),
        ),
      );
      await tester.pump();
      await tester.pump();

      expect(find.byType(CachedNetworkImage), findsNothing);
      expect(find.byType(Image), findsOneWidget);
      verifyNever(
        () => imageService.getProcessedJokeImageUrl(
          any(),
          width: any(named: 'width'),
        ),
      );
    });

    testWidgets('rounds explicit width to nearest hundred', (tester) async {
      const url = 'https://example.com/image.jpg';
      when(() => imageService.isValidImageUrl(url)).thenReturn(true);
      when(
        () => imageService.getProcessedJokeImageUrl(
          url,
          width: any(named: 'width'),
        ),
      ).thenReturn(_sampleImage);

      await tester.pumpWidget(
        wrap(const CachedJokeImage(imageUrlOrAssetPath: url, width: 175)),
      );
      await tester.pump();

      final capturedWidths = verify(
        () => imageService.getProcessedJokeImageUrl(
          url,
          width: captureAny(named: 'width'),
        ),
      ).captured;
      expect(capturedWidths, isNotEmpty);
      expect(capturedWidths.last, 200);
    });

    testWidgets('uses layout width when explicit width is absent', (
      tester,
    ) async {
      const url = 'https://example.com/image.jpg';
      when(() => imageService.isValidImageUrl(url)).thenReturn(true);
      when(
        () => imageService.getProcessedJokeImageUrl(
          url,
          width: any(named: 'width'),
        ),
      ).thenReturn(_sampleImage);

      await tester.pumpWidget(
        wrap(
          Align(
            alignment: Alignment.topLeft,
            child: SizedBox(
              width: 245,
              child: const CachedJokeImage(imageUrlOrAssetPath: url),
            ),
          ),
        ),
      );
      await tester.pump();

      final capturedWidths = verify(
        () => imageService.getProcessedJokeImageUrl(
          url,
          width: captureAny(named: 'width'),
        ),
      ).captured;
      expect(capturedWidths, isNotEmpty);
      expect(capturedWidths.last, 300);
    });

    testWidgets('clamps width to 1024 when constraints are large', (
      tester,
    ) async {
      const url = 'https://example.com/image.jpg';
      when(() => imageService.isValidImageUrl(url)).thenReturn(true);
      when(
        () => imageService.getProcessedJokeImageUrl(
          url,
          width: any(named: 'width'),
        ),
      ).thenReturn(_sampleImage);

      await tester.pumpWidget(
        wrap(
          SizedBox(
            width: 400,
            child: OverflowBox(
              minWidth: 1600,
              maxWidth: 1600,
              alignment: Alignment.topLeft,
              child: const CachedJokeImage(imageUrlOrAssetPath: url),
            ),
          ),
        ),
      );
      await tester.pump();

      final capturedWidths = verify(
        () => imageService.getProcessedJokeImageUrl(
          url,
          width: captureAny(named: 'width'),
        ),
      ).captured;
      expect(capturedWidths, isNotEmpty);
      expect(capturedWidths.last, 1024);
    });

    testWidgets('passes null width when constraints are unbounded', (
      tester,
    ) async {
      const url = 'https://example.com/image.jpg';
      when(() => imageService.isValidImageUrl(url)).thenReturn(true);
      when(
        () => imageService.getProcessedJokeImageUrl(
          url,
          width: any(named: 'width'),
        ),
      ).thenReturn(_sampleImage);

      await tester.pumpWidget(
        wrap(
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: const CachedJokeImage(imageUrlOrAssetPath: url, height: 120),
          ),
        ),
      );
      await tester.pump();

      verify(
        () => imageService.getProcessedJokeImageUrl(url, width: null),
      ).called(greaterThanOrEqualTo(1));
    });

    testWidgets('wraps image with ClipRRect when borderRadius provided', (
      tester,
    ) async {
      const url = 'https://example.com/image.jpg';
      when(() => imageService.isValidImageUrl(url)).thenReturn(true);
      when(
        () => imageService.getProcessedJokeImageUrl(
          url,
          width: any(named: 'width'),
        ),
      ).thenReturn(_sampleImage);

      await tester.pumpWidget(
        wrap(
          const CachedJokeImage(
            imageUrlOrAssetPath: url,
            borderRadius: BorderRadius.all(Radius.circular(12)),
          ),
        ),
      );
      await tester.pump();

      expect(find.byType(ClipRRect), findsOneWidget);
    });

    testWidgets('retries load after offline-to-online signal', (tester) async {
      const url = 'https://example.com/image.jpg';
      final connectivity = StreamController<int>.broadcast();
      addTearDown(connectivity.close);

      when(() => imageService.isValidImageUrl(url)).thenReturn(true);
      when(
        () => imageService.getProcessedJokeImageUrl(
          url,
          width: any(named: 'width'),
        ),
      ).thenReturn(_sampleImage);

      await tester.pumpWidget(
        wrap(
          const CachedJokeImage(imageUrlOrAssetPath: url),
          offlineStream: connectivity.stream,
        ),
      );
      await tester.pump();

      final cachedWidget = tester.widget<CachedNetworkImage>(
        find.byType(CachedNetworkImage),
      );
      final element = tester.element(find.byType(CachedNetworkImage));
      cachedWidget.errorWidget!(element, url, 'error');
      await tester.pump();

      connectivity.add(1);
      await tester.pump(const Duration(seconds: 3));

      verify(
        () => imageService.getProcessedJokeImageUrl(
          url,
          width: any(named: 'width'),
        ),
      ).called(greaterThanOrEqualTo(2));
    });
  });

  group('CachedJokeThumbnail', () {
    testWidgets('requests thumbnail URL and size', (tester) async {
      const url = 'https://example.com/full.jpg';
      const thumb = 'https://example.com/thumb.jpg';
      when(() => imageService.isValidImageUrl(url)).thenReturn(true);
      when(() => imageService.getThumbnailUrl(url)).thenReturn(thumb);
      when(() => imageService.isValidImageUrl(thumb)).thenReturn(true);
      when(
        () => imageService.getProcessedJokeImageUrl(
          thumb,
          width: any(named: 'width'),
        ),
      ).thenReturn(_sampleImage);

      await tester.pumpWidget(wrap(const CachedJokeThumbnail(imageUrl: url)));
      await tester.pump();

      verify(() => imageService.getThumbnailUrl(url)).called(1);
      verify(
        () => imageService.getProcessedJokeImageUrl(
          thumb,
          width: any(named: 'width'),
        ),
      ).called(greaterThanOrEqualTo(1));

      final cachedImage = tester.widget<CachedJokeImage>(
        find.byType(CachedJokeImage),
      );
      expect(cachedImage.width, 100);
      expect(cachedImage.height, 100);
    });
  });
}
