import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/counter_example/application/counter_provider.dart';

class CounterScreen extends ConsumerWidget {
  const CounterScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Listen to the counter provider
    final counter = ref.watch(counterProvider);
    // Get the notifier to call the increment method
    // final counterNotifier = ref.read(counterProvider.notifier); // Not needed this way for StateProvider

    return Scaffold(
      appBar: AppBar(
        title: const Text('Counter Example'),
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            const Text('You have pushed the button this many times:'),
            Text(
              '$counter', // Display the counter value from the provider
              style: Theme.of(context).textTheme.headlineMedium,
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          // Call the increment method on the notifier for StateProvider
          ref.read(counterProvider.notifier).state++;
        },
        tooltip: 'Increment',
        child: const Icon(Icons.add),
      ),
    );
  }
}
