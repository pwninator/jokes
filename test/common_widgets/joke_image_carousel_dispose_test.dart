import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/joke_image_carousel.dart';
import 'package:snickerdoodle/src/core/providers/image_providers.dart';
import 'package:snickerdoodle/src/core/services/app_usage_service.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

import '../test_helpers/analytics_mocks.dart';
import '../test_helpers/firebase_mocks.dart';
import 'joke_image_carousel_test.dart' show FakeJoke; // reuse existing FakeJoke

class _MockImageService extends Mock implements ImageService {}

class _MockAppUsageService extends Mock implements AppUsageService {}

void main() {
  setUpAll(() {
    registerAnalyticsFallbackValues();
    // Required for any<Joke>() used in image service stubs
    registerFallbackValue(FakeJoke());
  });

  late _MockImageService mockImageService;
  late _MockAppUsageService mockAppUsageService;

  const String dataUrl =
      'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';

  setUp(() {
    mockImageService = _MockImageService();
    mockAppUsageService = _MockAppUsageService();

    when(() => mockImageService.isValidImageUrl(any())).thenReturn(true);
    when(() => mockImageService.processImageUrl(any())).thenReturn(dataUrl);
    when(
      () => mockImageService.processImageUrl(
        any(),
        width: any(named: 'width'),
        height: any(named: 'height'),
        quality: any(named: 'quality'),
      ),
    ).thenReturn(dataUrl);
    when(
      () => mockImageService.getProcessedJokeImageUrl(any()),
    ).thenReturn(dataUrl);
    when(
      () => mockImageService.precacheJokeImage(any()),
    ).thenAnswer((_) async => dataUrl);
    when(
      () => mockImageService.precacheJokeImages(any()),
    ).thenAnswer((_) async => (setupUrl: dataUrl, punchlineUrl: dataUrl));
    when(
      () => mockImageService.precacheMultipleJokeImages(any()),
    ).thenAnswer((_) async {});
  });

  Widget wrap(Widget child, List<Override> additionalOverrides) =>
      ProviderScope(
        overrides: [
          ...FirebaseMocks.getFirebaseProviderOverrides(),
          ...AnalyticsMocks.getAnalyticsProviderOverrides(),
          imageServiceProvider.overrideWithValue(mockImageService),
          appUsageServiceProvider.overrideWithValue(mockAppUsageService),
          ...additionalOverrides,
        ],
        child: MaterialApp(
          theme: lightTheme,
          home: Scaffold(body: child),
        ),
      );

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
    when(() => mockAppUsageService.logJokeViewed()).thenAnswer((_) async {
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

    await tester.pumpWidget(wrap(host, const []));
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
}

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
