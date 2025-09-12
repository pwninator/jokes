"""Custom LLM Agent"""

import dataclasses
import functools
import re

from agents import agents_common, constants
from common import models
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import BaseLlm, LlmResponse

_WORKER_NUMBER_SUFFIX_REGEX = re.compile(r"_Worker\d+$")


class QuillLlmAgent(LlmAgent):
  """Custom LLM client"""

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    if isinstance(self.model, BaseLlm):
      model_name = self.model.model
    else:
      model_name = self.model

    agents_common.add_after_model_callback(
      self, functools.partial(set_usage_costs, model_name=model_name))


def set_usage_costs(
  model_name: str,
  callback_context: CallbackContext,
  llm_response: LlmResponse,
) -> None:
  """Sets the usage costs for the LLM to state."""

  if not (usage := llm_response.usage_metadata):
    return

  if usage.cached_content_token_count:
    raise ValueError(f"Unexpected token type: {usage}")

  input_tokens = 0
  if usage.prompt_token_count:
    input_tokens = usage.prompt_token_count

  thought_tokens = 0
  if usage.thoughts_token_count:
    thought_tokens = usage.thoughts_token_count

  output_tokens = 0
  if usage.candidates_token_count:
    output_tokens = usage.candidates_token_count

  if input_tokens + thought_tokens + output_tokens == 0:
    if usage.total_token_count and usage.total_token_count > 0:
      raise ValueError(f"Unexpected usage metadata: {usage}")
    return

  cost = agents_common.get_llm_cost(
    model_name=model_name,
    input_tokens=input_tokens,
    thinking_tokens=thought_tokens,
    output_tokens=output_tokens,
  )

  token_counts = {
    "input_tokens": input_tokens,
    "thought_tokens": thought_tokens,
    "output_tokens": output_tokens,
  }

  agent_name = callback_context.agent_name
  agent_name = _WORKER_NUMBER_SUFFIX_REGEX.sub("_Worker", agent_name)

  llm_usage = models.SingleGenerationMetadata(
    label=f"Agent_{agent_name}",
    model_name=model_name,
    token_counts=token_counts,
    generation_time_sec=0,
    cost=cost,
    retry_count=0,
  )

  updated_usages = callback_context.state.get(constants.STATE_LLM_COST, [])
  updated_usages.append(dataclasses.asdict(llm_usage))
  callback_context.state[constants.STATE_LLM_COST] = updated_usages
