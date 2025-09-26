import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:path/path.dart' as p;
import 'package:share_plus/share_plus.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';

void main() {
  group('ImageService stackImages', () {
    late ImageService imageService;

    setUpAll(() {
      TestWidgetsFlutterBinding.ensureInitialized();
    });

    setUp(() {
      imageService = ImageService();
    });

    Future<XFile> createTestImage(int width, int height, String name) async {
      final image = img.Image(width: width, height: height);
      final png = img.encodePng(image);
      final tempDir = await Directory.systemTemp.createTemp();
      final file = File(p.join(tempDir.path, '$name.png'));
      await file.writeAsBytes(png);
      return XFile(file.path);
    }

    test('should stack two images vertically', () async {
      final image1 = await createTestImage(100, 150, 'image1');
      final image2 = await createTestImage(100, 200, 'image2');

      final stackedImageFile = await imageService.stackImages([image1, image2]);
      final stackedImageBytes = await stackedImageFile.readAsBytes();
      final decodedImage = img.decodeImage(stackedImageBytes);

      expect(decodedImage, isNotNull);
      expect(decodedImage!.width, 100);
      expect(decodedImage.height, 350);
    });

    test('should throw an error if not exactly two images are provided',
        () async {
      final image1 = await createTestImage(100, 150, 'image1');
      expect(() => imageService.stackImages([image1]), throwsArgumentError);
      final image2 = await createTestImage(100, 200, 'image2');
      final image3 = await createTestImage(100, 100, 'image3');
      expect(
          () => imageService.stackImages([image1, image2, image3]), throwsArgumentError);
    });
  });
}