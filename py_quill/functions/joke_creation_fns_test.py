"""Tests for joke_creation_fns."""

import pytest
from common import models
from functions import joke_creation_fns


class DummyReq:
  """Simple request stub for testing."""

  def __init__(self, data=None, args=None, path="", method='POST'):
    self._data = data or {}
    self.args = args or {}
    self.path = path
    self.method = method
    self.headers = {}
    self.is_json = True

  def get_json(self):
    return {"data": self._data}


@pytest.fixture(autouse=True)
def reset_image_quality(monkeypatch):
  """Ensure the image quality map is predictable in tests."""
  monkeypatch.setattr(
    joke_creation_fns.image_generation, 'PUN_IMAGE_CLIENTS_BY_QUALITY',
    {
      "low": object(),
      "medium": object(),
    })


def test_joke_creation_process_creates_joke_from_text(monkeypatch):
  """Scenario 1 should call joke_operations.create_joke."""
  monkeypatch.setattr(
    joke_creation_fns, 'get_user_id',
    lambda req, allow_unauthenticated=False: "user-42")

  created_kwargs = {}

  def fake_create_joke(**kwargs):
    created_kwargs.update(kwargs)
    return models.PunnyJoke(
      key="j-1", setup_text="Setup", punchline_text="Punch")

  monkeypatch.setattr(joke_creation_fns.joke_operations, 'create_joke',
                      fake_create_joke)
  monkeypatch.setattr(joke_creation_fns.joke_operations, 'to_response_joke',
                      lambda joke: {
                        "key": joke.key,
                        "owner_user_id": "user-42"
                      })

  req = DummyReq(data={
    "setup_text": "Setup",
    "punchline_text": "Punch",
    "admin_owned": True,
  })

  resp = joke_creation_fns.joke_creation_process(req)

  assert resp["data"]["joke_data"]["key"] == "j-1"
  assert created_kwargs["admin_owned"] is True
  assert created_kwargs["user_id"] == "user-42"


def test_joke_creation_process_applies_suggestions(monkeypatch):
  """Scenario 2 should apply suggestions and persist the joke."""
  monkeypatch.setattr(
    joke_creation_fns, 'get_user_id',
    lambda req, allow_unauthenticated=False: "user-42")
  joke = models.PunnyJoke(key="j-2", setup_text="S", punchline_text="P")
  monkeypatch.setattr(joke_creation_fns.firestore, 'get_punny_joke',
                      lambda joke_id: joke if joke_id == "j-2" else None)
  monkeypatch.setattr(joke_creation_fns.firestore, 'upsert_punny_joke',
                      lambda updated: updated)  # Return the joke as saved

  suggestions = {}

  def fake_modify(j, setup_suggestion, punchline_suggestion):
    suggestions["setup"] = setup_suggestion
    suggestions["punchline"] = punchline_suggestion
    return j  # Return the joke (modified)

  monkeypatch.setattr(joke_creation_fns.joke_operations,
                      'modify_image_descriptions', fake_modify)
  monkeypatch.setattr(joke_creation_fns.joke_operations, 'to_response_joke',
                      lambda _: {"key": "j-2"})

  req = DummyReq(data={
    "joke_id": "j-2",
    "setup_suggestion": "new setup",
    "punchline_suggestion": "new punchline",
  })

  resp = joke_creation_fns.joke_creation_process(req)

  assert resp["data"]["joke_data"]["key"] == "j-2"
  assert suggestions == {
    "setup": "new setup",
    "punchline": "new punchline",
  }


def test_joke_creation_process_applies_partial_suggestions(monkeypatch):
  """Scenario 2 should work with only setup_suggestion."""
  monkeypatch.setattr(
    joke_creation_fns, 'get_user_id',
    lambda req, allow_unauthenticated=False: "user-42")
  joke = models.PunnyJoke(key="j-2", setup_text="S", punchline_text="P")
  monkeypatch.setattr(joke_creation_fns.firestore, 'get_punny_joke',
                      lambda joke_id: joke if joke_id == "j-2" else None)
  monkeypatch.setattr(joke_creation_fns.firestore, 'upsert_punny_joke',
                      lambda updated: updated)

  suggestions = {}

  def fake_modify(j, setup_suggestion, punchline_suggestion):
    suggestions["setup"] = setup_suggestion
    suggestions["punchline"] = punchline_suggestion
    return j

  monkeypatch.setattr(joke_creation_fns.joke_operations,
                      'modify_image_descriptions', fake_modify)
  monkeypatch.setattr(joke_creation_fns.joke_operations, 'to_response_joke',
                      lambda _: {"key": "j-2"})

  req = DummyReq(data={
    "joke_id": "j-2",
    "setup_suggestion": "new setup",
  })

  resp = joke_creation_fns.joke_creation_process(req)

  assert resp["data"]["joke_data"]["key"] == "j-2"
  assert suggestions == {
    "setup": "new setup",
    "punchline": None,  # Only setup_suggestion provided
  }


def test_joke_creation_process_generates_images(monkeypatch):
  """Scenario 3 should regenerate images for the joke."""
  monkeypatch.setattr(
    joke_creation_fns, 'get_user_id',
    lambda req, allow_unauthenticated=False: "user-42")
  joke = models.PunnyJoke(
    key="j-3",
    setup_text="Setup",
    punchline_text="Punch",
    setup_image_description="desc",
    punchline_image_description="desc",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, 'get_punny_joke',
                      lambda _: joke)

  generate_called = {}

  def fake_generate(target_joke, quality):
    generate_called["joke"] = target_joke
    generate_called["quality"] = quality
    return target_joke

  monkeypatch.setattr(joke_creation_fns.joke_operations,
                      'generate_joke_images', fake_generate)
  monkeypatch.setattr(joke_creation_fns.firestore, 'upsert_punny_joke',
                      lambda updated: updated)
  monkeypatch.setattr(joke_creation_fns.joke_operations, 'to_response_joke',
                      lambda _: {"key": "j-3"})

  req = DummyReq(data={
    "joke_id": "j-3",
    "populate_images": True,
    "image_quality": "medium",
  })

  resp = joke_creation_fns.joke_creation_process(req)

  assert resp["data"]["joke_data"]["key"] == "j-3"
  assert generate_called["joke"] == joke
  assert generate_called["quality"] == "medium"


def test_joke_creation_process_requires_valid_params(monkeypatch):
  """Unsupported parameter combinations should return errors."""
  monkeypatch.setattr(
    joke_creation_fns, 'get_user_id',
    lambda req, allow_unauthenticated=False: "user-42")

  req = DummyReq(data={"admin_owned": True})

  resp = joke_creation_fns.joke_creation_process(req)

  assert "error" in resp["data"]

