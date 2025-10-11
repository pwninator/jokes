import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';

void main() {
  group('discoverCategoriesProvider', () {
    test(
      'includes Halloween seasonal tile before approved categories',
      () async {
        final container = ProviderContainer(
          overrides: [
            // Provide some approved categories from Firestore
            jokeCategoriesProvider.overrideWith(
              (ref) => Stream.value([
                JokeCategory(
                  id: 'firestore:1',
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

        // Expect popular first, then halloween, then firestore-approved
        expect(categories.length, 3);
        expect(categories[0].type, CategoryType.popular);
        expect(categories[1].type, CategoryType.seasonal);
        expect(categories[1].seasonalValue, 'Halloween');
        expect(categories[2].id, 'firestore:1');
      },
    );
  });
}
