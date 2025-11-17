"""Functions for generating story prompts."""

# pylint: disable=line-too-long

import json
import random

from common import models
from common.models import ReadingLevel
from services import llm_client
from services.llm_client import LlmModel

_SETTINGS = [
  # Real Man-made
  "Garden",
  "School",
  "Marketplace",
  "Playground",
  "Factory",
  "Junkyard",
  "Village",
  "Library",
  "Attic",
  "Carnival",
  "Castle",

  # Real Natural
  "Forest",
  "Underwater",
  "Outer Space",
  "Swamp",
  "Beach",
  "Mountain",
  "Desert",
  "Cave",
  "Underground",

  # Fantasy
  "Candy Land",
  "Sky World",
  "a magical forest",
  "Magic School",
]

_GENRES = [
  # Realistic Fiction
  "Adventure",
  "Mystery",
  "Action",
  "Western",
  "Comedy",
  "Slice of Life",
  "Sports",
  "Magical Realism",

  # Fantasy
  "Fantasy",
  "High fantasy",
  "Urban Fantasy",
  "Animal Fantasy",
  "Mythological Fantasy",
  "Fairy Tale Retelling",
  "Dragons",

  # Space
  "Space",
  "Space Opera",
  "Space Western",

  # Science Fiction
  "Science Fiction",
  "Time Travel",
  "Steampunk",
  "Superhero",

  # Historical
  "Historical",
  "Alternate History",
  "Historical Fiction",
]

_CHARACTER_INSTRUCTION = [
  "one that closely fits expectations of this character's description",
  "one that pushes the boundaries of imagination on what this character can do",
  "one that ignores this character's preferred activities, putting them in novel situations",
]

_READING_LEVEL_GUIDELINES = {
  ReadingLevel.PRE_K: """The story should be suitable for a Pre-K reader.""",
  ReadingLevel.KINDERGARTEN:
  """The story should be suitable for a Kindergarten reader.""",
  ReadingLevel.FIRST:
  """The story should be suitable for a 1st Grade reader.""",
  ReadingLevel.SECOND:
  """The story should be suitable for a 2nd Grade reader.""",
  ReadingLevel.THIRD:
  """The story should be suitable for a 3rd Grade reader.""",
  ReadingLevel.FOURTH:
  """The story should be suitable for a 4th Grade reader.""",
  ReadingLevel.FIFTH:
  """The story should be suitable for a 5th Grade reader.""",
  ReadingLevel.SIXTH:
  """The story should be suitable for a 6th Grade reader.""",
}

# pylint: disable=line-too-long
_llm = llm_client.get_client(
  label="Story Prompt Generator",
  model=LlmModel.GEMINI_2_5_FLASH,
  temperature=1.0,
  system_instructions=[
    """As a best selling children's author, write a short prompt for a Pixar-style children's story.
The prompt should be 1 sentence and no more than 20 words.
Just mention the main character(s) by name. Do not describe them because the author already knows them.

Guidelines:
- The plot should be intentional, not by accidents.
- The plot should be uplifting, positive, and encourage good behavior.

Format your response as a JSON object with:
- A "story_prompt" field containing a single 1-sentence story prompt
"""
  ],
  response_schema={
    "type": "OBJECT",
    "properties": {
      "story_prompt": {
        "type": "STRING",
        "description": "1 sentence story prompt"
      },
    },
  },
)
# pylint: enable=line-too-long

_SUGGESTION_PROBABILITY = 0.5


def get_random_prompt(
  main_characters: list[models.Character],
  side_characters: list[models.Character],
  reading_level: int = ReadingLevel.THIRD.value,
) -> str | None:
  """Generates a random story prompt.

  Args:
    main_characters: The main characters in the story.
    side_characters: The side characters in the story.
    reading_level: Integer representing the reading level (0=Pre-K, 1=K, 2=1st, etc.)

  Returns: The main story prompt.
  """
  prompt_parts = []

  # Get reading level guidelines
  reading_level_enum = ReadingLevel.from_value(reading_level)
  reading_level_guidelines = _READING_LEVEL_GUIDELINES[reading_level_enum]
  prompt_parts.append(reading_level_guidelines)

  characters = main_characters + side_characters
  if characters:
    _add_characters(prompt_parts, characters, "Character")
    suggest_settings_probability = _SUGGESTION_PROBABILITY
  else:
    prompt_parts.append(
      "The main characters will be chosen by a separate process, "
      "so just write the prompt for the story setting/plot.")
    # Always suggest a setting if there are no characters
    suggest_settings_probability = 1.0

  _randomized(prompt_parts, "suggested setting", _SETTINGS,
              suggest_settings_probability)
  _randomized(prompt_parts, "suggested genre", _GENRES,
              _SUGGESTION_PROBABILITY)

  print("\n\n".join(prompt_parts))
  response = _llm.generate("\n\n".join(prompt_parts))

  try:
    result = json.loads(response.text)
    return result["story_prompt"]
  except json.JSONDecodeError:
    print(f"Error parsing prompt response: {response.text}")
    return None


# pylint: disable=line-too-long
def _add_characters(
  prompt_parts: list[str],
  characters: list[models.Character],
  character_type: str,
) -> None:
  """Adds the characters to the prompt parts.

  Args:
    prompt_parts: The list of prompt parts.
    characters: The list of characters.
    character_type: The type of character to add.
  """
  if len(characters) > 1:
    prompt_parts.append(
      "The story prompt should involve all of the given characters, with each playing a unique role suited to their individual characteristics."
    )

  for char in characters:
    char_lines = [f"{character_type}:"]
    if char.is_public:
      char_lines.append(
        "The story should be directly inspired by and perfectly suited to this character's description."
      )
    else:
      _randomized(char_lines, "story", _CHARACTER_INSTRUCTION, 0.7)
    char_lines.append(char.description_xml)
    prompt_parts.append("\n".join(char_lines))


def _randomized(
  prompt_parts: list[str],
  suggestion_type: str,
  options: list[str],
  probability: float,
) -> None:
  """Adds a randomized suggestion to the prompt parts.

  Args:
    prompt_parts: The list of prompt parts.
    suggestion_type: The type of suggestion to add.
    options: The list of options.
    probability: The probability of adding a suggestion.

  Returns: The updated list of prompt parts.
  """
  if random.random() < probability:
    prompt_parts.append(f"The {suggestion_type} is {random.choice(options)}.")
