import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/image_selector_carousel.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/services/performance_service.dart';

// Mock classes
class MockImageService extends Mock implements ImageService {}

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockPerformanceService extends Mock implements PerformanceService {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MockImageService mockImageService;
  late MockAnalyticsService mockAnalyticsService;
  late MockPerformanceService mockPerformanceService;

  setUpAll(() {
    // Register fallback values for mocktail
    registerFallbackValue(<String, String>{});
    registerFallbackValue(TraceName.imageDownload);
  });

  setUp(() {
    // Create fresh mocks per test
    mockImageService = MockImageService();
    mockAnalyticsService = MockAnalyticsService();
    mockPerformanceService = MockPerformanceService();

    // Stub default behavior
    when(
      () => mockImageService.getProcessedJokeImageUrl(
        any(),
        width: any(named: 'width'),
      ),
    ).thenReturn('https://example.com/processed-image.jpg');
    when(() => mockImageService.isValidImageUrl(any())).thenReturn(true);
    when(
      () => mockImageService.getThumbnailUrl(any()),
    ).thenReturn('https://example.com/thumbnail.jpg');
    when(
      () => mockAnalyticsService.logErrorImageLoad(
        imageType: any(named: 'imageType'),
        imageUrlHash: any(named: 'imageUrlHash'),
        errorMessage: any(named: 'errorMessage'),
      ),
    ).thenAnswer((_) async {});
    when(
      () => mockPerformanceService.startNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
        attributes: any(named: 'attributes'),
      ),
    ).thenReturn(null);
    when(
      () => mockPerformanceService.stopNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
      ),
    ).thenReturn(null);
    when(
      () => mockPerformanceService.dropNamedTrace(
        name: any(named: 'name'),
        key: any(named: 'key'),
      ),
    ).thenReturn(null);
  });

  Widget buildTestWidget(Widget child) {
    return ProviderScope(
      overrides: [
        imageServiceProvider.overrideWithValue(mockImageService),
        analyticsServiceProvider.overrideWithValue(mockAnalyticsService),
        performanceServiceProvider.overrideWithValue(mockPerformanceService),
      ],
      child: MaterialApp(home: Scaffold(body: child)),
    );
  }

  group('ImageSelectorCarousel', () {
    testWidgets('returns empty widget when no images provided', (tester) async {
      await tester.pumpWidget(
        buildTestWidget(
          ImageSelectorCarousel(
            imageUrls: const [],
            title: 'Gallery',
            onImageSelected: (_) {},
          ),
        ),
      );

      expect(find.text('Gallery'), findsNothing);
      expect(find.byType(PageView), findsNothing);
    });

    testWidgets('renders title and highlights first indicator', (tester) async {
      const urls = ['a', 'b', 'c'];

      await tester.pumpWidget(
        buildTestWidget(
          ImageSelectorCarousel(
            imageUrls: urls,
            title: 'Gallery',
            onImageSelected: (_) {},
          ),
        ),
      );

      expect(find.text('Gallery'), findsOneWidget);
      expect(find.byType(PageView), findsOneWidget);

      final firstIndicator = find.byType(AnimatedContainer).first;
      expect(tester.getSize(firstIndicator).width, 20);
    });

    testWidgets('initially displays provided selected image without callback', (
      tester,
    ) async {
      const urls = ['u1', 'u2', 'u3'];
      String? selected;

      await tester.pumpWidget(
        buildTestWidget(
          ImageSelectorCarousel(
            imageUrls: urls,
            selectedImageUrl: urls[2],
            title: 'Gallery',
            onImageSelected: (value) => selected = value,
          ),
        ),
      );
      await tester.pump();

      expect(selected, isNull);

      final pageView = tester.widget<PageView>(find.byType(PageView));
      expect(pageView.controller?.initialPage, 2);
    });

    testWidgets('invokes onImageSelected only after user swipes to new page', (
      tester,
    ) async {
      const urls = ['first', 'second'];
      String? selected;

      await tester.pumpWidget(
        buildTestWidget(
          ImageSelectorCarousel(
            imageUrls: urls,
            title: 'Gallery',
            onImageSelected: (value) => selected = value,
          ),
        ),
      );
      await tester.pump();

      expect(selected, isNull);

      await tester.drag(find.byType(PageView), const Offset(-400, 0));
      await tester.pump();

      expect(selected, urls[1]);
    });

    testWidgets('shows correct number of page indicators', (tester) async {
      const urls = ['one', 'two', 'three'];

      await tester.pumpWidget(
        buildTestWidget(
          ImageSelectorCarousel(
            imageUrls: urls,
            title: 'Gallery',
            onImageSelected: (_) {},
          ),
        ),
      );
      await tester.pump();

      // Should have 3 indicators (one for each image)
      final indicators = find.byType(AnimatedContainer);
      expect(indicators, findsNWidgets(3));

      // First indicator should be active (width 20), others inactive (width 8)
      final firstIndicator = indicators.at(0);
      final secondIndicator = indicators.at(1);
      final thirdIndicator = indicators.at(2);

      expect(tester.getSize(firstIndicator).width, 20);
      expect(tester.getSize(secondIndicator).width, 8);
      expect(tester.getSize(thirdIndicator).width, 8);
    });
  });
}
