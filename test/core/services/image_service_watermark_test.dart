import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:share_plus/share_plus.dart';
import 'package:snickerdoodle/src/core/services/image_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('ImageService watermark', () {
    late ImageService service;

    setUp(() async {
      service = ImageService();
      // Ensure the asset is available to the test binding
      // Flutter test loads assets from pubspec; no extra setup needed if listed.
    });

    test('adds watermark and preserves dimensions', () async {
      // Create a simple base image in memory (solid color)
      final base = img.Image(width: 400, height: 300);
      final baseColor = img.ColorUint8.rgb(200, 200, 200);
      img.fill(base, color: baseColor);
      final basePng = img.encodePng(base);

      final tempFile = await File(
        '${Directory.systemTemp.path}/base_${DateTime.now().millisecondsSinceEpoch}.png',
      ).create(recursive: true);
      await tempFile.writeAsBytes(basePng, flush: true);

      final original = XFile(tempFile.path);
      final watermarked = await service.addWatermarkToFile(original);

      // Read watermarked bytes directly from XFile (may be in-memory)
      final outBytes = await watermarked.readAsBytes();
      final outImage = img.decodeImage(outBytes);

      expect(outImage, isNotNull);
      expect(outImage!.width, equals(base.width));
      expect(outImage.height, equals(base.height));

      // Quick pixel check near bottom center should differ from plain base
      // Sample near bottom-left where watermark is drawn
      final sampleX = 20; // near left padding (16)
      final sampleY = outImage.height - 20; // above bottom padding
      final pixel = outImage.getPixel(sampleX, sampleY);
      // At least one channel should differ due to watermark blending
      expect(
        pixel.r != baseColor.r ||
            pixel.g != baseColor.g ||
            pixel.b != baseColor.b,
        isTrue,
      );
    });
  });
}
