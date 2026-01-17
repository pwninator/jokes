"""Prompt helpers for social post generation."""

from __future__ import annotations

import json
from dataclasses import dataclass

from common import models
from firebase_functions import logger
from services import llm_client
from services.llm_client import LlmModel


@dataclass(frozen=True)
class SocialPostStrategy:
  """Strategy for generating social post text."""

  goal: str
  cta: str
  audience: str


@dataclass(frozen=True)
class PlatformConfig:
  """Configuration for social platform post generation."""

  strategies: dict[models.JokeSocialPostType, SocialPostStrategy]
  client: llm_client.LlmClient


_PLATFORM_CONFIGS: dict[models.SocialPlatform, PlatformConfig] = {
  models.SocialPlatform.PINTEREST:
  PlatformConfig(
    strategies={
      models.JokeSocialPostType.JOKE_GRID_TEASER:
      SocialPostStrategy(
        goal=("CURIOSITY. The punchline is hidden. Description must intrigue "
              "users to click. Do NOT reveal the answer."),
        cta="Get the answer",
        audience="Families looking for quick entertainment, bored kids.",
      ),
      models.JokeSocialPostType.JOKE_GRID:
      SocialPostStrategy(
        goal="SAVES. High-value resource. Optimize for users saving to boards.",
        cta="Save this for later",
        audience="Parents, teachers, and grandparents.",
      ),
    },
    client=llm_client.get_client(
      label="Pinterest Social Post Text",
      model=LlmModel.GEMINI_3_0_FLASH_PREVIEW,
      temperature=1.0,
      output_tokens=8000,
      system_instructions=[
        """You are a social media marketing expert for a wholesome kids jokes brand called Snickerdoodle Jokes.

Your job: analyze the attached image and generate Pinterest-ready text for the pin.
Do not invent details that are not visible in the image.
Never include hashtags. Keep the tone friendly, playful, and family-safe.

Return ONLY valid JSON (no markdown, no commentary) with:
- pinterest_title: Max 100 characters. Front-load keywords.
- pinterest_description: Max 500 characters. Natural sentences. No hashtags.
- pinterest_alt_text: Max 500 characters. Describe the visual content for accessibility/SEO.
"""
      ],
      response_schema={
        "type":
        "OBJECT",
        "properties": {
          "pinterest_title": {
            "type": "STRING",
            "description": "Pinterest title, max 100 characters."
          },
          "pinterest_description": {
            "type": "STRING",
            "description": "Pinterest description, max 500 characters."
          },
          "pinterest_alt_text": {
            "type":
            "STRING",
            "description":
            "Accessibility alt text describing the image, max 500 characters."
          },
        },
        "required": [
          "pinterest_title",
          "pinterest_description",
          "pinterest_alt_text",
        ],
      },
    ),
  ),
}


def _get_platform_config(platform: models.SocialPlatform) -> PlatformConfig:
  config = _PLATFORM_CONFIGS.get(platform)
  if not config:
    raise ValueError(f"Unsupported social platform: {platform}")
  return config


def generate_pinterest_post_text(
  image_bytes: bytes,
  *,
  post_type: models.JokeSocialPostType,
) -> tuple[str, str, str, models.GenerationMetadata]:
  """Generate Pinterest text fields based on the provided image."""
  config = _get_platform_config(models.SocialPlatform.PINTEREST)
  strategy = config.strategies.get(post_type)
  if not strategy:
    raise ValueError(
      f"Unsupported post type: {post_type} for platform: {models.SocialPlatform.PINTEREST}"
    )

  prompt = f"""STRATEGIC CONTEXT
* Post format: {post_type.description}
* Audience: {strategy.audience}
* CTA: {strategy.cta}
* Goal: {strategy.goal}
"""

  response = config.client.generate([
    prompt,
    ("image/png", image_bytes),
  ])

  try:
    result = json.loads(response.text)
  except json.JSONDecodeError as exc:
    logger.error("Invalid Pinterest JSON response: %s", response.text)
    raise ValueError("Failed to generate Pinterest post text") from exc

  title = result.get("pinterest_title")
  description = result.get("pinterest_description")
  alt_text = result.get("pinterest_alt_text")
  if not title or not description or not alt_text:
    logger.error("Missing Pinterest fields in response: %s", response.text)
    raise ValueError("Failed to generate Pinterest post text")

  return title, description, alt_text, response.metadata
