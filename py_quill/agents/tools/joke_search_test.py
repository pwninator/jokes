import asyncio
import unittest
from unittest import mock

from common import config, models
from services import search

from py_quill.agents.tools import joke_search


class JokeSearchTest(unittest.TestCase):

  @mock.patch.object(search, "search_jokes")
  @mock.patch.object(joke_search.firestore, "get_punny_jokes")
  def test_search_for_jokes(self, mock_get_punny_jokes, mock_search_jokes):
    # Arrange
    query = "jokes about dogs"
    joke_key = "joke123"
    search_result = search.JokeSearchResult(
      joke=models.PunnyJoke(key=joke_key,
                            setup_text="setup",
                            punchline_text="punchline"),
      vector_distance=0.1,
    )
    mock_search_jokes.return_value = [search_result]

    punny_joke = models.PunnyJoke(key=joke_key,
                                  setup_text="setup",
                                  punchline_text="punchline")
    mock_get_punny_jokes.return_value = [punny_joke]

    # Act
    result = asyncio.run(joke_search.search_for_jokes(query))

    # Assert
    mock_get_punny_jokes.assert_called_once_with([joke_key])
    self.assertEqual(result, ["setup punchline"])


if __name__ == "__main__":
  unittest.main()
