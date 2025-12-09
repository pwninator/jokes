import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:snickerdoodle/src/common_widgets/app_bar_configured_screen.dart';
import 'package:snickerdoodle/src/common_widgets/image_selector_carousel.dart';
import 'package:snickerdoodle/src/config/router/router_providers.dart';
import 'package:snickerdoodle/src/core/services/app_logger.dart';
import 'package:snickerdoodle/src/core/theme/app_theme.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_data_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_model.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_repository_provider.dart';
import 'package:snickerdoodle/src/features/jokes/data/services/joke_cloud_function_service.dart'
    show SafetyCheckException, jokeCloudFunctionServiceProvider;

/// Guided form for creating or editing a joke.
///
class JokeEditorScreen extends ConsumerStatefulWidget {
  const JokeEditorScreen({super.key, this.jokeId});

  final String? jokeId;

  @override
  ConsumerState<JokeEditorScreen> createState() => _JokeEditorScreenState();
}

enum _EditorStage { textEntry, sceneIdeas, imageGeneration }

class _JokeEditorScreenState extends ConsumerState<JokeEditorScreen> {
  final _formKey = GlobalKey<FormState>();
  final _setupController = TextEditingController();
  final _punchlineController = TextEditingController();
  final _setupSceneIdeaController = TextEditingController();
  final _punchlineSceneIdeaController = TextEditingController();
  final _setupSceneSuggestionController = TextEditingController();
  final _punchlineSceneSuggestionController = TextEditingController();
  final _setupImageDescriptionController = TextEditingController();
  final _punchlineImageDescriptionController = TextEditingController();

  bool _isStage1Submitting = false;
  bool _isSetupSuggestionLoading = false;
  bool _isPunchlineSuggestionLoading = false;
  bool _isGenerateDescriptionsLoading = false;
  bool _isGenerateImagesLoading = false;

  bool _stage1Expanded = true;
  bool _stage2Expanded = false;
  bool _stage3Expanded = false;
  bool _autoOpenedStage2 = false;
  bool _autoOpenedStage3 = false;

  String? _currentJokeId;
  Joke? _latestJoke;
  String? _selectedSetupImageUrl;
  String? _selectedPunchlineImageUrl;
  String _imageQuality = 'low';
  bool _regenerateSceneIdeas = false;

  String? get _resolvedJokeId => _currentJokeId ?? widget.jokeId;
  bool get _hasExistingJoke => _resolvedJokeId != null;
  bool get _hasSceneIdeas =>
      (_latestJoke?.setupSceneIdea?.isNotEmpty ?? false) &&
      (_latestJoke?.punchlineSceneIdea?.isNotEmpty ?? false);
  bool get _hasImageDescriptions =>
      (_latestJoke?.setupImageDescription?.isNotEmpty ?? false) &&
      (_latestJoke?.punchlineImageDescription?.isNotEmpty ?? false);
  bool get _hasGeneratedImages =>
      (_latestJoke?.allSetupImageUrls.isNotEmpty ?? false) ||
      (_latestJoke?.allPunchlineImageUrls.isNotEmpty ?? false);

  @override
  void initState() {
    super.initState();
    _currentJokeId = widget.jokeId;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(keyboardResizeProvider.notifier).state = true;
    });
  }

  @override
  void dispose() {
    _setupController.dispose();
    _punchlineController.dispose();
    _setupSceneIdeaController.dispose();
    _punchlineSceneIdeaController.dispose();
    _setupSceneSuggestionController.dispose();
    _punchlineSceneSuggestionController.dispose();
    _setupImageDescriptionController.dispose();
    _punchlineImageDescriptionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final jokeId = _resolvedJokeId;
    if (jokeId != null) {
      final jokeAsync = ref.watch(jokeStreamByIdProvider(jokeId));
      return jokeAsync.when(
        data: (joke) {
          if (joke == null) {
            return _buildNotFoundScreen();
          }
          _handleJokeLoaded(joke);
          return _buildScreen();
        },
        loading: _buildLoadingScreen,
        error: (error, _) => _buildErrorScreen(error),
      );
    }
    return _buildScreen();
  }

  AppBarConfiguredScreen _buildNotFoundScreen() {
    return AppBarConfiguredScreen(
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

  AppBarConfiguredScreen _buildLoadingScreen() {
    return AppBarConfiguredScreen(
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
    );
  }

  AppBarConfiguredScreen _buildErrorScreen(Object error) {
    return AppBarConfiguredScreen(
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
    );
  }

  AppBarConfiguredScreen _buildScreen() {
    final title = _hasExistingJoke ? 'Edit Joke' : 'Add New Joke';
    return AppBarConfiguredScreen(
      title: title,
      body: Form(
        key: _formKey,
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              _buildStageCard(
                stage: _EditorStage.textEntry,
                stepNumber: 1,
                title: 'Enter setup & punchline',
                enabled: true,
                isComplete: _hasExistingJoke,
                isExpanded: _stage1Expanded,
                child: _buildStageOneContent(),
              ),
              _buildStageCard(
                stage: _EditorStage.sceneIdeas,
                stepNumber: 2,
                title: 'Refine scene ideas',
                enabled: _hasExistingJoke,
                isComplete: _hasImageDescriptions,
                isExpanded: _stage2Expanded,
                child: _buildStageTwoContent(),
              ),
              _buildStageCard(
                stage: _EditorStage.imageGeneration,
                stepNumber: 3,
                title: 'Generate images',
                enabled: _hasImageDescriptions,
                isComplete: _hasGeneratedImages,
                isExpanded: _stage3Expanded,
                child: _buildStageThreeContent(),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStageCard({
    required _EditorStage stage,
    required int stepNumber,
    required String title,
    required bool enabled,
    required bool isComplete,
    required bool isExpanded,
    required Widget child,
  }) {
    final header = ListTile(
      onTap: enabled ? () => _toggleStage(stage) : null,
      title: Text('Step $stepNumber: $title'),
      trailing: Icon(
        isComplete
            ? Icons.check_circle
            : (isExpanded ? Icons.expand_less : Icons.expand_more),
      ),
    );

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Opacity(
        opacity: enabled ? 1 : 0.5,
        child: Column(
          children: [
            header,
            if (enabled && isExpanded) const Divider(height: 1),
            if (enabled && isExpanded)
              Padding(padding: const EdgeInsets.all(16), child: child),
          ],
        ),
      ),
    );
  }

  Widget _buildStageOneContent() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
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
            return null;
          },
        ),
        const SizedBox(height: 16),
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
            return null;
          },
        ),
        if (_hasExistingJoke) ...[
          const SizedBox(height: 12),
          CheckboxListTile(
            key: const Key('regenerateSceneIdeasCheckbox'),
            value: _regenerateSceneIdeas,
            onChanged: _isStage1Submitting
                ? null
                : (value) {
                    setState(() {
                      _regenerateSceneIdeas = value ?? false;
                    });
                  },
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            title: const Text('Regenerate scene ideas after updating text'),
          ),
        ],
        const SizedBox(height: 16),
        ElevatedButton(
          key: Key(_hasExistingJoke ? 'updateJokeButton' : 'saveJokeButton'),
          onPressed: _isStage1Submitting ? null : _submitStageOne,
          child: _isStage1Submitting
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : Text(_hasExistingJoke ? 'Update Joke Text' : 'Create Joke'),
        ),
      ],
    );
  }

  Widget _buildStageTwoContent() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextFormField(
          key: const Key('setupSceneIdeaTextField'),
          controller: _setupSceneIdeaController,
          maxLines: 6,
          decoration: const InputDecoration(
            labelText: 'Setup Scene Idea',
            hintText: 'Describe the concept for the setup illustration',
            border: OutlineInputBorder(),
            alignLabelWithHint: true,
          ),
        ),
        const SizedBox(height: 8),
        _buildSuggestionRow(
          controller: _setupSceneSuggestionController,
          isLoading: _isSetupSuggestionLoading,
          buttonKey: const Key('setupSceneSuggestionButton'),
          textFieldKey: const Key('setupSceneSuggestionTextField'),
          onPressed: () => _requestSceneModification(isSetup: true),
        ),
        const SizedBox(height: 16),
        TextFormField(
          key: const Key('punchlineSceneIdeaTextField'),
          controller: _punchlineSceneIdeaController,
          maxLines: 6,
          decoration: const InputDecoration(
            labelText: 'Punchline Scene Idea',
            hintText: 'Describe the concept for the punchline illustration',
            border: OutlineInputBorder(),
            alignLabelWithHint: true,
          ),
        ),
        const SizedBox(height: 8),
        _buildSuggestionRow(
          controller: _punchlineSceneSuggestionController,
          isLoading: _isPunchlineSuggestionLoading,
          buttonKey: const Key('punchlineSceneSuggestionButton'),
          textFieldKey: const Key('punchlineSceneSuggestionTextField'),
          onPressed: () => _requestSceneModification(isSetup: false),
        ),
        const SizedBox(height: 16),
        FilledButton(
          key: const Key('generateImageDescriptionsButton'),
          onPressed: _isGenerateDescriptionsLoading
              ? null
              : _handleGenerateDescriptions,
          child: _isGenerateDescriptionsLoading
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Generate Image Descriptions'),
        ),
      ],
    );
  }

  Widget _buildSuggestionRow({
    required TextEditingController controller,
    required bool isLoading,
    required Key buttonKey,
    required Key textFieldKey,
    required VoidCallback onPressed,
  }) {
    return Row(
      children: [
        Expanded(
          child: TextField(
            key: textFieldKey,
            controller: controller,
            decoration: const InputDecoration(
              labelText: 'Suggestion',
              hintText: 'e.g. “Make it sillier”',
              border: OutlineInputBorder(),
            ),
          ),
        ),
        const SizedBox(width: 8),
        IconButton(
          key: buttonKey,
          onPressed: isLoading ? null : onPressed,
          icon: isLoading
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.auto_awesome),
          tooltip: 'Ask AI to update scene idea',
        ),
      ],
    );
  }

  Widget _buildStageThreeContent() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextFormField(
          key: const Key('setupImageDescriptionTextField'),
          controller: _setupImageDescriptionController,
          maxLines: 6,
          decoration: const InputDecoration(
            labelText: 'Setup Image Description',
            border: OutlineInputBorder(),
            alignLabelWithHint: true,
          ),
        ),
        const SizedBox(height: 16),
        TextFormField(
          key: const Key('punchlineImageDescriptionTextField'),
          controller: _punchlineImageDescriptionController,
          maxLines: 6,
          decoration: const InputDecoration(
            labelText: 'Punchline Image Description',
            border: OutlineInputBorder(),
            alignLabelWithHint: true,
          ),
        ),
        const SizedBox(height: 16),
        DropdownButtonFormField<String>(
          initialValue: _imageQuality,
          decoration: const InputDecoration(
            labelText: 'Image Quality',
            border: OutlineInputBorder(),
          ),
          items: const [
            DropdownMenuItem(value: 'low', child: Text('Low (fast)')),
            DropdownMenuItem(value: 'medium', child: Text('Medium')),
            DropdownMenuItem(value: 'high', child: Text('High (slow)')),
          ],
          onChanged: (val) {
            if (val != null) {
              setState(() {
                _imageQuality = val;
              });
            }
          },
        ),
        const SizedBox(height: 16),
        FilledButton(
          key: const Key('generateImagesButton'),
          onPressed: _isGenerateImagesLoading
              ? null
              : _generateImagesWithCreationProcess,
          child: _isGenerateImagesLoading
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Generate Images'),
        ),
        const SizedBox(height: 16),
        if (_latestJoke?.allSetupImageUrls.isNotEmpty ?? false) ...[
          const SizedBox(height: 16),
          ImageSelectorCarousel(
            imageUrls: _latestJoke!.allSetupImageUrls,
            selectedImageUrl: _selectedSetupImageUrl,
            title: 'Setup Images',
            onImageSelected: (value) {
              if (value != _selectedSetupImageUrl) {
                setState(() {
                  _selectedSetupImageUrl = value;
                });
              }
            },
          ),
        ],
        if (_latestJoke?.allPunchlineImageUrls.isNotEmpty ?? false) ...[
          const SizedBox(height: 16),
          ImageSelectorCarousel(
            imageUrls: _latestJoke!.allPunchlineImageUrls,
            selectedImageUrl: _selectedPunchlineImageUrl,
            title: 'Punchline Images',
            onImageSelected: (value) {
              if (value != _selectedPunchlineImageUrl) {
                setState(() {
                  _selectedPunchlineImageUrl = value;
                });
              }
            },
          ),
        ],
        const SizedBox(height: 16),
        OutlinedButton(
          key: const Key('saveImageSelectionButton'),
          onPressed: _hasGeneratedImages ? _saveImageSelection : null,
          child: const Text('Save Image Selection'),
        ),
      ],
    );
  }

  void _toggleStage(_EditorStage stage) {
    setState(() {
      switch (stage) {
        case _EditorStage.textEntry:
          _stage1Expanded = !_stage1Expanded;
          break;
        case _EditorStage.sceneIdeas:
          if (_hasExistingJoke) {
            _stage2Expanded = !_stage2Expanded;
          }
          break;
        case _EditorStage.imageGeneration:
          if (_hasImageDescriptions) {
            _stage3Expanded = !_stage3Expanded;
          }
          break;
      }
    });
  }

  Future<void> _submitStageOne() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _isStage1Submitting = true;
    });

    final setup = _setupController.text.trim();
    final punchline = _punchlineController.text.trim();

    try {
      if (_hasExistingJoke) {
        await _updateExistingJokeTextsViaCf(setup, punchline);
      } else {
        await _createJokeInCloud(setup, punchline);
      }
    } catch (e, st) {
      _showSnack('Error saving joke', exception: e, stackTrace: st);
    } finally {
      if (mounted) {
        setState(() {
          _isStage1Submitting = false;
        });
      }
    }
  }

  Future<void> _createJokeInCloud(String setup, String punchline) async {
    final jokeService = ref.read(jokeCloudFunctionServiceProvider);
    final joke = await jokeService.createJokeWithResponse(
      setupText: setup,
      punchlineText: punchline,
      adminOwned: true,
    );
    setState(() {
      _applyJoke(joke);
      _stage1Expanded = false;
      _stage2Expanded = true;
    });
    _showSnack('Joke created. Scene ideas ready for refinement.');
  }

  Future<void> _updateExistingJokeTextsViaCf(
    String setup,
    String punchline,
  ) async {
    final jokeId = _resolvedJokeId;
    if (jokeId == null) return;
    final jokeService = ref.read(jokeCloudFunctionServiceProvider);
    final joke = await jokeService.updateJokeTextViaCreationProcess(
      jokeId: jokeId,
      setupText: setup,
      punchlineText: punchline,
      regenerateSceneIdeas: _regenerateSceneIdeas,
    );
    _applyJoke(joke);
    if (_regenerateSceneIdeas) {
      setState(() {
        _stage1Expanded = false;
        _stage2Expanded = true;
        _stage3Expanded = false;
      });
      _showSnack('Joke updated and scene ideas regenerated');
    } else {
      _showSnack('Joke updated');
    }
  }

  Future<void> _requestSceneModification({required bool isSetup}) async {
    final jokeId = _resolvedJokeId;
    if (jokeId == null) {
      _showSnack('Create the joke first');
      return;
    }
    final suggestion = isSetup
        ? _setupSceneSuggestionController.text.trim()
        : _punchlineSceneSuggestionController.text.trim();
    if (suggestion.isEmpty) {
      _showSnack('Enter a suggestion first');
      return;
    }

    setState(() {
      if (isSetup) {
        _isSetupSuggestionLoading = true;
      } else {
        _isPunchlineSuggestionLoading = true;
      }
    });

    try {
      final service = ref.read(jokeCloudFunctionServiceProvider);
      final joke = await service.modifyJokeSceneIdeas(
        jokeId: jokeId,
        setupSuggestion: isSetup ? suggestion : null,
        punchlineSuggestion: isSetup ? null : suggestion,
        setupSceneIdea: _setupSceneIdeaController.text.trim(),
        punchlineSceneIdea: _punchlineSceneIdeaController.text.trim(),
      );
      _applyJoke(joke);
      if (isSetup) {
        _setupSceneSuggestionController.clear();
      } else {
        _punchlineSceneSuggestionController.clear();
      }
      _showSnack('Scene idea updated');
    } on SafetyCheckException catch (e, st) {
      _showSnack(
        'Safety check failed. Please keep instructions kid-friendly.',
        exception: e,
        stackTrace: st,
      );
    } catch (e, st) {
      _showSnack('Error updating scene idea', exception: e, stackTrace: st);
    } finally {
      if (mounted) {
        setState(() {
          if (isSetup) {
            _isSetupSuggestionLoading = false;
          } else {
            _isPunchlineSuggestionLoading = false;
          }
        });
      }
    }
  }

  Future<void> _handleGenerateDescriptions() async {
    final jokeId = _resolvedJokeId;
    if (jokeId == null) {
      _showSnack('Create the joke first');
      return;
    }
    if (_setupSceneIdeaController.text.trim().isEmpty ||
        _punchlineSceneIdeaController.text.trim().isEmpty) {
      _showSnack('Provide both scene ideas before generating');
      return;
    }

    setState(() {
      _isGenerateDescriptionsLoading = true;
    });

    try {
      final service = ref.read(jokeCloudFunctionServiceProvider);
      final joke = await service.generateImageDescriptionsViaCreationProcess(
        jokeId: jokeId,
        setupSceneIdea: _setupSceneIdeaController.text.trim(),
        punchlineSceneIdea: _punchlineSceneIdeaController.text.trim(),
      );
      _applyJoke(joke);
      setState(() {
        _stage2Expanded = false;
        _stage3Expanded = true;
      });
      _showSnack('Image descriptions generated');
    } on SafetyCheckException catch (e, st) {
      _showSnack(
        'Safety check failed. Please adjust the scene ideas.',
        exception: e,
        stackTrace: st,
      );
    } catch (e, st) {
      _showSnack('Error generating descriptions', exception: e, stackTrace: st);
    } finally {
      if (mounted) {
        setState(() {
          _isGenerateDescriptionsLoading = false;
        });
      }
    }
  }

  Future<void> _generateImagesWithCreationProcess() async {
    final jokeId = _resolvedJokeId;
    if (jokeId == null) {
      _showSnack('Create the joke first');
      return;
    }
    setState(() {
      _isGenerateImagesLoading = true;
    });
    try {
      final service = ref.read(jokeCloudFunctionServiceProvider);
      final joke = await service.generateImagesViaCreationProcess(
        jokeId: jokeId,
        imageQuality: _imageQuality,
        setupSceneIdea: _setupSceneIdeaController.text.trim(),
        punchlineSceneIdea: _punchlineSceneIdeaController.text.trim(),
        setupImageDescription: _setupImageDescriptionController.text.trim(),
        punchlineImageDescription: _punchlineImageDescriptionController.text
            .trim(),
      );
      _applyJoke(joke);
      _showSnack('Images generated successfully');
    } on SafetyCheckException catch (e, st) {
      _showSnack(
        'Safety check failed. Please adjust the scene ideas.',
        exception: e,
        stackTrace: st,
      );
      // } catch (e, st) {
      // _showSnack('Error generating images', exception: e, stackTrace: st);
    } finally {
      if (mounted) {
        setState(() {
          _isGenerateImagesLoading = false;
        });
      }
    }
  }

  Future<void> _saveImageSelection() async {
    final jokeId = _resolvedJokeId;
    if (jokeId == null) {
      _showSnack('Create the joke first');
      return;
    }
    final repo = ref.read(jokeRepositoryProvider);
    await repo.updateJoke(
      jokeId: jokeId,
      setupText: _setupController.text.trim(),
      punchlineText: _punchlineController.text.trim(),
      setupImageUrl: _selectedSetupImageUrl,
      punchlineImageUrl: _selectedPunchlineImageUrl,
      setupImageDescription: _setupImageDescriptionController.text.trim(),
      punchlineImageDescription: _punchlineImageDescriptionController.text
          .trim(),
    );
    _showSnack('Selection saved');
  }

  void _applyJoke(Joke joke) {
    _latestJoke = joke;
    _currentJokeId ??= joke.id;
    _setupSceneIdeaController.text = joke.setupSceneIdea ?? '';
    _punchlineSceneIdeaController.text = joke.punchlineSceneIdea ?? '';
    _setupImageDescriptionController.text =
        joke.setupImageDescription ?? _setupImageDescriptionController.text;
    _punchlineImageDescriptionController.text =
        joke.punchlineImageDescription ??
        _punchlineImageDescriptionController.text;
    _selectedSetupImageUrl ??= joke.setupImageUrl;
    _selectedPunchlineImageUrl ??= joke.punchlineImageUrl;
  }

  void _handleJokeLoaded(Joke? joke) {
    if (joke == null) return;
    _latestJoke = joke;
    _currentJokeId ??= joke.id;

    if (_setupController.text.isEmpty) {
      _setupController.text = joke.setupText;
    }
    if (_punchlineController.text.isEmpty) {
      _punchlineController.text = joke.punchlineText;
    }
    if (_setupSceneIdeaController.text.isEmpty &&
        (joke.setupSceneIdea?.isNotEmpty ?? false)) {
      _setupSceneIdeaController.text = joke.setupSceneIdea!;
    }
    if (_punchlineSceneIdeaController.text.isEmpty &&
        (joke.punchlineSceneIdea?.isNotEmpty ?? false)) {
      _punchlineSceneIdeaController.text = joke.punchlineSceneIdea!;
    }
    if (_setupImageDescriptionController.text.isEmpty &&
        (joke.setupImageDescription?.isNotEmpty ?? false)) {
      _setupImageDescriptionController.text = joke.setupImageDescription!;
    }
    if (_punchlineImageDescriptionController.text.isEmpty &&
        (joke.punchlineImageDescription?.isNotEmpty ?? false)) {
      _punchlineImageDescriptionController.text =
          joke.punchlineImageDescription!;
    }
    _selectedSetupImageUrl ??= joke.setupImageUrl;
    _selectedPunchlineImageUrl ??= joke.punchlineImageUrl;

    if (_hasSceneIdeas && !_autoOpenedStage2) {
      _autoOpenedStage2 = true;
      _stage1Expanded = false;
      _stage2Expanded = true;
    }
    if (_hasImageDescriptions && !_autoOpenedStage3) {
      _autoOpenedStage3 = true;
      _stage2Expanded = false;
      _stage3Expanded = true;
    }
  }

  void _showSnack(String message, {Object? exception, StackTrace? stackTrace}) {
    final isError = exception != null;
    if (exception != null) {
      AppLogger.error(
        message,
        stackTrace: stackTrace,
        keys: {'exception': exception.toString()},
      );
    }
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError
            ? Theme.of(context).appColors.authError
            : Theme.of(context).appColors.success,
        duration: const Duration(seconds: 4),
      ),
    );
  }
}
