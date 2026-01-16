"""Social post generation operations."""

from __future__ import annotations

from common import models
from functions.prompts import social_post_prompts


def generate_social_post_text(
  jokes: list[models.PunnyJoke],
  post_type: models.JokeSocialPostType,
) -> tuple[str, str]:
  """Generate title and description for a social post."""
  title, description, _metadata = social_post_prompts.generate_social_post_text(
    jokes,
    post_type,
  )
  return title, description
