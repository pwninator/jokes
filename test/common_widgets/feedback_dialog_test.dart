import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/common_widgets/feedback_dialog.dart';
import 'package:snickerdoodle/src/core/providers/analytics_providers.dart';
import 'package:snickerdoodle/src/core/services/analytics_service.dart';

class _MockAnalytics extends Mock implements AnalyticsService {}

void main() {
  testWidgets('logs feedback_dialog_shown on open', (tester) async {
    final mockAnalytics = _MockAnalytics();
    when(() => mockAnalytics.logFeedbackDialogShown()).thenAnswer((_) async {});

    await tester.pumpWidget(
      ProviderScope(
        overrides: [analyticsServiceProvider.overrideWithValue(mockAnalytics)],
        child: const MaterialApp(home: Scaffold(body: FeedbackDialog())),
      ),
    );

    await tester.pumpAndSettle();
    verify(() => mockAnalytics.logFeedbackDialogShown()).called(1);
  });
}
