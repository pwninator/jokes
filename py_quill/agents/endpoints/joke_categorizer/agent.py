"""Joke populator agent."""

from agents.jokes import categorizer_agent
from firebase_admin import initialize_app
from google.adk.agents import BaseAgent

app = initialize_app()

DEPLOYED_AGENT_ID = "9034260434923814912"


def get_root_agent() -> BaseAgent:
  """Get the root agent."""
  return categorizer_agent.get_joke_categorizer_agent()
