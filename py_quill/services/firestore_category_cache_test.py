"""Tests for category cache reads in firestore service."""

from common import models
from services import firestore as firestore_service


def test_populate_category_cached_jokes_accepts_minimal_keys():
  category = models.JokeCategory(id="cats", display_name="Cats")
  cache_payload = {
    "jokes": [{
      "key": "j1",
      "setup_text": "Setup",
      "punchline_text": "Punchline",
      "setup_image_url": "setup.png",
      "punchline_image_url": "punchline.png",
    }]
  }

  class _CacheDoc:

    def __init__(self, data):
      self.exists = True
      self._data = data

    def to_dict(self):
      return dict(self._data)

  class _CategoryRef:

    def __init__(self, data):
      self._data = data

    def collection(self, name: str):
      assert name == "category_jokes"
      return self

    def document(self, name: str):
      assert name == "cache"
      return self

    def get(self):
      return _CacheDoc(self._data)

  firestore_service._populate_category_cached_jokes(category,  # pylint: disable=protected-access
                                                    _CategoryRef(cache_payload))

  assert len(category.jokes) == 1
  joke = category.jokes[0]
  assert joke.key == "j1"
  assert joke.setup_text == "Setup"
  assert joke.punchline_text == "Punchline"
  assert joke.setup_image_url == "setup.png"
  assert joke.punchline_image_url == "punchline.png"
