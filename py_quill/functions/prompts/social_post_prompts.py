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
        goal=(
          "CURIOSITY GAP. The punchline is hidden. You MUST intrigue the user to click. "
          "Do NOT reveal the answer. Focus on the 'mystery'."),
        cta="See the answer",
        audience="Families looking for quick entertainment, bored kids.",
      ),
      models.JokeSocialPostType.JOKE_GRID:
      SocialPostStrategy(
        goal=
        "SAVES & UTILITY. This is a complete resource. Optimize for users saving this to their boards for later.",
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
        """You are a Pinterest SEO expert for Snickerdoodle Jokes.
                
Your job: Analyze the image and generate high-intent Pinterest copy.
RULES:
1. Title: Max 100 chars. **CRITICAL: Front-load the main keyword in the first 30 characters.**
2. Description: Max 500 chars. Use natural sentences, not lists. Integrate keywords organically.
3. NO HASHTAGS in description.
4. Alt Text: Describe the image visually for accessibility.

Return ONLY valid JSON."""
      ],
      response_schema={
        "type":
        "OBJECT",
        "properties": {
          "pinterest_title": {
            "type": "STRING",
            "description": "SEO optimized title, max 100 chars."
          },
          "pinterest_description": {
            "type": "STRING",
            "description": "Keyword rich description, max 500 chars."
          },
          "pinterest_alt_text": {
            "type": "STRING",
            "description": "Visual description, max 500 chars."
          },
        },
        "required":
        ["pinterest_title", "pinterest_description", "pinterest_alt_text"],
      },
    ),
  ),
  models.SocialPlatform.INSTAGRAM:
  PlatformConfig(
    strategies={
      models.JokeSocialPostType.JOKE_GRID_TEASER:
      SocialPostStrategy(
        goal=(
          "ENGAGEMENT. The punchline is hidden. Ask users to GUESS the answer in the comments."
        ),
        cta="Guess the punchline below! 👇",
        audience="Parents and families.",
      ),
      models.JokeSocialPostType.JOKE_GRID:
      SocialPostStrategy(
        goal=(
          "RELATABILITY. This is shareable content. Write a caption that feels like a friend recommending a laugh."
        ),
        cta="Send this to a parent who needs a smile",
        audience="Parents, teachers, and grandparents.",
      ),
    },
    client=llm_client.get_client(
      label="Instagram Social Post Text",
      model=LlmModel.GEMINI_3_0_FLASH_PREVIEW,
      temperature=1.0,  # High temp for creativity
      output_tokens=8000,
      system_instructions=[
        """You are an Instagram Growth expert for Snickerdoodle Jokes.

Your job: Analyze the image and generate engaging Instagram copy.
RULES:
1. Caption: Max 2200 chars. Start with a "Hook" (short, punchy first line). Use line breaks.
2. Tone: Friendly, playful, "Bestie" energy.
3. HASHTAGS: You MUST append a block of 20-30 relevant hashtags at the very bottom of the caption. Mix broad tags (#parenting) with niche tags (#lunchboxjokes).

Return ONLY valid JSON."""
      ],
      response_schema={
        "type": "OBJECT",
        "properties": {
          "instagram_caption": {
            "type": "STRING",
            "description": "Caption with hook, body, CTA, and 30 hashtags."
          },
          "instagram_alt_text": {
            "type": "STRING",
            "description": "Visual description only."
          },
        },
        "required": ["instagram_caption", "instagram_alt_text"],
      },
    ),
  ),
  models.SocialPlatform.FACEBOOK:
  PlatformConfig(
    strategies={
      models.JokeSocialPostType.JOKE_GRID_TEASER:
      SocialPostStrategy(
        goal=(
          "CLICK-THROUGH. Tease the hidden punchline. Make them want to click the link to see the answer."
        ),
        cta="Click the link to see the punchline",
        audience="Families and community groups.",
      ),
      models.JokeSocialPostType.JOKE_GRID:
      SocialPostStrategy(
        goal=(
          "SHARING. Keep it short. Encourage them to share this with friends."
        ),
        cta="Share if this made you smile!",
        audience="Parents and grandparents.",
      ),
    },
    client=llm_client.get_client(
      label="Facebook Social Post Text",
      model=LlmModel.GEMINI_3_0_FLASH_PREVIEW,
      temperature=1.0,
      output_tokens=8000,
      system_instructions=[
        """You are a Facebook Community Manager for Snickerdoodle Jokes.

Your job: Analyze the image and generate a Facebook post.
RULES:
1. Message: Max 600 chars. Conversational and warm.
2. LINKS: You MUST incorporate the provided URL naturally into the message text.
3. HASHTAGS: Use 1-3 hashtags max (or none).

Return ONLY valid JSON."""
      ],
      response_schema={
        "type": "OBJECT",
        "properties": {
          "facebook_message": {
            "type": "STRING",
            "description": "Post text including the link."
          },
        },
        "required": ["facebook_message"],
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


def generate_instagram_post_text(
  image_bytes: bytes,
  *,
  post_type: models.JokeSocialPostType,
) -> tuple[str, str, models.GenerationMetadata]:
  """Generate Instagram text fields based on the provided image."""
  config = _get_platform_config(models.SocialPlatform.INSTAGRAM)
  strategy = config.strategies.get(post_type)
  if not strategy:
    raise ValueError(
      f"Unsupported post type: {post_type} for platform: {models.SocialPlatform.INSTAGRAM}"
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
    logger.error("Invalid Instagram JSON response: %s", response.text)
    raise ValueError("Failed to generate Instagram post text") from exc

  caption = result.get("instagram_caption")
  alt_text = result.get("instagram_alt_text")
  if not caption or not alt_text:
    logger.error("Missing Instagram fields in response: %s", response.text)
    raise ValueError("Failed to generate Instagram post text")

  return caption, alt_text, response.metadata


def generate_facebook_post_text(
  image_bytes: bytes,
  *,
  post_type: models.JokeSocialPostType,
  link_url: str,
) -> tuple[str, models.GenerationMetadata]:
  """Generate Facebook text fields based on the provided image."""
  if not isinstance(link_url, str) or not link_url.strip():
    raise ValueError("link_url is required for Facebook post text generation")
  normalized_link_url = link_url.strip()
  config = _get_platform_config(models.SocialPlatform.FACEBOOK)
  strategy = config.strategies.get(post_type)
  if not strategy:
    raise ValueError(
      f"Unsupported post type: {post_type} for platform: {models.SocialPlatform.FACEBOOK}"
    )

  prompt = f"""STRATEGIC CONTEXT
* Post format: {post_type.description}
* Audience: {strategy.audience}
* CTA: {strategy.cta}
* Goal: {strategy.goal}
* Link URL to include: {normalized_link_url}
"""

  response = config.client.generate([
    prompt,
    ("image/png", image_bytes),
  ])

  try:
    result = json.loads(response.text)
  except json.JSONDecodeError as exc:
    logger.error("Invalid Facebook JSON response: %s", response.text)
    raise ValueError("Failed to generate Facebook post text") from exc

  message = result.get("facebook_message")
  if not message:
    logger.error("Missing Facebook fields in response: %s", response.text)
    raise ValueError("Failed to generate Facebook post text")

  return message, response.metadata
