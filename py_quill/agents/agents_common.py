"""Common functions for agents."""

import json
import pprint
import time
from typing import Any

from agents import constants
from common import models
from firebase_functions import logger
from google.adk.agents import BaseAgent
from google.adk.agents.base_agent import (AfterAgentCallback,
                                          BeforeAgentCallback)
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.llm_agent import AfterModelCallback, BeforeModelCallback
from google.adk.models import LlmResponse
from google.genai import types
from services.llm_client import LlmModel, get_client
from vertexai.preview.reasoning_engines import AdkApp


def run_agent(
  inputs: str | dict[str, Any],
  agent: BaseAgent | None = None,
  adk_app: Any | None = None,
  user_id: str = "default_user",
) -> tuple[str | None, dict[str, Any], models.GenerationMetadata]:
  """Runs an agent with the given inputs.
  
  Args:
    agent: The agent to run.
    inputs: The inputs to the agent.

  Returns:
    A tuple of the final output, final state, and generation metadata.
  """

  start_time = time.perf_counter()
  input_str = inputs if isinstance(inputs, str) else json.dumps(inputs)

  final_output = None
  final_state = {}

  adk_app = adk_app if adk_app else AdkApp(agent=agent)
  for event in adk_app.stream_query(user_id=user_id, message=input_str):
    (
      final_output,
      state_delta,
    ) = parse_event(event)
    final_state.update(state_delta)

  generation_metadata = models.GenerationMetadata()
  for generation_dict in final_state.get(constants.STATE_LLM_COST, []):
    generation_metadata.add_generation(
      models.SingleGenerationMetadata(**generation_dict))

  elapsed_time = time.perf_counter() - start_time
  costs_by_model_parts = []
  costs_by_label_parts = []
  for model_name, (
      count, cost) in generation_metadata.counts_and_costs_by_model.items():
    costs_by_model_parts.append(f"{model_name}: ${cost:.4f} ({count})")
  for label, (count,
              cost) in generation_metadata.counts_and_costs_by_label.items():
    costs_by_label_parts.append(f"{label}: ${cost:.4f} ({count})")

  print(
    f"""
Costs by model:
{"\n".join(costs_by_model_parts)}

Costs by Agent:
{"\n".join(costs_by_label_parts)}

Total Cost: ${generation_metadata.total_cost:.4f}
Elapsed Time: {elapsed_time:.1f}s
""",
    flush=True,
  )

  return final_output, final_state, generation_metadata


def ensure_state_from_user_content(callback_context: CallbackContext) -> None:
  """BeforeAgentCallback that ensures that the state is set from the user content."""

  if not callback_context.user_content or not callback_context.user_content.parts:
    print("No user content found in callback context.", flush=True)
    return

  user_content_str = "".join(part.text
                             for part in callback_context.user_content.parts
                             if part.text).strip()

  try:
    user_content_data = json.loads(user_content_str)
  except json.JSONDecodeError:
    # Set the entire user content as user input
    user_content_data = {constants.STATE_USER_INPUT: user_content_str}

  if not isinstance(user_content_data, dict):
    raise ValueError(
      f"User content must be a dictionary, got {type(user_content_data)}: {user_content_data}"
    )

  for key, value in user_content_data.items():
    if key in callback_context.state:
      print(f"State key '{key}' already exists, skipping update.", flush=True)
    else:
      callback_context.state[key] = value.strip() if isinstance(value,
                                                                str) else value
      print(f"Setting state key '{key}' to value: {value}", flush=True)


def skip_agent_if_state_key_present(state_key: str) -> BeforeAgentCallback:
  """Gets a BeforeAgentCallback that skips the agent if the state key is present."""

  def callback(callback_context: CallbackContext) -> types.Content | None:
    """Callback to skip the agent if the state key is present."""

    if callback_context.state.get(state_key):
      # If the state key is present, skip the agent.
      return LlmResponse(content=None)

    return None

  return callback


def parse_event(
  event: dict[str, Any],
  print_actions: bool = False,
) -> tuple[str, dict[str, Any]]:
  """Parses an agent event.

  Returns:
    Tuple of [response str, state_delta]
  """
  agent_name = event["author"]

  logger.info(f"\n\n\nEvent: {event}\n\n\n")

  if "content" in event:
    if "parts" in event["content"]:
      text = "".join(p["text"] for p in event["content"]["parts"]
                     if "text" in p).strip()
      try:
        # Pretty print if it's valid JSON
        output_data = json.loads(text)
        text = pprint.pformat(output_data, width=120, sort_dicts=False)
      except json.JSONDecodeError:
        pass
    else:
      text = event["content"]

  else:
    text = pprint.pformat(event, width=120, sort_dicts=False)

  actions = event.get("actions", {})
  actions_str = pprint.pformat(actions, width=120, sort_dicts=False)

  state_delta = actions.get("state_delta", {})

  if metadata_list := state_delta.get(constants.STATE_LLM_COST):
    # This event's generation metadata is the last one
    single_generation_metadata = models.SingleGenerationMetadata(
      **(metadata_list[-1]))

    model_name = single_generation_metadata.model_name
    tokens_str = ", ".join(
      f"{k}: {v}" for k, v in single_generation_metadata.token_counts.items())
    cost = single_generation_metadata.cost

    usage_str = f"(Model: {model_name}, Cost: ${cost:.4f} - {tokens_str})"
  elif "usage_metadata" in event:
    # Make sure that usage metadata is always processed
    raise ValueError(f"{agent_name} has unprocessed usage metadata: {event}")
  else:
    usage_str = ""

  print(f"""
===========================================================================
Agent: {agent_name} {usage_str}
===========================================================================
{text}
""",
        flush=True)
  if print_actions:
    print(f"Actions:\n{actions_str}", flush=True)

  return text, state_delta


def get_llm_cost(
  input_tokens: int,
  thinking_tokens: int,
  cached_tokens: int,
  output_tokens: int,
  model_name: str,
) -> float:
  """Calculates the LLM cost."""
  try:
    llm_model_enum_member = LlmModel(model_name)
  except ValueError:
    logger.error(
      f"Invalid model_name '{model_name}' not found in LlmModel enum. Falling back to GEMINI_2_5_FLASH for cost calculation."
    )
    llm_model_enum_member = LlmModel.GEMINI_2_5_FLASH

  # TODO: Refactor LlmClient so that we can calculate the cost without
  # creating a client instance.
  client = get_client(label="cost_calculation",
                      model=llm_model_enum_member,
                      temperature=0)
  token_counts = {
    'prompt_tokens': input_tokens,
    'cached_prompt_tokens': cached_tokens,
    'output_tokens': output_tokens + thinking_tokens,
  }
  # Filter out zero counts as llm_client's _calculate_generation_cost might expect non-empty values if keys are present
  # or some models might not define costs for all three (e.g., no thinking_tokens cost)
  filtered_token_counts = {k: v for k, v in token_counts.items() if v > 0}

  if not filtered_token_counts:
    # If all token counts are zero, the cost is zero.
    return 0.0
  return client.calculate_generation_cost(filtered_token_counts)


def add_before_model_callback(agent: BaseAgent,
                              callback: BeforeModelCallback) -> None:
  """Adds a before model callback to an agent."""
  if not agent.before_model_callback:
    agent.before_model_callback = callback
  elif isinstance(agent.before_model_callback, list):
    agent.before_model_callback.append(callback)
  else:
    agent.before_model_callback = [
      agent.before_model_callback,
      callback,
    ]


def add_after_model_callback(agent: BaseAgent,
                             callback: AfterModelCallback) -> None:
  """Adds a after model callback to an agent."""
  if not agent.after_model_callback:
    agent.after_model_callback = callback
  elif isinstance(agent.after_model_callback, list):
    agent.after_model_callback.append(callback)
  else:
    agent.after_model_callback = [
      agent.after_model_callback,
      callback,
    ]


def add_before_agent_callback(agent: BaseAgent,
                              callback: BeforeAgentCallback) -> None:
  """Adds a before agent callback to an agent."""
  if not agent.before_agent_callback:
    agent.before_agent_callback = callback
  elif isinstance(agent.before_agent_callback, list):
    agent.before_agent_callback.append(callback)
  else:
    agent.before_agent_callback = [
      agent.before_agent_callback,
      callback,
    ]


def add_after_agent_callback(agent: BaseAgent,
                             callback: AfterAgentCallback) -> None:
  """Adds a after agent callback to an agent."""
  if not agent.after_agent_callback:
    agent.after_agent_callback = callback
  elif isinstance(agent.after_agent_callback, list):
    agent.after_agent_callback.append(callback)
  else:
    agent.after_agent_callback = [
      agent.after_agent_callback,
      callback,
    ]
