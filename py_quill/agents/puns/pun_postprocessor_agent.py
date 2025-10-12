"""Agent to postprocess puns."""
import dataclasses
import functools
import logging

from agents import constants
from agents.common_agents import parallel_multi_agent
from agents.common_agents.quill_llm_agent import QuillLlmAgent
from common import image_generation
from google.adk.agents import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types
from pydantic import BaseModel, ValidationError
from services.llm_client import LlmModel


class PunLine(BaseModel):
  """Model for a single line of a pun with its associated image data."""

  text: str
  """The text of this pun line."""

  image_description: str
  """Description of the image for this pun line."""

  image_prompt: str
  """Prompt used to generate the image for this pun line.
  This field should be left empty and will be populated later after generating the image."""

  image_url: str = ""
  """URL of the generated image for this line.
  This field should be left empty and will be populated later after generating the image."""


class Pun(BaseModel):
  """Model for a punny motivational saying."""

  phrase_topic: str | None
  """Topic of the saying/quote/phrase, e.g., 'badminton', 'inspiration', etc."""

  pun_theme: str
  """Theme of the pun, e.g. "cat", "capybara", "coffee", etc."""

  pun_word: str
  """The pun word used in the saying, e.g., "purr-fect"."""

  punned_word: str
  """The word that is being punned, e.g., "perfect"."""

  pun_lines: list[PunLine]
  """Lines of the motivational pun with their associated image data."""

  tags: list[str]
  """A list of 1-2 word strings that will be used to help search for jokes.
  They include the joke's themes and topics, including potentially multiple of
  each. E.g. for the joke 'why are giraffes slow to apologize? Because I'm
  takes them a long time to swallow their pride.', the tags could be 'giraffe'
  and 'apologies'. For 'what do panda ghosts say? Bam-boo!', the tags could be
  'panda', 'bamboo', 'ghost', and 'Halloween'."""

  for_kids: bool
  """A boolean indicating whether the joke is good for kids. This means the
  joke is not only appropriate, clean, positive, and wholesome, but also
  understandable by kids."""

  for_adults: bool
  """A boolean indicating whether the joke will be interesting for adults. This
  includes sophisticated and witty humor, and excludes jokes that are too
  simple or obvious."""

  seasonal: str | None = None
  """If the joke is related to a seasonal event, this should be the name of
  that event, e.g. 'Halloween', 'Super Bowl', etc. If the joke is not related
  to any events, this should be null."""

  pun_firestore_key: str | None = None
  """Firestore key of the pun, if any."""


def get_pun_postprocessor_agent(
  num_workers: int,
  input_var: str = constants.STATE_ITEMS_KEEP,
  output_var: str = constants.STATE_FINALIZED_PUNS,
) -> BaseAgent:
  """Gets a parallel agent that postprocesses puns."""

  return parallel_multi_agent.get_parallel_multi_agent(
    name="PunPostprocessor",
    description=
    "Agent that analyzes puns, extracting metadata, and generating the pun's image.",
    single_agent_fn=_get_single_pun_postprocessor_agent,
    num_workers=num_workers,
    input_var=input_var,
    output_var=output_var,
  )


def _get_single_pun_postprocessor_agent(
  i: int,
  input_key: str,
  output_key: str,
) -> BaseAgent:

  return QuillLlmAgent(
    name=f"PunPostprocessor_Worker{i:02d}",
    model=LlmModel.GEMINI_2_5_FLASH,
    generate_content_config=types.GenerateContentConfig(
      temperature=0.6,
      max_output_tokens=50000,
      top_p=0.95,
    ),
    planner=constants.PLANNER_THINKING,
    include_contents='none',  # Reads from state.
    output_schema=Pun,
    disallow_transfer_to_parent=True,  # Required when specifying output_schema
    disallow_transfer_to_peers=True,  # Required when specifying output_schema
    output_key=output_key,
    after_agent_callback=functools.partial(_generate_image_callback,
                                           output_key=output_key),
    description=
    "Agent that analyzes puns, extracting metadata, and generating the pun's image.",
    instruction=
    f"""You are a master artist who specializes in taking puns and turning them into beautiful, inspirational, funny, and super cute illustrations. Your task is to take the given pun, analyze and understand it, and write detailed illustration descriptions that will be used to generate images for each line of the pun.

## Illustration Description Guidelines:

The described illustrations should:
  * serve as visual aid to maximize the impact and humor of the pun
    * The first line sets up the joke, so it should be:
      1. create a sense of mystery and intrigue, teasing the viewer about the punchline but not giving it away
        * If applicable, drop a seemingly obvious bit misleading hint to make the punchline reveal more surprising. For example, for the joke "What goes black, white, black, white, black, white?", the first line could show a picture of a penguin or zebra, which are both black and white, but the punchline turns out to be "A panda rolling down a hill," which is an absurdly surprising reveal to maximize comedic impact.
      2. generally, should be relatively calm in mood
      3. super cute and wholesome to draw the viewer's attention
    * The last line is the punchline, so it should be:
      1. reveal the punchline in a way that is funny, surprising, and unexpected
      2. exciting, dramatic, and dynamic to sell the punchline
      3. also super cute and wholesome
  * be unbearably cute and funny. Describe character attributes to maximize cuteness and humor.
  * strive for simplicity, containing only the minimal objects/characters (ideally no more than 2-3) needed to set up and sell the joke
  * be relevant to both the phrase_topic and pun_theme
  * prominently display the text of the specific pun line
  * be consistent with the Creative Brief
  * conform to the purpose of the line. For example, for a line that sets up the joke, the image should NOT include any hints that give away the punchline.
    * Example: For the input ["what animal knows the best coffee shops?", "A coffee-bara!"], the main point of the punchline is coffee-bara/capybara, so the second line's image should include a capybara, but the first line's image should feature a DIFFERENT animal so it doesn't give away the punchline.
    * Example: For the input ["What do you call a royale giraffe?", "Your Highness!"], the setup line explicitly mentions a giraffe and the punchline's main point is the giraffe's height, so BOTH images should include a giraffe, but the first image should frame the giraffe in a way that does not accentuate its height.
  * appropriate for all ages
  * characters, scenes, objects, etc. that appear in multiple images should be described consistently (e.g. color, size, clothing, etc.)

## Core Task:

* Analyze the pun and understand its meaning and context. To do so, state the following:

  * phrase_topic: The topic of the entire phrase/saying/quote. This typically comes from the Creative Brief. If not, infer it from the pun.
  * pun_theme: The theme of the pun. This should come from both the Creative Brief and the pun itself.
  * pun_word: The pun word used in the saying. This word should appear exactly in the pun text, e.g. "purr-fect".
  * punned_word: The word that is being punned. It's the word that the reader expects. This word may appear in the pun text if it's a homograph, but often does not (e.g. "perfect").
  * tags: A list of 1-2 word strings that will be used to help search for jokes. They include the joke's themes and topics, including potentially multiple of each. All tags should be singular.
      * The tags will be used both as categories to organize jokes in an app, as well as for searching jokes, so include both broad tags like "dog", which will serve well as categories, as well as specific tags like "Dalmation" for searching.
      * Example: For the joke 'why are giraffes slow to apologize? Because I'm takes them a long time to swallow their pride.', the tags could be 'giraffe' and 'apologies'.
      * Example: For the joke 'what do panda ghosts say? Bam-boo!', the tags could be 'panda', 'bamboo', 'ghost', 'Halloween', and 'dad joke'.
      * Example: For the joke 'what did the Dalmation say after the meal? That hit the spots!', the tags could be 'Dalmation', 'dog', 'spots', and 'dad joke'.
  * for_kids: A boolean indicating whether the joke is good for kids. This means the joke is not only appropriate, clean, positive, and wholesome, but also simple and understandable by elementary school-aged children.
  * for_adults: A boolean indicating whether the joke will be interesting for adults. This includes sophisticated and witty humor, and excludes jokes that are too simple or obvious.
  * seasonal: If the joke is related to a seasonal event, this should be the name of that event, e.g. 'Halloween', 'Super Bowl', etc. This field will be used to find jokes for joke books for each event, so include all jokes suitable for such books. If the joke is not related to any events, this should be null.
      * Example: All jokes related to activities or monsters typically associated with Halloween, or pop culture references related to Halloween, should be labeled as 'Halloween'.
      * Example: All jokes related to Santa, his elves, holiday gifting, Christmas trees, or otherwise suitable for a Christmas joke book should be labeled as 'Christmas'.

* Write simple scene descriptions for EACH LINE of the pun. Each description will be used to generate a separate image. The described scenes should capture the specific line's meaning and context with the minimal elements needed to set up and sell the joke. Focus on being funny, super cute, and relevant to both the phrase_topic and pun_theme. Each description should include only:
  * The text of the specific pun line
  * The essential subject(s) needed for the joke
  * The minimal background/environment elements required
  * The mood/tone/emotion of the scene
  * A detailed description of every element in the scene
    * E.g. if the scene has a cat, describe the cat's breed, color, size, position, expression, etc.

## Inputs:

* Creative Brief: A paragraph defining the project's main subject, target audience, tone, and constraints.
* Pun to Analyze: The pun to be postprocessed.

## Output Format:

Output a JSON object with the following fields:
  * pun_lines: Array of objects, each containing:
    - text: The text of this pun line
    - image_description: The image description for this pun line
  * phrase_topic
  * pun_theme
  * pun_word
  * punned_word
  * tags
  * for_kids
  * for_adults
  * seasonal

## Example of the 2-line pun:

Input:
["Why did the cat become a chef?", "Because it was purr-fect at cooking!"]

Output:
{{
    "phrase_topic": "cooking",
    "pun_theme": "cat",
    "pun_word": "purr-fect",
    "punned_word": "perfect",
    "tags": ["cat", "cooking", "chef"],
    "for_kids": true,
    "for_adults": false,
    "seasonal": null,
    "pun_lines": [
        {{
          "text": "Why did the cat become a chef?",
          "image_description": "A cute orange tabby kitten wearing a tall white chef's hat, looking curious and determined",
        }},
        {{
          "text": "Because it was purr-fect at cooking!",
          "image_description": "The kitten is now standing next to a steaming pot, looking proud and satisfied",
        }}
      ]
}}

## Creative Brief:
{{{constants.STATE_CREATIVE_BRIEF}}}

## Pun to Analyze:
{{{input_key}}}
""")


def _generate_image_callback(
  callback_context: CallbackContext,
  output_key: str,
) -> None:
  """Generates images for each line of the pun."""

  pun_model_dict = callback_context.state.get(output_key)
  try:
    pun_model = Pun.model_validate(pun_model_dict)
  except ValidationError as e:
    logging.warning(f"Pun postprocessor input is not a valid Pun: {e}\n"
                    f"Input: {pun_model_dict}")
    return

  # Generate images for each pun line
  pun_data = [(pun_line.text, pun_line.image_description)
              for pun_line in pun_model.pun_lines]

  # On initial generation, always use low quality
  images = image_generation.generate_pun_images(pun_data, "low")

  # Update pun lines with generated images and collect LLM costs
  all_llm_costs = []
  for pun_line, image in zip(pun_model.pun_lines, images):
    if image and image.url:
      pun_line.image_url = image.url
      pun_line.image_description = image.original_prompt
      pun_line.image_prompt = image.final_prompt

      if image.generation_metadata and image.generation_metadata.generations:
        all_llm_costs.extend(
          dataclasses.asdict(generation)
          for generation in image.generation_metadata.generations)

  callback_context.state[output_key] = pun_model.model_dump()

  # Add all image generation costs to the LLM cost tracking
  llm_cost = callback_context.state.get(constants.STATE_LLM_COST, [])
  llm_cost.extend(all_llm_costs)
  callback_context.state[constants.STATE_LLM_COST] = llm_cost
