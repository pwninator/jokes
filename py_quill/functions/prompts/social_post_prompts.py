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


# 1. SHARED LOGIC VARIABLES
# -------------------------

_COMMON_VISUAL_LOGIC = """
### STEP 1: VISUAL ANALYSIS
Analyze the input image(s) to determine the Content Type. 

**TYPE A: Joke Entertainment (Single, Grid, or Carousel)**
*Visual Cues:* One or more cartoon illustrations with jokes/text. Could be a single image, a 4-panel grid, or a carousel.
*Critical Distinction:* Does NOT have "cut here" lines or scissors icons.
*Content Goal:* Pure Entertainment / Laughter.

**TYPE B: The "Printable Resource"**
*Visual Cues:* Explicit "worksheet" vibes. Look for dotted lines (for cutting), scissors icons, "Name: ___" fields, or text like "Free Download" or "Page 1".
*Content Goal:* Utility / Tool.

**TYPE C: The "Physical Book"**
*Visual Cues:* Photo of a physical book object (curved pages, spine), hands holding a book, or a 3D product mockup.
*Content Goal:* Product Desire / Sales.
"""

_GLOBAL_CONSTRAINTS = """
### GLOBAL CONSTRAINTS
1. NO first-person language ("I", "We", "My", "Our"). Speak as an observer.
2. NO slang ("Bestie", "Vibes", "Fam"). Keep it timeless.
3. RETURN ONLY VALID JSON.
"""

# 2. PLATFORM CONFIGURATION
# -------------------------

_PLATFORM_CONFIGS: dict[models.SocialPlatform, PlatformConfig] = {
  models.SocialPlatform.PINTEREST:
  PlatformConfig(
    strategies={
      models.JokeSocialPostType.JOKE_GRID_TEASER:
      SocialPostStrategy(
        goal="CLARITY. Punchline hidden. Link to answer.",
        cta="Answer at link",
        audience="Families.",
      ),
      models.JokeSocialPostType.JOKE_GRID:
      SocialPostStrategy(
        goal="SEO. Describe the content for search.",
        cta="",
        audience="Parents.",
      ),
    },
    client=llm_client.get_client(
      label="Pinterest Social Post Text",
      model=LlmModel.GEMINI_3_0_FLASH_PREVIEW,
      temperature=0.5,
      output_tokens=8000,
      system_instructions=[
        f"""You are a Pinterest SEO expert.
                
{_COMMON_VISUAL_LOGIC}

### STEP 2: GENERATE METADATA
Your goal is RANKING in search. Do not describe the art style. Describe the SEARCH INTENT.

**IF TYPE A (Joke Content):**
- Title: Specific keywords. (e.g., "Best Dinosaur Puns & Jokes for Kids").
- Description: Focus on age group and usage. 
  - BAD: "A drawing of a dinosaur saying a joke."
  - GOOD: "Clean dinosaur dad jokes for early readers (ages 5-8). Perfect for school lunchbox notes or reading practice."

**IF TYPE B (Printable):**
- Title: High-intent keywords. (e.g., "Free Printable Lunchbox Notes PDF - Dinosaur Theme").
- Description: Focus on the 'Problem/Solution'.
  - BAD: "A sheet with 4 cards."
  - GOOD: "Downloadable tear-off lunch notes to make packing lunch easy. Instant PDF download for elementary school kids."

**IF TYPE C (Book):**
- Title: Gift/Product focus. (e.g., "Best Joke Book for 2nd Graders - Stocking Stuffer").
- Description: Focus on the benefit (Screen-free).
  - GOOD: "The perfect screen-free gift for 7 year olds. A physical book of wholesome animal jokes to build reading confidence."

{_GLOBAL_CONSTRAINTS}
- SPECIFIC PINTEREST RULE: NO HASHTAGS.
"""
      ],
      response_schema={
        "type":
        "OBJECT",
        "properties": {
          "pinterest_title": {
            "type": "STRING",
            "description": "SEO title."
          },
          "pinterest_description": {
            "type": "STRING",
            "description": "SEO description."
          },
          "pinterest_alt_text": {
            "type": "STRING",
            "description": "Visual description."
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
        goal="MINIMAL TEASE. Direct to caption.",
        cta="Check caption",
        audience="Followers.",
      ),
      models.JokeSocialPostType.JOKE_GRID:
      SocialPostStrategy(
        goal="AESTHETIC. Image is hero.",
        cta="",
        audience="Followers.",
      ),
    },
    client=llm_client.get_client(
      label="Instagram Social Post Text",
      model=LlmModel.GEMINI_3_0_FLASH_PREVIEW,
      temperature=0.7,
      output_tokens=8000,
      system_instructions=[
        f"""You are an Instagram caption generator.

{_COMMON_VISUAL_LOGIC}

### STEP 2: GENERATE CAPTION
Based on the determined Content Type:

**IF TYPE A (Joke Content):**
- Rule: **Thematic Observation.** You MUST reference the specific subject (e.g., "Dinosaurs", "Cats", "Coffee").
- Tone: Playful but brief.
- Constraint: Do NOT explain the punchline. Do NOT say "Here is a joke."
- Bad Example: "A solid lineup." (Too vague)
- Good Examples: 
   - "Tea, Rex? Classic. 🦖"
   - "Some top tier dino puns."
   - "T-Rex logic. 🤔"

**IF TYPE B (Printable):**
- Rule: Utility promise.
- Example: "Lunchbox notes sorted. ✅ Link in bio."

**IF TYPE C (Book):**
- Rule: Product highlight.
- Example: "Screen-free entertainment. 📚"

{_GLOBAL_CONSTRAINTS}
- SPECIFIC INSTAGRAM RULE: Exactly 3-5 relevant hashtags.
"""
      ],
      response_schema={
        "type": "OBJECT",
        "properties": {
          "instagram_caption": {
            "type": "STRING",
            "description": "Minimal caption + tags."
          },
          "instagram_alt_text": {
            "type": "STRING",
            "description": "Visual description."
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
        goal="DIRECT. Link to answer.",
        cta="See punchline",
        audience="Families.",
      ),
      models.JokeSocialPostType.JOKE_GRID:
      SocialPostStrategy(
        goal="PASSIVE. Just the joke.",
        cta="",
        audience="Parents.",
      ),
    },
    client=llm_client.get_client(
      label="Facebook Social Post Text",
      model=LlmModel.GEMINI_3_0_FLASH_PREVIEW,
      temperature=0.7,
      output_tokens=8000,
      system_instructions=[
        f"""You are a Facebook Community Manager.

{_COMMON_VISUAL_LOGIC}

### STEP 2: GENERATE MESSAGE
Based on the determined Content Type:

**IF TYPE A (Joke Content):**
- Rule: **Contextual Labeling.** Briefly state what the content is so parents know why they are sharing it.
- Tone: Warm but direct.
- Bad Example: "Some favorites." (Useless)
- Good Examples: 
   - "Two simple dino jokes for the kids."
   - "Trying out some new animal puns."

**IF TYPE B (Printable):**
- Rule: Direct link sharing.
- Example: "We put these up as a free PDF. Grab them here: [Link]"

**IF TYPE C (Book):**
- Rule: Soft recommendation.
- Example: "Great option if you need a screen-free gift idea."

{_GLOBAL_CONSTRAINTS}
- SPECIFIC FACEBOOK RULE: 0-1 hashtags. Include URL naturally.
"""
      ],
      response_schema={
        "type": "OBJECT",
        "properties": {
          "facebook_message": {
            "type": "STRING",
            "description": "Post text."
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
