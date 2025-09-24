"""Agent deployment.

Run with:

python -m agents.endpoints.joke_updater.deploy
"""

from agents import app_init, constants
from vertexai import agent_engines

from . import agent

app_init.init()

agent_to_deploy = agent.get_root_agent()

kwargs = {
  "agent_engine": agent_to_deploy,
  "requirements": constants.AGENT_DEPLOYMENT_REQUIREMENTS,
  "extra_packages": constants.AGENT_DEPLOYMENT_EXTRA_PACKAGES,
  "gcs_dir_name": constants.AGENT_DEPLOYMENT_GCS_DIR_NAME,
  "display_name": agent_to_deploy.name,
  "description": "Agent that updates jokes.",
  "env_vars": constants.AGENT_DEPLOYMENT_ENV_VARS,
}

remote_agent = agent_engines.create(**kwargs)
