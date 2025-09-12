"""Evaluator agent."""

import functools
import logging
from typing import Any, Callable, Optional

from agents import constants
from agents.common_agents import parallel_multi_agent
from agents.common_agents.quill_llm_agent import QuillLlmAgent
from google.adk.agents import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types
from pydantic import BaseModel
from services import llm_client

_EMPTY_EVAL_STR = "{}"


def get_multi_evaluator_agent(
  name: str,
  description: str,
  num_workers: int,
  instruction: str,
  input_var: str,
  output_var: str,
  output_type: type[BaseModel],
  input_list_fn: Optional[Callable[[Any], list[Any]]] = lambda x: x,
  **kwargs,
) -> BaseAgent:
  """Gets a multi-evaluator agent."""

  def _single_agent_fn(
    i: int,
    input_key: str,
    output_key: str,
  ) -> QuillLlmAgent:
    """Gets a single evaluator agent."""
    return get_single_evaluator_agent(
      name=f"{name}_Worker{i:02d}",
      input_key=input_key,
      output_critique_key=output_key,
      output_type=output_type,
      instruction=instruction,
    )

  multi_agent = parallel_multi_agent.get_parallel_multi_agent(
    name=name,
    description=description,
    single_agent_fn=_single_agent_fn,
    input_var=input_var,
    output_var=output_var,
    input_list_fn=input_list_fn,
    num_workers=num_workers,
    **kwargs,
  )

  return multi_agent


def get_single_evaluator_agent(
  name: str,
  input_key: str,
  output_critique_key: str,
  output_type: type[BaseModel],
  instruction: str,
) -> BaseAgent:
  """Gets a single evaluator agent."""

  agent = QuillLlmAgent(
    name=name,
    model=llm_client.LlmModel.GEMINI_2_5_FLASH,
    generate_content_config=types.GenerateContentConfig(
      temperature=0.1,
      max_output_tokens=50000,
      top_p=0.95,
    ),
    planner=constants.PLANNER_NO_THINKING,
    include_contents='none',  # Reads from state.
    after_agent_callback=functools.partial(
      store_evaluated_items_callback,
      output_critique_key=output_critique_key,
      input_key=input_key,
    ),
    output_key=output_critique_key,  # Use the function argument
    output_schema=output_type,
    disallow_transfer_to_parent=True,  # Required when specifying output_schema
    disallow_transfer_to_peers=True,  # Required when specifying output_schema
    description=
    "Evaluates a single pun based on linguistic and comedic merits using a detailed methodology.",
    instruction=instruction.format(input_key=input_key),
  )
  return agent


def store_evaluated_items_callback(
  callback_context: CallbackContext,
  output_critique_key: str,
  input_key: str,
) -> None:
  """Processes the evaluation result and updates the item content."""
  evaluation_result = callback_context.state.get(output_critique_key)

  if not isinstance(evaluation_result, dict):
    logging.error(
      f"Evaluation result in state ('{output_critique_key}') is not a dict. Type: {type(evaluation_result)}. Skipping processing."
    )
    return

  item_str = callback_context.state.get(input_key)

  if item_str is None:
    # The item was not present in the input
    return

  # Populate the output text field with the initial input to ensure fidelity
  evaluation_result["text"] = item_str
