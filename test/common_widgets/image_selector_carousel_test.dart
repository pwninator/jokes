import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/common_widgets/image_selector_carousel.dart';

import '../test_helpers/analytics_mocks.dart';
import '../test_helpers/core_mocks.dart';

Widget _wrap(Widget child) => ProviderScope(
      overrides: [
        ...CoreMocks.getCoreProviderOverrides(),
        ...AnalyticsMocks.getAnalyticsProviderOverrides(),
      ],
      child: MaterialApp(home: Scaffold(body: child)),
    );

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() {
    registerAnalyticsFallbackValues();
  });

  group('ImageSelectorCarousel', () {
    testWidgets('returns empty widget when no images provided', (tester) async {
      await tester.pumpWidget(
        _wrap(
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
        _wrap(
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
        _wrap(
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
        _wrap(
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
      await tester.pumpAndSettle();

      expect(selected, urls[1]);
    });

    testWidgets('page indicators update when selection changes', (
      tester,
    ) async {
      const urls = ['one', 'two', 'three'];

      await tester.pumpWidget(
        _wrap(
          ImageSelectorCarousel(
            imageUrls: urls,
            title: 'Gallery',
            onImageSelected: (_) {},
          ),
        ),
      );
      await tester.pump();

      await tester.drag(find.byType(PageView), const Offset(-400, 0));
      await tester.pumpAndSettle();

      final firstIndicator = find.byType(AnimatedContainer).at(0);
      final secondIndicator = find.byType(AnimatedContainer).at(1);
      expect(tester.getSize(firstIndicator).width, 8);
      expect(tester.getSize(secondIndicator).width, 20);
    });
  });
}
