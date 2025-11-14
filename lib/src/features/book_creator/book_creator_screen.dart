import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/book_creator/book_creator_providers.dart';
import 'package:snickerdoodle/src/features/book_creator/joke_selector_screen.dart';

class BookCreatorScreen extends ConsumerWidget {
  const BookCreatorScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selectedJokes = ref.watch(selectedJokesProvider);
    final bookCreatorState = ref.watch(bookCreatorControllerProvider);

    ref.listen<AsyncValue<void>>(bookCreatorControllerProvider,
        (previous, state) {
      state.whenOrNull(
        error: (error, stackTrace) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(SnackBar(content: Text('Error: $error')));
        },
      );
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Book Creator')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              key: const Key('book_creator_screen-title-field'),
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                labelText: 'Book Title',
              ),
              onChanged: (title) {
                ref.read(bookTitleProvider.notifier).setTitle(title);
              },
            ),
            const SizedBox(height: 16),
            Expanded(
              child: Container(
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.grey),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: selectedJokes.isEmpty
                    ? const Center(child: Text('No jokes selected.'))
                    : GridView.builder(
                        key: const Key('book_creator_screen-jokes-grid'),
                        padding: const EdgeInsets.all(8),
                        gridDelegate:
                            const SliverGridDelegateWithFixedCrossAxisCount(
                              crossAxisCount: 2,
                              crossAxisSpacing: 8,
                              mainAxisSpacing: 8,
                              childAspectRatio: 3 / 4,
                            ),
                        itemCount: selectedJokes.length,
                        itemBuilder: (context, index) {
                          final joke = selectedJokes[index];
                          return Card(
                            key: Key(
                              'book_creator_screen-joke-card-${joke.id}',
                            ),
                            child: Column(
                              children: [
                                Expanded(
                                  child: joke.setupImageUrl != null
                                      ? Image.network(
                                          joke.setupImageUrl!,
                                          fit: BoxFit.cover,
                                          width: double.infinity,
                                        )
                                      : Container(
                                          color: Colors.grey[200],
                                          child: const Center(
                                            child: Icon(Icons.image),
                                          ),
                                        ),
                                ),
                                Padding(
                                  padding: const EdgeInsets.all(8.0),
                                  child: Text(
                                    joke.setupText,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
              ),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              key: const Key('book_creator_screen-add-jokes-button'),
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (context) => const JokeSelectorScreen(),
                  ),
                );
              },
              icon: const Icon(Icons.add),
              label: const Text('Add Jokes'),
            ),
            const SizedBox(height: 8),
            FilledButton(
              key: const Key('book_creator_screen-save-book-button'),
              onPressed: bookCreatorState.isLoading
                  ? null
                  : () async {
                      final success = await ref
                          .read(bookCreatorControllerProvider.notifier)
                          .createBook();
                      if (!context.mounted) return;
                      if (success) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Book created successfully!'),
                          ),
                        );
                        ref.read(bookTitleProvider.notifier).setTitle('');
                        ref
                            .read(selectedJokesProvider.notifier)
                            .setJokes([]);
                      }
                    },
              child: bookCreatorState.isLoading
                  ? const SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(color: Colors.white),
                    )
                  : const Text('Save Book'),
            ),
          ],
        ),
      ),
    );
  }
}
