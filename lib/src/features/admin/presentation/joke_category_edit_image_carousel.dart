import 'package:flutter/material.dart';
import 'package:snickerdoodle/src/common_widgets/cached_joke_image.dart';

class JokeCategoryEditImageCarousel extends StatefulWidget {
  final List<String> imageUrls;
  final String? selectedImageUrl;
  final Function(String) onImageSelected;
  final Function(String) onImageDeleted;
  final VoidCallback onImageAdded;

  const JokeCategoryEditImageCarousel({
    super.key,
    required this.imageUrls,
    this.selectedImageUrl,
    required this.onImageSelected,
    required this.onImageDeleted,
    required this.onImageAdded,
  });

  @override
  State<JokeCategoryEditImageCarousel> createState() =>
      _JokeCategoryEditImageCarouselState();
}

class _JokeCategoryEditImageCarouselState
    extends State<JokeCategoryEditImageCarousel> {
  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 150,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: widget.imageUrls.length + 1,
        itemBuilder: (context, index) {
          if (index == widget.imageUrls.length) {
            return _buildAddImageButton();
          }
          final imageUrl = widget.imageUrls[index];
          final isSelected = imageUrl == widget.selectedImageUrl;
          return _buildImageTile(imageUrl, isSelected);
        },
      ),
    );
  }

  Widget _buildImageTile(String imageUrl, bool isSelected) {
    return GestureDetector(
      onTap: () => widget.onImageSelected(imageUrl),
      child: Card(
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(
            color: isSelected ? Colors.blue : Colors.transparent,
            width: 3,
          ),
        ),
        child: Stack(
          children: [
            CachedJokeImage(
              imageUrlOrAssetPath: imageUrl,
              width: 150,
              height: 150,
              fit: BoxFit.cover,
            ),
            Positioned(
              top: 4,
              right: 4,
              child: IconButton(
                icon: const Icon(Icons.delete, color: Colors.white),
                onPressed: () => widget.onImageDeleted(imageUrl),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAddImageButton() {
    return GestureDetector(
      onTap: widget.onImageAdded,
      child: Card(
        child: SizedBox(
          width: 150,
          height: 150,
          child: const Center(child: Icon(Icons.add_a_photo, size: 50)),
        ),
      ),
    );
  }
}
