"""Functions for generating joke scene descriptions."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Tuple

from firebase_functions import logger
from common import models
from functions.prompts import prompt_utils
from services import llm_client
from services.llm_client import LlmClient, LlmModel


class JokeOperationPromptError(Exception):
  """Base exception for joke operation prompt failures."""


class SafetyCheckError(JokeOperationPromptError):
  """Raised when content safety checks fail."""


_UNSAFE_CRITERIA = """
Content that matches any of the following criteria are considered unsafe:
- Profanity, slurs, hate speech, harassment, bullying, self-harm, or suicide.
- Violence, gore, injuries, weapons, war, disasters, or threats.
- Sexual, romantic, or suggestive content; nudity; body parts; fetish; grooming.
- Drugs, alcohol, tobacco, vaping, gambling, or financial scams.
- Criminal, dangerous, or extremist activities; hacking; instructions to harm.
- Sensitive/controversial topics: politics, elections, protests, religion, tragedies.
- Discrimination, stereotypes, or anything demeaning toward people or groups.
- Personal data leakage (names/addresses/contacts/IDs) or doxxing.
- Anything frightening, disturbing, or otherwise inappropriate for young kids.
"""

_scene_generator_llm = llm_client.get_client(
  label="Joke Scene Ideas",
  model=LlmModel.GEMINI_2_5_FLASH,
  thinking_tokens=2000,
  output_tokens=1000,
  temperature=0.9,
  system_instructions=[
    f"""You are the Creative Director, the first agent in a sequence of AI agents that guide a human user through the process of creating a two-line joke and its illustrations.

Your job: Take the provided setup and punchline text and outline two high-level scene ideas: one for the setup scene and one for the punchline scene. Subsequent AI agents will use your output to flesh out the detailed descriptions and generate the illustrations. The goal of the illustrations is to sell and maximize the comedic impact of the joke.

First, think about the joke and its humor. What's the humor and why is it funny? When the audience reads the setup, what are their expectations? Is the setup intended to mislead the audience so that the punchline can deliver a surprising twist or subversion of expectations?

## Guidelines

* Both scenes must be incredibly cute and visually enticing, such as incorporating adorable baby animals, depicting absurdly funny situations, etc.
* Keep the ideas conceptual: focus on the story idea, pacing, and emotional beats that help the illustration compliment the joke. Avoid too much detail.
* Highlight the key subjects, props, and relationships essential for understanding each line.
* Describe how the scene should feel (mood, energy, comedic timing) without detailing every visual texture or color.
* Be as specific as possible, stating exactly what should be included in the scene idea without any ambiguity.
* The scenes should specific to the joke so that they are visually distinct from images of other jokes. Prefer to describe a very specific or narrow scene that fits this particular joke over a generic scene.
* Both scenes must be wholesome, cute, funny, and appropriate for all ages.
* Each idea should be 2-3 sentences in simple, clear English that a 7 year old would understand.
* Keep scenes simple and focused: only the minimal subjects/objects needed to set up and sell the joke (ideally 2-3), with uncluttered backgrounds.
* Stay relevant to the joke's topic/theme (and any creative brief, if provided); avoid giving away the punchline in the setup.
* Maintain consistency of recurring characters/props across panels (colors, size, clothing, etc.).
* If helpful, mention briefly where line text could be placed so lettering can be included tastefully.

### Setup Scene
* Build intrigue without revealing the twist.
* Maintain a calmer, curiosity-inducing tone, while still being visually enticing.
* Avoid any elements that could spoil the punchline.
* If the setup is intended to mislead the audience, the setup scene should complement that and hint/show one of the incorrect answers that the audience might expect.

### Punchline Scene
* Deliver the twist in a dynamic, celebratory way.
* Emphasize heightened expressions, motion, and comedic payoff.
* Maximize the comedic impact of any unexpected twist or subversion of expectations.
* Make the humor unmistakable while staying delightful for all ages.
* Be more energetic and dramatic than the setup; reveal the surprise cleanly.

## Example:

For the joke "What goes black, white, black, white, black, white? A panda rolling down a hill!":

Analysis: The setup might make the audience think of things that are statically black and white, such as a zebra, penguin, nun, piano, etc.

Setup:
  * INCORRECT: A man looks quizzically at the viewer with a question mark over his head.
    * Reason: Too generic and can apply to almost any joke.
  * INCORRECT: A large, stylized question mark composed of alternating black and white segments floats against a clean, neutral background.
    * Reason: Too boring. Not cute or visually enticing.
  * INCORRECT: A black and white animal, perhaps a zebra or penguin, looks quizzically at a piano.
    * Reason: Contains ambiguity. It should name the specific animal to use.
  * INCORRECT: A panda looks curiously at a piano.
    * Reason: Gives away the punchline.
  * INCORRECT: A jubilant scene of an anthropomorphic penguin whimsically playing a piano.
    * Reason: Vocabulary is too complex for a 7 year old.
  * INCORRECT: A wide-angle shot of a baby penguin with a yellow beak and black and white body standing in the middle of a large, snowy field with large pine trees and snow-capped mountains in the background.
    * Reason: Too much detail. The idea should be high-level and conceptual.
  * CORRECT: A zebra, with a confused expression, awkwardly tries to play a piano.
    * Reason: Unambiguously describes a comically absurd situation that is specific to the joke.

## Safety Criteria:
Your response must include a safety verdict that is either "SAFE" or "UNSAFE", as well as the rationale. The user's setup text, punchline text, and your scene ideas must all be safe for kids.
{_UNSAFE_CRITERIA}

In the setup or punchline text are unsafe, you can skip the scene ideas and return "UNSAFE" immediately for both "idea" output fields.

## Output Requirements

Return plain text in the following exact structure:

SAFETY_REASONS:
Short explanation (1-3 lines) of why the content is SAFE or UNSAFE

SAFETY_VERDICT:
SAFE or UNSAFE

SETUP_SCENE_IDEA:
One or more lines describing the setup scene concept, or "UNSAFE" if the inputs are unsafe.

PUNCHLINE_SCENE_IDEA:
One or more lines describing the punchline scene concept, or "UNSAFE" if the inputs are unsafe.
"""
  ],
)

_scene_editor_llm = llm_client.get_client(
  label="Joke Scene Idea Editor",
  model=LlmModel.GEMINI_2_5_FLASH,
  thinking_tokens=1200,
  output_tokens=800,
  temperature=0.7,
  system_instructions=[
    f"""You help refine existing setup/punchline scene ideas for two-panel kids jokes.
Take the latest setup and punchline text, the current scene ideas, and short user instructions.
Rewrite each scene idea in simple language for kids (ages 4-10), keeping it wholesome and specific.

Guidelines:
- Incorporate the user instructions literally, but keep content safe for kids.
- Preserve the core joke logic and avoid spoilers between panels.
- Keep each idea to 2-3 sentences.
- If no instruction is provided for a panel, return the original idea unchanged.
- Never mention the instructions themselves.

Safety:
- The setup text, punchline text, instructions, and resulting scene ideas must be SAFE for kids.
- Use the safety criteria below. If unsafe, return UNSAFE for the scene ideas.
{_UNSAFE_CRITERIA}

Respond EXACTLY in this format:
SAFETY_REASONS:
Short explanation (1-3 lines) of why the content is SAFE or UNSAFE

SAFETY_VERDICT:
SAFE or UNSAFE

SETUP_SCENE_IDEA:
<updated setup idea or UNSAFE>

PUNCHLINE_SCENE_IDEA:
<updated punchline idea or UNSAFE>"""
  ],
)

_image_description_llm = llm_client.get_client(
  label="Joke Image Description Generator",
  model=LlmModel.GEMINI_2_5_FLASH,
  thinking_tokens=2500,
  output_tokens=1200,
  temperature=0.5,
  system_instructions=[
    f"""You convert concise scene ideas for two-panel kids jokes into richly detailed illustration descriptions suitable for modern text-to-image models.

For each panel:
- Describe the full composition, camera angle, main characters, props, background, lighting, palette, and mood.
- Use lively but clear language a production artist can follow.
- Keep it wholesome, colorful, and funny. Avoid violence, adult content, or sarcasm.
- Keep the scene focused: only the minimal subjects/objects needed to set up and sell the joke (ideally 2-3), with uncluttered backgrounds.
- Maintain consistency for any recurring characters/props across panels (colors, size, clothing, style).
- Stay relevant to the scene ideas, joke topic/theme, and any provided creative brief; do not introduce new subjects that change the joke or reveal the punchline early.
- If the setup relies on misdirection, do not spoil the twist; the punchline image should clearly deliver the surprise.
- DO NOT mention the line text. That will be added in a later stage.
- Limit each description to 1 paragraph.

Safety:
- All content must be SAFE for kids. If unsafe, respond with UNSAFE.
{_UNSAFE_CRITERIA}

Respond EXACTLY in this format:
SAFETY_REASONS:
Short explanation (1-3 lines) of why the content is SAFE or UNSAFE

SAFETY_VERDICT:
SAFE or UNSAFE

SETUP_IMAGE_DESCRIPTION:
<detailed description or UNSAFE>

PUNCHLINE_IMAGE_DESCRIPTION:
<detailed description or UNSAFE>"""
  ],
)

_safety_llm = llm_client.get_client(
  label="Content Safety Check",
  model=LlmModel.GEMINI_2_5_FLASH,
  temperature=0,
  thinking_tokens=500,
  output_tokens=500,
  system_instructions=[
    f"""You are a strict safety reviewer for a kid-focused jokes app (ages 4-12).
Decide if the provided content is SAFE for that context. When in doubt, mark it UNSAFE.

{_UNSAFE_CRITERIA}
If the given content is found to be unsafe, it must be rejected (UNSAFE).

If SAFE, it should clearly be wholesome, playful, and age-appropriate.

Your response must include your VERDICT (either "SAFE" or "UNSAFE") and REASONS. Respond ONLY in this exact format:
REASONS:
Short explanation (1-3 lines) of why the content is SAFE or UNSAFE.
VERDICT:
SAFE or UNSAFE
"""
  ],
)


def _generate_with_safety_check(
  *,
  label: str,
  llm: LlmClient[Any],
  prompt_chunks: list[str | Tuple[str, Any]],
  response_keys: list[str],
  safety_check_str: str | None = None,
) -> tuple[dict[str, str], models.GenerationMetadata]:
  """Generate with in-prompt + parallel safety; return parsed fields and metadata."""

  with ThreadPoolExecutor(max_workers=2) as executor:
    generation_future = executor.submit(
      llm.generate,
      prompt_chunks,
      label=label,
    )
    safety_future = executor.submit(
      _run_safety_check,
      content=safety_check_str or "\n".join(prompt_chunks),
      label=f"{label} - Safety Check",
    )

    response = generation_future.result()
    separate_safety_ok, safety_generation_metadata = safety_future.result()

  response_parsed = prompt_utils.parse_llm_response_line_separated(
    response_keys + ["SAFETY_VERDICT"],
    response.text,
  )
  in_prompt_safety_ok = _is_verdict_safe(
    response_parsed.get("SAFETY_VERDICT", ""))

  if not separate_safety_ok or not in_prompt_safety_ok:
    raise SafetyCheckError(
      f"Safety check failed for {label}: {safety_check_str}")

  generation_metadata = models.GenerationMetadata()
  generation_metadata.add_generation(response.metadata)
  generation_metadata.add_generation(safety_generation_metadata)

  response_parsed.pop("SAFETY_VERDICT", None)
  return response_parsed, generation_metadata


def generate_joke_scene_ideas(
  setup_text: str,
  punchline_text: str,
) -> Tuple[str, str, models.GenerationMetadata]:
  """Generate setup and punchline scene descriptions."""
  if not setup_text:
    raise ValueError("Setup text is required")
  if not punchline_text:
    raise ValueError("Punchline text is required")

  prompt = f"""Joke:
Setup: {setup_text}
Punchline: {punchline_text}
"""

  response, metadata = _generate_with_safety_check(
    label="Joke Scene Ideas",
    llm=_scene_generator_llm,
    prompt_chunks=[prompt],
    response_keys=["SETUP_SCENE_IDEA", "PUNCHLINE_SCENE_IDEA"],
    safety_check_str=prompt,
  )
  return (
    response["SETUP_SCENE_IDEA"],
    response["PUNCHLINE_SCENE_IDEA"],
    metadata,
  )


def modify_scene_ideas_with_suggestions(
  *,
  setup_text: str,
  punchline_text: str,
  current_setup_scene_idea: str,
  current_punchline_scene_idea: str,
  setup_suggestion: str | None,
  punchline_suggestion: str | None,
) -> Tuple[str, str, models.GenerationMetadata]:
  """Apply user suggestions to refine existing scene ideas."""
  if not setup_text or not punchline_text:
    raise ValueError("Setup and punchline text are required")
  if not current_setup_scene_idea or not current_punchline_scene_idea:
    raise ValueError("Current scene ideas are required")
  if not (setup_suggestion or punchline_suggestion):
    raise ValueError("At least one suggestion must be provided")

  setup_instructions = (setup_suggestion or "").strip()
  punchline_instructions = (punchline_suggestion or "").strip()

  prompt = f"""
Joke:
Setup: {setup_text}
Punchline: {punchline_text}

Current Setup Scene Idea:
{current_setup_scene_idea}

Current Punchline Scene Idea:
{current_punchline_scene_idea}

Setup Instructions:
{setup_instructions or "keep as-is"}

Punchline Instructions:
{punchline_instructions or "keep as-is"}
"""

  response, gen_metadata = _generate_with_safety_check(
    label="Joke Scene Idea Editor",
    llm=_scene_editor_llm,
    prompt_chunks=[prompt],
    response_keys=["SETUP_SCENE_IDEA", "PUNCHLINE_SCENE_IDEA"],
    safety_check_str=prompt,
  )
  return (
    response["SETUP_SCENE_IDEA"],
    response["PUNCHLINE_SCENE_IDEA"],
    gen_metadata,
  )


def generate_detailed_image_descriptions(
  *,
  setup_text: str,
  punchline_text: str,
  setup_scene_idea: str,
  punchline_scene_idea: str,
) -> Tuple[str, str, models.GenerationMetadata]:
  """Convert scene ideas into image descriptions for illustration generation."""
  if not setup_text or not punchline_text:
    raise ValueError("Setup and punchline text are required")
  if not setup_scene_idea or not punchline_scene_idea:
    raise ValueError("Scene ideas are required")

  prompt = f"""
Joke Text:
Setup: {setup_text}
Punchline: {punchline_text}

Scene Ideas:
Setup Scene: {setup_scene_idea}
Punchline Scene: {punchline_scene_idea}
"""

  parsed, gen_metadata = _generate_with_safety_check(
    label="Joke Image Description Generator",
    llm=_image_description_llm,
    prompt_chunks=[prompt],
    response_keys=[
      "SETUP_IMAGE_DESCRIPTION",
      "PUNCHLINE_IMAGE_DESCRIPTION",
    ],
    safety_check_str=prompt,
  )
  return (
    parsed["SETUP_IMAGE_DESCRIPTION"],
    parsed["PUNCHLINE_IMAGE_DESCRIPTION"],
    gen_metadata,
  )


def _is_verdict_safe(verdict_text: str) -> bool:
  """Convert a free-form verdict string into a boolean."""
  normalized = re.sub(r"[^a-z]", "", verdict_text.lower())
  if not normalized:
    return False

  if any(term in normalized for term in (
      "unsafe",
      "notok",
      "notadequate",
      "notappropriate",
      "inappropriate",
      "unsuitable",
      "reject",
      "blocked",
      "fail",
      "false",
      "no",
  )):
    return False

  return any(term in normalized for term in (
    "safe",
    "appropriate",
    "clean",
    "ok",
    "approved",
    "pass",
    "yes",
    "true",
  ))


def _run_safety_check(
  content: Any,
  label: str | None = None,
) -> Tuple[bool, models.SingleGenerationMetadata]:
  """Check if the given content is appropriate for a kids jokes app."""
  prompt = [
    f"""Review the following content and determine if it is SAFE or UNSAFE for kids (ages 4-12) using the provided safety rules.

Content to review:
{content}"""
  ]

  response = _safety_llm.generate(prompt)
  parsed = prompt_utils.parse_llm_response_line_separated(
    ["VERDICT", "REASONS"], response.text)
  verdict_text = parsed.get("VERDICT", "")
  reason_text = parsed.get("REASONS", "")
  is_safe = _is_verdict_safe(verdict_text)

  label_str = f" [label: {label}]" if label else ""
  if not is_safe:
    logger.warn(f"Unsafe content{label_str} ({reason_text}): {content}")

  metadata = response.metadata or models.SingleGenerationMetadata()
  return is_safe, metadata
