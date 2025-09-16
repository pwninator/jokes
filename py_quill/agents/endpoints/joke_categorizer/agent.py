"""Joke populator agent."""

from agents.jokes import categorizer_agent
from google.adk.agents import BaseAgent

DEPLOYED_AGENT_ID = "9034260434923814912"


def get_root_agent() -> BaseAgent:
  """Get the root agent."""
  return categorizer_agent.get_joke_categorizer_agent()
