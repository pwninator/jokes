"""Parallel multi-agent."""

import functools
import logging
import pprint
from typing import Any, Callable, Optional

from agents import agents_common
from google.adk.agents import BaseAgent, ParallelAgent, SequentialAgent
from google.adk.agents.base_agent import (AfterAgentCallback,
                                          BeforeAgentCallback)
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse


def get_parallel_multi_agent(
  *,
  name: str,
  description: str,
  single_agent_fn: Callable[[int, str, str], BaseAgent],
  num_workers: int,
  input_var: str,
  output_var: str,
  input_list_fn: Optional[Callable[[Any], list[Any]]] = lambda x: x,
  before_agent_callback: Optional[BeforeAgentCallback] = None,
  after_agent_callback: Optional[AfterAgentCallback] = None,
  **kwargs,
) -> ParallelAgent:
  """Wraps a single-input agent to handle multiple inputs in parallel.

  Args:
    name: The name of the agent.
    description: The description of the agent.
    single_agent_fn: A function that returns a single  agent.
    num_workers: The number of workers to use.
    input_var: The key of the input variable in the state.
    output_var: The key of the output variable in the state.
    input_list_fn: A function that gets a list of inputs from input_var.
    before_agent_callback: A callback to be called before the agent runs.
    after_agent_callback: A callback to be called after the agent runs.
    **kwargs: Additional arguments to pass to the parallel agent.
  Returns:
    A parallel agent that handles multiple inputs in parallel.
  """

  worker_input_output_keys = [(f"{input_var}_{i:02d}", f"{output_var}_{i:02d}")
                              for i in range(num_workers)]

  sub_agents_list = []
  for i, (input_key, output_key) in enumerate(worker_input_output_keys):
    sub_agent_i = single_agent_fn(i, input_key, output_key)

    agents_common.add_before_agent_callback(
      sub_agent_i,
      functools.partial(
        _check_single_input_is_present,
        single_input_key=input_key,
      ),
    )
    sub_agents_list.append(sub_agent_i)

  before_multi_agent_callbacks = [
    functools.partial(
      _distribute_inputs_before_callback,
      input_var=input_var,
      input_list_fn=input_list_fn,
      num_workers=num_workers,
      worker_input_output_keys=worker_input_output_keys,
    ),
  ]
  after_multi_agent_callbacks = [
    functools.partial(
      _aggregate_results_after_callback,
      output_var=output_var,
      worker_input_output_keys=worker_input_output_keys,
    ),
  ]
  if before_agent_callback:
    if isinstance(before_agent_callback, list):
      before_multi_agent_callbacks.extend(before_agent_callback)
    else:
      before_multi_agent_callbacks.append(before_agent_callback)
  if after_agent_callback:
    if isinstance(after_agent_callback, list):
      after_multi_agent_callbacks.extend(after_agent_callback)
    else:
      after_multi_agent_callbacks.append(after_agent_callback)

  # parallel_agent_instance = ParallelAgent(
  parallel_agent_instance = SequentialAgent(
    name=name,
    sub_agents=sub_agents_list,
    description=description,
    before_agent_callback=before_multi_agent_callbacks,
    after_agent_callback=after_multi_agent_callbacks,
    **kwargs,
  )
  return parallel_agent_instance


def _distribute_inputs_before_callback(
  callback_context: CallbackContext,
  input_var: str,
  input_list_fn: Callable[[Any], list[Any]],
  num_workers: int,
  worker_input_output_keys: list[tuple[str, str]],
) -> None:
  """Distributes a list of inputs into individual state entries for sub-agents."""
  raw_inputs_to_process = callback_context.state.get(input_var)
  if not raw_inputs_to_process:
    raise ValueError(
      f"'{input_var}' not found in state: {pprint.pformat(callback_context.state)}"
    )
  inputs_to_process = input_list_fn(raw_inputs_to_process)
  if not isinstance(inputs_to_process, list):
    raise ValueError(
      f"Expected '{input_var}' to be a list, but got {inputs_to_process}")

  num_inputs_available = len(inputs_to_process)
  if num_inputs_available > num_workers:
    logging.warning(
      f"Number of inputs to process ({num_inputs_available}) exceeds "
      f"number of workers ({num_workers}). Extra inputs will be ignored.")

  # Distribute inputs to worker slots
  for i, (input_key, _) in enumerate(worker_input_output_keys):
    if i < num_inputs_available:
      callback_context.state[input_key] = inputs_to_process[i]
    else:
      # For sub-agents that don't have a corresponding input
      callback_context.state[input_key] = None

  logging.info(
    f"Distributed {min(num_inputs_available, num_workers)} items to {num_workers} worker slots."
  )


def _aggregate_results_after_callback(
  callback_context: CallbackContext,
  output_var: str,
  worker_input_output_keys: list[tuple[str, str]],
) -> None:
  """Aggregates results from parallel sub-agents."""

  all_outputs = callback_context.state.get(output_var, [])

  for _, output_key in worker_input_output_keys:
    if output := callback_context.state.get(output_key):
      all_outputs.append(output)
      callback_context.state[output_key] = None

  callback_context.state[output_var] = all_outputs


def _check_single_input_is_present(
  callback_context: CallbackContext,
  single_input_key: str,
) -> LlmResponse | None:
  """Checks if the input item is present in state; returns empty if not."""
  item_content = callback_context.state.get(single_input_key)

  if item_content:
    # Item is present. Proceed with evaluation
    return None
  else:
    return LlmResponse(content=None)
