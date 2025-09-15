from unittest import mock

import pytest
from agents.tools import get_all_jokes
from common import models


@pytest.mark.asyncio
async def test_get_all_jokes(monkeypatch):
  """Test that get_all_jokes returns a list of formatted jokes."""
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
  mock_get_all_jokes_async = mock.AsyncMock(return_value=mock_jokes)
  monkeypatch.setattr("services.firestore.get_all_jokes_async",
                      mock_get_all_jokes_async)

  # Act
  jokes = await get_all_jokes.get_all_jokes()

  # Assert
  assert jokes == [
    "Why did the scarecrow win an award? Because he was outstanding in his field.",
    "What do you call a fake noodle? An Impasta."
  ]
  mock_get_all_jokes_async.assert_called_once()


def test_populate_state_with_all_storage_jokes(monkeypatch):
  """populate_state_with_all_storage_jokes formats and stores jokes in state."""
  from agents import constants
  from agents.tools import get_all_jokes as tool

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

  def fake_get_all_jokes(states=None):  # pylint: disable=unused-argument
    return mock_jokes

  monkeypatch.setattr("services.firestore.get_all_jokes", fake_get_all_jokes)

  class FakeContext:

    def __init__(self):
      self.state = {}

  ctx = FakeContext()

  # Act
  tool.populate_state_with_all_storage_jokes(ctx)

  # Assert
  assert constants.STATE_ALL_STORAGE_JOKES in ctx.state
  assert ctx.state[constants.STATE_ALL_STORAGE_JOKES] == [
    "Why did the scarecrow win an award? Because he was outstanding in his field.",
    "What do you call a fake noodle? An Impasta.",
  ]
