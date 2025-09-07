import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:snickerdoodle/src/features/admin/presentation/deep_research_screen.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_search_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_admin_rating.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_search_result.dart';
import 'package:snickerdoodle/src/features/jokes/domain/joke_state.dart';

class MockJokeRepository extends Mock implements JokeRepository {}

class MockJokeCloudFunctionService extends Mock
    implements JokeCloudFunctionService {}

void main() {
  setUpAll(() {
    registerFallbackValue(JokeAdminRating.unreviewed);
    // Fallback for MatchMode enum used in cloud function mock
    registerFallbackValue(MatchMode.tight);
    // Fallback for SearchScope enum used in cloud function mock
    registerFallbackValue(SearchScope.userJokeSearch);
    // Fallback for SearchLabel enum used in cloud function mock
    registerFallbackValue(SearchLabel.none);
  });

  Widget buildTestWidget(List<Override> overrides) {
    return ProviderScope(
      overrides: overrides,
      child: const MaterialApp(home: DeepResearchScreen()),
    );
  }

  testWidgets(
    'Deep Research: generates prompt with mixed results and copy button',
    (tester) async {
      final mockRepo = MockJokeRepository();
      final mockCloud = MockJokeCloudFunctionService();
      final overrides = [
        jokeRepositoryProvider.overrideWithValue(mockRepo),
        jokeCloudFunctionServiceProvider.overrideWithValue(mockCloud),
      ];

      // Stub repository stream lookups for jokes by id when live list resolves
      final jokes = <Joke>[
        Joke(
          id: '1',
          setupText: 'Setup A',
          punchlineText: 'Punchline A',
          adminRating: JokeAdminRating.approved,
          state: JokeState.approved,
        ),
        Joke(
          id: '2',
          setupText: 'Setup B',
          punchlineText: 'Punchline B',
          adminRating: JokeAdminRating.rejected,
          state: JokeState.rejected,
        ),
      ];

      // Provide batch lookup
      when(() => mockRepo.getJokesByIds(any())).thenAnswer((_) async => jokes);
      // Provide cloud function search ids
      when(
        () => mockCloud.searchJokes(
          searchQuery: any(named: 'searchQuery'),
          maxResults: any(named: 'maxResults'),
          publicOnly: any(named: 'publicOnly'),
          matchMode: any(named: 'matchMode'),
          scope: any(named: 'scope'),
          label: any(named: 'label'),
        ),
      ).thenAnswer(
        (_) async => const [
          JokeSearchResult(id: '1', vectorDistance: 0.1),
          JokeSearchResult(id: '2', vectorDistance: 0.2),
        ],
      );

      // Stub search ids provider by directly setting state then mocking getJokesByIds
      // Simulate two ids found
      // Build with overrides
      await tester.pumpWidget(buildTestWidget(overrides));
      await tester.pump();
      when(() => mockRepo.getJokesByIds(any())).thenAnswer((_) async => jokes);

      // Enter topic and submit
      await tester.enterText(
        find.widgetWithText(TextFormField, 'joke topic'),
        'penguins',
      );
      await tester.tap(find.text('Create prompt'));
      await tester.pumpAndSettle();

      // Verify prompt contains positive/negative sections
      expect(
        find.textContaining('Here are some examples of good jokes'),
        findsOneWidget,
      );
      expect(find.textContaining('Setup A Punchline A'), findsOneWidget);
      expect(
        find.textContaining('Here are some examples of bad jokes'),
        findsOneWidget,
      );
      expect(find.textContaining('Setup B Punchline B'), findsOneWidget);

      // New response input and buttons exist (updated labels)
      expect(find.text('Paste LLM response here'), findsOneWidget);
      expect(find.text('Submit'), findsOneWidget);
      expect(find.text('Copy Response Prompt'), findsOneWidget);

      // Provide a simple ###-delimited response and submit
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Paste LLM response here'),
        'Setup A###Punchline A\nSetup B###Punchline B',
      );
      await tester.tap(find.text('Submit'));
      await tester.pumpAndSettle();

      // Confirmation dialog should appear with parsed items
      expect(find.text('Confirm jokes to create'), findsOneWidget);
      expect(find.text('Setup A'), findsOneWidget);
      expect(find.text('Punchline A'), findsOneWidget);
      expect(find.text('Setup B'), findsOneWidget);
      expect(find.text('Punchline B'), findsOneWidget);

      // Close the dialog (Cancel)
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
    },
  );
}
