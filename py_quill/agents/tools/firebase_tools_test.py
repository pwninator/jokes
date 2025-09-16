import asyncio
import importlib
import sys
from types import SimpleNamespace

import pytest
from agents import constants
from common import config, models


@pytest.fixture()
def tool(monkeypatch):
  """Import the firebase_tools module with Firebase init stubbed out.

  We reload the module to ensure the initialize_app side effect is neutralized.
  """
  # Ensure firebase_admin import in module under test does not require the real package
  monkeypatch.setitem(sys.modules, "firebase_admin",
                      SimpleNamespace(initialize_app=lambda: None))
  # Import or reload after patching initialize_app
  import agents.tools.firebase_tools as _tool
  return importlib.reload(_tool)


@pytest.fixture()
def fake_ctx():

  class Ctx:

    def __init__(self):
      self.state = {}

  return Ctx()


@pytest.mark.asyncio
async def test_get_all_jokes(tool, monkeypatch):
  # Arrange
  mock_jokes = [
    models.PunnyJoke(
      key="joke1",
      setup_text="Why did the scarecrow win an award?",
      punchline_text="Because he was outstanding in his field."),
    models.PunnyJoke(key="joke2",
                     setup_text="What do you call a fake noodle?",
                     punchline_text="An Impasta."),
  ]

  async def fake_get_all_jokes_async():
    return mock_jokes

  monkeypatch.setattr("services.firestore.get_all_jokes_async",
                      fake_get_all_jokes_async)

  # Act
  jokes = await tool.get_all_jokes()

  # Assert
  assert jokes == [
    "Why did the scarecrow win an award? Because he was outstanding in his field.",
    "What do you call a fake noodle? An Impasta.",
  ]


def test_populate_state_with_all_storage_jokes(tool, monkeypatch, fake_ctx):
  # Arrange
  mock_jokes = [
    models.PunnyJoke(
      key="j1",
      setup_text="Why did the scarecrow win an award?",
      punchline_text="Because he was outstanding in his field."),
    models.PunnyJoke(key="j2",
                     setup_text="What do you call a fake noodle?",
                     punchline_text="An Impasta."),
  ]

  def fake_get_all_jokes():
    return mock_jokes

  monkeypatch.setattr("services.firestore.get_all_jokes", fake_get_all_jokes)

  # Act
  tool.populate_state_with_all_storage_jokes(fake_ctx)

  # Assert
  assert constants.STATE_ALL_STORAGE_JOKES in fake_ctx.state
  assert fake_ctx.state[constants.STATE_ALL_STORAGE_JOKES] == [
    "Why did the scarecrow win an award? Because he was outstanding in his field.",
    "What do you call a fake noodle? An Impasta.",
  ]


def test_populate_state_with_all_joke_categories_non_empty(
    tool, monkeypatch, fake_ctx):
  # Arrange
  monkeypatch.setattr(
    "services.firestore.get_all_joke_categories",
    lambda: [
      models.JokeCategory(display_name="Animal Jokes",
                          joke_description_query="animals"),
      models.JokeCategory(display_name="Seasonal",
                          joke_description_query="season"),
    ],
  )

  # Act
  tool.populate_state_with_all_joke_categories(fake_ctx)

  # Assert
  assert constants.STATE_ALL_STORAGE_JOKE_CATEGORIES in fake_ctx.state
  cats = fake_ctx.state[constants.STATE_ALL_STORAGE_JOKE_CATEGORIES]
  assert isinstance(cats, list) and len(cats) == 2
  assert cats[0]["key"] == "animal_jokes"
  assert cats[1]["display_name"] == "Seasonal"


def test_populate_state_with_all_joke_categories_empty(tool, monkeypatch,
                                                       fake_ctx):
  # Arrange: no categories
  monkeypatch.setattr("services.firestore.get_all_joke_categories", lambda: [])

  # Act
  tool.populate_state_with_all_joke_categories(fake_ctx)

  # Assert
  assert fake_ctx.state[constants.STATE_ALL_STORAGE_JOKE_CATEGORIES] == []


@pytest.mark.asyncio
async def test_save_joke_categories_valid(tool, monkeypatch):
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


@pytest.mark.asyncio
async def test_save_joke_categories_ignores_invalid_and_does_not_call_upsert(
    tool, monkeypatch):

  async def should_not_be_called(_):  # pragma: no cover
    raise AssertionError("upsert should not be called for invalid input")

  monkeypatch.setattr("services.firestore.upsert_joke_categories",
                      should_not_be_called)

  # Act & Assert: should not raise
  await tool.save_joke_categories([])  # empty
  await tool.save_joke_categories(["not-a-dict"])  # wrong type
  await tool.save_joke_categories([{
    "display_name": "",
    "joke_description_query": "animals"
  }])  # blank display
  await tool.save_joke_categories([{
    "display_name": "Animals",
    "joke_description_query": ""
  }])  # blank query


@pytest.mark.asyncio
async def test_search_for_jokes_returns_formatted_jokes(tool, monkeypatch):
  # Arrange: make to_thread run inline
  async def fake_to_thread(func, *args, **kwargs):
    return func(*args, **kwargs)

  monkeypatch.setattr("asyncio.to_thread", fake_to_thread)

  captured = {}

  def fake_search_jokes(query, limit, distance_threshold, label,
                        field_filters):
    captured.update(
      dict(query=query,
           limit=limit,
           distance_threshold=distance_threshold,
           label=label,
           field_filters=field_filters))

    class _R:

      def __init__(self, key):
        self.joke = models.PunnyJoke(key=key,
                                     setup_text="S",
                                     punchline_text="P")

    return [_R("a1"), _R("a2")]

  def fake_get_punny_jokes(keys):
    assert keys == ["a1", "a2"]
    return [
      models.PunnyJoke(key="a1", setup_text="Setup1", punchline_text="Punch1"),
      models.PunnyJoke(key="a2", setup_text="Setup2", punchline_text="Punch2"),
    ]

  monkeypatch.setattr("services.search.search_jokes", fake_search_jokes)
  monkeypatch.setattr("services.firestore.get_punny_jokes",
                      fake_get_punny_jokes)

  # Act
  result = await tool.search_for_jokes("dogs")

  # Assert
  assert result == ["Setup1 Punch1", "Setup2 Punch2"]
  # Query should be normalized to include the word 'jokes'
  assert "jokes" in captured["query"].lower()
  assert captured["limit"] == 15
  assert captured["distance_threshold"] == config.JOKE_SEARCH_TIGHT_THRESHOLD
  assert captured["label"] == "joke_search_tool"
  assert isinstance(captured["field_filters"], list)


@pytest.mark.asyncio
async def test_search_for_jokes_empty_query_returns_empty(tool):
  result = await tool.search_for_jokes("   ")
  assert result == []


@pytest.mark.asyncio
async def test_get_num_search_results_delegates_to_search(tool, monkeypatch):

  async def fake_search_for_jokes(q):  # pylint: disable=unused-argument
    return ["a", "b", "c"]

  monkeypatch.setattr(tool, "search_for_jokes", fake_search_for_jokes)

  count = await tool.get_num_search_results("anything")
  assert count == 3
