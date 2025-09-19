import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_modification_providers.dart';
import 'package:snickerdoodle/src/core/providers/crash_reporting_provider.dart';

class ModifyImageDialog extends ConsumerStatefulWidget {
  final String jokeId;
  final String? setupImageUrl;
  final String? punchlineImageUrl;

  const ModifyImageDialog({
    super.key,
    required this.jokeId,
    this.setupImageUrl,
    this.punchlineImageUrl,
  });

  @override
  ConsumerState<ModifyImageDialog> createState() => _ModifyImageDialogState();
}

class _ModifyImageDialogState extends ConsumerState<ModifyImageDialog> {
  final TextEditingController _setupController = TextEditingController();
  final TextEditingController _punchlineController = TextEditingController();
  int _textChangeCounter = 0; // Force rebuilds when text changes

  @override
  void initState() {
    super.initState();
    _setupController.addListener(_onTextChanged);
    _punchlineController.addListener(_onTextChanged);
  }

  @override
  void dispose() {
    _setupController.removeListener(_onTextChanged);
    _punchlineController.removeListener(_onTextChanged);
    _setupController.dispose();
    _punchlineController.dispose();
    super.dispose();
  }

  void _onTextChanged() {
    setState(() {
      _textChangeCounter++; // Increment to force rebuild
    });
  }

  bool get _canSubmit {
    // Use _textChangeCounter to ensure this is recalculated on every rebuild
    final _ = _textChangeCounter;
    final setupText = _setupController.text.trim();
    final punchlineText = _punchlineController.text.trim();
    return setupText.isNotEmpty || punchlineText.isNotEmpty;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return AlertDialog(
      title: const Text('Modify Images'),
      content: SizedBox(
        width: 400,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Setup image section
              Container(
                width: 150,
                height: 150,
                decoration: BoxDecoration(
                  border: Border.all(
                    color: theme.colorScheme.outline.withValues(alpha: 0.3),
                  ),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child:
                      widget.setupImageUrl != null &&
                          widget.setupImageUrl!.isNotEmpty
                      ? Image.network(
                          widget.setupImageUrl!,
                          fit: BoxFit.cover,
                          errorBuilder: (context, error, stackTrace) {
                            // Report image load error (non-fatal)
                            final crash = ref.read(
                              crashReportingServiceProvider,
                            );
                            crash.recordNonFatal(
                              error,
                              stackTrace: stackTrace,
                              keys: {
                                'screen': 'ModifyImageDialog',
                                'imageType': 'setup',
                                'jokeId': widget.jokeId,
                                'imageUrl': widget.setupImageUrl,
                              },
                            );
                            return Container(
                              color: theme.colorScheme.surfaceContainerHighest,
                              child: Icon(
                                Icons.image_not_supported,
                                color: theme.colorScheme.onSurface.withValues(
                                  alpha: 0.5,
                                ),
                              ),
                            );
                          },
                        )
                      : Container(
                          color: theme.colorScheme.surfaceContainerHighest,
                          child: Icon(
                            Icons.image_not_supported,
                            color: theme.colorScheme.onSurface.withValues(
                              alpha: 0.5,
                            ),
                          ),
                        ),
                ),
              ),
              const SizedBox(height: 8),
              SizedBox(
                height: 100, // 5 lines * ~20px per line
                child: TextField(
                  key: const Key('modify_image_dialog-setup-text-field'),
                  controller: _setupController,
                  maxLines: 5,
                  decoration: const InputDecoration(
                    hintText: 'Enter instructions to modify the setup image...',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(height: 24),
              // Punchline image section
              Container(
                width: 150,
                height: 150,
                decoration: BoxDecoration(
                  border: Border.all(
                    color: theme.colorScheme.outline.withValues(alpha: 0.3),
                  ),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child:
                      widget.punchlineImageUrl != null &&
                          widget.punchlineImageUrl!.isNotEmpty
                      ? Image.network(
                          widget.punchlineImageUrl!,
                          fit: BoxFit.cover,
                          errorBuilder: (context, error, stackTrace) {
                            // Report image load error (non-fatal)
                            final crash = ref.read(
                              crashReportingServiceProvider,
                            );
                            crash.recordNonFatal(
                              error,
                              stackTrace: stackTrace,
                              keys: {
                                'screen': 'ModifyImageDialog',
                                'imageType': 'punchline',
                                'jokeId': widget.jokeId,
                                'imageUrl': widget.punchlineImageUrl,
                              },
                            );
                            return Container(
                              color: theme.colorScheme.surfaceContainerHighest,
                              child: Icon(
                                Icons.image_not_supported,
                                color: theme.colorScheme.onSurface.withValues(
                                  alpha: 0.5,
                                ),
                              ),
                            );
                          },
                        )
                      : Container(
                          color: theme.colorScheme.surfaceContainerHighest,
                          child: Icon(
                            Icons.image_not_supported,
                            color: theme.colorScheme.onSurface.withValues(
                              alpha: 0.5,
                            ),
                          ),
                        ),
                ),
              ),
              const SizedBox(height: 8),
              SizedBox(
                height: 100, // 5 lines * ~20px per line
                child: TextField(
                  key: const Key('modify_image_dialog-punchline-text-field'),
                  controller: _punchlineController,
                  maxLines: 5,
                  decoration: const InputDecoration(
                    hintText:
                        'Enter instructions to modify the punchline image...',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          key: const Key('modify_image_dialog-cancel-button'),
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          key: const Key('modify_image_dialog-submit-button'),
          onPressed: !_canSubmit ? null : _submitModifications,
          child: const Text('Submit'),
        ),
      ],
    );
  }

  Future<void> _submitModifications() async {
    final setupInstructions = _setupController.text.trim();
    final punchlineInstructions = _punchlineController.text.trim();

    // Close dialog immediately
    Navigator.of(context).pop();

    // Start the modification process in the background
    try {
      final modificationService = ref.read(jokeModificationProvider.notifier);
      final success = await modificationService.modifyJoke(
        widget.jokeId,
        setupInstructions: setupInstructions.isEmpty ? null : setupInstructions,
        punchlineInstructions: punchlineInstructions.isEmpty
            ? null
            : punchlineInstructions,
      );

      // Show success/error message using the parent context
      if (mounted) {
        if (success) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Images modified successfully!'),
              backgroundColor: Colors.green,
            ),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Failed to modify images. Please try again.'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }
}
