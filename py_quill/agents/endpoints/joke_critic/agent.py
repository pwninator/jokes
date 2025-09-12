"""Joke critic agent."""

from agents import app_init
from agents.common_agents import creative_brief_agent
from agents.jokes import punny_joke_agents
from google.adk.agents import BaseAgent, SequentialAgent

# app_init.init()

DEPLOYED_AGENT_ID = "792888621114851328"


def get_root_agent() -> BaseAgent:
  """Get the root agent."""
  return SequentialAgent(
    name="JokeCritic",
    sub_agents=[
      creative_brief_agent.get_creative_brief_agent(),
      punny_joke_agents.get_joke_writer_agent(),
      punny_joke_agents.get_joke_critic_agent(),
    ],
    description="Critiques and improves punny jokes.",
  )
