"""Joke updater agent."""

from agents.jokes import updater_agent
from google.adk.agents import BaseAgent

DEPLOYED_AGENT_ID = None


def get_root_agent() -> BaseAgent:
  """Get the root agent."""
  return updater_agent.get_joke_updater_agent()
