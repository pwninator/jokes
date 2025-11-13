"""Image editing service using PIL."""

from __future__ import annotations

from typing import Tuple

from PIL import Image, ImageEnhance, ImageFilter


class ImageEditor:
  """Service for creating and composing images using PIL."""

  def create_blank_image(
      self,
      width: int,
      height: int,
      color: Tuple[int, int, int] = (255, 255, 255),
  ) -> Image.Image:
    """Create a new blank RGB image of specified size."""
    return Image.new('RGB', (width, height), color)

  def scale_image(self, image: Image.Image,
                  scale_factor: float) -> Image.Image:
    """Return a new image scaled by scale_factor using high-quality resampling."""
    new_width = max(1, int(round(image.width * scale_factor)))
    new_height = max(1, int(round(image.height * scale_factor)))
    return image.resize(
      size=(new_width, new_height),
      resample=Image.Resampling.LANCZOS,
    )

  def rotate_image(self, image: Image.Image, degrees: float) -> Image.Image:
    """Return a new image rotated by degrees. Uses RGBA to preserve transparency."""
    if image.mode != 'RGBA':
      image = image.convert('RGBA')

    # Add 2px transparent border to prevent edge artifacts during rotation
    border = 2
    bordered = Image.new(
      'RGBA',
      (image.width + border * 2, image.height + border * 2),
      (0, 0, 0, 0),
    )
    bordered.paste(image, (border, border))

    return bordered.rotate(
      angle=degrees,
      resample=Image.Resampling.BICUBIC,
      expand=True,
      fillcolor=(0, 0, 0, 0),
    )

  def paste_image(
    self,
    base_image: Image.Image,
    image_to_paste: Image.Image,
    x: int,
    y: int,
    add_shadow: bool = False,
  ) -> Image.Image:
    """Paste image_to_paste onto base_image at (x, y) coordinates.

    If add_shadow is True, a subtle drop shadow is rendered beneath the image.
    """
    # Ensure base supports alpha composite if needed
    if base_image.mode != 'RGBA':
      base_rgba = base_image.convert('RGBA')
    else:
      base_rgba = base_image

    paste_img = image_to_paste
    if paste_img.mode != 'RGBA':
      paste_img = paste_img.convert('RGBA')

    if add_shadow:
      # Use alpha mask to shape the shadow so rotation/transparency are respected.
      alpha = paste_img.split()[-1]
      blur_radius = 12
      shadow_offset_x, shadow_offset_y = 8, 8
      pad = blur_radius + max(shadow_offset_x, shadow_offset_y)
      padded_mask = Image.new('L',
                              (alpha.width + pad * 2, alpha.height + pad * 2),
                              0)
      padded_mask.paste(alpha, (pad, pad))
      shadow_mask = padded_mask.filter(ImageFilter.GaussianBlur(blur_radius))
      shadow_mask = ImageEnhance.Brightness(shadow_mask).enhance(0.6)

      dest_x = x + shadow_offset_x - pad
      dest_y = y + shadow_offset_y - pad

      # Clip mask if it would overflow the canvas bounds.
      mask_left = 0
      mask_top = 0
      mask_right, mask_bottom = shadow_mask.size

      if dest_x < 0:
        mask_left = min(-dest_x, mask_right)
        dest_x = 0
      if dest_y < 0:
        mask_top = min(-dest_y, mask_bottom)
        dest_y = 0
      if dest_x + (mask_right - mask_left) > base_rgba.width:
        mask_right = mask_left + max(0, base_rgba.width - dest_x)
      if dest_y + (mask_bottom - mask_top) > base_rgba.height:
        mask_bottom = mask_top + max(0, base_rgba.height - dest_y)

      cropped_mask = shadow_mask.crop(
        (mask_left, mask_top, mask_right, mask_bottom))

      if cropped_mask.size[0] > 0 and cropped_mask.size[1] > 0:
        base_rgba.paste(
          (0, 0, 0, 255),
          (dest_x, dest_y),
          cropped_mask,
        )

    # Paste the actual image on top using its alpha as mask
    base_rgba.paste(paste_img, (x, y), paste_img)

    return base_rgba
