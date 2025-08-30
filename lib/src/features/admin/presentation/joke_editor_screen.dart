import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/image_selector_carousel.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';

class JokeEditorScreen extends ConsumerStatefulWidget {
  const JokeEditorScreen({super.key, this.jokeId});

  final String? jokeId;

  @override
  ConsumerState<JokeEditorScreen> createState() => _JokeEditorScreenState();
}

class _JokeEditorScreenState extends ConsumerState<JokeEditorScreen> {
  final _formKey = GlobalKey<FormState>();
  final _setupController = TextEditingController();
  final _punchlineController = TextEditingController();
  final _setupImageDescriptionController = TextEditingController();
  final _punchlineImageDescriptionController = TextEditingController();
  bool _isLoading = false;

  // Track selected images for carousels
  String? _selectedSetupImageUrl;
  String? _selectedPunchlineImageUrl;

  bool get _isEditMode => widget.jokeId != null;

  @override
  void initState() {
    super.initState();
    // Enable keyboard resizing for this screen
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(keyboardResizeProvider.notifier).state = true;
    });
  }

  @override
  void dispose() {
    // Disable keyboard resizing when leaving this screen
    ref.read(keyboardResizeProvider.notifier).state = false;
    _setupController.dispose();
    _punchlineController.dispose();
    _setupImageDescriptionController.dispose();
    _punchlineImageDescriptionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Handle different ways of getting the joke
    if (widget.jokeId != null) {
      // Joke ID provided - fetch joke from provider
      final jokeAsync = ref.watch(jokeByIdProvider(widget.jokeId!));

      return jokeAsync.when(
        data: (joke) {
          if (joke == null) {
            return AdaptiveAppBarScreen(
              title: 'Edit Joke',
              body: const Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.error_outline, size: 64),
                    SizedBox(height: 16),
                    Text('Joke not found'),
                  ],
                ),
              ),
            );
          }
          return _buildEditorContent(joke);
        },
        loading: () => AdaptiveAppBarScreen(
          title: 'Edit Joke',
          body: const Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                CircularProgressIndicator(),
                SizedBox(height: 16),
                Text('Loading joke...'),
              ],
            ),
          ),
        ),
        error: (error, stackTrace) => AdaptiveAppBarScreen(
          title: 'Edit Joke',
          body: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, size: 64),
                const SizedBox(height: 16),
                Text('Error loading joke: $error'),
              ],
            ),
          ),
        ),
      );
    } else {
      // Creating new joke
      return _buildEditorContent(null);
    }
  }

  Widget _buildEditorContent(Joke? joke) {
    final isEditMode = joke != null;

    // Initialize form fields if this is the first time loading a joke via ID
    if (joke != null &&
        widget.jokeId != null &&
        _setupController.text.isEmpty) {
      _setupController.text = joke.setupText;
      _punchlineController.text = joke.punchlineText;
      _setupImageDescriptionController.text = joke.setupImageDescription ?? '';
      _punchlineImageDescriptionController.text =
          joke.punchlineImageDescription ?? '';

      // Set initial selected images
      _selectedSetupImageUrl = joke.setupImageUrl;
      _selectedPunchlineImageUrl = joke.punchlineImageUrl;
    }

    return AdaptiveAppBarScreen(
      title: isEditMode ? 'Edit Joke' : 'Add New Joke',
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  isEditMode
                      ? 'Edit the joke setup and punchline below:'
                      : 'Create a new joke by filling out the setup and punchline below:',
                  style: const TextStyle(fontSize: 16),
                ),
                const SizedBox(height: 24),

                // Setup Text Field
                TextFormField(
                  key: const Key('setupTextField'),
                  controller: _setupController,
                  decoration: const InputDecoration(
                    labelText: 'Setup',
                    hintText: 'Enter the joke setup...',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.question_mark),
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
                  key: const Key('punchlineTextField'),
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

                // Image Description Fields (only show in edit mode)
                if (isEditMode) ...[
                  const SizedBox(height: 24),
                  const Divider(),
                  const SizedBox(height: 16),

                  Text(
                    'Image Descriptions',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Setup Image Carousel (if available)
                  if (joke.allSetupImageUrls.isNotEmpty) ...[
                    ImageSelectorCarousel(
                      imageUrls: joke.allSetupImageUrls,
                      selectedImageUrl: _selectedSetupImageUrl,
                      title: 'Setup Images',
                      onImageSelected: (imageUrl) {
                        // Only update state if the selection actually changed
                        if (_selectedSetupImageUrl != imageUrl) {
                          setState(() {
                            _selectedSetupImageUrl = imageUrl;
                          });
                        }
                      },
                    ),
                    const SizedBox(height: 16),
                  ],

                  // Setup Image Description Field
                  TextFormField(
                    key: const Key('setupImageDescriptionTextField'),
                    controller: _setupImageDescriptionController,
                    decoration: const InputDecoration(
                      labelText: 'Setup Image Description',
                      hintText: 'Describe the setup image...',
                      border: OutlineInputBorder(),
                      alignLabelWithHint: true,
                    ),
                    maxLines: 10,
                    validator: (value) {
                      // Allow empty descriptions; validate length only if not empty
                      if (value != null &&
                          value.trim().isNotEmpty &&
                          value.trim().length < 10) {
                        return 'Description must be at least 10 characters long';
                      }
                      return null;
                    },
                  ),

                  const SizedBox(height: 16),

                  // Punchline Image Carousel (if available)
                  if (joke.allPunchlineImageUrls.isNotEmpty) ...[
                    ImageSelectorCarousel(
                      imageUrls: joke.allPunchlineImageUrls,
                      selectedImageUrl: _selectedPunchlineImageUrl,
                      title: 'Punchline Images',
                      onImageSelected: (imageUrl) {
                        // Only update state if the selection actually changed
                        if (_selectedPunchlineImageUrl != imageUrl) {
                          setState(() {
                            _selectedPunchlineImageUrl = imageUrl;
                          });
                        }
                      },
                    ),
                    const SizedBox(height: 16),
                  ],

                  // Punchline Image Description Field
                  TextFormField(
                    key: const Key('punchlineImageDescriptionTextField'),
                    controller: _punchlineImageDescriptionController,
                    decoration: const InputDecoration(
                      labelText: 'Punchline Image Description',
                      hintText: 'Describe the punchline image...',
                      border: OutlineInputBorder(),
                      alignLabelWithHint: true,
                    ),
                    maxLines: 10,
                    validator: (value) {
                      // Allow empty descriptions; validate length only if not empty
                      if (value != null &&
                          value.trim().isNotEmpty &&
                          value.trim().length < 10) {
                        return 'Description must be at least 10 characters long';
                      }
                      return null;
                    },
                  ),
                ],

                const SizedBox(height: 24),

                // Save Button
                ElevatedButton(
                  key: Key(_isEditMode ? 'updateJokeButton' : 'saveJokeButton'),
                  onPressed: _isLoading ? null : _saveJoke,
                  child: _isLoading
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Text(
                          _isEditMode ? 'Update Joke' : 'Save Joke',
                          style: const TextStyle(fontSize: 16),
                        ),
                ),
              ],
            ),
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

      if (_isEditMode) {
        // Update existing joke
        final setupImageDescription = _setupImageDescriptionController.text
            .trim();
        final punchlineImageDescription = _punchlineImageDescriptionController
            .text
            .trim();
        await _updateJoke(
          setup,
          punchline,
          setupImageDescription,
          punchlineImageDescription,
        );
      } else {
        // Create new joke
        await _createJoke(setup, punchline);
      }
    } catch (e) {
      debugPrint('Error saving joke (id=${widget.jokeId}): $e');
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

  Future<void> _createJoke(String setup, String punchline) async {
    // Call the Firebase Cloud Function using the service
    final jokeService = ref.read(jokeCloudFunctionServiceProvider);
    final result = await jokeService.createJokeWithResponse(
      setupText: setup,
      punchlineText: punchline,
      adminOwned: true,
    );

    if (mounted) {
      if (result != null && result['success'] == true) {
        // Success - show message, clear form, stay on page
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Joke saved successfully!'),
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

        // Clear the form for next joke
        _setupController.clear();
        _punchlineController.clear();

        // Reset form validation state after clearing controllers
        if (mounted) {
          setState(() {
            // Force UI update after clearing
          });
        }
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
  }

  Future<void> _updateJoke(
    String setup,
    String punchline,
    String setupImageDescription,
    String punchlineImageDescription,
  ) async {
    // Update the joke directly in Firestore using the repository
    final jokeRepository = ref.read(jokeRepositoryProvider);

    await jokeRepository.updateJoke(
      jokeId: widget.jokeId!,
      setupText: setup,
      punchlineText: punchline,
      setupImageUrl: _selectedSetupImageUrl,
      punchlineImageUrl: _selectedPunchlineImageUrl,
      setupImageDescription: setupImageDescription,
      punchlineImageDescription: punchlineImageDescription,
    );

    if (mounted) {
      // Success - show message and navigate back
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('Joke updated successfully!'),
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

      // Navigate back to previous screen
      Navigator.of(context).pop();
    }
  }
}
