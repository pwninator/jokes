import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/subscription_prompt_dialog.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';
import 'package:snickerdoodle/src/core/services/remote_config_service.dart';

class _MockAnalyticsService extends Mock implements AnalyticsService {}

class _MockSubscriptionPromptNotifier extends Mock
    implements SubscriptionPromptNotifier {}

class _FakeRemoteConfigValues extends Fake implements RemoteConfigValues {}

class _FakeSubscriptionPromptState extends Fake
    implements SubscriptionPromptState {}

const List<int> _transparentPixelPng = [
  0x89,
  0x50,
  0x4E,
  0x47,
  0x0D,
  0x0A,
  0x1A,
  0x0A,
  0x00,
  0x00,
  0x00,
  0x0D,
  0x49,
  0x48,
  0x44,
  0x52,
  0x00,
  0x00,
  0x00,
  0x01,
  0x00,
  0x00,
  0x00,
  0x01,
  0x08,
  0x06,
  0x00,
  0x00,
  0x00,
  0x1F,
  0x15,
  0xC4,
  0x89,
  0x00,
  0x00,
  0x00,
  0x0A,
  0x49,
  0x44,
  0x41,
  0x54,
  0x78,
  0x9C,
  0x63,
  0x00,
  0x01,
  0x00,
  0x00,
  0x05,
  0x00,
  0x01,
  0x0D,
  0x0A,
  0x2D,
  0xB4,
  0x00,
  0x00,
  0x00,
  0x00,
  0x49,
  0x45,
  0x4E,
  0x44,
  0xAE,
  0x42,
  0x60,
  0x82,
];

final ByteData _testCookieImageData = Uint8List.fromList(
  _transparentPixelPng,
).buffer.asByteData();

class _TestAssetBundle extends CachingAssetBundle {
  _TestAssetBundle(this._imageData);

  final ByteData _imageData;

  @override
  Future<ByteData> load(String key) {
    if (key == cookieIconAssetPath) {
      return Future.value(_imageData);
    }
    return rootBundle.load(key);
  }
}

void main() {
  group('SubscriptionPromptDialog', () {
    late _MockAnalyticsService mockAnalytics;
    late _MockSubscriptionPromptNotifier mockSubscriptionNotifier;

    setUpAll(() {
      TestWidgetsFlutterBinding.ensureInitialized();
      registerFallbackValue(_FakeRemoteConfigValues());
      registerFallbackValue(_FakeSubscriptionPromptState());
    });

    setUp(() {
      mockAnalytics = _MockAnalyticsService();
      mockSubscriptionNotifier = _MockSubscriptionPromptNotifier();

      // Setup default mock behavior
      when(
        () => mockAnalytics.logSubscriptionPromptShown(),
      ).thenAnswer((_) async {});
      when(
        () => mockAnalytics.logSubscriptionOnPrompt(),
      ).thenAnswer((_) async {});
      when(
        () => mockAnalytics.logSubscriptionDeclinedMaybeLater(),
      ).thenAnswer((_) async {});
      when(
        () => mockAnalytics.logErrorSubscriptionPermission(
          source: any(named: 'source'),
          errorMessage: any(named: 'errorMessage'),
        ),
      ).thenAnswer((_) async {});
      when(
        () => mockAnalytics.logErrorSubscriptionPrompt(
          errorMessage: any(named: 'errorMessage'),
          phase: any(named: 'phase'),
        ),
      ).thenAnswer((_) async {});
      when(
        () => mockSubscriptionNotifier.subscribeUser(),
      ).thenAnswer((_) async => true);
      when(
        () => mockSubscriptionNotifier.dismissPrompt(),
      ).thenAnswer((_) async {});
    });

    Widget createTestWidget() {
      return ProviderScope(
        overrides: [
          analyticsServiceProvider.overrideWithValue(mockAnalytics),
          subscriptionPromptProvider.overrideWith(
            (ref) => mockSubscriptionNotifier,
          ),
        ],
        child: DefaultAssetBundle(
          bundle: _TestAssetBundle(_testCookieImageData),
          child: MaterialApp(
            home: Scaffold(
              body: Builder(
                builder: (context) => ElevatedButton(
                  onPressed: () => showDialog(
                    context: context,
                    builder: (context) => const SubscriptionPromptDialog(),
                  ),
                  child: const Text('Show Dialog'),
                ),
              ),
            ),
          ),
        ),
      );
    }

    testWidgets('displays dialog with correct content and scrollable behavior', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(400, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Tap button to show dialog
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      // Check main title
      expect(find.text('Start Every Day with a Smile!'), findsOneWidget);

      // Check subtitle
      expect(
        find.text(
          "Keep the laughs coming! We can send one new, handpicked joke straight to your phone each day!",
        ),
        findsOneWidget,
      );

      // Check benefits list
      expect(find.text('Daily notifications with fresh jokes'), findsOneWidget);
      expect(find.text('Completely free!'), findsOneWidget);
      expect(
        find.text('To get jokes, tap "Allow" on the next screen.'),
        findsOneWidget,
      );

      // Check action buttons
      expect(find.text('Maybe Later'), findsOneWidget);
      expect(
        find.byWidgetPredicate((widget) {
          return widget is Image &&
              widget.image is AssetImage &&
              (widget.image as AssetImage).assetName == cookieIconAssetPath;
        }),
        findsOneWidget,
      );

      // Verify buttons have correct keys
      expect(
        find.byKey(const Key('subscription_prompt_dialog-maybe-later-button')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('subscription_prompt_dialog-subscribe-button')),
        findsOneWidget,
      );

      // Verify SingleChildScrollView is present for scrollable content
      expect(find.byType(SingleChildScrollView), findsOneWidget);

      // Verify AlertDialog structure
      expect(find.byType(AlertDialog), findsOneWidget);
    });

    testWidgets('handles subscribe button tap successfully', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(400, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Tap button to show dialog
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      // Tap subscribe button
      await tester.ensureVisible(
        find.byKey(const Key('subscription_prompt_dialog-subscribe-button')),
      );
      await tester.tap(
        find.byKey(const Key('subscription_prompt_dialog-subscribe-button')),
      );
      await tester.pumpAndSettle();

      // Verify analytics calls
      verify(() => mockAnalytics.logSubscriptionOnPrompt()).called(1);

      // Verify subscription service call
      verify(() => mockSubscriptionNotifier.subscribeUser()).called(1);

      // Wait for snackbar to appear
      await tester.pump(const Duration(milliseconds: 100));

      // Verify success snackbar is shown
      expect(
        find.text(
          'Successfully subscribed to daily jokes! 🎉',
          skipOffstage: false,
        ),
        findsOneWidget,
      );
    });

    testWidgets('handles subscribe button tap with error', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(400, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      // Override mock to throw error
      when(
        () => mockSubscriptionNotifier.subscribeUser(),
      ).thenThrow(Exception('Permission denied'));

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Tap button to show dialog
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      // Tap subscribe button
      await tester.ensureVisible(
        find.byKey(const Key('subscription_prompt_dialog-subscribe-button')),
      );
      await tester.tap(
        find.byKey(const Key('subscription_prompt_dialog-subscribe-button')),
      );
      await tester.pumpAndSettle();

      // Verify error analytics call
      verify(
        () => mockAnalytics.logErrorSubscriptionPermission(
          source: 'prompt',
          errorMessage: 'Exception: Permission denied',
        ),
      ).called(1);

      // Wait for snackbar to appear
      await tester.pump(const Duration(milliseconds: 100));

      // Verify error snackbar is shown
      expect(
        find.textContaining(
          'Notification permission is required for daily jokes',
        ),
        findsOneWidget,
      );
    });

    testWidgets('handles maybe later button tap', (WidgetTester tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Tap button to show dialog
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      // Tap maybe later button
      await tester.ensureVisible(
        find.byKey(const Key('subscription_prompt_dialog-maybe-later-button')),
      );
      await tester.tap(
        find.byKey(const Key('subscription_prompt_dialog-maybe-later-button')),
      );
      await tester.pumpAndSettle();

      // Verify analytics calls
      verify(() => mockAnalytics.logSubscriptionDeclinedMaybeLater()).called(1);

      // Verify dismiss call
      verify(() => mockSubscriptionNotifier.dismissPrompt()).called(1);

      // Wait for snackbar to appear
      await tester.pump(const Duration(milliseconds: 100));

      // Verify maybe later snackbar is shown
      expect(
        find.textContaining('No problem! If you ever change your mind'),
        findsOneWidget,
      );
    });

    testWidgets('shows loading state during subscription', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(400, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      // Make subscription take time
      when(() => mockSubscriptionNotifier.subscribeUser()).thenAnswer((
        _,
      ) async {
        await Future.delayed(const Duration(milliseconds: 100));
        return true;
      });

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Tap button to show dialog
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      // Tap subscribe button
      await tester.ensureVisible(
        find.byKey(const Key('subscription_prompt_dialog-subscribe-button')),
      );
      await tester.tap(
        find.byKey(const Key('subscription_prompt_dialog-subscribe-button')),
      );
      await tester.pump();

      // Verify loading indicator is shown
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // Verify button is disabled during loading
      final subscribeButton = tester.widget<ElevatedButton>(
        find.byKey(const Key('subscription_prompt_dialog-subscribe-button')),
      );
      expect(subscribeButton.onPressed, isNull);

      // Wait for completion
      await tester.pump(const Duration(milliseconds: 150));
      await tester.pumpAndSettle();

      // Verify loading indicator is gone
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets('disables buttons during loading', (WidgetTester tester) async {
      tester.view.physicalSize = const Size(400, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      // Make subscription take time
      when(() => mockSubscriptionNotifier.subscribeUser()).thenAnswer((
        _,
      ) async {
        await Future.delayed(const Duration(milliseconds: 100));
        return true;
      });

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Tap button to show dialog
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      // Tap subscribe button
      await tester.ensureVisible(
        find.byKey(const Key('subscription_prompt_dialog-subscribe-button')),
      );
      await tester.tap(
        find.byKey(const Key('subscription_prompt_dialog-subscribe-button')),
      );
      await tester.pump();

      // Verify both buttons are disabled during loading
      final subscribeButton = tester.widget<ElevatedButton>(
        find.byKey(const Key('subscription_prompt_dialog-subscribe-button')),
      );
      expect(subscribeButton.onPressed, isNull);

      final maybeLaterButton = tester.widget<ElevatedButton>(
        find.byKey(const Key('subscription_prompt_dialog-maybe-later-button')),
      );
      expect(maybeLaterButton.onPressed, isNull);

      // Wait for completion to avoid timer issues
      await tester.pump(const Duration(milliseconds: 150));
      await tester.pumpAndSettle();
    });

    testWidgets('handles dismiss prompt error gracefully', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(400, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      // Override mock to throw error on dismiss
      when(
        () => mockSubscriptionNotifier.dismissPrompt(),
      ).thenThrow(Exception('Dismiss error'));

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Tap button to show dialog
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      // Tap maybe later button
      await tester.ensureVisible(
        find.byKey(const Key('subscription_prompt_dialog-maybe-later-button')),
      );
      await tester.tap(
        find.byKey(const Key('subscription_prompt_dialog-maybe-later-button')),
      );
      await tester.pumpAndSettle();

      // Verify error analytics call
      verify(
        () => mockAnalytics.logErrorSubscriptionPrompt(
          errorMessage: 'Exception: Dismiss error',
          phase: 'dismiss_prompt',
        ),
      ).called(1);

      // Wait for snackbar to appear
      await tester.pump(const Duration(milliseconds: 100));

      // Verify maybe later snackbar is still shown despite error
      expect(
        find.textContaining('No problem! If you ever change your mind'),
        findsOneWidget,
      );
    });

    testWidgets('lays out content side-by-side on wide screens', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(900, 500);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      final scrollView = tester.widget<SingleChildScrollView>(
        find.byType(SingleChildScrollView),
      );
      expect(scrollView.child, isA<Row>());

      final Text title = tester.widget<Text>(
        find.text('Start Every Day with a Smile!'),
      );
      expect(title.textAlign, TextAlign.start);
    });

    testWidgets('content is scrollable on small screens', (
      WidgetTester tester,
    ) async {
      // Set a small screen size to test scrolling
      tester.view.physicalSize = const Size(300, 400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Tap button to show dialog
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      // Verify SingleChildScrollView is present
      expect(find.byType(SingleChildScrollView), findsOneWidget);

      // Verify we can scroll the content
      final scrollView = tester.widget<SingleChildScrollView>(
        find.byType(SingleChildScrollView),
      );
      expect(scrollView.child, isA<Column>());

      // Test that scrolling works by attempting to scroll
      await tester.drag(
        find.byType(SingleChildScrollView),
        const Offset(0, -100),
      );
      await tester.pumpAndSettle();

      // Content should still be visible after scrolling
      expect(find.text('Start Every Day with a Smile!'), findsOneWidget);
    });
  });
}
