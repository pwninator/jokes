import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';

class JokeViewerScreen extends ConsumerWidget {
  const JokeViewerScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final jokesAsyncValue = ref.watch(jokesProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Jokes'),
      ),
      body: jokesAsyncValue.when(
        data: (jokes) {
          if (jokes.isEmpty) {
            return const Center(
              child: Text('No jokes found! Try adding some.'),
            );
          }
          return ListView.builder(
            itemCount: jokes.length,
            itemBuilder: (context, index) {
              final joke = jokes[index];
              return Card(
                margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        joke.setupText,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        joke.punchlineText,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ],
                  ),
                ),
              );
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stackTrace) => Center(
          child: Text('Error loading jokes: $error'),
        ),
      ),
    );
  }
}
