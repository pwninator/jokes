import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/joke_card.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';

class JokeViewerScreen extends ConsumerWidget {
  const JokeViewerScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final jokesAsyncValue = ref.watch(jokesProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Jokes')),
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
              return JokeCard(
                joke: joke,
                index: index,
                isAdminMode: false,
              );
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stackTrace) {
          debugPrint('Error loading jokes: $error');
          debugPrint('Stack trace: $stackTrace');
          return Center(child: Text('Error loading jokes: $error'));
        },
      ),
    );
  }
}
