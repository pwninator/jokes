"""Tests for joke_operation_prompts helper functions."""

from __future__ import annotations

import pytest

from common import models
from functions.prompts import joke_operation_prompts


class _DummyResponse:
  """Simple stub that mimics llm_client responses."""

  def __init__(self, text: str):
    self.text = text
    self.metadata = models.SingleGenerationMetadata(model_name="dummy")


class _DummyClient:
  """Minimal client stub that records prompts and returns canned text."""

  def __init__(self, text: str):
    self._text = text
    self.last_prompt = None

  def generate(self, prompt_parts, label=None, extra_log_data=None):
    self.last_prompt = prompt_parts
    _ = extra_log_data
    _ = label
    return _DummyResponse(self._text)


def test_modify_scene_ideas_with_suggestions_requires_instruction():
  """At least one non-empty suggestion should be required."""
  with pytest.raises(ValueError):
    joke_operation_prompts.modify_scene_ideas_with_suggestions(
      setup_text="setup",
      punchline_text="punch",
      current_setup_scene_idea="old setup",
      current_punchline_scene_idea="old punch",
      setup_suggestion=None,
      punchline_suggestion=None,
    )


def test_modify_scene_ideas_with_suggestions_parses_llm_response(monkeypatch):
  """Scene idea helper should return parsed values from the LLM."""
  dummy_client = _DummyClient("""SAFETY_REASONS:
ok

SAFETY_VERDICT:
SAFE

SETUP_SCENE_IDEA:
New setup idea

PUNCHLINE_SCENE_IDEA:
New punchline idea""")
  monkeypatch.setattr(
    joke_operation_prompts,
    "_scene_editor_llm",
    dummy_client,
  )
  monkeypatch.setattr(
    joke_operation_prompts,
    "_run_safety_check",
    lambda content, label=None: (
      True,
      models.SingleGenerationMetadata(model_name="safety"),
    ),
  )

  setup, punchline, metadata = (
    joke_operation_prompts.modify_scene_ideas_with_suggestions(
      setup_text="setup",
      punchline_text="punch",
      current_setup_scene_idea="old setup",
      current_punchline_scene_idea="old punch",
      setup_suggestion="make it sillier",
      punchline_suggestion="add confetti",
    ))

  assert setup == "New setup idea"
  assert punchline == "New punchline idea"
  assert len(metadata.generations) == 2
  assert {g.model_name for g in metadata.generations} == {"dummy", "safety"}
  assert dummy_client.last_prompt is not None
  assert "Setup: setup" in dummy_client.last_prompt[0]
  assert "Punchline: punch" in dummy_client.last_prompt[0]


def test_generate_detailed_image_descriptions_requires_scene_ideas():
  """Both scene ideas are required to create detailed descriptions."""
  with pytest.raises(ValueError):
    joke_operation_prompts.generate_detailed_image_descriptions(
      setup_text="setup",
      punchline_text="punch",
      setup_scene_idea="",
      punchline_scene_idea="idea",
    )


def test_generate_detailed_image_descriptions_parses_llm_response(
  monkeypatch, ):
  """Detailed description helper should return parsed values from the LLM."""
  dummy_client = _DummyClient("""SAFETY_REASONS:
ok

SAFETY_VERDICT:
SAFE

SETUP_IMAGE_DESCRIPTION:
Detailed setup description

PUNCHLINE_IMAGE_DESCRIPTION:
Detailed punchline description""")
  monkeypatch.setattr(
    joke_operation_prompts,
    "_image_description_llm",
    dummy_client,
  )
  monkeypatch.setattr(
    joke_operation_prompts,
    "_run_safety_check",
    lambda content, label=None: (
      True,
      models.SingleGenerationMetadata(model_name="safety"),
    ),
  )

  setup_desc, punch_desc, metadata = (
    joke_operation_prompts.generate_detailed_image_descriptions(
      setup_text="setup",
      punchline_text="punch",
      setup_scene_idea="scene setup",
      punchline_scene_idea="scene punch",
    ))

  assert setup_desc == "Detailed setup description"
  assert punch_desc == "Detailed punchline description"
  assert len(metadata.generations) == 2
  assert {g.model_name for g in metadata.generations} == {"dummy", "safety"}
  assert dummy_client.last_prompt is not None
  assert "scene setup" in dummy_client.last_prompt[0]
  assert "scene punch" in dummy_client.last_prompt[0]
