"""Prompt helpers for social post generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from common import models
from firebase_functions import logger
from services import llm_client
from services.llm_client import LlmModel


@dataclass(frozen=True)
class SocialPostStrategy:
  """Strategy for generating social post text."""

  goal: str
  guidelines: str
  cta: str
  audience: str


@dataclass(frozen=True)
class PlatformConfig:
  """Configuration for social platform post generation."""

  system_prompt: str
  post_strategies: dict[models.JokeSocialPostType, SocialPostStrategy]
  output_schema: dict[str, Any]


_PLATFORM_CONFIGS: dict[models.SocialPlatform, PlatformConfig] = {

  ######################
  ##### PINTEREST ######
  ######################
  models.SocialPlatform.PINTEREST:
  PlatformConfig(
    system_prompt="""You are a Pinterest SEO expert.

Write titles and descriptions to optimize for SEO. Include both high volume and long-tail keywords for broad match search.

Titles:
100 characters or less. Craft a catchy, benefit-driven headline that creates curiosity or offers a clear solution. Should describe content both in the post and in the click-through link. Frontload important keywords in the first 50 characters. 

Descriptions:
2-3 sentences. Prioritize searchability by naturally weaving relevant keywords into the first sentence. Focus on the user's intent by clearly describing the specific value, solution, or inspiration they will gain from clicking through to your site. End with a direct call to action that explicitly tells the viewer what to do next.
""",
    post_strategies={
      models.JokeSocialPostType.JOKE_GRID_TEASER:
      SocialPostStrategy(
        goal="Drive clickthroughs to the site.",
        guidelines=
        "Emphasize the withheld punchline as a reason to click. Keywords must highlight searchability while description creates urgency to complete the incomplete joke.",
        cta="Visit site to see punchline",
        audience="All",
      ),
      models.JokeSocialPostType.JOKE_GRID:
      SocialPostStrategy(
        goal="Drive saves, comments, and shares",
        guidelines=
        "Emphasize a suitable benefit or use case for the jokes, e.g. sharing/connecting with a friend, entertaining a child, cheering up their day, etc. Keywords for discovery, but description should highlight why this content is worth saving or sharing with others. End with CTA to see more jokes at the site.",
        cta="Visit site to see more jokes",
        audience="All",
      ),
      models.JokeSocialPostType.JOKE_CAROUSEL:
      SocialPostStrategy(
        goal="Drive pin saves, comments, and shares",
        guidelines=
        "Emphasize a suitable benefit or use case for the jokes, e.g. sharing/connecting with a friend, entertaining a child, cheering up their day, etc. Keywords for discovery, but description should highlight why this content is worth saving or sharing with others. End with CTA to see more jokes at the site.",
        cta="Visit site to see more jokes",
        audience="All",
      ),
      models.JokeSocialPostType.JOKE_REEL_VIDEO:
      SocialPostStrategy(
        goal="Drive saves, shares, and clickthrough from a short-form video",
        guidelines=
        "Treat this as a joke reel post. Keep wording punchy and scannable while still being SEO-friendly. Highlight the joke payoff and why someone should save/share it.",
        cta="Visit site to see more jokes",
        audience="All",
      ),
    },
    output_schema={
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

  ######################
  ##### INSTAGRAM ######
  ######################
  models.SocialPlatform.INSTAGRAM:
  PlatformConfig(
    system_prompt="""You are an Instagram caption generator.

Write a caption to optimize for engagement. Include exactly 3-5 relevant hashtags at the bottom separated by a blank line. Use this format:

[Caption body]

[3-5 hashtags]
""",
    post_strategies={
      models.JokeSocialPostType.JOKE_GRID_TEASER:
      SocialPostStrategy(
        goal="Drive engagement and comments",
        guidelines="Emphasize the withheld punchline as a reason to comment.",
        cta="None",
        audience="All",
      ),
      models.JokeSocialPostType.JOKE_GRID:
      SocialPostStrategy(
        goal="Drive engagement and comments",
        guidelines=
        "The caption should be a short pun related to the content theme that's not already in the content, like a side comment that adds humor to the content.",
        cta="None",
        audience="All",
      ),
      models.JokeSocialPostType.JOKE_CAROUSEL:
      SocialPostStrategy(
        goal="Drive engagement and comments",
        guidelines=
        "The caption should be a short pun related to the content theme that's not already in the content, like a side comment that adds humor to the content.",
        cta="None",
        audience="All",
      ),
      models.JokeSocialPostType.JOKE_REEL_VIDEO:
      SocialPostStrategy(
        goal="Drive reel watch-through, comments, and shares",
        guidelines=
        "The caption should be a short pun related to the content theme that's not already in the content, like a side comment that adds humor to the content.",
        cta="None",
        audience="All",
      ),
    },
    output_schema={
      "type": "OBJECT",
      "properties": {
        "instagram_caption": {
          "type": "STRING",
          "description": "Caption, a blank line, then 3-5 hashtags."
        },
        "instagram_alt_text": {
          "type": "STRING",
          "description": "Visual description of the content."
        },
      },
      "required": ["instagram_caption", "instagram_alt_text"],
    },
  ),

  ######################
  ##### FACEBOOK #######
  ######################
  models.SocialPlatform.FACEBOOK:
  PlatformConfig(
    system_prompt="""You are a Facebook Community Manager.

The post should include the body, a CTA to the link URL, and 1 relevant hashtag, each separated by a blank line.

Write a short post message in this format:

[Post body]

[CTA to see more jokes at the link below]
[Link URL]

[1 relevant hashtag]
""",
    post_strategies={
      models.JokeSocialPostType.JOKE_GRID_TEASER:
      SocialPostStrategy(
        goal="Drive comments and shares",
        guidelines=
        "This post's URL contains the punchline to the hidden joke, so the CTA should reflect that.",
        cta="See the punchline at the URL",
        audience="All",
      ),
      models.JokeSocialPostType.JOKE_GRID:
      SocialPostStrategy(
        goal="Drive comments and shares",
        guidelines=
        "The post should be a simple, wholesome statement related to the content, maybe using a pun related to the joke themes that's not already in the images. Occasionally, once every 4-8 posts,, include a CTA to encourage sharing or commenting.",
        cta="None",
        audience="All",
      ),
      models.JokeSocialPostType.JOKE_CAROUSEL:
      SocialPostStrategy(
        goal="Drive comments and shares",
        guidelines=
        "The post should be a simple, wholesome statement related to the content, maybe using a pun related to the joke themes that's not already in the images. Occasionally, once every 4-8 posts, include a CTA to encourage sharing or commenting.",
        cta="None",
        audience="All",
      ),
      models.JokeSocialPostType.JOKE_REEL_VIDEO:
      SocialPostStrategy(
        goal="Drive reel engagement and clickthrough",
        guidelines=
        "The post should be a simple, wholesome statement related to the content, maybe using a pun related to the joke themes that's not already in the images. Occasionally, once every 4-8 posts, include a CTA to encourage sharing or commenting.",
        cta="None",
        audience="All",
      ),
    },
    output_schema={
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
}

_COMMON_SYSTEM_PROMPT = """\
You are also given a list of recent posts. Use this information to avoid repeating content and ensure that each post is unique and fresh. For example, if including a pun, make sure it's not already in the recent posts.
"""

_REEL_DIALOG_OUTPUT_SCHEMA = {
  "type": "OBJECT",
  "properties": {
    "intro_script": {
      "type": "STRING",
      "description": "A very short opener spoken before the setup.",
    },
    "response_script": {
      "type": "STRING",
      "description": "A brief listener response to the setup text.",
    },
  },
  "required": ["intro_script", "response_script"],
}

_LLM_CLIENTS: dict[models.SocialPlatform, llm_client.LlmClient[Any]] = {
  platform:
  llm_client.get_client(
    label=f"{platform.value} Social Post Text",
    model=LlmModel.GEMINI_3_0_FLASH_PREVIEW,
    temperature=1.0,
    thinking_tokens=1000,
    output_tokens=8000,
    system_instructions=[platform_config.system_prompt, _COMMON_SYSTEM_PROMPT],
    response_schema=platform_config.output_schema,
  )
  for platform, platform_config in _PLATFORM_CONFIGS.items()
}

_REEL_DIALOG_LLM = llm_client.get_client(
  label="Social Reel Dialog Script",
  model=LlmModel.GEMINI_3_0_FLASH_PREVIEW,
  temperature=1.0,
  thinking_tokens=1000,
  output_tokens=4000,
  system_instructions=[
    """Write a short two-character dialog between a Teller, who tells a joke to a Listener.

Generate only the opener and the listener response for this fixed 4-turn structure:
1. Teller says the intro_script
2. Teller says the joke setup line exactly as provided
3. Listener responds with the response_script
4. Teller says the joke punchline exactly as provided

Requirements:
- `intro_script` must be short and natural, aiming to capture the audience's attention.
- `response_script` must fit the setup. Match the right question word when needed, such as what/how/why/who/where/when.
- Keep both lines concise and conversational.
- Do not include speaker labels, emojis, quotes, or extra commentary.
- If other recent scripts are provided, aim for variety and keep the script fresh by avoiding repeating the same intro/response patterns.
- Return valid JSON only.

Example 1:
Input:
Setup text: Why did the chicken cross the road?
Punchline text: To get to the other side!
Output:
intro_script: Hey!
response_script: I don't know. Why?

Example 2:
Input:
Setup text: How do you make a dog laugh?
Punchline text: You give it a funny bone!
Output:
intro_script: Pss!
response_script: Hmmm, how?
""",
  ],
  response_schema=_REEL_DIALOG_OUTPUT_SCHEMA,
)


def _get_platform_config(platform: models.SocialPlatform) -> PlatformConfig:
  config = _PLATFORM_CONFIGS.get(platform)
  if not config:
    raise ValueError(f"Unsupported social platform: {platform}")
  return config


def _get_llm_client(
    platform: models.SocialPlatform) -> llm_client.LlmClient[Any]:
  client = _LLM_CLIENTS.get(platform)
  if not client:
    raise ValueError(f"Unsupported social platform: {platform}")
  return client


def generate_pinterest_post_text(
  image_bytes_list: list[bytes],
  *,
  post_type: models.JokeSocialPostType,
  recent_posts: list[models.JokeSocialPost],
) -> tuple[str, str, str, models.GenerationMetadata]:
  """Generate Pinterest text fields based on the provided image(s)."""
  if not image_bytes_list:
    raise ValueError("image_bytes_list must contain at least one image")
  config = _get_platform_config(models.SocialPlatform.PINTEREST)
  strategy = config.post_strategies.get(post_type)
  if not strategy:
    raise ValueError(
      f"Unsupported post type: {post_type} for platform: {models.SocialPlatform.PINTEREST}"
    )

  recent_posts_prompt = _get_recent_posts_prompt_str(
    recent_posts, models.SocialPlatform.PINTEREST)
  prompt = f"""STRATEGIC CONTEXT
* Post format: {post_type.description}
* Guidelines: {strategy.guidelines}
* Audience: {strategy.audience}
* CTA: {strategy.cta}
* Goal: {strategy.goal}

RECENT POSTS
{recent_posts_prompt}
"""

  client = _get_llm_client(models.SocialPlatform.PINTEREST)
  response = client.generate([prompt] + [("image/png", image_bytes)
                                         for image_bytes in image_bytes_list])

  try:
    result = json.loads(response.text)
  except json.JSONDecodeError as exc:
    logger.error(f"Invalid Pinterest JSON response: {response.text}")
    raise ValueError("Failed to generate Pinterest post text") from exc

  title = result.get("pinterest_title")
  description = result.get("pinterest_description")
  alt_text = result.get("pinterest_alt_text")
  if not title or not description or not alt_text:
    logger.error(f"Missing Pinterest fields in response: {response.text}")
    raise ValueError("Failed to generate Pinterest post text")

  return title, description, alt_text, models.GenerationMetadata.from_single_generation_metadata(
    response.metadata)


def generate_instagram_post_text(
  image_bytes_list: list[bytes],
  *,
  post_type: models.JokeSocialPostType,
  recent_posts: list[models.JokeSocialPost],
) -> tuple[str, str, models.GenerationMetadata]:
  """Generate Instagram text fields based on the provided image(s)."""
  if not image_bytes_list:
    raise ValueError("image_bytes_list must contain at least one image")
  config = _get_platform_config(models.SocialPlatform.INSTAGRAM)
  strategy = config.post_strategies.get(post_type)
  if not strategy:
    raise ValueError(
      f"Unsupported post type: {post_type} for platform: {models.SocialPlatform.INSTAGRAM}"
    )

  recent_posts_prompt = _get_recent_posts_prompt_str(
    recent_posts, models.SocialPlatform.INSTAGRAM)
  prompt = f"""STRATEGIC CONTEXT
* Post format: {post_type.description}
* Guidelines: {strategy.guidelines}
* Audience: {strategy.audience}
* CTA: {strategy.cta}
* Goal: {strategy.goal}

RECENT POSTS
{recent_posts_prompt}
"""

  client = _get_llm_client(models.SocialPlatform.INSTAGRAM)
  response = client.generate([prompt] + [("image/png", image_bytes)
                                         for image_bytes in image_bytes_list])

  try:
    result = json.loads(response.text)
  except json.JSONDecodeError as exc:
    logger.error(f"Invalid Instagram JSON response: {response.text}")
    raise ValueError("Failed to generate Instagram post text") from exc

  caption = result.get("instagram_caption")
  alt_text = result.get("instagram_alt_text")
  if not caption or not alt_text:
    logger.error(f"Missing Instagram fields in response: {response.text}")
    raise ValueError("Failed to generate Instagram post text")

  return caption, alt_text, models.GenerationMetadata.from_single_generation_metadata(
    response.metadata)


def generate_facebook_post_text(
  image_bytes_list: list[bytes],
  *,
  post_type: models.JokeSocialPostType,
  link_url: str,
  recent_posts: list[models.JokeSocialPost],
) -> tuple[str, models.GenerationMetadata]:
  """Generate Facebook text fields based on the provided image(s)."""
  if not image_bytes_list:
    raise ValueError("image_bytes_list must contain at least one image")
  if not link_url.strip():
    raise ValueError("link_url is required for Facebook post text generation")
  normalized_link_url = link_url.strip()
  config = _get_platform_config(models.SocialPlatform.FACEBOOK)
  strategy = config.post_strategies.get(post_type)
  if not strategy:
    raise ValueError(
      f"Unsupported post type: {post_type} for platform: {models.SocialPlatform.FACEBOOK}"
    )

  recent_posts_prompt = _get_recent_posts_prompt_str(
    recent_posts, models.SocialPlatform.FACEBOOK)
  prompt = f"""STRATEGIC CONTEXT
* Post format: {post_type.description}
* Guidelines: {strategy.guidelines}
* Audience: {strategy.audience}
* CTA: {strategy.cta}
* Goal: {strategy.goal}
* Link URL to include: {normalized_link_url}

RECENT POSTS
{recent_posts_prompt}
"""

  client = _get_llm_client(models.SocialPlatform.FACEBOOK)
  response = client.generate([prompt] + [("image/png", image_bytes)
                                         for image_bytes in image_bytes_list])

  try:
    result = json.loads(response.text)
  except json.JSONDecodeError as exc:
    logger.error(f"Invalid Facebook JSON response: {response.text}")
    raise ValueError("Failed to generate Facebook post text") from exc

  message = result.get("facebook_message")
  if not message:
    logger.error(f"Missing Facebook fields in response: {response.text}")
    raise ValueError("Failed to generate Facebook post text")

  return message, models.GenerationMetadata.from_single_generation_metadata(
    response.metadata)


def generate_joke_reel_dialog_scripts(
  *,
  setup_text: str,
  punchline_text: str,
  recent_posts: list[models.JokeSocialPost],
) -> tuple[str, str, models.GenerationMetadata]:
  """Generate varied intro/response lines for a joke reel dialog."""
  normalized_setup = setup_text.strip()
  normalized_punchline = punchline_text.strip()
  if not normalized_setup:
    raise ValueError("setup_text is required for reel dialog generation")
  if not normalized_punchline:
    raise ValueError("punchline_text is required for reel dialog generation")

  prompt_chunks: list[str] = [
    f"""CURRENT JOKE
* Setup text: {normalized_setup}
* Punchline text: {normalized_punchline}
"""
  ]

  recent_scripts_prompt = _get_recent_reel_scripts_prompt_str(recent_posts)
  if recent_scripts_prompt:
    prompt_chunks.append(recent_scripts_prompt)

  response = _REEL_DIALOG_LLM.generate(prompt_chunks)
  try:
    result = json.loads(response.text)
  except json.JSONDecodeError as exc:
    logger.error(f"Invalid reel dialog JSON response: {response.text}")
    raise ValueError("Failed to generate reel dialog scripts") from exc

  intro_script = str(result.get("intro_script", "")).strip()
  response_script = str(result.get("response_script", "")).strip()
  if not intro_script or not response_script:
    logger.error(f"Missing reel dialog fields in response: {response.text}")
    raise ValueError("Failed to generate reel dialog scripts")

  return (
    intro_script,
    response_script,
    models.GenerationMetadata.from_single_generation_metadata(
      response.metadata),
  )


def _get_recent_posts_prompt_str(recent_posts: list[models.JokeSocialPost],
                                 platform: models.SocialPlatform) -> str:
  """Generate a prompt string for the recent posts."""
  if not recent_posts:
    return ""
  return "\n\n".join(
    [post.platform_summary(platform) for post in recent_posts])


def _get_recent_reel_scripts_prompt_str(
    recent_posts: list[models.JokeSocialPost]) -> str | None:
  """Generate a prompt block describing recent reel intro/response pairs."""
  if not recent_posts:
    return None

  summaries: list[str] = []
  for index, post in enumerate(recent_posts, start=1):
    intro_script = (post.reel_intro_script or "").strip()
    response_script = (post.reel_response_script or "").strip()

    if not post.jokes:
      continue
    joke = post.jokes[0]
    if not (joke.setup_text and joke.punchline_text and intro_script
            and response_script):
      continue

    summaries.append(f"""
Recent script {index}:
Intro: {intro_script}
Setup: {joke.setup_text}
Response: {response_script}
Punchline: {joke.punchline_text}
""".strip())

  return "\n\n".join(summaries) if summaries else None
