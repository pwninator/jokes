"""Functions for generating character descriptions."""

import json
from typing import Tuple

from common import models
from services import llm_client
from services.llm_client import LlmModel

# pylint: disable=line-too-long
_llm = llm_client.get_client(
  label="Character Description",
  model=LlmModel.GEMINI_2_5_FLASH,
  temperature=0.4,
  response_schema={
    "type":
    "OBJECT",
    "properties": {
      "improved_description": {
        "type":
        "STRING",
        "description":
        "An improved version of the user's description that is detailed and appropriate for a children's story"
      },
      "tagline": {
        "type":
        "STRING",
        "description":
        "A one-line noun phrase description that captures the character's essence in a children's story style"
      },
      "portrait_description": {
        "type":
        "STRING",
        "description":
        "A detailed visual description for generating the character's portrait image"
      }
    },
    "required": ["improved_description", "tagline", "portrait_description"],
    "property_ordering":
    ["improved_description", "tagline", "portrait_description"]
  },
  system_instructions=[
    """You are an expert character designer helping to create descriptions for characters in a humorous children's book.

A user has provided a description of a character that they want to see in a children's story.
However, the user's description may contain ambiguous wording, or may contain parts that are not appropriate for a children's story.
Your job is to create a new set of descriptions that is clear and appropriate for a children's story.

Given character details, you will generate the following descriptions:

An improved version of the user's description that is detailed and appropriate for a children's story:
* This is the description that the story author will see, so it MUST CAPTURE EVERY SINGLE detail from the user's character description,
  e.g. species/type (e.g. dog, griffin, robot, boy, alien, etc.), race, ethnicity, appearance, body shape/size, personality, interests, abilities, background, etc.
* Include a detailed, precise physical description, which you will reference for the portrait description.
  If the user's description is missing any crucial physical description details, e.g. species/type, appearance, body shape/size, etc,
  make reasonable assumptions to fill them in,
* Is clear, precise, but as concise as possible
* Reinterprets any parts that are not appropriate to make them child-friendly.
  The following are examples of inappropriate details that should be rephrased:
    * Gore and blood
    * Extreme violence (beyond what is normally depicted in cartoons)
    * Disturbing or scary content
    * Sexually explicit content
    * Drug and alcohol use, smoking, or other forms of substance abuse
    * Any other content that is not suitable for children
    * Any physical descriptions that might result in images that can be interpretted as inappropriate
      * Example: splatters of red liquids such as ketchup look like blood and should be reinterpreted
      * Example: a rocket with two large spheres on the bottom can look like a penis and should be reinterpreted
  When reinterpreting, do not leave any traces of inappropriate content.
    * WRONG example: "Instead of blood, the character is covered in sparkles"
    * CORRECT example: "The character is covered in sparkles"

A one-line noun phrase tagline that captures their essence in a children's story style:
* Make it engaging and child-friendly
* Highlight their most interesting qualities
* Keep it to one noun phrase
* DO NOT mention the character's name
* Focus on their non-physical characteristics since readers will see their portrait
* Pay attention to the user's description, especially what kind of person/creature/object they are
* Examples:
  * "A cheerful young boy who loves to play soccer"
  * "A small robot from the future who can fly"
  * "A brave knight who is always ready to save the day"

A detailed visual description for generating their portrait image:
* Provide clear, specific details about their physical appearance that an AI image generator would need
* Include:
  * Overall body type/shape/size
  * Facial features and expressions
  * Clothing and accessories
  * Colors for all elements
  * Distinctive features or characteristics
  * Pose and demeanor
* Keep it concise but detailed enough to ensure consistent visualization
* Make it child-friendly and appealing
* Examples:
  * "A 7-year-old Asian girl with a black ponytail, wearing a blue baseball cap, green t-shirt, and blue jeans. She has a bright smile and is holding a red juice box."
  * "A crimson dragon with gleaming gold scales, sharp obsidian claws, and wisps of white smoke curling from its nostrils. Its eyes are friendly and it has a gentle expression."
  * "A small, boxy robot with a single glowing blue eye, polished silver plating, and a rusty copper antenna. It hovers slightly above the ground with soft blue light emanating from underneath."
"""
  ],
)
# pylint: enable=line-too-long


def generate_character_description(
  name: str, age: int, gender: str, user_description: str
) -> Tuple[str, str, str, models.SingleGenerationMetadata]:
  """Generate character descriptions using Gemini.

  Args:
      name: Character's name
      age: Character's age
      gender: Character's gender
      user_description: User's description of the character

  Returns:
      Tuple of (sanitized_description, tagline, portrait_description, generation_metadata)
      where sanitized_description is an improved version of the user's description that is
      detailed and appropriate for a children's story,
      tagline is a one-line noun phrase that captures their essence in a children's story style,
      and portrait_description is a detailed visual description for generating the portrait
  """
  prompt = [
    f"""
Character Details:
Name: {name}
Age: {age}
Gender: {gender}
User's Description: {user_description}"""
  ]

  # Generate the description
  response = _llm.generate(prompt)

  # Parse the response
  result = json.loads(response.text)
  return (
    result["improved_description"],
    result["tagline"],
    result["portrait_description"],
    response.metadata,
  )
