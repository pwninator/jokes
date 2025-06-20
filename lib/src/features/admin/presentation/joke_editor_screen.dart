import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';

class JokeEditorScreen extends ConsumerStatefulWidget {
  const JokeEditorScreen({super.key});

  @override
  ConsumerState<JokeEditorScreen> createState() => _JokeEditorScreenState();
}

class _JokeEditorScreenState extends ConsumerState<JokeEditorScreen> {
  final _formKey = GlobalKey<FormState>();
  final _setupController = TextEditingController();
  final _punchlineController = TextEditingController();
  bool _isLoading = false;

  @override
  void dispose() {
    _setupController.dispose();
    _punchlineController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Add New Joke'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Create a new joke by filling out the setup and punchline below:',
                style: TextStyle(fontSize: 16),
              ),
              const SizedBox(height: 24),

              // Setup Text Field
              TextFormField(
                controller: _setupController,
                decoration: const InputDecoration(
                  labelText: 'Setup',
                  hintText: 'Enter the joke setup...',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.lightbulb_outline),
                ),
                maxLines: 3,
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Please enter a setup for the joke';
                  }
                  if (value.trim().length < 5) {
                    return 'Setup must be at least 5 characters long';
                  }
                  return null;
                },
              ),

              const SizedBox(height: 16),

              // Punchline Text Field
              TextFormField(
                controller: _punchlineController,
                decoration: const InputDecoration(
                  labelText: 'Punchline',
                  hintText: 'Enter the punchline...',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.mood),
                ),
                maxLines: 3,
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Please enter a punchline for the joke';
                  }
                  if (value.trim().length < 5) {
                    return 'Punchline must be at least 5 characters long';
                  }
                  return null;
                },
              ),

              const SizedBox(height: 24),

              // Save Button
              ElevatedButton(
                onPressed: _isLoading ? null : _saveJoke,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
                child:
                    _isLoading
                        ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                        : const Text(
                          'Save Joke',
                          style: TextStyle(fontSize: 16),
                        ),
              ),

              const SizedBox(height: 16),

              // Info text
              Text(
                'Your joke will be reviewed and added to the collection.',
                style: TextStyle(
                  fontSize: 12,
                  color: Theme.of(
                    context,
                  ).colorScheme.onSurface.withValues(alpha: 0.6),
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _saveJoke() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _isLoading = true;
    });

    try {
      final setup = _setupController.text.trim();
      final punchline = _punchlineController.text.trim();

      // Call the Firebase Cloud Function using the service
      final jokeService = ref.read(jokeCloudFunctionServiceProvider);
      final result = await jokeService.createJokeWithResponse(
        setupText: setup,
        punchlineText: punchline,
      );

      if (mounted) {
        if (result != null && result['success'] == true) {
          // Success
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: const Text('Joke saved successfully!'),
              backgroundColor: Theme.of(context).appColors.success,
              action: SnackBarAction(
                label: 'View',
                textColor: Colors.white,
                onPressed: () {
                  Navigator.of(context).pop(); // Go back to management screen
                },
              ),
            ),
          );

          // Clear the form
          _setupController.clear();
          _punchlineController.clear();

          // Navigate back after a short delay
          Future.delayed(const Duration(seconds: 1), () {
            if (mounted) {
              Navigator.of(context).pop();
            }
          });
        } else {
          // Error
          final errorMessage = result?['error'] ?? 'Failed to save joke';

          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Error: $errorMessage'),
              backgroundColor: Theme.of(context).appColors.authError,
              duration: const Duration(seconds: 5),
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error saving joke: $e'),
            backgroundColor: Theme.of(context).appColors.authError,
            duration: const Duration(seconds: 5),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }
}
