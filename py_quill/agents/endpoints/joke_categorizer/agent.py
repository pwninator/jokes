"""Joke populator agent."""

from agents.jokes import categorizer_agent
from google.adk.agents import BaseAgent

# app_init.init()

DEPLOYED_AGENT_ID = ""


def get_root_agent() -> BaseAgent:
  """Get the root agent."""
  return categorizer_agent.get_joke_categorizer_agent()
