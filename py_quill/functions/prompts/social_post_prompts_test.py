"""Tests for social_post_prompts."""

from __future__ import annotations

import dataclasses
import json

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
    self.prompts = None

  def generate(self, prompts):
    self.prompts = prompts
    return _FakeResponse(self._text)


def test_generate_pinterest_post_text_parses_fields(monkeypatch):
  fake_text = json.dumps({
    "pinterest_title":
    "Cute Jokes",
    "pinterest_description":
    "Tiny giggles for your day.",
    "pinterest_alt_text":
    "A two-row grid of joke panels.",
  })
  fake_client = _FakeClient(fake_text)
  config = social_post_prompts._PLATFORM_CONFIGS[
    models.SocialPlatform.PINTEREST]
  monkeypatch.setitem(
    social_post_prompts._PLATFORM_CONFIGS,
    models.SocialPlatform.PINTEREST,
    dataclasses.replace(config, client=fake_client),
  )

  image_bytes = b"\x89PNGfake"
  title, description, alt_text, metadata = social_post_prompts.generate_pinterest_post_text(
    image_bytes,
    post_type=models.JokeSocialPostType.JOKE_GRID,
  )

  assert title == "Cute Jokes"
  assert description == "Tiny giggles for your day."
  assert alt_text == "A two-row grid of joke panels."
  assert isinstance(metadata, models.GenerationMetadata)
  assert fake_client.prompts[1] == ("image/png", image_bytes)


def test_generate_pinterest_post_text_requires_output(monkeypatch):
  fake_text = json.dumps({
    "pinterest_title": "Cute Jokes",
    "pinterest_description": "",
    "pinterest_alt_text": "Alt text",
  })
  fake_client = _FakeClient(fake_text)
  config = social_post_prompts._PLATFORM_CONFIGS[
    models.SocialPlatform.PINTEREST]
  monkeypatch.setitem(
    social_post_prompts._PLATFORM_CONFIGS,
    models.SocialPlatform.PINTEREST,
    dataclasses.replace(config, client=fake_client),
  )

  with pytest.raises(ValueError):
    social_post_prompts.generate_pinterest_post_text(
      b"image",
      post_type=models.JokeSocialPostType.JOKE_GRID_TEASER,
    )
