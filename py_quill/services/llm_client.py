"""LLM client."""

from __future__ import annotations

import base64
import pprint
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generator, Generic, Optional, Tuple, TypeVar, Union

import anthropic
import httpx
from common import config, models
from firebase_functions import logger
from google.api_core.exceptions import ResourceExhausted
from typing_extensions import override
from vertexai.generative_models import (GenerationConfig, GenerativeModel,
                                        HarmBlockThreshold, HarmCategory, Part,
                                        SafetySetting)

_T = TypeVar("_T")

_SAFETY_PROMPT = "Ensure that your output is safe for children."

_MIN_EMIT_INTERVAL_SEC = 3
"""Minimum interval between emitting LLM response chunks."""


class Error(Exception):
  """Base class for exceptions in this module."""


class LlmError(Error):
  """Exception raised for errors in the LLM."""


@dataclass(kw_only=True)
class LlmResponse:
  """A chunk of response from an LLM.

  For streaming responses, chunks will be yielded with is_final=False and metadata=None
  until the final chunk which will have is_final=True and complete metadata.
  """
  text: str
  """All text accumulated so far."""

  text_delta: str
  """The delta of text since the last chunk."""

  thinking_text: str
  """All thinking text accumulated so far."""

  thinking_text_delta: str
  """The delta of thinking text since the last chunk."""

  metadata: Optional[models.SingleGenerationMetadata] = None
  """Metadata about the generation."""

  is_final: bool = False
  """Whether this is the final chunk."""

  def __str__(self) -> str:
    return f"""********** Thinking **********
{self.thinking_text}
********** Response **********
{self.text}
********** Metadata **********
{self.metadata}
********** Is Final **********
{self.is_final}
********** End **********
"""


class LlmModel(str, Enum):
  """LLM model names."""
  # Gemini models
  GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"
  GEMINI_2_5_FLASH = "gemini-2.5-flash"
  GEMINI_2_5_PRO = "gemini-2.5-pro"

  # Anthropic models
  CLAUDE_3_5_HAIKU = "claude-3-5-haiku-20241022"
  CLAUDE_3_7_SONNET = "claude-3-7-sonnet-20250219"


def get_client(label: str,
               model: LlmModel,
               temperature: float,
               system_instructions: list[str] | None = None,
               response_schema: Optional[dict] = None,
               thinking_tokens: int = 0,
               output_tokens: int = 8000,
               max_retries: int = 5,
               **kwargs: Any) -> LlmClient[Any]:
  """Get the appropriate LLM client for the given model name."""
  if model in VertexClient.GENERATION_COSTS:
    return VertexClient(
      label=label,
      model=model,
      temperature=temperature,
      system_instructions=system_instructions,
      response_schema=response_schema,
      thinking_tokens=thinking_tokens,
      output_tokens=output_tokens,
      max_retries=max_retries,
      **kwargs,
    )
  elif model in AnthropicClient.GENERATION_COSTS:
    return AnthropicClient(
      label=label,
      model=model,
      temperature=temperature,
      system_instructions=system_instructions,
      response_schema=response_schema,
      thinking_tokens=thinking_tokens,
      output_tokens=output_tokens,
      max_retries=max_retries,
      **kwargs,
    )
  else:
    raise ValueError(f"Unknown model: {model}")


class LlmClient(ABC, Generic[_T]):
  """Abstract base class for LLM clients."""

  def __init__(
    self,
    label: str,
    model: LlmModel,
    temperature: float,
    system_instructions: list[str] | None,
    response_schema: Optional[dict],
    thinking_tokens: int,
    output_tokens: int,
    max_retries: int,
  ):
    self.label = label
    self.model = model
    self.temperature = temperature
    self.response_schema = response_schema
    self.thinking_tokens = thinking_tokens
    self.output_tokens = output_tokens
    self.max_retries = max_retries

    system_instruction_lines = []
    if system_instructions:
      system_instruction_lines = system_instructions
    system_instruction_lines.append(_SAFETY_PROMPT)
    self.system_instructions = "\n\n".join(system_instruction_lines)

    self._model_client: _T | None = None

  @property
  def model_client(self) -> _T:
    """Get the model."""
    if self._model_client is None:
      self._model_client = self._create_model_client()
    return self._model_client

  @property
  def thinking_enabled(self) -> bool:
    """Whether thinking is enabled."""
    return self.thinking_tokens > 0

  @abstractmethod
  def _create_model_client(self) -> _T:
    """Create the model."""

  @abstractmethod
  def _get_generation_costs(self) -> dict[str, float]:
    """Get the generation costs in USD per token by token type."""

  @abstractmethod
  def _stream_internal(
    self,
    prompt_chunks: list[Union[str, Tuple[str, Any]]],
  ) -> Generator[LlmResponse, None, None]:
    """Stream a response from the LLM.

    Args:
        prompt_chunks: List of prompt chunks. Each chunk can be either:
            - A string containing text
            - A tuple of (mime_type, data) for images

    Yields:
        LlmResponseChunk containing the generated text and metadata. All chunks except
        the final one will have is_final=False and metadata=None.
    """
    raise NotImplementedError

  @abstractmethod
  def _is_retryable_error(self, error: Exception) -> bool:
    """Whether the error is retryable."""
    raise NotImplementedError

  def generate(
    self,
    prompt_chunks: list[Union[str, Tuple[str, Any]]],
    label: str | None = None,
    extra_log_data: dict[str, Any] | None = None,
  ) -> LlmResponse:
    """Generate a response from the LLM.

    Args:
        prompt_chunks: List of prompt chunks. Each chunk can be either:
            - A string containing text
            - A tuple of (mime_type, data) for images
        label: Label override.

    Returns:
      The final LLM response.

    Raises:
        LlmError: If the LLM fails to generate a response after max retries.
    """
    last_response = None
    for response in self.stream(
        prompt_chunks=prompt_chunks,
        label=label,
        extra_log_data=extra_log_data,
    ):
      last_response = response

    if not last_response:
      raise LlmError("No response from LLM")
    if not last_response.is_final:
      raise LlmError(f"LLM returned a non-final response: {last_response}")

    return last_response

  def stream(
    self,
    prompt_chunks: list[Union[str, Tuple[str, Any]]],
    label: str | None = None,
    extra_log_data: dict[str, Any] | None = None,
  ) -> Generator[LlmResponse, None, None]:
    """Stream responses from the LLM.

    Args:
        prompt_chunks: List of prompt chunks. Each chunk can be either:
            - A string containing text
            - A tuple of (mime_type, data) for images
        label: Label override.
        extra_log_data: Extra log data to include in the log.

    Yields:
        LlmResponseChunk containing the generated text and metadata. All chunks except
        the final one will have is_final=False and metadata=None.

    Raises:
        LlmError: If the LLM fails to generate a response after max retries.
    """
    start_time = time.perf_counter()
    label = label or self.label

    logger.info(f"{self.model.value} start: {label}")

    initial_delay = 5
    backoff_factor = 2
    max_delay = 60

    last_response = None
    retry_count = 0

    # Accumulate deltas to yield only once per _MIN_EMIT_INTERVAL_SEC
    answer_delta = []
    thinking_delta = []
    last_yield_time = 0

    while retry_count <= self.max_retries:
      try:
        for response in self._stream_internal(prompt_chunks=prompt_chunks):
          if response.metadata:
            response.metadata.label = label
            response.metadata.model_name = self.model.value
            response.metadata.generation_time_sec = time.perf_counter(
            ) - start_time
            response.metadata.cost = self.calculate_generation_cost(
              response.metadata.token_counts)
            response.metadata.retry_count = retry_count

            self._log_response(prompt_chunks, response, extra_log_data)
          last_response = response

          if response.text_delta:
            answer_delta.append(response.text_delta)
          if response.thinking_text_delta:
            thinking_delta.append(response.thinking_text_delta)

          if response.is_final or (time.time() - last_yield_time
                                   > _MIN_EMIT_INTERVAL_SEC):
            response.text_delta = "".join(answer_delta)
            response.thinking_text_delta = "".join(thinking_delta)
            yield response
            answer_delta = []
            thinking_delta = []
            last_yield_time = time.time()
        break
      except Exception as e:  # pylint: disable=broad-except
        retryable_str = "retryable" if self._is_retryable_error(
          e) else "non-retryable"
        merged_extra_log_data = self._get_merged_extra_log_data(extra_log_data)
        logger.error(
          "LLM call failed with %s error:\n%s",
          retryable_str,
          traceback.format_exc(),
          extra={"json_fields": merged_extra_log_data},
        )
        if not self._is_retryable_error(e):
          raise LlmError(
            f"LLM call to {self.model.value} ({self.label}) failed with non-retryable error"
          ) from e

        retry_count += 1
        if retry_count > self.max_retries:
          raise LlmError(
            f"LLM call to {self.model.value} ({self.label}) failed after "
            f"{self.max_retries} retries:\n{e}") from e

        delay = min(max_delay,
                    initial_delay * (backoff_factor**(retry_count - 1)))
        logger.warn(
          "LLM call to %s (%s) failed: %s\nRetrying in %s seconds...",
          self.model.value,
          self.label,
          e,
          delay,
          extra={"json_fields": merged_extra_log_data},
        )
        time.sleep(delay)

    if last_response is None:
      raise LlmError("Failed to generate response from LLM after "
                     f"{self.max_retries} retries")
    if not last_response.is_final:
      raise LlmError(f"Last LLM response was not final: {last_response}")

  def _log_response(
    self,
    prompt_chunks: list[Union[str, Tuple[str, Any]]],
    response: LlmResponse,
    extra_log_data: dict[str, Any] | None = None,
  ) -> None:
    """Log the LLM response and metadata.

    Args:
        prompt_chunks: Original prompt chunks
        response: Generated LLM response (must be final chunk with metadata)
    """
    if not response.is_final or not response.metadata:
      return

    # Create a text version of prompt_chunks for logging
    text_chunks = []
    for chunk in prompt_chunks:
      if isinstance(chunk, str):
        text_chunks.append(chunk)
      elif isinstance(chunk, tuple) and len(chunk) == 2:
        mime_type, _ = chunk
        text_chunks.append(f"[BYTES: {mime_type}]")
      else:
        text_chunks.append(str(chunk))
    prompt_str = "".join(text_chunks)

    metadata = response.metadata
    usage_str = "\n".join(f"{k}: {v}"
                          for k, v in metadata.token_counts.items())

    # Format log parts
    log_parts = []
    log_parts.append(f"""
============================== Prompt ==============================
{prompt_str}
""")

    if response.thinking_text.strip():
      log_parts.append(f"""
============================== Thinking ==============================
{response.thinking_text}
""")

    log_parts.append(f"""
============================== Response ==============================
{response.text}
""")

    log_parts.append(f"""
============================== Metadata ==============================
Model: {self.model.value}
Generation time: {metadata.generation_time_sec:.2f} seconds
Retry count: {metadata.retry_count}
Generation cost: ${metadata.cost:.6f}
{usage_str}
""")

    header = f"{self.model.value} done: {self.label}"
    combined_log = header + "\n" + "\n\n".join(log_parts)

    merged_extra_log_data = self._get_merged_extra_log_data(extra_log_data)
    log_extra_data = {
      "generation_cost_usd": metadata.cost,
      "generation_time_sec": metadata.generation_time_sec,
      "retry_count": metadata.retry_count,
      **metadata.token_counts,
      **merged_extra_log_data,
    }

    # Log combined if under limit, otherwise log parts separately
    if len(combined_log) <= 65_000:
      logger.info(combined_log, extra={"json_fields": log_extra_data})
    else:
      # Log each part separately, prepending the header to each.
      # Attach the structured data only to the last part's log entry.
      num_parts = len(log_parts)
      for i, part in enumerate(log_parts):
        is_last_part = i == (num_parts - 1)
        if is_last_part:
          # Use lazy formatting for the final log call with extra data
          logger.info("%s\n%s",
                      header,
                      part,
                      extra={"json_fields": log_extra_data})
        else:
          # Use lazy formatting for intermediate parts
          logger.info("%s\n%s",
                      header,
                      part,
                      extra={"json_fields": merged_extra_log_data})

  def _get_merged_extra_log_data(
      self, extra_log_data: dict[str, Any] | None) -> dict[str, Any]:
    """Merge the extra log data with the model-specific log data."""
    return {
      "model_name": self.model.value,
      "label": self.label,
      **(extra_log_data or {}),
    }

  def calculate_generation_cost(self, usage_metadata: dict[str, Any]) -> float:
    """Calculate the generation cost in USD."""
    total_cost = 0
    costs_by_token_type = self._get_generation_costs()
    for token_type, count in usage_metadata.items():
      if token_type not in costs_by_token_type:
        raise ValueError(
          f"""Unknown token type ({token_type}) for model {self.model.value}:
{usage_metadata}""")
      total_cost += costs_by_token_type[token_type] * count
    return total_cost


class VertexClient(LlmClient[GenerativeModel]):
  """Vertex AI client implementation."""

  # https://cloud.google.com/vertex-ai/generative-ai/pricing
  GENERATION_COSTS = {
    # Gemini 2.5
    LlmModel.GEMINI_2_5_FLASH_LITE: {
      "prompt_tokens": 0.1 / 1_000_000,
      "cached_prompt_tokens": 0.1 / 1_000_000,
      "output_tokens": 0.4 / 1_000_000,
    },
    LlmModel.GEMINI_2_5_FLASH: {
      "prompt_tokens": 0.30 / 1_000_000,
      "cached_prompt_tokens": 0.0375 / 1_000_000,
      "output_tokens": 2.50 / 1_000_000,
    },
    LlmModel.GEMINI_2_5_PRO: {
      "prompt_tokens": 1.25 / 1_000_000,
      "cached_prompt_tokens": 0.31 / 1_000_000,
      "output_tokens": 10.0 / 1_000_000,
    },
  }

  def __init__(
    self,
    label: str,
    model: LlmModel,
    temperature: float,
    system_instructions: list[str] | None,
    response_schema: Optional[dict],
    thinking_tokens: int,
    output_tokens: int,
    max_retries: int,
  ):
    system_instructions = system_instructions or []

    super().__init__(
      label=label,
      model=model,
      temperature=temperature,
      system_instructions=system_instructions,
      response_schema=response_schema,
      thinking_tokens=thinking_tokens,
      output_tokens=output_tokens,
      max_retries=max_retries,
    )

  @override
  def _create_model_client(self) -> GenerativeModel:
    return GenerativeModel(self.model.value,
                           system_instruction=self.system_instructions)

  @override
  def _get_generation_costs(self) -> dict[str, float]:
    """Get the generation costs in USD per token by token type."""
    # https://cloud.google.com/vertex-ai/generative-ai/pricing
    if costs := self.GENERATION_COSTS.get(self.model):
      return costs
    else:
      raise ValueError(f"Unknown Vertex model {self.model}")

  @override
  def _stream_internal(
    self,
    prompt_chunks: list[Union[str, Tuple[str, bytes]]],
  ) -> Generator[LlmResponse, None, None]:

    # Convert image tuples to Vertex AI Parts
    vertex_chunks = []
    for chunk in prompt_chunks:
      if isinstance(chunk, str):
        vertex_chunks.append(chunk)
      elif isinstance(chunk, tuple) and len(chunk) == 2:
        mime_type, data = chunk
        vertex_chunks.append(Part.from_data(data, mime_type=mime_type))
      else:
        raise ValueError(f"Invalid prompt chunk: {chunk}")

    responses = self.model_client.generate_content(
      vertex_chunks,
      generation_config=GenerationConfig(
        temperature=self.temperature,
        max_output_tokens=self.thinking_tokens + self.output_tokens,
        response_mime_type="application/json"
        if self.response_schema else None,
        response_schema=self.response_schema,
      ),
      safety_settings=[
        SafetySetting(
          category=HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
          threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
        SafetySetting(
          category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
          threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
        SafetySetting(
          category=HarmCategory.HARM_CATEGORY_HARASSMENT,
          threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
        SafetySetting(
          category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
          threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
        SafetySetting(
          category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
          threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
      ],
      labels={"query": self.label},
      stream=True,
    )

    accumulated_answer: list[str] = []
    prompt_feedback = []
    final_usage_metadata = None

    responses = list(responses)
    logger.info(pprint.pformat([r.to_dict() for r in responses], width=120))
    for response in responses:

      if response.usage_metadata:
        final_usage_metadata = response.usage_metadata

      if response.prompt_feedback:
        logger.info(f"Prompt feedback: {response.prompt_feedback}")
        prompt_feedback.append(response.prompt_feedback)

      if not response.candidates:
        continue

      response_parts = response.candidates[0].content.parts

      if response_parts:
        for part in response_parts:
          answer_delta = None
          try:
            answer_delta = part.text
          except AttributeError:
            logger.warn(f"Part has no text: {part}")

          if answer_delta:
            accumulated_answer.append(answer_delta)
            yield LlmResponse(
              text="".join(accumulated_answer).strip(),
              text_delta=answer_delta,
              thinking_text="",
              thinking_text_delta="",
              is_final=False,
            )
      else:
        logger.warn(f"No parts in response: {response}")

    if final_usage_metadata is None:
      raise ValueError("No usage metadata received from Vertex AI")

    cached_prompt_tokens = final_usage_metadata.cached_content_token_count
    prompt_tokens = final_usage_metadata.prompt_token_count - cached_prompt_tokens
    output_tokens = final_usage_metadata.candidates_token_count
    token_counts = {
      'prompt_tokens': prompt_tokens,
      'cached_prompt_tokens': cached_prompt_tokens,
      'output_tokens': output_tokens,
    }

    # Yield final chunk with metadata
    yield LlmResponse(
      text="".join(accumulated_answer).strip(),
      text_delta="",
      thinking_text="",
      thinking_text_delta="",
      metadata=models.SingleGenerationMetadata(token_counts=token_counts),
      is_final=True,
    )

  @override
  def _is_retryable_error(self, error: Exception) -> bool:
    """Whether the error is retryable."""
    return isinstance(error, ResourceExhausted)


class AnthropicClient(LlmClient[anthropic.Anthropic]):
  """Anthropic client implementation."""

  GENERATION_COSTS = {
    LlmModel.CLAUDE_3_5_HAIKU: {
      "input_tokens": 0.80 / 1_000_000,
      "output_tokens": 4.0 / 1_000_000,
      "cache_creation_input_tokens": 1.0 / 1_000_000,
      "cache_read_input_tokens": 0.08 / 1_000_000,
    },
    LlmModel.CLAUDE_3_7_SONNET: {
      "input_tokens": 3.0 / 1_000_000,
      "output_tokens": 15.0 / 1_000_000,
      "cache_creation_input_tokens": 3.75 / 1_000_000,
      "cache_read_input_tokens": 0.30 / 1_000_000,
    }
  }

  def __init__(
    self,
    label: str,
    model: LlmModel,
    temperature: float,
    system_instructions: list[str] | None,
    response_schema: Optional[dict],
    thinking_tokens: int,
    output_tokens: int,
    max_retries: int,
    cache_enabled: bool = False,
  ):
    super().__init__(
      label=label,
      model=model,
      temperature=temperature,
      system_instructions=system_instructions,
      response_schema=response_schema,
      thinking_tokens=thinking_tokens,
      output_tokens=output_tokens,
      max_retries=max_retries,
    )
    self.cache_enabled = cache_enabled

  @override
  def _create_model_client(self) -> anthropic.Anthropic:
    """Create the Anthropic client."""
    return anthropic.Anthropic(api_key=config.get_anthropic_api_key())

  @override
  def _get_generation_costs(self) -> dict[str, float]:
    """Get the generation costs in USD per token by token type."""
    # https://docs.anthropic.com/claude/docs/models-overview
    # https://www.anthropic.com/pricing#anthropic-api
    if costs := self.GENERATION_COSTS.get(self.model):
      return costs
    else:
      raise ValueError(f"Unknown Anthropic model {self.model}")

  @override
  def _stream_internal(
    self,
    prompt_chunks: list[Union[str, Tuple[str, Any]]],
  ) -> Generator[LlmResponse, None, None]:
    # Add JSON schema as system message if provided
    if self.response_schema:
      raise ValueError("JSON schema is not supported for Anthropic")

    # Add system instructions if provided
    system_chunks = None
    if self.system_instructions:
      system_chunks = [
        self._text_chunk(self.system_instructions, cache=self.cache_enabled)
      ]

    # Build the user chunks to pass to Claude
    user_chunks = []
    for chunk in prompt_chunks:
      if isinstance(chunk, str):
        user_chunks.append(self._text_chunk(chunk))
      elif isinstance(chunk, tuple) and len(chunk) == 2:
        mime_type, data = chunk
        user_chunks.append(self._image_chunk(data, mime_type))
      else:
        raise ValueError(f"Invalid prompt chunk: {chunk}")

    accumulated_thinking = []
    thinking_delta = []
    accumulated_answer = []
    answer_delta = []
    accumulated_usage = {
      "input_tokens": 0,
      "output_tokens": 0,
      "cache_creation_input_tokens": 0,
      "cache_read_input_tokens": 0,
    }
    with self.model_client.messages.stream(
        model=self.model.value,
        system=system_chunks or anthropic.NOT_GIVEN,
        messages=[{
          "role": "user",
          "content": user_chunks,
        }],
        max_tokens=self.thinking_tokens + self.output_tokens,
        thinking={
          "type": "enabled",
          "budget_tokens": self.thinking_tokens,
        } if self.thinking_enabled else anthropic.NOT_GIVEN,
        # If thinking is enabled, temperature must be set to 1
        temperature=1 if self.thinking_enabled else self.temperature,
    ) as stream:
      for event in stream:
        match event.type:
          case "message_start":
            pass
          case "content_block_start":
            if event.content_block.type not in ("text", "thinking"):
              raise ValueError(
                f"Unsupported content block type: {event.content_block.type}")
          case "content_block_delta":
            match event.delta.type:
              case "thinking_delta":
                thinking_delta.append(event.delta.thinking)
              case "text_delta":
                answer_delta.append(event.delta.text)
              case "signature_delta":
                pass
              case _:
                raise ValueError(
                  f"Unsupported delta type: {event.delta.type} ({event})")
          case "thinking":
            pass
          case "text":
            pass
          case "signature":
            pass
          case "content_block_stop":
            pass
          case "message_delta":
            pass
          case "message_stop":
            accumulated_usage[
              "input_tokens"] += event.message.usage.input_tokens
            accumulated_usage[
              "output_tokens"] += event.message.usage.output_tokens
            accumulated_usage[
              "cache_creation_input_tokens"] += event.message.usage.cache_creation_input_tokens
            accumulated_usage[
              "cache_read_input_tokens"] += event.message.usage.cache_read_input_tokens
          case _:
            raise ValueError(f"Unsupported event type: {event.type}")

        if answer_delta or thinking_delta:
          accumulated_answer.extend(answer_delta)
          accumulated_thinking.extend(thinking_delta)
          yield LlmResponse(
            text="".join(accumulated_answer),
            text_delta="".join(answer_delta),
            thinking_text="".join(accumulated_thinking),
            thinking_text_delta="".join(thinking_delta),
            is_final=False,
          )
          answer_delta = []
          thinking_delta = []

    accumulated_thinking.extend(thinking_delta)
    accumulated_answer.extend(answer_delta)

    if not accumulated_answer:
      raise ValueError("No answer received from Anthropic")

    # Yield final chunk with metadata
    yield LlmResponse(
      text="".join(accumulated_answer),
      text_delta="".join(answer_delta),
      thinking_text="".join(accumulated_thinking),
      thinking_text_delta="".join(thinking_delta),
      metadata=models.SingleGenerationMetadata(
        token_counts=accumulated_usage, ),
      is_final=True,
    )

  @override
  def _is_retryable_error(self, error: Exception) -> bool:
    """Whether the error is retryable."""
    return isinstance(error, httpx.RemoteProtocolError)

  def _text_chunk(self, s: str, cache: bool = False) -> dict[str, Any]:
    """Create a text chunk."""
    chunk = {
      "type": "text",
      "text": s,
    }
    if cache:
      chunk["cache_control"] = {"type": "ephemeral"}
    return chunk

  def _image_chunk(self, data: bytes, mime_type: str) -> dict[str, Any]:
    """Create an image chunk."""
    return {
      "type": "image",
      "source": {
        "type": "base64",
        "media_type": mime_type,
        "data": base64.standard_b64encode(data).decode('utf-8'),
      },
    }
