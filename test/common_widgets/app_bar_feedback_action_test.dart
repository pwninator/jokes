import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_widget.dart';
import 'package:snickerdoodle/src/common_widgets/feedback_notification_icon.dart';
import 'package:snickerdoodle/src/config/router/route_names.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_prompt_providers.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';

Future<void> _pumpAppBar(
  WidgetTester tester, {
  required FutureOr<bool> Function(Ref) shouldShow,
  List<Widget>? actions,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [shouldShowFeedbackActionProvider.overrideWith(shouldShow)],
      child: MaterialApp(
        home: Scaffold(
          appBar: AppBarWidget(title: 'Inbox', actions: actions),
        ),
      ),
    ),
  );
  await tester.pump();
}

FeedbackEntry _buildUnreadEntry() {
  final userTime = DateTime(2024, 1, 1, 12, 0);
  final adminTime = userTime.add(const Duration(minutes: 5));

  return FeedbackEntry(
    id: 'entry-1',
    userId: 'user-1',
    creationTime: userTime,
    conversation: [
      FeedbackConversationEntry(
        speaker: SpeakerType.user,
        text: 'Hi there!',
        timestamp: userTime,
      ),
      FeedbackConversationEntry(
        speaker: SpeakerType.admin,
        text: 'Hello from support',
        timestamp: adminTime,
      ),
    ],
    lastAdminViewTime: adminTime,
    lastUserViewTime: userTime,
  );
}

void main() {
  group('AppBarWidget feedback action', () {
    testWidgets('appends feedback icon when provider resolves true', (
      tester,
    ) async {
      await _pumpAppBar(
        tester,
        shouldShow: (ref) async => true,
        actions: const [Icon(Icons.search, key: Key('search-action'))],
      );

      expect(find.byKey(const Key('search-action')), findsOneWidget);
      expect(
        find.byKey(const Key('feedback-notification-icon')),
        findsOneWidget,
      );
    });

    testWidgets('excludes feedback icon when provider resolves false', (
      tester,
    ) async {
      await _pumpAppBar(tester, shouldShow: (ref) async => false);

      expect(find.byKey(const Key('feedback-notification-icon')), findsNothing);
    });

    testWidgets('waits for provider completion before showing icon', (
      tester,
    ) async {
      final completer = Completer<bool>();

      await _pumpAppBar(tester, shouldShow: (ref) => completer.future);

      expect(find.byKey(const Key('feedback-notification-icon')), findsNothing);

      completer.complete(true);
      await tester.pump();
      await tester.pump();

      expect(
        find.byKey(const Key('feedback-notification-icon')),
        findsOneWidget,
      );
    });
  });

  group('FeedbackNotificationIcon', () {
    testWidgets('renders badge when unread replies exist', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            unreadFeedbackProvider.overrideWithValue([_buildUnreadEntry()]),
          ],
          child: const MaterialApp(
            home: Scaffold(body: FeedbackNotificationIcon()),
          ),
        ),
      );

      await tester.pump();
      expect(find.bySemanticsLabel('New reply'), findsOneWidget);
    });

    testWidgets('hides badge when no unread replies exist', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: Scaffold(body: FeedbackNotificationIcon())),
        ),
      );

      await tester.pump();
      expect(find.bySemanticsLabel('New reply'), findsNothing);
    });

    testWidgets('pushes feedback route and shows success snackbar', (
      tester,
    ) async {
      final router = GoRouter(
        initialLocation: '/',
        routes: [
          GoRoute(
            path: '/',
            builder: (context, state) =>
                const Scaffold(body: Center(child: FeedbackNotificationIcon())),
          ),
          GoRoute(
            name: RouteNames.feedback,
            path: '/feedback',
            builder: (context, state) {
              Future.microtask(() => Navigator.of(context).pop(true));
              return const SizedBox.shrink();
            },
          ),
        ],
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            unreadFeedbackProvider.overrideWithValue([_buildUnreadEntry()]),
          ],
          child: MaterialApp.router(routerConfig: router),
        ),
      );

      await tester.pump();

      await tester.tap(
        find.byKey(const Key('feedback_notification_icon-open-button')),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.text('Thanks for your feedback!'), findsOneWidget);
    });
  });
}
