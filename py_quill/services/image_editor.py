"""Image editing service using PIL."""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np
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

  def crop_image(
    self,
    image: Image.Image,
    left: int = 0,
    top: int = 0,
    right: int | None = None,
    bottom: int | None = None,
  ) -> Image.Image:
    """Return a cropped view of the image using the provided box coordinates."""
    if right is None:
      right = image.width
    if bottom is None:
      bottom = image.height
    return image.crop((left, top, right, bottom))

  def enhance_image(
    self,
    image: Image.Image,
    histogram_strength: float = 1.0,
    soft_clip_base: float = 0.0,
    strong_clip_base: float = 3.5,
    edge_threshold: int = 70,
    mask_blur_ksize: int = 35,
    saturation_boost: float = 1.3,
    contrast_alpha: float = 1.1,
    brightness_beta: float = 7.0,
    sharpen_amount: float = 1.0,
  ) -> Image.Image:
    """Enhance image quality using robust white balance, CLAHE, and adjustments.

    Applies the following enhancements:
    1. Robust White Balance (Top 2% percentile - "White Patch")
    2. CLAHE (Contrast Limited Adaptive Histogram Equalization)
    3. Small saturation enhancement
    4. Small contrast enhancement
    5. Small brightness enhancement
    6. Sharpening
    """
    # Convert PIL to OpenCV (RGB -> BGR)
    img_np = np.array(image)

    # Handle RGBA if present
    has_alpha = False
    alpha_channel = None

    if image.mode == 'RGBA':
      has_alpha = True
      # img_np is RGBA, keep alpha for later
      alpha_channel = img_np[:, :, 3]
      img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
    elif image.mode == 'RGB':
      img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    else:
      # Fallback for other modes
      img_rgb = np.array(image.convert('RGB'))
      img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

    # Apply enhancement pipeline
    result = img_bgr
    # Do not apply white balance because the images are intentionally drawn
    # on textured, tinted paper backgrounds.
    # result = self._robust_white_balance(result)
    result = self._apply_smart_clahe_hybrid(
      result,
      strength=histogram_strength,
      soft_clip_base=soft_clip_base,
      strong_clip_base=strong_clip_base,
      edge_threshold=edge_threshold,
      mask_blur_ksize=mask_blur_ksize,
    )
    result = self._enhance_saturation(result, saturation_boost)
    result = self._enhance_contrast_brightness(
      result,
      contrast_alpha,
      brightness_beta,
    )
    result = self._sharpen_image(result, sharpen_amount)

    # Convert back to PIL (BGR -> RGB)
    img_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)

    if has_alpha and alpha_channel is not None:
      # Re-attach alpha channel
      img_rgba = np.dstack((img_rgb, alpha_channel))
      return Image.fromarray(img_rgba)

    return Image.fromarray(img_rgb)

  def _robust_white_balance(self, img_bgr: np.ndarray) -> np.ndarray:
    """Apply robust white balance using top 2% percentile method.

    Args:
      img_bgr: Input image in BGR format as numpy array.

    Returns:
      White-balanced image in BGR format as numpy array.
    """
    # Identify the brightest pixels (reference white)
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l_channel = lab[:, :, 0]

    # Calculate threshold for top 2% luminance
    threshold = np.percentile(l_channel, 98)
    mask = l_channel >= threshold

    # If we found valid highlight pixels
    if np.any(mask):
      # Calculate average color of the highlights
      avg_b = np.mean(img_bgr[:, :, 0][mask])
      avg_g = np.mean(img_bgr[:, :, 1][mask])
      avg_r = np.mean(img_bgr[:, :, 2][mask])

      # Prevent division by zero
      avg_b = max(avg_b, 1e-5)
      avg_g = max(avg_g, 1e-5)
      avg_r = max(avg_r, 1e-5)

      # Calculate global gray value of highlights
      avg_gray = (avg_b + avg_g + avg_r) / 3

      # Calculate scaling factors
      scale_b = avg_gray / avg_b
      scale_g = avg_gray / avg_g
      scale_r = avg_gray / avg_r

      # Apply scaling
      result = img_bgr.astype(np.float32)
      result[:, :, 0] *= scale_b
      result[:, :, 1] *= scale_g
      result[:, :, 2] *= scale_r
      return np.clip(result, 0, 255).astype(np.uint8)

    return img_bgr

  def _apply_smart_clahe_hybrid(
    self,
    img_bgr: np.ndarray,
    strength: float,
    soft_clip_base: float,
    strong_clip_base: float,
    edge_threshold: int,
    mask_blur_ksize: int,
  ) -> np.ndarray:
    """Apply Hybrid CLAHE: strong contrast for details, soft for flat areas.

    Args:
      img_bgr: Input image in BGR format as numpy array.
      strength: Multiplier applied to base clip limits.
      soft_clip_base: Base CLAHE clip limit for soft regions.
      strong_clip_base: Base CLAHE clip limit for detailed regions.
      edge_threshold: Sobel magnitude threshold for the detail mask.
      mask_blur_ksize: Gaussian blur kernel size used to soften the mask.

    Returns:
      Contrast-enhanced image in BGR format as numpy array.
    """
    # 1. Convert to LAB color space
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    # Scale clip limits
    soft_clip = soft_clip_base * strength
    strong_clip = max(0.1, strong_clip_base * strength)

    # 2. Generate soft and strong CLAHE versions
    if soft_clip <= 0.0001:
      # If soft clip is effectively zero, skip CLAHE and keep original luminance
      l_soft = l
    else:
      clahe_soft = cv2.createCLAHE(clipLimit=soft_clip, tileGridSize=(8, 8))
      l_soft = clahe_soft.apply(l)

    clahe_strong = cv2.createCLAHE(clipLimit=strong_clip, tileGridSize=(8, 8))
    l_strong = clahe_strong.apply(l)

    # 3. Detail mask creation
    l_blur = cv2.GaussianBlur(l, (5, 5), 0)

    grad_x = cv2.Sobel(l_blur, cv2.CV_16S, 1, 0, ksize=3)
    grad_y = cv2.Sobel(l_blur, cv2.CV_16S, 0, 1, ksize=3)
    abs_grad_x = cv2.convertScaleAbs(grad_x)
    abs_grad_y = cv2.convertScaleAbs(grad_y)
    edges = cv2.addWeighted(abs_grad_x, 0.5, abs_grad_y, 0.5, 0)

    _, mask = cv2.threshold(edges, edge_threshold, 255, cv2.THRESH_BINARY)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.dilate(mask, kernel, iterations=2)

    mask_blur_size = max(1, mask_blur_ksize | 1)
    mask = cv2.GaussianBlur(mask, (mask_blur_size, mask_blur_size), 0)

    mask_float = mask.astype(np.float32) / 255.0
    l_final = (l_strong.astype(np.float32) *
               mask_float) + (l_soft.astype(np.float32) * (1.0 - mask_float))

    l_final = np.clip(l_final, 0, 255).astype(np.uint8)

    limg = cv2.merge((l_final, a, b))
    return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

  def _enhance_saturation(
    self,
    img_bgr: np.ndarray,
    saturation_boost: float,
  ) -> np.ndarray:
    """Enhance image saturation.

    Args:
      img_bgr: Input image in BGR format as numpy array.
      saturation_boost: Multiplier for the saturation channel.

    Returns:
      Saturation-enhanced image in BGR format as numpy array.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    s = s.astype(np.float32) * saturation_boost
    s = np.clip(s, 0, 255).astype(np.uint8)
    hsv = cv2.merge([h, s, v])
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

  def _enhance_contrast_brightness(
    self,
    img_bgr: np.ndarray,
    contrast_alpha: float,
    brightness_beta: float,
  ) -> np.ndarray:
    """Enhance contrast and brightness.

    Args:
      img_bgr: Input image in BGR format as numpy array.
      contrast_alpha: Contrast scaling factor (>1 to increase contrast).
      brightness_beta: Brightness offset (>0 to brighten).

    Returns:
      Contrast and brightness-enhanced image in BGR format as numpy array.
    """
    return cv2.convertScaleAbs(img_bgr,
                               alpha=contrast_alpha,
                               beta=brightness_beta)

  def _sharpen_image(
    self,
    img_bgr: np.ndarray,
    sharpen_amount: float,
  ) -> np.ndarray:
    """Apply unsharp masking to sharpen the image.

    Args:
      img_bgr: Input image in BGR format as numpy array.
      sharpen_amount: Strength of sharpening. 0 disables sharpening.

    Returns:
      Sharpened image in BGR format as numpy array.
    """
    amount = max(0.0, sharpen_amount)
    if amount == 0.0:
      return img_bgr

    gaussian = cv2.GaussianBlur(img_bgr, (0, 0), 3.0)
    # Original implementation used 1.5 and -0.5 (equivalent to amount=0.5)
    return cv2.addWeighted(img_bgr, 1.0 + amount, gaussian, -amount, 0)
