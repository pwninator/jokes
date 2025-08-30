import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/search/presentation/search_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Submitting <2 chars shows banner and does not update query', (
    tester,
  ) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: SearchScreen())),
    );

    // Ensure initial state
    final container = ProviderScope.containerOf(
      tester.element(find.byType(SearchScreen)),
    );
    expect(
      container.read(searchQueryProvider(SearchScope.userJokeSearch)).query,
      '',
    );

    // Enter 1-char query and submit
    final field = find.byKey(const Key('search-tab-search-field'));
    expect(field, findsOneWidget);
    await tester.enterText(field, 'a');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    // Verify MaterialBanner is shown
    expect(find.text('Please enter a longer search query'), findsOneWidget);

    // Provider should still have empty query
    expect(
      container.read(searchQueryProvider(SearchScope.userJokeSearch)).query,
      '',
    );
  });
}
