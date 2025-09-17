import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/core/data/repositories/feedback_repository.dart';
import 'package:snickerdoodle/src/core/providers/feedback_providers.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_admin_screen.dart';

import '../../../test_helpers/firebase_mocks.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('shows unread badge when unread feedback > 0', (tester) async {
    final now = DateTime.now();
    final entries = [
      FeedbackEntry(
        id: '1',
        creationTime: now,
        userId: 'userA',
        lastAdminViewTime: null,
        messages: [Message(text: 'Help!', timestamp: now, isFromAdmin: false)],
        lastMessage: Message(text: 'Help!', timestamp: now, isFromAdmin: false),
      ),
    ];

    final container = ProviderContainer(
      overrides: FirebaseMocks.getFirebaseProviderOverrides(
        additionalOverrides: [
          allFeedbackProvider.overrideWith((ref) => Stream.value(entries)),
        ],
      ),
    );
    addTearDown(container.dispose);

    // Force portrait for consistent UI
    final originalSize = tester.view.physicalSize;
    tester.view.physicalSize = const Size(600, 800);
    addTearDown(() => tester.view.physicalSize = originalSize);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: JokeAdminScreen()),
      ),
    );

    await tester.pump();

    expect(find.text('Feedback'), findsOneWidget);
    // The badge text
    expect(find.text('1'), findsOneWidget);
  });
}
