"""Social post generation operations."""

from __future__ import annotations

from common import models
from functions.prompts import social_post_prompts


def generate_pinterest_post_text(
  image_bytes: bytes,
  *,
  post_type: models.JokeSocialPostType,
) -> tuple[str, str, str]:
  """Generate Pinterest text fields based on the composed image."""
  title, description, alt_text, _metadata = (
    social_post_prompts.generate_pinterest_post_text(
      image_bytes,
      post_type=post_type,
    ))
  return title, description, alt_text
