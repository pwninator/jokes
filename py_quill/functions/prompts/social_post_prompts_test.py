"""Tests for social_post_prompts."""

from __future__ import annotations

import pytest

from common import models
from functions.prompts import social_post_prompts


class _FakeResponse:
  def __init__(self, text: str):
    self.text = text
    self.metadata = models.GenerationMetadata()


class _FakeClient:
  def __init__(self, text: str):
    self._text = text

  def generate(self, _prompts):
    return _FakeResponse(self._text)


def test_generate_social_post_text_parses_fields(monkeypatch):
  fake_text = """TITLE:
Cute Jokes

DESCRIPTION:
Tiny giggles for your day."""
  monkeypatch.setattr(social_post_prompts, "_social_post_llm",
                      _FakeClient(fake_text))

  joke = models.PunnyJoke(setup_text="Setup", punchline_text="Punch")
  title, description, metadata = social_post_prompts.generate_social_post_text(
    [joke],
    models.JokeSocialPostType.JOKE_GRID,
  )

  assert title == "Cute Jokes"
  assert description == "Tiny giggles for your day."
  assert isinstance(metadata, models.GenerationMetadata)


def test_generate_social_post_text_requires_output(monkeypatch):
  fake_text = "TITLE:\n\nDESCRIPTION:\n"
  monkeypatch.setattr(social_post_prompts, "_social_post_llm",
                      _FakeClient(fake_text))

  joke = models.PunnyJoke(setup_text="Setup", punchline_text="Punch")
  with pytest.raises(ValueError):
    social_post_prompts.generate_social_post_text(
      [joke],
      models.JokeSocialPostType.JOKE_GRID_TEASER,
    )
