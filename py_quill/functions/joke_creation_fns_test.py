"""Tests for joke_creation_fns."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from agents import constants
from common import models, posable_character_sequence
from functions import joke_creation_fns
from PIL import Image
from services import gen_audio


class DummyReq:
  """Dummy request class for testing."""

  def __init__(self,
               is_json=True,
               data=None,
               args=None,
               headers=None,
               path="",
               method='POST'):
    self.is_json = is_json
    self._data = data or {}
    self.args = args or {}
    self.headers = headers or {}
    self.path = path
    self.method = method

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


def test_joke_creation_process_overrides_seasonal_tags(monkeypatch):
  captured_init = {}
  saved = {}

  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "user-1")

  created_joke = models.PunnyJoke(
    key="j-1",
    setup_text="Setup",
    punchline_text="Punch",
  )

  def fake_initialize_joke(**kwargs):
    captured_init.update(kwargs)
    return created_joke

  def fake_generate_metadata(joke):
    joke.seasonal = "Auto"
    joke.tags = ["auto"]
    return joke

  def fake_upsert(joke, operation=None, update_metadata=None):  # pylint: disable=unused-argument
    saved["joke"] = joke
    return joke

  monkeypatch.setattr(joke_creation_fns.joke_operations, "initialize_joke",
                      fake_initialize_joke)
  monkeypatch.setattr(joke_creation_fns.joke_operations,
                      "generate_joke_metadata", fake_generate_metadata)
  monkeypatch.setattr(joke_creation_fns.firestore, "upsert_punny_joke",
                      fake_upsert)

  req = DummyReq(
    data={
      "joke_id": "j-1",
      "setup_text": "Setup",
      "punchline_text": "Punch",
      "seasonal": " Winter ",
      "tags": "snow, cozy,",
    })

  joke_creation_fns.joke_creation_process(req)

  assert captured_init["seasonal"] == "Winter"
  assert captured_init["tags"] == ["snow", "cozy"]
  assert saved["joke"].seasonal == "Winter"
  assert saved["joke"].tags == ["snow", "cozy"]


def test_joke_creation_process_clears_seasonal_and_tags(monkeypatch):
  captured_init = {}
  saved = {}

  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "user-1")

  created_joke = models.PunnyJoke(
    key="j-2",
    setup_text="Setup",
    punchline_text="Punch",
    seasonal="Spring",
    tags=["fresh"],
  )

  def fake_initialize_joke(**kwargs):
    captured_init.update(kwargs)
    return created_joke

  def fake_upsert(joke, operation=None, update_metadata=None):  # pylint: disable=unused-argument
    saved["joke"] = joke
    return joke

  monkeypatch.setattr(joke_creation_fns.joke_operations, "initialize_joke",
                      fake_initialize_joke)
  monkeypatch.setattr(joke_creation_fns.firestore, "upsert_punny_joke",
                      fake_upsert)

  req = DummyReq(
    data={
      "joke_id": "j-2",
      "setup_text": "Setup",
      "punchline_text": "Punch",
      "seasonal": "",
      "tags": "",
    })

  joke_creation_fns.joke_creation_process(req)

  assert captured_init["seasonal"] == ""
  assert captured_init["tags"] == []
  assert saved["joke"].seasonal is None
  assert saved["joke"].tags == []


def test_joke_creation_process_creates_joke_from_text(monkeypatch):
  """Scenario 1 should initialize, regenerate, and save a new joke."""
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "user-42")

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

  def fake_upsert(joke, *, operation=None, update_metadata=None):
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
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "user-42")
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

  def fake_upsert(joke_to_save, *, operation=None, update_metadata=None):
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
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "user-42")
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
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "user-42")
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
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "user-42")
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
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "user-42")

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
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "user-42")

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
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "user-42")
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
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "user-42")

  req = DummyReq(data={"admin_owned": True})

  resp = joke_creation_fns.joke_creation_process(req)

  # For error cases, the function likely returns a response with status code != 200
  # We should check the response data
  data = resp.get_json()["data"]
  assert "error" in data


def test_joke_creation_process_defaults_op_to_proc(monkeypatch):
  """Missing op should default to the proc handler."""
  sentinel = object()
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")
  monkeypatch.setattr(joke_creation_fns, "_run_joke_creation_proc",
                      lambda _req: sentinel)

  resp = joke_creation_fns.joke_creation_process(DummyReq())

  assert resp is sentinel


def test_joke_creation_process_rejects_unknown_op(monkeypatch):
  """Unknown ops should return a validation error."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")
  resp = joke_creation_fns.joke_creation_process(
    DummyReq(data={"op": "unknown"}))

  data = resp.get_json()["data"]
  assert "error" in data
  assert "Unsupported op" in data["error"]


def test_joke_creation_process_handles_joke_image_op(monkeypatch):
  """JOKE_IMAGE should generate setup and punchline images."""
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "admin-user")

  mock_client = MagicMock()
  mock_setup_image = MagicMock()
  mock_setup_image.url = "http://example.com/setup.png"
  mock_setup_image.gcs_uri = "gs://bucket/setup.png"
  mock_setup_image.custom_temp_data = {"image_generation_call_id": "call-123"}

  mock_punchline_image = MagicMock()
  mock_punchline_image.url = "http://example.com/punchline.png"
  mock_punchline_image.custom_temp_data = {}

  mock_client.generate_image.side_effect = [
    mock_setup_image,
    mock_punchline_image,
  ]
  monkeypatch.setattr(joke_creation_fns, "_select_image_client",
                      lambda quality: mock_client)

  data = {
    "op":
    joke_creation_fns.JokeCreationOp.JOKE_IMAGE.value,
    "setup_image_prompt":
    "Setup prompt",
    "punchline_image_prompt":
    "Punch prompt",
    "setup_reference_images": [
      constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[0],
      constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[1],
    ],
    "punchline_reference_images": [
      constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[2],
    ],
    "include_setup_image":
    True,
    "image_quality":
    "low",
  }

  resp = joke_creation_fns.joke_creation_process(DummyReq(data=data))

  payload = resp.get_json()["data"]
  assert payload["setup_image_url"] == "http://example.com/setup.png"
  assert payload["punchline_image_url"] == "http://example.com/punchline.png"

  mock_client.generate_image.assert_called()
  first_call = mock_client.generate_image.call_args_list[0]
  assert first_call.args[0] == "Setup prompt"
  assert first_call.args[1] == [
    constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[0],
    constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[1],
  ]
  assert first_call.kwargs["save_to_firestore"] is False

  second_call = mock_client.generate_image.call_args_list[1]
  assert second_call.args[0] == "Punch prompt"
  assert second_call.args[1] == [
    constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS[2],
    "call-123",
  ]
  assert second_call.kwargs["save_to_firestore"] is False


def test_joke_creation_process_handles_printable_note_op(monkeypatch):
  """PRINTABLE_NOTE should create a manual notes sheet."""
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "admin-user")

  jokes = [
    models.PunnyJoke(
      key=f"j-{i}",
      setup_text=f"setup {i}",
      punchline_text=f"punch {i}",
    ) for i in range(5)
  ]

  monkeypatch.setattr(joke_creation_fns.firestore, "get_punny_jokes",
                      lambda joke_ids: jokes)

  captured = {}

  def fake_ensure_joke_notes_sheet(jokes_arg, sheet_slug=None, **_kwargs):
    captured["jokes"] = jokes_arg
    captured["sheet_slug"] = sheet_slug
    return models.JokeSheet(
      key="sheet-1",
      joke_ids=[j.key for j in jokes_arg],
      sheet_slug=sheet_slug,
      image_gcs_uri="gs://bucket/sheet.png",
      pdf_gcs_uri="gs://bucket/sheet.pdf",
    )

  monkeypatch.setattr(
    joke_creation_fns.joke_notes_sheet_operations,
    "ensure_joke_notes_sheet",
    fake_ensure_joke_notes_sheet,
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.PRINTABLE_NOTE.value,
        "joke_ids": [j.key for j in jokes],
        "sheet_slug": "manual-notes-pack",
      }))

  data = resp.get_json()["data"]
  assert data["sheet_id"] == "sheet-1"
  assert data["sheet_slug"] == "manual-notes-pack"
  assert captured["sheet_slug"] == "manual-notes-pack"
  assert len(captured["jokes"]) == 5


def test_joke_creation_process_handles_joke_audio_op(monkeypatch):
  """JOKE_AUDIO should generate and return three audio GCS URIs."""
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "admin-user",
  )

  joke = models.PunnyJoke(
    key="j-audio-1",
    setup_text="Setup",
    punchline_text="Punch",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, "get_punny_joke",
                      lambda _joke_id: joke)

  captured_audio_args: dict[str, str] = {}

  def fake_generate_audio(_joke,
                          *,
                          temp_output=False,
                          script_template=None,
                          audio_model=None,
                          allow_partial=False):
    captured_audio_args["script_template"] = script_template
    captured_audio_args["audio_model"] = audio_model
    captured_audio_args["allow_partial"] = allow_partial
    return joke_creation_fns.joke_operations.JokeAudioResult(
      dialog_gcs_uri="gs://public/audio/dialog.wav",
      setup_gcs_uri="gs://public/audio/setup.wav",
      response_gcs_uri="gs://public/audio/response.wav",
      punchline_gcs_uri="gs://public/audio/punchline.wav",
      generation_metadata=models.SingleGenerationMetadata(
        model_name="gemini-tts",
        token_counts={
          "prompt_tokens": 123,
          "output_tokens": 456,
        },
        cost=0.0123,
      ),
      clip_timing=None,
    )

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_audio",
    fake_generate_audio,
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.JOKE_AUDIO.value,
        "joke_id": "j-audio-1",
        "audio_model": "gemini-2.5-flash-preview-tts",
        "script_template": [
          {
            "voice": "GEMINI_LEDA",
            "script": "{setup_text}",
            "pause_sec_after": 1,
          },
          {
            "voice": "GEMINI_PUCK",
            "script": "what?",
            "pause_sec_after": 1,
          },
          {
            "voice": "GEMINI_LEDA",
            "script": "{punchline_text}",
          },
        ],
      }))

  payload = resp.get_json()["data"]
  assert payload["dialog_audio_gcs_uri"] == "gs://public/audio/dialog.wav"
  assert payload["setup_audio_gcs_uri"] == "gs://public/audio/setup.wav"
  assert payload["response_audio_gcs_uri"] == "gs://public/audio/response.wav"
  assert payload[
    "punchline_audio_gcs_uri"] == "gs://public/audio/punchline.wav"
  assert payload["audio_generation_metadata"]["model_name"] == "gemini-tts"
  assert payload["audio_generation_metadata"]["token_counts"][
    "prompt_tokens"] == 123
  assert payload["audio_generation_metadata"]["token_counts"][
    "output_tokens"] == 456
  turns = captured_audio_args["script_template"]
  assert [(t.voice, t.script, t.pause_sec_after) for t in turns] == [
    (gen_audio.Voice.GEMINI_LEDA, "{setup_text}", 1.0),
    (gen_audio.Voice.GEMINI_PUCK, "what?", 1.0),
    (gen_audio.Voice.GEMINI_LEDA, "{punchline_text}", None),
  ]
  assert captured_audio_args["audio_model"].value == "gemini-2.5-flash-preview-tts"


def test_joke_creation_process_handles_joke_audio_op_invalid_audio_model(
  monkeypatch,
):
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "admin-user",
  )

  joke = models.PunnyJoke(
    key="j-audio-invalid-model",
    setup_text="Setup",
    punchline_text="Punch",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, "get_punny_joke",
                      lambda _joke_id: joke)

  def should_not_run(*_args, **_kwargs):
    raise AssertionError("generate_joke_audio should not be called")

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_audio",
    should_not_run,
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.JOKE_AUDIO.value,
        "joke_id": "j-audio-invalid-model",
        "audio_model": "invalid-model-name",
      }))

  assert resp.status_code == 400
  payload = resp.get_json()["data"]
  assert payload["error_type"] == "invalid_request"
  assert "Invalid audio_model" in payload["error"]


def test_joke_creation_process_handles_joke_video_op(monkeypatch):
  """JOKE_VIDEO should generate and return a video GCS URI."""
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "admin-user",
  )

  joke = models.PunnyJoke(
    key="j-video-1",
    setup_text="Setup",
    punchline_text="Punch",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, "get_punny_joke",
                      lambda _joke_id: joke)

  audio_metadata = models.SingleGenerationMetadata(model_name="gemini-tts")
  generation_metadata = models.GenerationMetadata()
  generation_metadata.add_generation(audio_metadata)
  generation_metadata.add_generation(
    models.SingleGenerationMetadata(model_name="moviepy"))

  captured_audio_args: dict[str, object] = {}
  captured_video_args: dict[str, object] = {}

  def fake_generate_audio(
    _joke,
    *,
    temp_output=False,
    script_template=None,
    audio_model=None,
    allow_partial=False,
  ):
    captured_audio_args["script_template"] = script_template
    captured_audio_args["audio_model"] = audio_model
    captured_audio_args["temp_output"] = temp_output
    captured_audio_args["allow_partial"] = allow_partial
    return joke_creation_fns.joke_operations.JokeAudioResult(
      dialog_gcs_uri="gs://public/audio/dialog.wav",
      setup_gcs_uri="gs://public/audio/setup.wav",
      response_gcs_uri="gs://public/audio/response.wav",
      punchline_gcs_uri="gs://public/audio/punchline.wav",
      generation_metadata=audio_metadata,
      clip_timing=None,
    )

  def fake_generate_video_from_audio(
    _joke,
    *,
    setup_audio_gcs_uri,
    response_audio_gcs_uri,
    punchline_audio_gcs_uri,
    clip_timing=None,
    audio_generation_metadata=None,
    temp_output=False,
    is_test=False,
    character_class=None,
  ):
    captured_video_args["setup_audio_gcs_uri"] = setup_audio_gcs_uri
    captured_video_args["response_audio_gcs_uri"] = response_audio_gcs_uri
    captured_video_args["punchline_audio_gcs_uri"] = punchline_audio_gcs_uri
    captured_video_args["audio_generation_metadata"] = audio_generation_metadata
    captured_video_args["clip_timing"] = clip_timing
    captured_video_args["temp_output"] = temp_output
    captured_video_args["is_test"] = is_test
    captured_video_args["character_class"] = character_class
    return ("gs://public/video/joke.mp4", generation_metadata)

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_audio",
    fake_generate_audio,
  )
  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_video_from_audio_uris",
    fake_generate_video_from_audio,
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.JOKE_VIDEO.value,
        "joke_id": "j-video-1",
        "audio_model": "gemini-2.5-flash-preview-tts",
        "script_template": [
          {
            "voice": "GEMINI_LEDA",
            "script": "{setup_text}",
            "pause_sec_after": 1,
          },
          {
            "voice": "GEMINI_PUCK",
            "script": "what?",
            "pause_sec_after": 1,
          },
          {
            "voice": "GEMINI_LEDA",
            "script": "{punchline_text}",
          },
        ],
      }))

  payload = resp.get_json()["data"]
  assert payload["video_gcs_uri"] == "gs://public/video/joke.mp4"
  assert payload["dialog_audio_gcs_uri"] == "gs://public/audio/dialog.wav"
  assert payload["setup_audio_gcs_uri"] == "gs://public/audio/setup.wav"
  assert payload["response_audio_gcs_uri"] == "gs://public/audio/response.wav"
  assert payload["punchline_audio_gcs_uri"] == "gs://public/audio/punchline.wav"
  assert payload["audio_generation_metadata"]["model_name"] == "gemini-tts"
  assert payload["video_generation_metadata"]["total_cost"] == 0
  assert payload["video_generation_metadata"]["costs_by_model"][
    "gemini-tts"] == 0
  assert payload["video_generation_metadata"]["costs_by_model"]["moviepy"] == 0
  turns = captured_audio_args["script_template"]
  assert [(t.voice, t.script, t.pause_sec_after) for t in turns] == [
    (gen_audio.Voice.GEMINI_LEDA, "{setup_text}", 1.0),
    (gen_audio.Voice.GEMINI_PUCK, "what?", 1.0),
    (gen_audio.Voice.GEMINI_LEDA, "{punchline_text}", None),
  ]
  assert captured_audio_args["audio_model"].value == "gemini-2.5-flash-preview-tts"
  assert captured_audio_args["temp_output"] is True
  assert captured_video_args["setup_audio_gcs_uri"] == "gs://public/audio/setup.wav"
  assert captured_video_args[
    "response_audio_gcs_uri"] == "gs://public/audio/response.wav"
  assert captured_video_args[
    "punchline_audio_gcs_uri"] == "gs://public/audio/punchline.wav"
  assert captured_video_args["audio_generation_metadata"] is audio_metadata
  assert captured_video_args["clip_timing"] is None
  assert captured_video_args["temp_output"] is True
  assert captured_video_args["is_test"] is False


def test_joke_creation_process_handles_joke_video_op_invalid_script_template(
  monkeypatch,
):
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "admin-user",
  )

  joke = models.PunnyJoke(
    key="j-video-invalid-template",
    setup_text="Setup",
    punchline_text="Punch",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, "get_punny_joke",
                      lambda _joke_id: joke)

  def should_not_run(*_args, **_kwargs):
    raise AssertionError("generate_joke_audio should not be called")

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_audio",
    should_not_run,
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.JOKE_VIDEO.value,
        "joke_id": "j-video-invalid-template",
        "script_template": {
          "voice": "GEMINI_LEDA",
          "script": "{setup_text}",
        },
      }))

  assert resp.status_code == 400
  payload = resp.get_json()["data"]
  assert payload["error_type"] == "invalid_request"
  assert "script_template must be a list" in payload["error"]


def test_joke_creation_process_handles_joke_video_op_can_generate_test_video(
  monkeypatch,
):
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "admin-user",
  )

  joke = models.PunnyJoke(
    key="j-video-1",
    setup_text="Setup",
    punchline_text="Punch",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, "get_punny_joke",
                      lambda _joke_id: joke)

  audio_metadata = models.SingleGenerationMetadata(model_name="gemini-tts")
  generation_metadata = models.GenerationMetadata()
  generation_metadata.add_generation(audio_metadata)
  generation_metadata.add_generation(
    models.SingleGenerationMetadata(model_name="moviepy"))

  captured_video_args: dict[str, object] = {}

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_audio",
    lambda *_args, **_kwargs: joke_creation_fns.joke_operations.JokeAudioResult(
      dialog_gcs_uri="gs://public/audio/dialog.wav",
      setup_gcs_uri="gs://public/audio/setup.wav",
      response_gcs_uri="gs://public/audio/response.wav",
      punchline_gcs_uri="gs://public/audio/punchline.wav",
      generation_metadata=audio_metadata,
      clip_timing=None,
    ),
  )

  def fake_generate_video_from_audio(
    _joke,
    *,
    setup_audio_gcs_uri,
    response_audio_gcs_uri,
    punchline_audio_gcs_uri,
    clip_timing=None,
    audio_generation_metadata=None,
    temp_output=False,
    is_test=False,
    character_class=None,
  ):
    captured_video_args["is_test"] = is_test
    return ("gs://public/video/joke.mp4", generation_metadata)

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_video_from_audio_uris",
    fake_generate_video_from_audio,
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.JOKE_VIDEO.value,
        "joke_id": "j-video-1",
        "is_test_video": True,
      }))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert payload["video_gcs_uri"] == "gs://public/video/joke.mp4"
  assert captured_video_args["is_test"] is True


def test_joke_creation_process_handles_joke_video_op_returns_partial_when_video_fails(
  monkeypatch,
):
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "admin-user",
  )

  joke = models.PunnyJoke(
    key="j-video-2",
    setup_text="Setup",
    punchline_text="Punch",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, "get_punny_joke",
                      lambda _joke_id: joke)

  audio_metadata = models.SingleGenerationMetadata(model_name="gemini-tts")

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_audio",
    lambda *_args, **_kwargs: joke_creation_fns.joke_operations.JokeAudioResult(
      dialog_gcs_uri="gs://public/audio/dialog.wav",
      setup_gcs_uri="gs://public/audio/setup.wav",
      response_gcs_uri="gs://public/audio/response.wav",
      punchline_gcs_uri="gs://public/audio/punchline.wav",
      generation_metadata=audio_metadata,
      clip_timing=None,
    ),
  )

  def fail_video(*_args, **_kwargs):
    raise RuntimeError("video boom")

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_video_from_audio_uris",
    fail_video,
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.JOKE_VIDEO.value,
        "joke_id": "j-video-2",
        "allow_partial": True,
      }))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert "video_gcs_uri" not in payload
  assert payload["dialog_audio_gcs_uri"] == "gs://public/audio/dialog.wav"
  assert payload["setup_audio_gcs_uri"] == "gs://public/audio/setup.wav"
  assert payload["response_audio_gcs_uri"] == "gs://public/audio/response.wav"
  assert payload["punchline_audio_gcs_uri"] == "gs://public/audio/punchline.wav"
  assert payload["audio_generation_metadata"]["model_name"] == "gemini-tts"
  assert payload["error_stage"] == "video_generation"
  assert "Error generating video" in payload["error"]
  assert payload["video_generation_metadata"]["generations"][0][
    "model_name"] == "gemini-tts"


def test_joke_creation_process_handles_joke_video_op_returns_partial_when_audio_split_fails(
  monkeypatch,
):
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "admin-user",
  )

  joke = models.PunnyJoke(
    key="j-video-3",
    setup_text="Setup",
    punchline_text="Punch",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, "get_punny_joke",
                      lambda _joke_id: joke)

  audio_metadata = models.SingleGenerationMetadata(model_name="gemini-tts")

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_audio",
    lambda *_args, **_kwargs: joke_creation_fns.joke_operations.JokeAudioResult(
      dialog_gcs_uri="gs://public/audio/dialog.wav",
      setup_gcs_uri=None,
      response_gcs_uri=None,
      punchline_gcs_uri=None,
      generation_metadata=audio_metadata,
      clip_timing=None,
    ),
  )

  video_mock_called = {"called": False}

  def should_not_run(*_args, **_kwargs):
    video_mock_called["called"] = True
    raise AssertionError("video should not run when audio split fails")

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_video_from_audio_uris",
    should_not_run,
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.JOKE_VIDEO.value,
        "joke_id": "j-video-3",
        "allow_partial": True,
      }))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert "video_gcs_uri" not in payload
  assert payload["dialog_audio_gcs_uri"] == "gs://public/audio/dialog.wav"
  assert payload["setup_audio_gcs_uri"] is None
  assert payload["response_audio_gcs_uri"] is None
  assert payload["punchline_audio_gcs_uri"] is None
  assert payload["audio_generation_metadata"]["model_name"] == "gemini-tts"
  assert payload["error_stage"] == "audio_split"
  assert video_mock_called["called"] is False


def test_joke_creation_process_updates_book_page_ready(monkeypatch):
  """When book_page_ready is provided, it is saved to metadata on upsert."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "user-1")

  joke = models.PunnyJoke(
    key="j-1",
    setup_text="Setup",
    punchline_text="Punch",
  )
  monkeypatch.setattr(joke_creation_fns.joke_operations, "initialize_joke",
                      lambda **_kwargs: joke)

  captured: dict = {}

  def fake_upsert(joke_to_save, *, operation=None, update_metadata=None):
    captured["operation"] = operation
    captured["update_metadata"] = update_metadata
    return joke_to_save

  monkeypatch.setattr(joke_creation_fns.firestore, "upsert_punny_joke",
                      fake_upsert)
  monkeypatch.setattr(joke_creation_fns.joke_operations, "to_response_joke",
                      lambda saved: {"key": saved.key})

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(data={
      "joke_id": "j-1",
      "book_page_ready": True,
    }))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert payload["joke_data"]["key"] == "j-1"
  assert captured["update_metadata"] == {"book_page_ready": True}


def test_joke_creation_process_handles_animation_op(monkeypatch):
  """ANIMATION op should upsert a PosableCharacterSequence."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")

  captured: dict = {}

  def fake_upsert(sequence):
    captured["sequence"] = sequence
    sequence.key = sequence.key or "seq-123"
    return sequence

  monkeypatch.setattr(joke_creation_fns.firestore,
                      "upsert_posable_character_sequence", fake_upsert)

  # Valid sequence JSON
  sequence_data = {
    "sequence_left_eye_open": [{
      "start_time": 0.0,
      "end_time": 0.0,
      "value": True
    }],
    "sequence_right_eye_open": [],
    "sequence_mouth_state": [],
    "sequence_left_hand_visible": [],
    "sequence_right_hand_visible": [],
    "sequence_left_hand_transform": [],
    "sequence_right_hand_transform": [],
    "sequence_head_transform": [],
    "sequence_sound_events": [],
  }

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.ANIMATION.value,
        "sequence_data": sequence_data,
        "sequence_id": "seq-custom",
      }))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert payload["key"] == "seq-custom"
  assert captured["sequence"].key == "seq-custom"
  assert len(captured["sequence"].sequence_left_eye_open) == 1
  assert captured["sequence"].sequence_left_eye_open[0].value is True


def _character_uri_payload(file_identifier: str = "char") -> dict[str, str]:
  base = f"gs://images.quillsstorybook.com/_joke_assets/characters/{file_identifier}"
  return {
    "head_gcs_uri": f"{base}/{file_identifier}_head.png",
    "left_hand_gcs_uri": f"{base}/{file_identifier}_hand_left.png",
    "right_hand_gcs_uri": f"{base}/{file_identifier}_hand_right.png",
    "mouth_open_gcs_uri": f"{base}/{file_identifier}_mouth_open.png",
    "mouth_closed_gcs_uri": f"{base}/{file_identifier}_mouth_closed.png",
    "mouth_o_gcs_uri": f"{base}/{file_identifier}_mouth_o.png",
    "left_eye_open_gcs_uri": f"{base}/{file_identifier}_eye_left_open.png",
    "left_eye_closed_gcs_uri": f"{base}/{file_identifier}_eye_left_closed.png",
    "right_eye_open_gcs_uri": f"{base}/{file_identifier}_eye_right_open.png",
    "right_eye_closed_gcs_uri": f"{base}/{file_identifier}_eye_right_closed.png",
  }


def test_joke_creation_process_handles_character_def_op_create(monkeypatch):
  """CHARACTER op should create a new character definition when no ID provided."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")

  captured: dict = {}

  def fake_create(char_def):
    captured["char_def"] = char_def
    char_def.key = "new-char-1"
    return char_def

  monkeypatch.setattr(joke_creation_fns.firestore,
                      "create_posable_character_def", fake_create)
  monkeypatch.setattr(joke_creation_fns.cloud_storage, "download_image_from_gcs",
                      lambda _uri: Image.new("RGBA", (640, 360), (0, 0, 0, 0)))

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.CHARACTER.value,
        "name": "New Guy",
        **_character_uri_payload("new_guy"),
      },
    ))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert payload["key"] == "new-char-1"
  assert captured["char_def"].name == "New Guy"
  assert captured["char_def"].width == 640
  assert captured["char_def"].height == 360
  assert captured["char_def"].head_gcs_uri.endswith("new_guy_head.png")


def test_joke_creation_process_handles_character_def_op_update(monkeypatch):
  """CHARACTER op should update character definition when ID provided."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")

  captured: dict = {}

  def fake_update(char_def):
    captured["char_def"] = char_def
    return True

  monkeypatch.setattr(joke_creation_fns.firestore,
                      "update_posable_character_def", fake_update)
  monkeypatch.setattr(joke_creation_fns.cloud_storage, "download_image_from_gcs",
                      lambda _uri: Image.new("RGBA", (500, 300), (0, 0, 0, 0)))

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.CHARACTER.value,
        "character_id": "existing-char-1",
        "name": "Updated Guy",
        **_character_uri_payload("updated_guy"),
      },
    ))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert payload["key"] == "existing-char-1"
  assert captured["char_def"].key == "existing-char-1"
  assert captured["char_def"].name == "Updated Guy"
  assert captured["char_def"].width == 500
  assert captured["char_def"].height == 300


def test_joke_creation_process_handles_character_def_op_update_not_found(
    monkeypatch):
  """CHARACTER op should return 404 when updating non-existent character."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")

  monkeypatch.setattr(joke_creation_fns.firestore,
                      "update_posable_character_def", lambda _: False)
  monkeypatch.setattr(joke_creation_fns.cloud_storage, "download_image_from_gcs",
                      lambda _uri: Image.new("RGBA", (500, 300), (0, 0, 0, 0)))

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.CHARACTER.value,
        "character_id": "missing-char",
        "name": "Ghost",
        **_character_uri_payload("ghost"),
      },
    ))

  assert resp.status_code == 404
  payload = resp.get_json()["data"]
  assert "Character def not found" in payload["error"]


def test_joke_creation_process_character_def_op_rejects_mismatched_dimensions(
    monkeypatch):
  """CHARACTER op should fail when asset dimensions do not match."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")

  def _download_image(uri: str):
    if uri.endswith("_head.png"):
      return Image.new("RGBA", (600, 400), (0, 0, 0, 0))
    return Image.new("RGBA", (500, 300), (0, 0, 0, 0))

  monkeypatch.setattr(joke_creation_fns.cloud_storage, "download_image_from_gcs",
                      _download_image)

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.CHARACTER.value,
        "name": "Mismatch",
        **_character_uri_payload("mismatch"),
      },
    ))

  assert resp.status_code == 400
  payload = resp.get_json()["data"]
  assert "matching dimensions" in payload["error"]
