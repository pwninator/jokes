import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/book_creator/book_creator_providers.dart';

class JokeSelectorScreen extends ConsumerWidget {
  const JokeSelectorScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final searchResult = ref.watch(searchedJokesProvider);
    final selectedJokes = ref.watch(selectedJokesProvider);
    final isCategory = ref.watch(jokeSearchIsCategoryProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Select Jokes')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('joke_selector_screen-search-field'),
                    decoration: const InputDecoration(
                      border: OutlineInputBorder(),
                      labelText: 'Search Jokes',
                      prefixIcon: Icon(Icons.search),
                    ),
                    onSubmitted: (query) {
                      ref
                          .read(jokeSearchQueryProvider.notifier)
                          .setQuery(query);
                    },
                  ),
                ),
                const SizedBox(width: 16),
                Row(
                  children: [
                    Checkbox(
                      key: const Key('joke_selector_screen-category-checkbox'),
                      value: isCategory,
                      onChanged: (value) {
                        ref
                            .read(jokeSearchIsCategoryProvider.notifier)
                            .setCategory(value ?? false);
                      },
                    ),
                    const Text('Category'),
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: searchResult.when(
              data: (jokes) {
                if (jokes.isEmpty) {
                  return const Center(child: Text('No jokes found.'));
                }
                return ListView.builder(
                  key: const Key('joke_selector_screen-jokes-list'),
                  itemCount: jokes.length,
                  itemBuilder: (context, index) {
                    final joke = jokes[index];
                    final isSelected = selectedJokes.any(
                      (j) => j.id == joke.id,
                    );

                    return GestureDetector(
                      key: Key('joke_selector_screen-joke-tile-${joke.id}'),
                      onTap: () {
                        ref
                            .read(selectedJokesProvider.notifier)
                            .toggleJokeSelection(joke);
                      },
                      child: Container(
                        height: 100,
                        margin: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          border: Border.all(
                            color: isSelected
                                ? Theme.of(context).primaryColor
                                : Colors.grey,
                            width: isSelected ? 2 : 1,
                          ),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            // Thumbnail
                            Container(
                              width: 84,
                              height: 100,
                              decoration: BoxDecoration(
                                color: Colors.grey[300],
                                borderRadius: const BorderRadius.only(
                                  topLeft: Radius.circular(7),
                                  bottomLeft: Radius.circular(7),
                                ),
                                image: joke.setupImageUrl != null
                                    ? DecorationImage(
                                        image: NetworkImage(
                                          joke.setupImageUrl!,
                                        ),
                                        fit: BoxFit.cover,
                                      )
                                    : null,
                              ),
                              child: joke.setupImageUrl == null
                                  ? const Icon(
                                      Icons.image,
                                      size: 40,
                                      color: Colors.white,
                                    )
                                  : null,
                            ),
                            // Stats
                            Expanded(
                              child: Padding(
                                padding: const EdgeInsets.all(12.0),
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      'Saves: ${joke.numSaves}',
                                      style: const TextStyle(
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      'Shares: ${joke.numShares}',
                                      style: const TextStyle(
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                            // Checkbox
                            if (isSelected)
                              const Padding(
                                padding: EdgeInsets.only(right: 12.0),
                                child: Icon(
                                  Icons.check_circle,
                                  color: Colors.green,
                                ),
                              ),
                          ],
                        ),
                      ),
                    );
                  },
                );
              },
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, stack) => Center(child: Text('Error: $error')),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
            child: FilledButton(
              key: const Key('joke_selector_screen-select-jokes-button'),
              onPressed: () {
                Navigator.of(context).pop();
              },
              style: FilledButton.styleFrom(
                minimumSize: const Size(double.infinity, 48),
              ),
              child: const Text('Select Jokes'),
            ),
          ),
        ],
      ),
    );
  }
}
