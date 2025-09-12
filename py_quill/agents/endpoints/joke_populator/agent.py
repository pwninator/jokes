"""Joke populator agent."""

from agents import app_init, constants
from agents.common_agents import creative_brief_agent
from agents.puns import pun_postprocessor_agent
from google.adk.agents import BaseAgent, SequentialAgent

# app_init.init()

DEPLOYED_AGENT_ID = "7587835296398442496"


def get_root_agent() -> BaseAgent:
  """Get the root agent."""
  return SequentialAgent(
    name="JokePopulator",
    sub_agents=[
      creative_brief_agent.get_creative_brief_agent(),
      pun_postprocessor_agent.get_pun_postprocessor_agent(
        num_workers=1,
        input_var=constants.STATE_ITEMS_NEW,
        output_var=constants.STATE_FINALIZED_PUNS,
      ),
    ],
    description="Populates jokes with metadata and images.",
  )
