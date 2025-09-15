from unittest import mock

import pytest
from agents import constants
from agents.tools import joke_categories as tool
from common import models


def test_populate_state_with_all_joke_categories(monkeypatch):
  # Arrange service return
  monkeypatch.setattr(
    "services.firestore.get_all_joke_categories",
    lambda: [
      models.JokeCategory(display_name="Animal Jokes",
                          joke_description_query="animals"),
      models.JokeCategory(display_name="Seasonal",
                          joke_description_query="season"),
    ],
  )

  class FakeContext:

    def __init__(self):
      self.state = {}

  ctx = FakeContext()

  # Act
  tool.populate_state_with_all_joke_categories(ctx)

  # Assert
  assert constants.STATE_ALL_STORAGE_JOKE_CATEGORIES in ctx.state
  cats = ctx.state[constants.STATE_ALL_STORAGE_JOKE_CATEGORIES]
  assert isinstance(cats, list) and len(cats) == 2
  assert cats[0]["key"] == "animal_jokes"
  assert cats[1]["display_name"] == "Seasonal"


@pytest.mark.asyncio
async def test_save_joke_categories(monkeypatch):
  captured = []

  async def fake_upsert(categories):
    captured.extend(categories)

  monkeypatch.setattr("services.firestore.upsert_joke_categories", fake_upsert)

  # Act
  await tool.save_joke_categories([
    {
      "display_name": "Animal Jokes",
      "joke_description_query": "animals"
    },
    {
      "display_name": "Seasonal",
      "joke_description_query": "season"
    },
  ])

  # Assert
  assert len(captured) == 2
  assert isinstance(captured[0], models.JokeCategory)
  assert captured[0].key == "animal_jokes"
