"""Jokes agent."""

import json

from agents import agents_common, constants
from agents.common_agents import creative_brief_agent
from agents.common_agents.quill_llm_agent import QuillLlmAgent
from agents.puns import (pun_evaluator_agent, pun_expansion_agent,
                         pun_postprocessor_agent)
from google.adk.agents import BaseAgent, SequentialAgent
from google.genai import types
from pydantic import BaseModel
from services.llm_client import LlmModel

_NUM_JOKE_CANDIDATES = 3


class PunnyJokesRawOutput(BaseModel):
  """Output model for the Punny Jokes Agent."""

  jokes: list[str]
  """List of generated punny jokes."""


def get_punny_jokes_agent() -> BaseAgent:
  """Get the punny jokes agent."""
  return QuillLlmAgent(
    name="PunnyJokes",
    model=LlmModel.GEMINI_2_5_FLASH,
    generate_content_config=types.GenerateContentConfig(
      temperature=1.0,
      max_output_tokens=8000,
      top_p=0.95,
    ),
    planner=constants.PLANNER_NO_THINKING,
    include_contents='none',  # Reads from state.
    output_key=constants.STATE_ITEMS_NEW,
    output_schema=PunnyJokesRawOutput,
    disallow_transfer_to_parent=True,  # Required when specifying output_schema
    disallow_transfer_to_peers=True,  # Required when specifying output_schema
    description="Generates a list of punny jokes.",
    instruction=
    f"""You are an expert writer of punny jokes. Your task is to write exactly {_NUM_JOKE_CANDIDATES} punny jokes using the given creative brief.

## Guidelines:
Your jokes should be punny, clever, and convey a positive message. They should be suitable for a wide audience of all ages, and can be used in various contexts, such as social media posts, posters, or greeting cards (unless stated otherwise in the Creative Brief). Pay careful attention to the Creative Brief and make sure that all of your jokes are aligned with it.

## Input:
* Creative Brief: A paragraph defining the main subject, target audience, tone, and constraints. Strictly follow its instructions.
* Pun Idea Map: An analysis breaking down the main topic into key components, associated ideas, and possible puns. Use this to inspire your jokes. Not all of the ideas/puns in the map are good, so use your judgement to pick the best ones.

## Output Format:
Output only a plain-text list of exactly {_NUM_JOKE_CANDIDATES} jokes. Each joke must be on a new line. Do not add any titles, numbering, introductions, or explanations.

## Creative Brief:
{{{constants.STATE_CREATIVE_BRIEF}}}

## Pun Idea Map:
{{{constants.STATE_PUN_IDEA_MAP}}}

Below are some excellent puns you have already generated before on other topics. Use them as examples, but do not repeat them.

{{{constants.STATE_EXISTING_DATA}}}
""",
  )


def get_joke_generator_root_agent() -> BaseAgent:
  """Get the root agent."""
  return SequentialAgent(
    name="PunnyJokesMultiAgentPipeline",
    sub_agents=[
      creative_brief_agent.get_creative_brief_agent(),
      pun_expansion_agent.get_pun_brainstormer_agent(),
      get_punny_jokes_agent(),
      pun_evaluator_agent.get_pun_evaluator_agent(
        input_list_fn=lambda x: x["jokes"]),
      pun_postprocessor_agent.get_pun_postprocessor_agent(
        num_workers=_NUM_JOKE_CANDIDATES),
    ],
    description="Manages the end-to-end punny joke generation process.",
  )


if __name__ == "__main__":
  inputs = {
    constants.STATE_USER_INPUT:
    """
Write jokes using puns about computer engineering.
""",
    constants.STATE_EXISTING_DATA:
    """
Why did the lion break up with his girlfriend? He caught her being a cheetah!
Why did the cat get sent to its room? It had a real cat-titude problem!
Why did the cat put off chasing the mouse until tomorrow? Because he was an expert in pro-cat-stination!
""",
  }

  output, state, _ = agents_common.run_agent(
    agent=get_joke_generator_root_agent(), inputs=inputs)
  print(f"""

Final State:
{json.dumps(state.get(constants.STATE_FINALIZED_PUNS, []), indent=2)}
""")
