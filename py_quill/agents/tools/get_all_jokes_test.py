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
      models.PunnyJoke(
          key="joke2",
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
