import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/subscription_prompt_dialog.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';
import 'package:snickerdoodle/src/core/services/daily_joke_subscription_service.dart';

class MockAnalyticsService extends Mock implements AnalyticsService {}

class MockSubscriptionPromptNotifier extends StateNotifier<SubscriptionPromptState>
    with Mock
    implements SubscriptionPromptNotifier {
  MockSubscriptionPromptNotifier() : super(const SubscriptionPromptState());
}

// A minimal asset bundle to provide the cookie image for tests.
class TestAssetBundle extends CachingAssetBundle {
  @override
  Future<ByteData> load(String key) async {
    if (key == cookieIconAssetPath) {
      // Return a 1x1 transparent pixel PNG
      const List<int> transparentPixel = [
        0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
        0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, 0x89, 0x00, 0x00, 0x00,
        0x0a, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9c, 0x63, 0x00, 0x01, 0x00, 0x00,
        0x05, 0x00, 0x01, 0x0d, 0x0a, 0x2d, 0xb4, 0x00, 0x00, 0x00, 0x00, 0x49,
        0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82,
      ];
      return ByteData.view(Uint8List.fromList(transparentPixel).buffer);
    }
    // Fallback to the root bundle for any other asset.
    return rootBundle.load(key);
  }
}

void main() {
  group('SubscriptionPromptDialog', () {
    late MockAnalyticsService mockAnalytics;
    late MockSubscriptionPromptNotifier mockSubscriptionNotifier;

    setUp(() {
      mockAnalytics = MockAnalyticsService();
      mockSubscriptionNotifier = MockSubscriptionPromptNotifier();
      when(() => mockAnalytics.logSubscriptionPromptShown()).thenAnswer((_) async {});
      when(() => mockAnalytics.logSubscriptionOnPrompt()).thenAnswer((_) async {});
      when(() => mockAnalytics.logSubscriptionDeclinedMaybeLater()).thenAnswer((_) async {});
      when(() => mockAnalytics.logErrorSubscriptionPermission(
          source: any(named: 'source'),
          errorMessage: any(named: 'errorMessage'))).thenAnswer((_) async {});
      when(() => mockSubscriptionNotifier.subscribeUser()).thenAnswer((_) async => true);
      when(() => mockSubscriptionNotifier.dismissPrompt()).thenAnswer((_) async {});
    });

    Widget createTestWidget() {
      return ProviderScope(
        overrides: [
          analyticsServiceProvider.overrideWithValue(mockAnalytics),
          subscriptionPromptProvider.overrideWith((ref) => mockSubscriptionNotifier),
        ],
        child: DefaultAssetBundle(
          bundle: TestAssetBundle(),
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

    Future<void> showDialogInTester(WidgetTester tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();
    }

    testWidgets('renders content correctly in tall layout', (tester) async {
      tester.view.physicalSize = const Size(500, 900); // Use a slightly wider screen to avoid overflow
      addTearDown(tester.view.resetPhysicalSize);

      await showDialogInTester(tester);

      final dialogFinder = find.byType(AlertDialog);
      expect(dialogFinder, findsOneWidget);
      final scrollView = tester.widget<SingleChildScrollView>(find.descendant(of: dialogFinder, matching: find.byType(SingleChildScrollView)));
      expect(scrollView.child, isA<Column>());
    });

    testWidgets('renders content correctly in wide layout', (tester) async {
        tester.view.physicalSize = const Size(900, 600); // Use a slightly taller screen
        addTearDown(tester.view.resetPhysicalSize);

        await showDialogInTester(tester);

        final dialogFinder = find.byType(AlertDialog);
        expect(dialogFinder, findsOneWidget);
        final scrollView = tester.widget<SingleChildScrollView>(find.descendant(of: dialogFinder, matching: find.byType(SingleChildScrollView)));
        expect(scrollView.child, isA<Row>());
    });


    testWidgets('successful subscription flow works correctly', (tester) async {
      when(() => mockSubscriptionNotifier.subscribeUser()).thenAnswer((_) async {
        await Future.delayed(const Duration(milliseconds: 50));
        return true;
      });

      await showDialogInTester(tester);

      final subscribeButtonFinder = find.byKey(const Key('subscription_prompt_dialog-subscribe-button'));
      await tester.ensureVisible(subscribeButtonFinder);
      await tester.tap(subscribeButtonFinder);
      await tester.pump(const Duration(milliseconds: 20));

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(tester.widget<ElevatedButton>(subscribeButtonFinder).onPressed, isNull);

      await tester.pumpAndSettle();

      expect(find.byType(AlertDialog), findsNothing);
      expect(find.textContaining('Successfully subscribed'), findsOneWidget);
      verify(() => mockAnalytics.logSubscriptionOnPrompt()).called(1);
      verify(() => mockSubscriptionNotifier.subscribeUser()).called(1);
    });

    testWidgets('handles cancellation correctly', (tester) async {
      await showDialogInTester(tester);
      final maybeLaterButtonFinder = find.byKey(const Key('subscription_prompt_dialog-maybe-later-button'));
      await tester.ensureVisible(maybeLaterButtonFinder);
      await tester.tap(maybeLaterButtonFinder);
      await tester.pumpAndSettle();

      expect(find.byType(AlertDialog), findsNothing);
      expect(find.textContaining('No problem!'), findsOneWidget);
      verify(() => mockAnalytics.logSubscriptionDeclinedMaybeLater()).called(1);
      verify(() => mockSubscriptionNotifier.dismissPrompt()).called(1);
    });

    testWidgets('handles subscription errors gracefully', (tester) async {
      when(() => mockSubscriptionNotifier.subscribeUser()).thenThrow(Exception('Permission denied'));
      await showDialogInTester(tester);

      final subscribeButtonFinder = find.byKey(const Key('subscription_prompt_dialog-subscribe-button'));
      await tester.ensureVisible(subscribeButtonFinder);
      await tester.tap(subscribeButtonFinder);
      await tester.pumpAndSettle();

      expect(find.byType(AlertDialog), findsNothing);
      expect(find.textContaining('Notification permission is required'), findsOneWidget);
      verify(() => mockAnalytics.logErrorSubscriptionPermission(source: 'prompt', errorMessage: any(named: 'errorMessage'))).called(1);
    });
  });
}