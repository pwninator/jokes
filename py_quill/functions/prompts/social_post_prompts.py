"""Prompt helpers for social post generation."""

from __future__ import annotations

from firebase_functions import logger

from common import models
from functions.prompts import prompt_utils
from services import llm_client
from services.llm_client import LlmModel

_social_post_llm = llm_client.get_client(
  label="Social Post Text",
  model=LlmModel.GEMINI_3_0_FLASH_PREVIEW,
  output_tokens=300,
  temperature=0.7,
  system_instructions=[
    """You are an expert social copywriter for a wholesome kids jokes brand.

You write short, upbeat titles and descriptions that work across Pinterest,
Instagram, and Facebook. Keep everything family-friendly and avoid profanity,
violence, or adult themes.

Rules:
- Keep the title under 60 characters.
- Keep the description 1-2 sentences, under 200 characters.
- For JOKE_GRID_TEASER, do NOT reveal the final punchline. Tease curiosity.
- For JOKE_GRID, it is fine to mention the jokes or humor at a high level.
- Avoid hashtags, calls to buy, or links.

Return plain text in this exact format:

TITLE:
<title>

DESCRIPTION:
<description>
""",
  ],
)


def generate_social_post_text(
  jokes: list[models.PunnyJoke],
  post_type: models.JokeSocialPostType,
) -> tuple[str, str, models.GenerationMetadata]:
  """Generate a title and description for a social post."""
  if not jokes:
    raise ValueError("jokes must not be empty")

  jokes_payload = "\n".join(
    f"- Setup: {joke.setup_text}\n  Punchline: {joke.punchline_text}"
    for joke in jokes
  )
  prompt = f"""
POST_TYPE: {post_type.value}

JOKES:
{jokes_payload}
"""

  response = _social_post_llm.generate([prompt])
  parsed = prompt_utils.parse_llm_response_line_separated(
    ["TITLE", "DESCRIPTION"],
    response.text,
  )

  title = parsed.get("TITLE", "").strip()
  description = parsed.get("DESCRIPTION", "").strip()
  if not title or not description:
    logger.error("Invalid social post response: %s", response.text)
    raise ValueError("Failed to generate social post text")

  return title, description, response.metadata
