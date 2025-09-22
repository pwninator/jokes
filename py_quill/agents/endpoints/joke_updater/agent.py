"""Agent that updates jokes."""
from agents import constants
from agents.common_agents.quill_llm_agent import QuillLlmAgent
from agents.tools import firebase_tools
from google.adk.agents import BaseAgent


def get_joke_updater_agent() -> BaseAgent:
  """Get the joke updater agent."""

  return QuillLlmAgent(
    name="joke_updater",
    model=constants.FAST_LLM_MODEL,
    tools=[
      firebase_tools.get_joke_details,
      firebase_tools.update_joke,
    ],
    instruction="""You are a joke updater. The user will give you a joke id and instructions on how to update the joke. You should get that joke's details, then use the update_joke tool to update the joke according to the user's instructions.""")
