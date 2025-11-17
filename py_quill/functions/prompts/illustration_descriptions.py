"""LLM prompt for generating illustration descriptions."""

from typing import Any

from common import models
from services import llm_client
from services.llm_client import LlmModel

# pylint: disable=line-too-long
_all_illustrations_llm = llm_client.get_client(
  label="Illustration Descriptions",
  model=LlmModel.GEMINI_2_5_FLASH,
  system_instructions=[
    """You are an expert art director helping to create illustrations for a humorous children's book.
I will provide you with:
1. The story text for context
2. Descriptions of the characters that may appear in the illustrations

Your task is to write detailed descriptions for the illustrations needed for the book.

First, write a description of the book's cover illustration featuring ONLY the main character
in an engaging, humorous scene that captures the spirit of the story.
The story is a comedy, and that should come across in the cover illustration.
The title, tagline, and character name of the book will be displayed separately and should NOT be included in the illustration.

Then, write a description for an illustration for each page of the story.
Instructions on how to create each page's illustration:
  1. First, choose the most important scene from the page. It should be a humorous scene, either a major reveal or a humorous action/interaction.
  2. Choose the ONE character that is most central to the scene.
  3. Illustrate the character in a humorous way that complements the text.

Additional instructions:
  - Strict Character Limit: Illustrations must NEVER contain more than one character.
  - Prioritize Character & Scene Variation: Across the book, aim to illustrate different characters and avoid repetitive poses or scenes.
    When multiple character choices are valid (following priority rules), select the character least illustrated elsewhere.
  - Use the provided character descriptions to ensure visual consistency across all illustrations
  - Create engaging and colorful compositions suitable for children
  - Ensure a clear focal point and visual hierarchy in each image
  - Include specific details about colors, lighting, perspective, and mood
  - Avoid any inappropriate content (violence, gore, drugs, etc.)
  - Each illustration's description should be around 3 sentences
  - Illustrations should NOT include any text

Respond in the following format:

COVER ILLUSTRATION:
[Description of the cover illustration featuring only the main character]

PAGE 1 ILLUSTRATION:
[Description of the illustration for page 1]

PAGE 2 ILLUSTRATION:
[Description of the illustration for page 2]

...and so on for each page.
"""
  ],
  temperature=0.2,
  output_tokens=1000,
)

_all_illustrations_llm = llm_client.get_client(
  label="Illustration Refinement",
  model=LlmModel.GEMINI_2_5_FLASH,
  system_instructions=[
    """You are a visual description generator. Given a base scene description (which may contain character names) and character descriptions, create a purely visual description of the scene suitable for an image generator. **Crucially, remove character names *only if* their description is provided**, describing figures based on their provided descriptions.

**Rules:**

1.  **Handle Names:** If a character name appears in the base description **and** a corresponding character description is provided, replace the name with the visual description (e.g., "Alice" becomes "a 5 year old girl with..."). If a name appears but **no** corresponding description is provided, leave the name as-is in the output (see Example 7). Focus on visual attributes from provided descriptions.
2.  **Describe Visual Elements:** Combine details from the base description and relevant character descriptions to create a coherent visual scene. Include details about actively present figures and relevant items.
3.  **Describe Item Attributes:** If an item associated with a character is mentioned (e.g., "Alice's dress"), describe the item using relevant attributes from the character's description (e.g., "a red dress"), even if the character isn't present. Remove the possessive name.
4.  **Prioritize Base Description:** If the base description provides specific visual details (e.g., "wearing her blue shirt") that conflict with the general character description, **use the base description details**.
5.  **Ignore Unmentioned Characters/Details:** Do not invent characters or details not implied by the input. Only use the provided character descriptions.

**Shared Character Descriptions for Examples:**

* **Alice:** A 5 year old girl with long, straight blond hair, blue eyes, wears a red dress.
* **Bob:** A tall man, brown beard, green shirt, carries a backpack.
* **Charlie:** A small fluffy white dog, floppy ears.
* **David:** An old wizard, long white beard, blue robe, pointy hat.

**Examples (using shared descriptions above):**

**Example 1 (Basic):**

* Base Image Description: "Alice steps onto the staircase."
* **Expected Output:** "A 5 year old girl with long, straight blond hair, blue eyes, wearing a red dress, steps onto the staircase."

**Example 2 (Multiple Present):**

* Base Image Description: "Alice, Bob, and Charlie stand near the fountain."
* **Expected Output:** "A 5 year old girl with long, straight blond hair, blue eyes, wearing a red dress, a tall man with a brown beard, green shirt, carrying a backpack, and a small fluffy white dog with floppy ears stand near the fountain."

**Example 3 (Conflict):**

* Base Image Description: "Alice, wearing her blue shirt, looks out the window."
* **Expected Output:** "A 5 year old girl with long, straight blond hair, blue eyes, wearing her blue shirt, looks out the window."

**Example 4 (Passive Mention - Item Only):**

* Base Image Description: "Bob picked up Alice's small doll."
* **Expected Output:** "A tall man with a brown beard, green shirt, carrying a backpack, picked up a small doll."

**Example 5 (Indirect Presence):**

* Base Image Description: "Bob touched the reflection of Alice in the mirror."
* **Expected Output:** "A tall man with a brown beard, green shirt, carrying a backpack, touched the reflection of a 5 year old girl with long, straight blond hair, blue eyes, wearing a red dress, in the mirror."

**Example 6 (Passive Mention - Include Item Attribute):**

* Base Image Description: "Bob picked up Alice's dress."
* **Expected Output:** "A tall man with a brown beard, green shirt, carrying a backpack, picked up a red dress."

**Example 7 (Name without Description):**

* Base Image Description: "Alice and Merlin watch the sunset."
* **Expected Output:** "A 5 year old girl with long, straight blond hair, blue eyes, wearing a red dress, and Merlin watch the sunset."

"""
  ],
  temperature=0.1,
)
# pylint: enable=line-too-long


def refine_illustration_description(
  base_description: str,
  character_descriptions: dict[str, str],
  extra_log_data: dict[str, Any],
) -> str:
  """Refine the illustration description by adding relevant details.

  Args:
    base_description: The base image description
    character_descriptions: Map of character names to their visual descriptions
    extra_log_data: Extra log data to include in the log

  Returns:
    Refined illustration description
  """
  prompt_parts = [f"""
Base Image Description:
{base_description}
"""]

  for name, char_description in character_descriptions.items():
    prompt_parts.append(f"""
Character Description:
{name}: {char_description}
""")

  response = _all_illustrations_llm.generate(prompt_parts,
                                             extra_log_data=extra_log_data)
  return response.text


def generate_all(
  story_pages: list[models.StoryPageData],
  main_character_description: tuple[str, str],
  supporting_character_descriptions: dict[str, str],
) -> tuple[str, list[str], models.SingleGenerationMetadata]:
  """Generate descriptions for the cover and all pages of the story in a single LLM call.

  This approach ensures visual consistency across all illustrations.

  Args:
      story_pages: List of story page data objects containing text and illustration descriptions
      main_character_description: Tuple of (character_name, description) for the main character
      supporting_character_descriptions: Map of character names to their visual descriptions

  Returns:
      Tuple of:
        - Cover illustration description (string)
        - List of page illustration descriptions (list of strings)
        - Generation metadata for the single LLM call
  """
  # Extract main character info
  main_character_name, main_character_desc = main_character_description

  # Build character descriptions section
  supporting_char_descriptions_list = []
  for name, desc in supporting_character_descriptions.items():
    # Remove newlines from description
    desc = desc.replace("\n", " ").strip()
    if not desc:
      continue
    supporting_char_descriptions_list.append(f"{name}: {desc}")

  supporting_character_desc_text = ""
  if supporting_char_descriptions_list:
    supporting_character_desc_text = "Supporting characters:\n" + \
        "\n".join(supporting_char_descriptions_list)

  # Build story context from pages
  story_context = "\n\n".join(
    [f"PAGE {i+1}:\n{page.text}" for i, page in enumerate(story_pages)])

  prompt_parts = [
    f"""
Story context:
{story_context}

Main character: {main_character_name}
{main_character_desc}
{supporting_character_desc_text}

Please create illustration descriptions for the cover and each page of this children's book.
"""
  ]

  response = _all_illustrations_llm.generate(prompt_parts)

  # Extract cover description
  cover_description = ""
  if "COVER ILLUSTRATION:" in response.text:
    parts = response.text.split("COVER ILLUSTRATION:", 1)
    cover_parts = parts[1].split("PAGE 1 ILLUSTRATION:", 1)
    cover_description = cover_parts[0].strip()

  # Extract page descriptions
  page_descriptions = []
  for i, _ in enumerate(story_pages):
    page_marker = f"PAGE {i+1} ILLUSTRATION:"
    next_page_marker = f"PAGE {i+2} ILLUSTRATION:" if i < len(
      story_pages) - 1 else None

    if page_marker in response.text:
      parts = response.text.split(page_marker, 1)
      if next_page_marker and next_page_marker in parts[1]:
        page_parts = parts[1].split(next_page_marker, 1)
        page_description = page_parts[0].strip()
      else:
        page_description = parts[1].strip()
        if i < len(story_pages) - 1:
          # If this isn't the last page but there's no next marker,
          # we might need to handle this differently
          page_description = page_description.split("\n\n", 1)[0].strip()

      page_descriptions.append(page_description)

  # Print the result for debugging
  print(f"Generated {len(page_descriptions)} page descriptions and "
        f"{1 if cover_description else 0} cover description")

  return cover_description, page_descriptions, response.metadata
