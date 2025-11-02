import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:showcaseview/showcaseview.dart';
import 'package:snickerdoodle/src/features/onboarding/application/onboarding_tour_controller.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('orderedKeys preserves feed, discover, saved order', () {
    final steps = OnboardingTourSteps();
    expect(steps.orderedKeys, [
      steps.feed.key,
      steps.discover.key,
      steps.saved.key,
    ]);
  });

  test('wrapWithOnboardingShowcase returns original child when step null', () {
    const child = Text('demo');
    final result = wrapWithOnboardingShowcase(step: null, child: child);
    expect(identical(result, child), isTrue);
  });

  testWidgets('mountedKeys only includes attached steps', (tester) async {
    final steps = OnboardingTourSteps();
    expect(steps.mountedKeys(), isEmpty);

    await tester.pumpWidget(
      MaterialApp(
        home: Column(
          children: [
            Container(key: steps.feed.key),
            const SizedBox(),
          ],
        ),
      ),
    );

    expect(steps.mountedKeys(), [steps.feed.key]);
  });

  testWidgets('wrapWithOnboardingShowcase decorates child when step provided', (
    tester,
  ) async {
    final step = OnboardingTourStep(
      key: GlobalKey(),
      title: 'Title',
      description: 'Description',
      automationKey: const Key('automation-key'),
    );

    ShowcaseView.register();

    await tester.pumpWidget(
      MaterialApp(
        home: wrapWithOnboardingShowcase(
          step: step,
          child: const SizedBox.shrink(),
        ),
      ),
    );

    expect(find.byType(Showcase), findsOneWidget);
    expect(find.byKey(step.automationKey), findsOneWidget);
  });
}
