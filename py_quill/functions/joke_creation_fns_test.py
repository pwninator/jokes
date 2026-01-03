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
  monkeypatch.setattr(joke_creation_fns.image_generation,
                      'PUN_IMAGE_CLIENTS_BY_QUALITY', {
                        "low": object(),
                        "medium": object(),
                        "medium_mini": object(),
                      })


@pytest.fixture(autouse=True)
def stub_scene_idea_generation(monkeypatch):
  """Prevent real prompt calls by stubbing scene idea generation."""

  def fake_generate(*_args, **_kwargs):
    return ("idea-setup", "idea-punch",
            models.SingleGenerationMetadata(model_name="test"))

  monkeypatch.setattr(
    joke_creation_fns.joke_operations.joke_operation_prompts,
    "generate_joke_scene_ideas",
    fake_generate,
  )


def test_joke_creation_process_creates_joke_from_text(monkeypatch):
  """Scenario 1 should initialize, regenerate, and save a new joke."""
  monkeypatch.setattr(joke_creation_fns,
                      'get_user_id',
                      lambda req, allow_unauthenticated=False: "user-42")

  init_kwargs = {}

  def fake_initialize(**kwargs):
    init_kwargs.update(kwargs)
    return models.PunnyJoke(
      setup_text=kwargs["setup_text"],
      punchline_text=kwargs["punchline_text"],
    )

  regen_called = {"count": 0}

  def fake_regenerate(joke):
    regen_called["count"] += 1
    return joke

  monkeypatch.setattr(joke_creation_fns.joke_operations, 'initialize_joke',
                      fake_initialize)
  monkeypatch.setattr(joke_creation_fns.joke_operations,
                      'regenerate_scene_ideas', fake_regenerate)

  upsert_calls = {}

  def fake_upsert(joke, *, operation=None):
    upsert_calls["operation"] = operation
    joke.key = "j-1"
    return joke

  monkeypatch.setattr(joke_creation_fns.firestore, 'upsert_punny_joke',
                      fake_upsert)
  monkeypatch.setattr(
    joke_creation_fns.joke_operations, 'to_response_joke', lambda joke: {
      "key": joke.key,
      "owner_user_id": "user-42"
    })

  req = DummyReq(data={
    "setup_text": "Setup",
    "punchline_text": "Punch",
    "admin_owned": True,
  })

  resp = joke_creation_fns.joke_creation_process(req)

  data = resp.get_json()["data"]
  assert data["joke_data"]["key"] == "j-1"
  assert init_kwargs["admin_owned"] is True
  assert init_kwargs["user_id"] == "user-42"
  assert regen_called["count"] == 1
  assert upsert_calls["operation"] == "CREATE"


def test_joke_creation_process_applies_suggestions(monkeypatch):
  """Scenario 2 should apply suggestions and persist the joke."""
  monkeypatch.setattr(joke_creation_fns,
                      'get_user_id',
                      lambda req, allow_unauthenticated=False: "user-42")
  joke = models.PunnyJoke(
    key="j-2",
    setup_text="S",
    punchline_text="P",
    setup_scene_idea="old setup",
    punchline_scene_idea="old punch",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, 'upsert_punny_joke',
                      lambda updated: updated)  # Return the joke as saved

  suggestions = {}

  def fake_modify(j, setup_suggestion, punchline_suggestion):
    suggestions["setup"] = setup_suggestion
    suggestions["punchline"] = punchline_suggestion
    return j  # Return the joke (modified)

  def fake_initialize(**kwargs):
    assert kwargs["joke_id"] == "j-2"
    if kwargs["setup_scene_idea"] is not None:
      joke.setup_scene_idea = kwargs["setup_scene_idea"]
    if kwargs["punchline_scene_idea"] is not None:
      joke.punchline_scene_idea = kwargs["punchline_scene_idea"]
    return joke

  monkeypatch.setattr(joke_creation_fns.joke_operations, 'initialize_joke',
                      fake_initialize)
  monkeypatch.setattr(joke_creation_fns.joke_operations,
                      'modify_image_scene_ideas', fake_modify)
  monkeypatch.setattr(joke_creation_fns.joke_operations, 'to_response_joke',
                      lambda _: {"key": "j-2"})

  upsert_calls = {}

  def fake_upsert(joke_to_save, *, operation=None):
    upsert_calls["operation"] = operation
    return joke_to_save

  monkeypatch.setattr(joke_creation_fns.firestore, 'upsert_punny_joke',
                      fake_upsert)

  req = DummyReq(
    data={
      "joke_id": "j-2",
      "setup_suggestion": "new setup",
      "punchline_suggestion": "new punchline",
      "setup_scene_idea": "override setup",
      "punchline_scene_idea": "override punch",
    })

  resp = joke_creation_fns.joke_creation_process(req)

  data = resp.get_json()["data"]
  assert data["joke_data"]["key"] == "j-2"
  assert suggestions == {
    "setup": "new setup",
    "punchline": "new punchline",
  }
  assert joke.setup_scene_idea == "override setup"
  assert joke.punchline_scene_idea == "override punch"
  assert upsert_calls["operation"] == "UPDATE_SCENE_IDEAS"


def test_joke_creation_process_applies_partial_suggestions(monkeypatch):
  """Scenario 2 should work with only setup_suggestion."""
  monkeypatch.setattr(joke_creation_fns,
                      'get_user_id',
                      lambda req, allow_unauthenticated=False: "user-42")
  joke = models.PunnyJoke(key="j-2", setup_text="S", punchline_text="P")
  monkeypatch.setattr(joke_creation_fns.firestore, 'upsert_punny_joke',
                      lambda updated: updated)

  suggestions = {}

  def fake_modify(j, setup_suggestion, punchline_suggestion):
    suggestions["setup"] = setup_suggestion
    suggestions["punchline"] = punchline_suggestion
    return j

  def fake_initialize(**kwargs):
    assert kwargs["joke_id"] == "j-2"
    return joke

  monkeypatch.setattr(joke_creation_fns.joke_operations, 'initialize_joke',
                      fake_initialize)
  monkeypatch.setattr(joke_creation_fns.joke_operations,
                      'modify_image_scene_ideas', fake_modify)
  monkeypatch.setattr(joke_creation_fns.joke_operations, 'to_response_joke',
                      lambda _: {"key": "j-2"})

  monkeypatch.setattr(joke_creation_fns.firestore, 'upsert_punny_joke',
                      lambda updated, **_kwargs: updated)

  req = DummyReq(data={
    "joke_id": "j-2",
    "setup_suggestion": "new setup",
  })

  resp = joke_creation_fns.joke_creation_process(req)

  data = resp.get_json()["data"]
  assert data["joke_data"]["key"] == "j-2"
  assert suggestions == {
    "setup": "new setup",
    "punchline": None,  # Only setup_suggestion provided
  }


def test_joke_creation_process_generates_images(monkeypatch):
  """Scenario 3 should regenerate images for the joke."""
  monkeypatch.setattr(joke_creation_fns,
                      'get_user_id',
                      lambda req, allow_unauthenticated=False: "user-42")
  joke = models.PunnyJoke(
    key="j-3",
    setup_text="Setup",
    punchline_text="Punch",
    setup_image_description="desc",
    punchline_image_description="desc",
  )
  generate_called = {}

  def fake_generate(target_joke, quality):
    generate_called["joke"] = target_joke
    generate_called["quality"] = quality
    return target_joke

  def fake_initialize(**kwargs):
    if kwargs["setup_scene_idea"] is not None:
      joke.setup_scene_idea = kwargs["setup_scene_idea"]
    if kwargs["setup_image_description"] is not None:
      joke.setup_image_description = kwargs["setup_image_description"]
    if kwargs["punchline_image_description"] is not None:
      joke.punchline_image_description = kwargs["punchline_image_description"]
    return joke

  monkeypatch.setattr(joke_creation_fns.joke_operations, 'initialize_joke',
                      fake_initialize)
  monkeypatch.setattr(joke_creation_fns.joke_operations,
                      'generate_joke_images', fake_generate)
  monkeypatch.setattr(joke_creation_fns.firestore, 'upsert_punny_joke',
                      lambda updated, **_kwargs: updated)
  monkeypatch.setattr(joke_creation_fns.joke_operations, 'to_response_joke',
                      lambda _: {"key": "j-3"})

  req = DummyReq(
    data={
      "joke_id": "j-3",
      "populate_images": True,
      "image_quality": "medium",
      "setup_scene_idea": "override setup idea",
    })

  resp = joke_creation_fns.joke_creation_process(req)

  data = resp.get_json()["data"]
  assert data["joke_data"]["key"] == "j-3"
  assert generate_called["joke"] == joke
  assert generate_called["quality"] == "medium"
  assert joke.setup_scene_idea == "override setup idea"


def test_joke_creation_process_uses_description_overrides(monkeypatch):
  """Image generation should use latest descriptions provided in the request."""
  monkeypatch.setattr(joke_creation_fns,
                      'get_user_id',
                      lambda req, allow_unauthenticated=False: "user-42")
  joke = models.PunnyJoke(
    key="j-3b",
    setup_text="Setup",
    punchline_text="Punch",
    setup_image_description="old setup desc",
    punchline_image_description="old punch desc",
  )
  generate_called = {}

  def fake_generate(target_joke, quality):
    generate_called["setup_desc"] = target_joke.setup_image_description
    generate_called["punch_desc"] = target_joke.punchline_image_description
    generate_called["quality"] = quality
    return target_joke

  def fake_initialize(**kwargs):
    if kwargs["setup_image_description"] is not None:
      joke.setup_image_description = kwargs["setup_image_description"]
    if kwargs["punchline_image_description"] is not None:
      joke.punchline_image_description = kwargs["punchline_image_description"]
    return joke

  monkeypatch.setattr(joke_creation_fns.joke_operations, 'initialize_joke',
                      fake_initialize)
  monkeypatch.setattr(joke_creation_fns.joke_operations,
                      'generate_joke_images', fake_generate)
  monkeypatch.setattr(joke_creation_fns.firestore, 'upsert_punny_joke',
                      lambda updated, **_kwargs: updated)
  monkeypatch.setattr(joke_creation_fns.joke_operations, 'to_response_joke',
                      lambda _: {"key": "j-3b"})

  req = DummyReq(
    data={
      "joke_id": "j-3b",
      "populate_images": True,
      "image_quality": "low",
      "setup_image_description": "new setup desc",
      "punchline_image_description": "new punch desc",
    })

  resp = joke_creation_fns.joke_creation_process(req)

  data = resp.get_json()["data"]
  assert data["joke_data"]["key"] == "j-3b"
  assert generate_called["setup_desc"] == "new setup desc"
  assert generate_called["punch_desc"] == "new punch desc"
  assert generate_called["quality"] == "low"


def test_joke_creation_process_updates_text_no_regen(monkeypatch):
  """Scenario 1.5 should update text without regenerating ideas when flag false."""
  monkeypatch.setattr(joke_creation_fns,
                      'get_user_id',
                      lambda req, allow_unauthenticated=False: "user-42")

  joke = models.PunnyJoke(
    key="j-5",
    setup_text="old setup",
    punchline_text="old punch",
    setup_scene_idea="scene setup",
    punchline_scene_idea="scene punch",
    generation_metadata=models.GenerationMetadata(),
  )
  regen_calls = {"count": 0}

  def fake_regenerate(target_joke):
    regen_calls["count"] += 1
    return target_joke

  def fake_initialize(**kwargs):
    if kwargs["setup_text"] is not None:
      joke.setup_text = kwargs["setup_text"]
    if kwargs["punchline_text"] is not None:
      joke.punchline_text = kwargs["punchline_text"]
    return joke

  monkeypatch.setattr(joke_creation_fns.joke_operations, 'initialize_joke',
                      fake_initialize)
  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    'regenerate_scene_ideas',
    fake_regenerate,
  )
  monkeypatch.setattr(joke_creation_fns.firestore, 'upsert_punny_joke',
                      lambda updated, **_kwargs: updated)
  monkeypatch.setattr(joke_creation_fns.joke_operations, 'to_response_joke',
                      lambda _: {"key": "j-5"})

  req = DummyReq(
    data={
      "joke_id": "j-5",
      "setup_text": "new setup",
      "punchline_text": "new punch",
      "regenerate_scene_ideas": False,
    })

  resp = joke_creation_fns.joke_creation_process(req)

  data = resp.get_json()["data"]
  assert data["joke_data"]["key"] == "j-5"
  assert joke.setup_text == "new setup"
  assert joke.punchline_text == "new punch"
  assert regen_calls["count"] == 0


def test_joke_creation_process_updates_text_with_regen(monkeypatch):
  """Scenario 1.5 should request regeneration when flag true."""
  monkeypatch.setattr(joke_creation_fns,
                      'get_user_id',
                      lambda req, allow_unauthenticated=False: "user-42")

  joke = models.PunnyJoke(
    key="j-6",
    setup_text="old setup",
    punchline_text="old punch",
    setup_scene_idea="scene setup",
    punchline_scene_idea="scene punch",
    generation_metadata=models.GenerationMetadata(),
  )
  regen_calls = {"count": 0}

  def fake_regenerate(target_joke):
    regen_calls["count"] += 1
    return target_joke

  def fake_initialize(**kwargs):
    if kwargs["setup_text"] is not None:
      joke.setup_text = kwargs["setup_text"]
    if kwargs["punchline_text"] is not None:
      joke.punchline_text = kwargs["punchline_text"]
    return joke

  monkeypatch.setattr(joke_creation_fns.joke_operations, 'initialize_joke',
                      fake_initialize)
  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    'regenerate_scene_ideas',
    fake_regenerate,
  )
  monkeypatch.setattr(joke_creation_fns.firestore, 'upsert_punny_joke',
                      lambda updated, **_kwargs: updated)
  monkeypatch.setattr(joke_creation_fns.joke_operations, 'to_response_joke',
                      lambda _: {"key": "j-6"})

  req = DummyReq(
    data={
      "joke_id": "j-6",
      "setup_text": "new setup",
      "punchline_text": "new punch",
      "regenerate_scene_ideas": True,
    })

  resp = joke_creation_fns.joke_creation_process(req)

  data = resp.get_json()["data"]
  assert data["joke_data"]["key"] == "j-6"
  assert regen_calls["count"] == 1


def test_joke_creation_process_generates_descriptions(monkeypatch):
  """Scenario 2.5 should generate image descriptions only."""
  monkeypatch.setattr(joke_creation_fns,
                      'get_user_id',
                      lambda req, allow_unauthenticated=False: "user-42")
  joke = models.PunnyJoke(
    key="j-4",
    setup_text="Setup",
    punchline_text="Punch",
    setup_scene_idea="scene 1",
    punchline_scene_idea="scene 2",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, 'get_punny_joke',
                      lambda _: joke)

  called = {}

  def fake_generate(j):
    called["joke"] = j
    j.setup_image_description = "desc 1"
    j.punchline_image_description = "desc 2"
    return j

  monkeypatch.setattr(joke_creation_fns.joke_operations,
                      'generate_image_descriptions', fake_generate)

  def fake_generate_images(target_joke, quality):
    called["image_quality"] = quality
    return target_joke

  monkeypatch.setattr(joke_creation_fns.joke_operations,
                      'generate_joke_images', fake_generate_images)
  monkeypatch.setattr(joke_creation_fns.firestore, 'upsert_punny_joke',
                      lambda updated, **_kwargs: updated)
  monkeypatch.setattr(joke_creation_fns.joke_operations, 'to_response_joke',
                      lambda _: {"key": "j-4"})

  req = DummyReq(
    data={
      "joke_id": "j-4",
      "generate_descriptions": True,
      "setup_scene_idea": "override setup idea",
    })

  resp = joke_creation_fns.joke_creation_process(req)

  data = resp.get_json()["data"]
  assert data["joke_data"]["key"] == "j-4"
  assert called["joke"].setup_image_description == "desc 1"
  assert called["joke"].punchline_image_description == "desc 2"
  # Override should have been applied before generation
  assert called["joke"].setup_scene_idea == "override setup idea"


def test_joke_creation_process_requires_valid_params(monkeypatch):
  """Unsupported parameter combinations should return errors."""
  monkeypatch.setattr(joke_creation_fns,
                      'get_user_id',
                      lambda req, allow_unauthenticated=False: "user-42")

  req = DummyReq(data={"admin_owned": True})

  resp = joke_creation_fns.joke_creation_process(req)

  # For error cases, the function likely returns a response with status code != 200
  # We should check the response data
  data = resp.get_json()["data"]
  assert "error" in data

@pytest.fixture(autouse=True)
def stub_metadata_generation(monkeypatch):
  """Prevent real prompt calls by stubbing metadata generation."""
  def fake_generate_metadata(joke):
    return joke

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_metadata",
    fake_generate_metadata,
  )
