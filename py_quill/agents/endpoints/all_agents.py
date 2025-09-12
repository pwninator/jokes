"""All agents."""

from typing import Callable

from agents.endpoints.joke_critic import agent as joke_critic
from agents.endpoints.joke_populator import agent as joke_populator
from common import utils
from google.adk.agents import BaseAgent
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

# Lazily initialized ADK apps
_ADK_APPS_BY_AGENT_NAME = {}


def get_joke_critic_agent_adk_app() -> agent_engines.AgentEngine:
  """Get the ADK app for the joke critic agent."""
  return _get_agent_adk_app(
    agent_name="JokeCritic",
    get_local_agent_fn=joke_critic.get_root_agent,
    remote_agent_id=joke_critic.DEPLOYED_AGENT_ID,
  )


def get_joke_populator_agent_adk_app() -> agent_engines.AgentEngine:
  """Get the ADK app for the joke populator agent."""
  return _get_agent_adk_app(
    agent_name="JokePopulator",
    get_local_agent_fn=joke_populator.get_root_agent,
    remote_agent_id=joke_populator.DEPLOYED_AGENT_ID,
  )


def _get_agent_adk_app(
  agent_name: str,
  get_local_agent_fn: Callable[[], BaseAgent],
  remote_agent_id: str,
) -> agent_engines.AgentEngine:
  """Get the ADK app for the agent."""

  if agent_name not in _ADK_APPS_BY_AGENT_NAME:
    if utils.is_emulator():
      agent_adk_app = AdkApp(agent=get_local_agent_fn())
    else:
      agent_adk_app = agent_engines.get(remote_agent_id)

    _ADK_APPS_BY_AGENT_NAME[agent_name] = agent_adk_app

  return _ADK_APPS_BY_AGENT_NAME[agent_name]
