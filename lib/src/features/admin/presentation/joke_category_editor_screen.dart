import 'dart:io';

import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:snickerdoodle/src/common_widgets/adaptive_app_bar_screen.dart';
import 'package:snickerdoodle/src/common_widgets/holdable_button.dart';
import 'package:snickerdoodle/src/features/admin/presentation/joke_category_edit_image_carousel.dart';
import 'package:snickerdoodle/src/features/jokes/application/joke_category_providers.dart';
import 'package:snickerdoodle/src/features/jokes/data/models/joke_category.dart';
import 'package:snickerdoodle/src/features/jokes/data/repositories/joke_category_repository.dart';

final jokeCategoryEditorProvider = StateNotifierProvider.autoDispose
    .family<JokeCategoryEditorNotifier, JokeCategory, JokeCategory>(
        (ref, category) {
  return JokeCategoryEditorNotifier(category);
});

class JokeCategoryEditorNotifier extends StateNotifier<JokeCategory> {
  JokeCategoryEditorNotifier(JokeCategory category) : super(category);

  void updateImageDescription(String description) {
    state = JokeCategory(
        id: state.id,
        displayName: state.displayName,
        jokeDescriptionQuery: description,
        imageUrl: state.imageUrl,
        state: state.state);
  }

  void updateState(JokeCategoryState newState) {
    state = JokeCategory(
        id: state.id,
        displayName: state.displayName,
        jokeDescriptionQuery: state.jokeDescriptionQuery,
        imageUrl: state.imageUrl,
        state: newState);
  }

  void selectImage(String imageUrl) {
    state = JokeCategory(
        id: state.id,
        displayName: state.displayName,
        jokeDescriptionQuery: state.jokeDescriptionQuery,
        imageUrl: imageUrl,
        state: state.state);
  }
}

class JokeCategoryEditorScreen extends StatelessWidget {
  const JokeCategoryEditorScreen({super.key, required this.category});

  final JokeCategory category;

  @override
  Widget build(BuildContext context) {
    return AdaptiveAppBarScreen(
      title: 'Edit Category',
      body: JokeCategoryEditorView(category: category),
    );
  }
}

class JokeCategoryEditorView extends ConsumerWidget {
  const JokeCategoryEditorView({super.key, required this.category});

  final JokeCategory category;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final editorState = ref.watch(jokeCategoryEditorProvider(category));
    final editorNotifier =
        ref.read(jokeCategoryEditorProvider(category).notifier);
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        children: [
          TextField(
            controller:
                TextEditingController(text: editorState.jokeDescriptionQuery),
            onChanged: editorNotifier.updateImageDescription,
            decoration: const InputDecoration(
              labelText: 'Image Description',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          DropdownButtonFormField<JokeCategoryState>(
            value: editorState.state,
            items: JokeCategoryState.values
                .map((state) => DropdownMenuItem(
                      value: state,
                      child: Text(state.name),
                    ))
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
          Consumer(
            builder: (context, ref, child) {
              final imagesAsync =
                  ref.watch(jokeCategoryImagesProvider(category.id));
              return imagesAsync.when(
                data: (imageUrls) => JokeCategoryEditImageCarousel(
                  imageUrls: imageUrls,
                  selectedImageUrl: editorState.imageUrl,
                  onImageSelected: editorNotifier.selectImage,
                  onImageDeleted: (imageUrl) {
                    ref
                        .read(jokeCategoryRepositoryProvider)
                        .deleteImageFromCategory(category.id, imageUrl);
                  },
                  onImageAdded: () async {
                    final imagePicker = ImagePicker();
                    final pickedFile =
                        await imagePicker.pickImage(source: ImageSource.gallery);
                    if (pickedFile != null) {
                      final storageRef = FirebaseStorage.instance
                          .ref()
                          .child('joke_category_images')
                          .child(category.id)
                          .child(DateTime.now().toIso8601String());
                      await storageRef.putFile(File(pickedFile.path));
                      final imageUrl = await storageRef.getDownloadURL();
                      await ref
                          .read(jokeCategoryRepositoryProvider)
                          .addImageToCategory(category.id, imageUrl);
                    }
                  },
                ),
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
                  await ref
                      .read(jokeCategoryRepositoryProvider)
                      .deleteCategory(category.id);
                  Navigator.of(context).pop();
                },
                onTap: () {},
                icon: Icons.delete,
                theme: Theme.of(context),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: ElevatedButton(
                  onPressed: () async {
                    await ref
                        .read(jokeCategoryRepositoryProvider)
                        .upsertCategory(editorState);
                    Navigator.of(context).pop();
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
