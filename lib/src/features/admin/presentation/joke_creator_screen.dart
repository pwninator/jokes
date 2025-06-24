import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_widget.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';

class JokeCreatorScreen extends ConsumerStatefulWidget {
  const JokeCreatorScreen({super.key});

  @override
  ConsumerState<JokeCreatorScreen> createState() => _JokeCreatorScreenState();
}

class _JokeCreatorScreenState extends ConsumerState<JokeCreatorScreen> {
  final _formKey = GlobalKey<FormState>();
  final _instructionsController = TextEditingController();
  bool _isLoading = false;
  Map<String, dynamic>? _generationResult;

  @override
  void dispose() {
    _instructionsController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const AppBarWidget(title: 'Joke Creator'),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Enter instructions for joke generation and critique:',
                style: const TextStyle(fontSize: 16),
              ),
              const SizedBox(height: 16),

              // Instructions Text Field
              TextFormField(
                controller: _instructionsController,
                decoration: const InputDecoration(
                  labelText: 'Instructions',
                  hintText: 'Enter detailed instructions for the AI to generate and critique jokes...',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.edit_note),
                ),
                maxLines: 8,
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Please enter instructions for joke generation';
                  }
                  if (value.trim().length < 10) {
                    return 'Instructions must be at least 10 characters long';
                  }
                  return null;
                },
              ),

              const SizedBox(height: 24),

              // Generate Button
              ElevatedButton(
                onPressed: _isLoading ? null : _generateJokes,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
                child: _isLoading
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text(
                        'Generate',
                        style: TextStyle(fontSize: 16),
                      ),
              ),

              const SizedBox(height: 16),

              // Info text
              Text(
                'The AI will generate and critique jokes based on your instructions.',
                style: TextStyle(
                  fontSize: 12,
                  color: Theme.of(context)
                      .colorScheme
                      .onSurface
                      .withValues(alpha: 0.6),
                ),
                textAlign: TextAlign.center,
              ),

              const SizedBox(height: 24),

              // Results Section
              if (_generationResult != null) ...[
                const Divider(),
                const SizedBox(height: 16),
                Text(
                  'Generation Results:',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 12),
                _buildResultsSection(),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildResultsSection() {
    if (_generationResult == null) return const SizedBox.shrink();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Success/Error indicator
            Row(
              children: [
                Icon(
                  _generationResult!['success'] == true
                      ? Icons.check_circle
                      : Icons.error,
                  color: _generationResult!['success'] == true
                      ? Theme.of(context).appColors.success
                      : Theme.of(context).appColors.authError,
                ),
                const SizedBox(width: 8),
                Text(
                  _generationResult!['success'] == true
                      ? 'Generation Successful'
                      : 'Generation Failed',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: _generationResult!['success'] == true
                        ? Theme.of(context).appColors.success
                        : Theme.of(context).appColors.authError,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Result content
            if (_generationResult!['success'] == true) ...[
              _buildSuccessContent(_generationResult!['data']),
            ] else ...[
              Text(
                'Error: ${_generationResult!['error'] ?? 'Unknown error occurred'}',
                style: TextStyle(
                  color: Theme.of(context).appColors.authError,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSuccessContent(dynamic data) {
    // This will need to be adapted based on the actual response format
    // from the critique_jokes function
    if (data is Map<String, dynamic>) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Response Data:',
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              data.toString(),
              style: const TextStyle(fontFamily: 'monospace'),
            ),
          ),
        ],
      );
    } else {
      return Text(
        data?.toString() ?? 'No data received',
        style: const TextStyle(fontFamily: 'monospace'),
      );
    }
  }

  Future<void> _generateJokes() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _isLoading = true;
      _generationResult = null;
    });

    try {
      final instructions = _instructionsController.text.trim();
      final jokeService = ref.read(jokeCloudFunctionServiceProvider);
      
      final result = await jokeService.critiqueJokes(
        instructions: instructions,
      );

      if (mounted) {
        setState(() {
          _generationResult = result;
        });

        // Show success/error snackbar
        if (result != null && result['success'] == true) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: const Text('Jokes generated successfully!'),
              backgroundColor: Theme.of(context).appColors.success,
              action: SnackBarAction(
                label: 'OK',
                textColor: Colors.white,
                onPressed: () {
                  ScaffoldMessenger.of(context).hideCurrentSnackBar();
                },
              ),
            ),
          );
        } else {
          final errorMessage = result?['error'] ?? 'Failed to generate jokes';
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
        setState(() {
          _generationResult = {
            'success': false,
            'error': 'Unexpected error: $e',
          };
        });

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error generating jokes: $e'),
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