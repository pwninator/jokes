"""Functions for generating joke scene descriptions."""

from typing import Tuple

from common import models
from functions.prompts import prompt_utils
from services import llm_client
from services.llm_client import LlmModel

# pylint: disable=line-too-long
_llm = llm_client.get_client(
  label="Joke Scene Ideas",
  model=LlmModel.GEMINI_2_5_FLASH_LITE,
  thinking_tokens=2000,
  output_tokens=1000,
  temperature=0.9,
  system_instructions=[
    """You are the Creative Director, the first agent in a sequence of AI agents that guide a human user through the process of creating a two-line joke and its illustrations.

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

## Output Requirements

Return plain text in the following exact structure:

SETUP_SCENE_IDEA:
<one or more lines describing the setup scene concept>

PUNCHLINE_SCENE_IDEA:
<one or more lines describing the punchline scene concept>
"""
  ],
)
# pylint: enable-line-too-long


def generate_joke_scene_ideas(
  setup_text: str,
  punchline_text: str,
) -> Tuple[str, str, models.SingleGenerationMetadata]:
  """Generate setup and punchline scene descriptions."""
  if not setup_text:
    raise ValueError("Setup text is required")
  if not punchline_text:
    raise ValueError("Punchline text is required")

  prompt = [
    f"""Joke:
Setup: {setup_text}
Punchline: {punchline_text}

Remember to respond exactly with SETUP_SCENE_IDEA and PUNCHLINE_SCENE_IDEA sections."""
  ]

  response = _llm.generate(prompt)
  result = prompt_utils.parse_llm_response_line_separated(
    ["SETUP_SCENE_IDEA", "PUNCHLINE_SCENE_IDEA"],
    response.text,
  )
  return (
    result["SETUP_SCENE_IDEA"],
    result["PUNCHLINE_SCENE_IDEA"],
    response.metadata,
  )
