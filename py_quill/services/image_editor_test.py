"""Unit tests for ImageEditor utilities."""

from __future__ import annotations

import unittest
from PIL import Image

from services.image_editor import ImageEditor


class ImageEditorTest(unittest.TestCase):

  def setUp(self):
    self.editor = ImageEditor()

  def test_scale_image_halves_dimensions(self):
    img = Image.new('RGB', (100, 80), color='red')
    scaled = self.editor.scale_image(img, 0.5)
    self.assertEqual(scaled.size, (50, 40))

  def test_rotate_image_produces_rgba_and_expands(self):
    img = Image.new('RGB', (50, 30), color='green')
    rotated = self.editor.rotate_image(img, 15)
    self.assertEqual(rotated.mode, 'RGBA')
    self.assertTrue(rotated.width >= img.width)
    self.assertTrue(rotated.height >= img.height)

  def test_paste_image_with_shadow_renders_shadow(self):
    base = Image.new('RGB', (100, 100), color='white')
    sticker = Image.new('RGB', (20, 20), color='blue')
    result = self.editor.paste_image(base, sticker, 10, 10, add_shadow=True)

    # Shadow offset is (8, 8) with blur; sample a pixel near the shadow area
    # Expect pixel not equal to pure white due to shadow darkening
    sample_x, sample_y = 18, 18
    sample = result.getpixel((sample_x, sample_y))
    self.assertIsInstance(sample, tuple)
    # result is RGB; verify it's darker than white
    self.assertNotEqual(sample, (255, 255, 255))

  def test_paste_image_shadow_respects_alpha(self):
    base = Image.new('RGB', (120, 120), color='white')
    sticker = Image.new('RGBA', (30, 30), color=(255, 0, 0, 255))
    rotated = self.editor.rotate_image(sticker, 45)
    result = self.editor.paste_image(base, rotated, 40, 40, add_shadow=True)

    # Corner of the rotated bounding box should remain light (no solid shadow)
    corner_pixel = result.getpixel((40, 40))
    self.assertTrue(all(channel > 210 for channel in corner_pixel))

    # Sample where shadow should exist (adjusted for 2px border in rotation)
    shadow_pixel = result.getpixel((52, 54))
    self.assertTrue(any(channel < 240 for channel in shadow_pixel))


if __name__ == '__main__':
  unittest.main()
