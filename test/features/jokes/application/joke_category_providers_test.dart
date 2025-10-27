import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/settings/application/feed_screen_status_provider.dart';

void main() {
  group('discoverCategoriesProvider', () {
    test(
      'includes popular, Halloween seasonal, and approved categories',
      () async {
        final container = ProviderContainer(
          overrides: [
            // Mock feed screen status to true (daily jokes tile won't appear)
            feedScreenStatusProvider.overrideWithValue(true),
            // Provide some approved categories from Firestore
            jokeCategoriesProvider.overrideWith(
              (ref) => Stream.value([
                JokeCategory(
                  id: '${JokeCategory.firestorePrefix}1',
                  displayName: 'Cats',
                  type: CategoryType.search,
                  jokeDescriptionQuery: 'cats',
                  state: JokeCategoryState.approved,
                ),
              ]),
            ),
          ],
        );
        addTearDown(container.dispose);

        // Wait for discoverCategoriesProvider to have a value
        final completer = Completer<void>();
        final sub = container.listen(discoverCategoriesProvider, (_, next) {
          if (next.hasValue && !completer.isCompleted) {
            completer.complete();
          }
        }, fireImmediately: true);
        addTearDown(sub.close);
        await completer.future;

        final async = container.read(discoverCategoriesProvider);
        expect(async.hasValue, isTrue);
        final categories = async.value!;

        // Expect presence regardless of order
        expect(categories.length, 3);
        expect(
          categories.any((category) => category.type == CategoryType.popular),
          isTrue,
        );
        expect(
          categories.any(
            (category) =>
                category.type == CategoryType.seasonal &&
                category.seasonalValue == 'Halloween',
          ),
          isTrue,
        );
        expect(
          categories.any(
            (category) => category.id == '${JokeCategory.firestorePrefix}1',
          ),
          isTrue,
        );
      },
    );

    test('includes daily jokes tile when feed screen is disabled', () async {
      final container = ProviderContainer(
        overrides: [
          // Mock feed screen status to false (daily jokes tile will appear)
          feedScreenStatusProvider.overrideWithValue(false),
          // Provide some approved categories from Firestore
          jokeCategoriesProvider.overrideWith(
            (ref) => Stream.value([
              JokeCategory(
                id: '${JokeCategory.firestorePrefix}1',
                displayName: 'Cats',
                type: CategoryType.search,
                jokeDescriptionQuery: 'cats',
                state: JokeCategoryState.approved,
              ),
            ]),
          ),
        ],
      );
      addTearDown(container.dispose);

      // Wait for discoverCategoriesProvider to have a value
      final completer = Completer<void>();
      final sub = container.listen(discoverCategoriesProvider, (_, next) {
        if (next.hasValue && !completer.isCompleted) {
          completer.complete();
        }
      }, fireImmediately: true);
      addTearDown(sub.close);
      await completer.future;

      final async = container.read(discoverCategoriesProvider);
      expect(async.hasValue, isTrue);
      final categories = async.value!;

      // Expect daily jokes tile to be present and first
      expect(categories.length, 4); // daily + popular + halloween + cats
      expect(categories.first.type, CategoryType.daily);
      expect(categories.first.displayName, 'Daily Jokes 📅');
      expect(categories.first.id, 'programmatic:daily');
    });
  });
}
