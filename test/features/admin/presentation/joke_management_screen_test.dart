import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_management_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';

class _MockJokeRepository extends Mock implements JokeRepository {}

class _MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Submitting search sets publicOnly=false and matchMode=LOOSE', (
    tester,
  ) async {
    final mockRepo = _MockJokeRepository();
    final mockService = _MockJokeCloudFunctionService();

    when(() => mockRepo.getJokes()).thenAnswer((_) => Stream.value(const []));

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          jokeRepositoryProvider.overrideWithValue(mockRepo),
          jokeCloudFunctionServiceProvider.overrideWithValue(mockService),
        ],
        child: const MaterialApp(home: Scaffold(body: JokeManagementScreen())),
      ),
    );

    // Open search field
    final searchChip = find.byKey(const Key('search-toggle-chip'));
    expect(searchChip, findsOneWidget);
    await tester.tap(searchChip);
    await tester.pumpAndSettle();

    // Enter text and submit (TextInputAction.search)
    final field = find.byKey(const Key('admin-search-field'));
    expect(field, findsOneWidget);
    await tester.enterText(field, 'cats');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();

    // Read provider state
    final context = tester.element(find.byType(JokeManagementScreen));
    final container = ProviderScope.containerOf(context);
    final params = container.read(searchQueryProvider);

    expect(params.query, 'cats');
    expect(params.maxResults, 50);
    expect(params.publicOnly, isFalse);
    expect(params.matchMode, MatchMode.loose);
  });
}
