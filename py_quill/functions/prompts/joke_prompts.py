"""Prompt to generate jokes related to a story prompt."""

from typing import Any, Generator, List

from common import models
from services import llm_client
from services.llm_client import LlmModel

# Temperature setting for joke generation
_TEMPERATURE = 0.9

# Default number of jokes to request
_DEFAULT_NUM_JOKES = 30

_MIN_JOKE_LENGTH = 10

# LLM client for joke generation
_llm = llm_client.get_client(
  label="Joke Generation",
  model=LlmModel.GEMINI_2_5_FLASH,
  temperature=_TEMPERATURE,
  output_tokens=2000,
  system_instructions=[
    """You are a comedian specialized in reciting clean, appropriate jokes for children's books.
Your goal is to recite jokes related to themes, characters, or concepts from a given prompt.
DO NOT make up your own jokes. Just recite ones that are related to things in the prompt.
The jokes should be:

1. Clean and appropriate for young children
2. Not too dark or scary
3. Related to any element in the prompt
4. Of excellent quality
5. Funny and engaging for both children and adults

Each joke should be self-contained, suitable for inclusion in a children's book.
The jokes can be longer than one-liners, but should be fewer than 5 sentences.

Format each joke as a single separate line with a dash (-) prefix.
Make sure that each joke is entirely contained in a single line.

Prioritize joke quality first:
DO NOT make up your own jokes or try to change jokes to fit the prompt.
Just recite jokes that you already know, verbatim, if they are related to the prompt.
Don't force it if you can't find a joke that fits the prompt.
In that case, just recite other good jokes.

Example output:
- What is a robot's favorite snack? Computer chips!
- What do you get if you cross a hamster with a car? A fur-rari!
- etc.
"""
  ],
)


def generate_jokes(
  prompt: str,
  extra_log_data: dict[str, Any],
  num_jokes: int = _DEFAULT_NUM_JOKES,
) -> Generator[tuple[list[str], models.GenerationMetadata], None, None]:
  """Generate jokes related to a story prompt.

  Args:
      story_prompt: The prompt to generate jokes for
      num_jokes: Number of jokes to generate
      extra_log_data: Extra log data to include in the log

  Yields:
      Tuple of (list of jokes, generation metadata)
  """
  prompt_parts = [
    f"""Generate {num_jokes} funny, clean jokes related to elements in the following prompt:

Prompt:
{prompt}
"""
  ]
  # prompt_parts = ["Generate an image of a phoenix and a dragon"]

  # Initialize buffer for accumulating partial responses
  buffer = ""
  for response in _llm.stream(prompt_parts, extra_log_data=extra_log_data):
    # Add new text to buffer
    buffer += response.text_delta

    # Parse complete jokes from buffer, keeping any partial joke at the end
    jokes, buffer = parse_jokes(buffer, is_final=response.is_final)

    yield jokes, models.GenerationMetadata()


def parse_jokes(text: str, is_final: bool) -> tuple[List[str], str]:
  """Parse jokes from the LLM response text.

  Args:
      text: The response text from the LLM
      is_final: Whether this is the final chunk of text

  Returns:
      Tuple of (list of complete jokes, remaining partial text)
  """
  # Split by lines
  lines = text.split('\n')

  # Separate lines into those to process now and those to buffer for later
  if not lines:
    # Handle empty input
    return [], ""

  if is_final:
    lines_to_process = lines
    text_to_buffer = ""
  else:
    lines_to_process = lines[:-1]
    text_to_buffer = lines[-1]

  # Process lines that we can safely parse now
  jokes = []
  for line in lines_to_process:
    line = line.strip()
    if line.startswith('-') or line.startswith('*'):
      # Extract the joke by removing the bullet/dash and trimming whitespace
      joke = line[1:].strip()
      if joke and len(
          joke
      ) > _MIN_JOKE_LENGTH:  # Ensure it's not an empty line or too short
        jokes.append(joke)

  return jokes, text_to_buffer
