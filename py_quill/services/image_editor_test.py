"""Unit tests for ImageEditor utilities."""

from __future__ import annotations

import unittest
from PIL import Image, ImageColor

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

  def test_trim_edges_crops_expected_region(self):
    img = Image.new('RGB', (10, 10), color='white')
    img.putpixel((2, 2), (0, 0, 255))

    trimmed = self.editor.trim_edges(img, left=2, top=2, right=3, bottom=4)

    self.assertEqual(trimmed.size, (5, 4))
    self.assertEqual(trimmed.getpixel((0, 0)), (0, 0, 255))

  def test_trim_edges_with_zero_trims_returns_identical_image(self):
    img = Image.new('RGB', (12, 8), color='purple')

    trimmed = self.editor.trim_edges(img)

    self.assertEqual(trimmed.size, (12, 8))
    expected_color = ImageColor.getrgb('purple')
    self.assertEqual(trimmed.getpixel((5, 4)), expected_color)

  def test_trim_edges_invalid_inputs_raise_value_error(self):
    img = Image.new('RGB', (15, 15), color='orange')

    with self.assertRaises(ValueError):
      self.editor.trim_edges(img, left=-1)
    with self.assertRaises(ValueError):
      self.editor.trim_edges(img, left=10, right=5)
    with self.assertRaises(ValueError):
      self.editor.trim_edges(img, top=7, bottom=8)

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

  def test_enhance_image_returns_valid_image(self):
    img = Image.new('RGB', (100, 100), color='blue')
    enhanced = self.editor.enhance_image(img)
    self.assertEqual(enhanced.size, (100, 100))
    self.assertEqual(enhanced.mode, 'RGB')

  def test_enhance_image_preserves_alpha(self):
    img = Image.new('RGBA', (100, 100), color=(0, 255, 0, 128))
    enhanced = self.editor.enhance_image(img)
    self.assertEqual(enhanced.size, (100, 100))
    self.assertEqual(enhanced.mode, 'RGBA')
    # Check alpha is preserved (roughly) - it's copied back directly so should be exact
    self.assertEqual(enhanced.getpixel((50, 50))[3], 128)

  def test_enhance_image_with_zero_soft_clip_base(self):
    img = Image.new('RGB', (80, 60), color='blue')
    # soft_clip_base=0 should skip the soft CLAHE branch gracefully
    enhanced = self.editor.enhance_image(
      img,
      histogram_strength=1.0,
      soft_clip_base=0.0,
    )
    self.assertEqual(enhanced.size, (80, 60))
    self.assertEqual(enhanced.mode, 'RGB')

  def test_enhance_image_with_custom_tone_and_sharpen_params(self):
    img = Image.new('RGB', (64, 64), color='red')
    enhanced = self.editor.enhance_image(
      img,
      saturation_boost=0.8,
      contrast_alpha=1.1,
      brightness_beta=0,
      sharpen_amount=0.0,
    )
    self.assertEqual(enhanced.size, (64, 64))
    self.assertEqual(enhanced.mode, 'RGB')


if __name__ == '__main__':
  unittest.main()
