// No-op
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
// No-op
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/holdable_button.dart';
import 'package:snickerdoodle/src/common_widgets/image_selector_carousel.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';

final jokeCategoryEditorProvider = StateNotifierProvider.autoDispose
    .family<JokeCategoryEditorNotifier, JokeCategory, JokeCategory>((
      ref,
      category,
    ) {
      return JokeCategoryEditorNotifier(category);
    });

class JokeCategoryEditorNotifier extends StateNotifier<JokeCategory> {
  JokeCategoryEditorNotifier(super.state);

  void updateImageDescription(String description) {
    state = JokeCategory(
      id: state.id,
      displayName: state.displayName,
      jokeDescriptionQuery: state.jokeDescriptionQuery,
      imageUrl: state.imageUrl,
      imageDescription: description,
      state: state.state,
    );
  }

  void updateState(JokeCategoryState newState) {
    state = JokeCategory(
      id: state.id,
      displayName: state.displayName,
      jokeDescriptionQuery: state.jokeDescriptionQuery,
      imageUrl: state.imageUrl,
      imageDescription: state.imageDescription,
      state: newState,
    );
  }

  void selectImage(String imageUrl) {
    state = JokeCategory(
      id: state.id,
      displayName: state.displayName,
      jokeDescriptionQuery: state.jokeDescriptionQuery,
      imageUrl: imageUrl,
      imageDescription: state.imageDescription,
      state: state.state,
    );
  }
}

class JokeCategoryEditorScreen extends ConsumerWidget {
  const JokeCategoryEditorScreen({super.key, required this.categoryId});

  final String categoryId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final categoryAsync = ref.watch(jokeCategoryByIdProvider(categoryId));
    return categoryAsync.when(
      data: (category) {
        if (category == null) {
          return AdaptiveAppBarScreen(
            title: 'Edit Category',
            body: const Center(child: Text('Category not found')),
          );
        }
        return PopScope(
          canPop: true,
          child: AdaptiveAppBarScreen(
            title: 'Edit Category',
            body: JokeCategoryEditorView(category: category),
          ),
        );
      },
      loading: () => AdaptiveAppBarScreen(
        title: 'Edit Category',
        body: const Center(child: CircularProgressIndicator()),
      ),
      error: (e, st) => AdaptiveAppBarScreen(
        title: 'Edit Category',
        body: Center(child: Text('Error: $e')),
      ),
    );
  }
}

class JokeCategoryEditorView extends ConsumerWidget {
  const JokeCategoryEditorView({super.key, required this.category});

  final JokeCategory category;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final editorState = ref.watch(jokeCategoryEditorProvider(category));
    final editorNotifier = ref.read(
      jokeCategoryEditorProvider(category).notifier,
    );
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 1) Display name (title style)
          Text(
            category.displayName,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          
          // 2) Joke description query (subtitle style)
          Text(
            editorState.jokeDescriptionQuery,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 16),

          // 3) State selector
          DropdownButtonFormField<JokeCategoryState>(
            initialValue: editorState.state,
            items: JokeCategoryState.values
                .map(
                  (state) =>
                      DropdownMenuItem(value: state, child: Text(state.name)),
                )
                .toList(),
            onChanged: (value) {
              if (value != null) {
                editorNotifier.updateState(value);
              }
            },
            decoration: const InputDecoration(
              labelText: 'State',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),

          // 4) Image description (editable)
          TextFormField(
            initialValue: editorState.imageDescription ?? '',
            onChanged: editorNotifier.updateImageDescription,
            minLines: 5,
            maxLines: 5,
            decoration: const InputDecoration(
              labelText: 'Image Description',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),

          // 4) Image selector
          Consumer(
            builder: (context, ref, child) {
              final imagesAsync = ref.watch(
                jokeCategoryImagesProvider(category.id),
              );
              return imagesAsync.when(
                data: (imageUrls) {
                  final hasSelected =
                      (editorState.imageUrl != null &&
                      editorState.imageUrl!.trim().isNotEmpty);
                  final urls = imageUrls.isEmpty && hasSelected
                      ? [editorState.imageUrl!]
                      : imageUrls;
                  return ImageSelectorCarousel(
                    imageUrls: urls,
                    selectedImageUrl: editorState.imageUrl,
                    title: 'Category Images',
                    onImageSelected: (url) {
                      if (url != null) {
                        editorNotifier.selectImage(url);
                      }
                    },
                  );
                },
                loading: () => const CircularProgressIndicator(),
                error: (e, st) => Text('Error: $e'),
              );
            },
          ),

          const Spacer(),
          Row(
            children: [
              HoldableButton(
                key: const Key('delete_category_button'),
                onHoldComplete: () async {
                  final navigator = Navigator.of(context);
                  await ref
                      .read(jokeCategoryRepositoryProvider)
                      .deleteCategory(category.id);
                  if (navigator.canPop()) {
                    navigator.pop();
                  }
                },
                onTap: () {},
                icon: Icons.delete,
                theme: Theme.of(context),
                color: Colors.red,
              ),
              const SizedBox(width: 16),
              Expanded(
                child: ElevatedButton(
                  onPressed: () async {
                    final navigator = Navigator.of(context);
                    await ref
                        .read(jokeCategoryRepositoryProvider)
                        .upsertCategory(editorState);
                    if (navigator.canPop()) {
                      navigator.pop();
                    }
                  },
                  child: const Text('Update Category'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
