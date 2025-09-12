"""Constants for the Jokes Agents."""

from google.adk.planners import BuiltInPlanner, PlanReActPlanner
from google.genai import types
from services import llm_client

LLM_MODEL = llm_client.LlmModel.GEMINI_2_5_FLASH

# Common State Keys
STATE_USER_INPUT = "user_input"
STATE_EXISTING_DATA = "existing_data"
STATE_CREATIVE_BRIEF = "creative_brief"
STATE_PUN_IDEA_MAP = "pun_idea_map"
STATE_CRITIQUE = "critique"
STATE_ITEMS_NEW = "items_new"
STATE_ITEMS_KEEP = "items_keep"
STATE_ITEMS_IMPROVE = "items_improve"
STATE_ITEMS_DISCARD = "items_discard"
STATE_LLM_COST = "llm_cost"

# Joke State Keys
STATE_JOKE_SEEDS = "joke_seeds"

# Pun State Keys
STATE_FINALIZED_PUNS = "finalized_puns"

# Planners
PLANNER_NO_THINKING = BuiltInPlanner(thinking_config=types.ThinkingConfig(
  thinking_budget=0, ), )
PLANNER_THINKING = BuiltInPlanner(
  thinking_config=types.ThinkingConfig(
    # thinking_budget=4000,
    include_thoughts=False, ), )
PLANNER_REACT = PlanReActPlanner()

# Agent Deployment Constants
# https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/deploy#configure-agent
AGENT_DEPLOYMENT_REQUIREMENTS = "requirements.txt"
AGENT_DEPLOYMENT_EXTRA_PACKAGES = [
  "agents",
  "common",
  "services",
]
AGENT_DEPLOYMENT_ENV_VARS = None
AGENT_DEPLOYMENT_GCS_DIR_NAME = None
