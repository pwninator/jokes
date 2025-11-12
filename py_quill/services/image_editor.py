"""Image editing service using PIL."""

from __future__ import annotations

from typing import Tuple

from PIL import Image


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

  def paste_image(
    self,
    base_image: Image.Image,
    image_to_paste: Image.Image,
    x: int,
    y: int,
  ) -> Image.Image:
    """Paste image_to_paste onto base_image at (x, y) coordinates."""
    base_image.paste(image_to_paste, (x, y))
    return base_image
