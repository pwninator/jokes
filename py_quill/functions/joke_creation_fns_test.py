"""Tests for joke_creation_fns."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
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
  """JOKE_AUDIO should generate and return audio GCS URIs."""
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

  captured_audio_args: dict[str, object] = {}

  def fake_generate_audio(_joke,
                          *,
                          temp_output=False,
                          script_template=None,
                          audio_model=None,
                          allow_partial=False):
    captured_audio_args["script_template"] = script_template
    captured_audio_args["audio_model"] = audio_model
    captured_audio_args["allow_partial"] = allow_partial
    return joke_creation_fns.joke_operations.JokeLipSyncResult(
      dialog_gcs_uri="gs://public/audio/dialog.wav",
      intro_audio_gcs_uri="gs://public/audio/intro.wav",
      setup_audio_gcs_uri="gs://public/audio/setup.wav",
      response_audio_gcs_uri="gs://public/audio/response.wav",
      punchline_audio_gcs_uri="gs://public/audio/punchline.wav",
      transcripts=joke_creation_fns.joke_operations.JokeAudioTranscripts(
        intro="intro", setup="setup", response="response", punchline="punch"),
      intro_sequence=None,
      setup_sequence=None,
      response_sequence=None,
      punchline_sequence=None,
      audio_generation_metadata=models.SingleGenerationMetadata(
        model_name="gemini-tts",
        token_counts={
          "prompt_tokens": 123,
          "output_tokens": 456,
        },
        cost=0.0123,
      ),
    )

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "get_joke_lip_sync_media",
    fake_generate_audio,
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op":
        joke_creation_fns.JokeCreationOp.JOKE_AUDIO.value,
        "joke_id":
        "j-audio-1",
        "audio_model":
        "gemini-2.5-flash-preview-tts",
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
  assert payload["intro_audio_gcs_uri"] == "gs://public/audio/intro.wav"
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
  assert captured_audio_args[
    "audio_model"].value == "gemini-2.5-flash-preview-tts"


def test_joke_creation_process_handles_joke_audio_op_invalid_audio_model(
  monkeypatch, ):
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
    "get_joke_lip_sync_media",
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
    setup_image_url="https://images.example.com/setup.png",
    punchline_image_url="https://images.example.com/punchline.png",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, "get_punny_joke",
                      lambda _joke_id: joke)

  audio_metadata = models.SingleGenerationMetadata(model_name="gemini-tts")
  generation_metadata = models.GenerationMetadata()
  generation_metadata.add_generation(audio_metadata)
  generation_metadata.add_generation(
    models.SingleGenerationMetadata(model_name="moviepy"))

  captured_video_args: dict[str, object] = {}

  def fake_generate_video(
    _joke,
    *,
    teller_character_def_id=None,
    listener_character_def_id=None,
    temp_output=False,
    script_template=None,
    audio_model=None,
    allow_partial=False,
  ):
    captured_video_args["teller_character_def_id"] = teller_character_def_id
    captured_video_args["listener_character_def_id"] = listener_character_def_id
    captured_video_args["script_template"] = script_template
    captured_video_args["audio_model"] = audio_model
    captured_video_args["temp_output"] = temp_output
    captured_video_args["allow_partial"] = allow_partial
    return joke_creation_fns.joke_operations.JokeVideoResult(
      video_gcs_uri="gs://public/video/joke.mp4",
      dialog_audio_gcs_uri="gs://public/audio/dialog.wav",
      intro_audio_gcs_uri="gs://public/audio/intro.wav",
      setup_audio_gcs_uri="gs://public/audio/setup.wav",
      response_audio_gcs_uri="gs://public/audio/response.wav",
      punchline_audio_gcs_uri="gs://public/audio/punchline.wav",
      audio_generation_metadata=audio_metadata,
      video_generation_metadata=generation_metadata,
    )

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_video",
    fake_generate_video,
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op":
        joke_creation_fns.JokeCreationOp.JOKE_VIDEO.value,
        "joke_id":
        "j-video-1",
        "teller_character_def_id":
        "char-teller",
        "listener_character_def_id":
        "char-listener",
        "audio_model":
        "gemini-2.5-flash-preview-tts",
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
  assert payload["intro_audio_gcs_uri"] == "gs://public/audio/intro.wav"
  assert payload["setup_audio_gcs_uri"] == "gs://public/audio/setup.wav"
  assert payload["response_audio_gcs_uri"] == "gs://public/audio/response.wav"
  assert payload[
    "punchline_audio_gcs_uri"] == "gs://public/audio/punchline.wav"
  assert payload["audio_generation_metadata"]["model_name"] == "gemini-tts"
  assert payload["video_generation_metadata"]["total_cost"] == 0
  assert payload["video_generation_metadata"]["costs_by_model"][
    "gemini-tts"] == 0
  assert payload["video_generation_metadata"]["costs_by_model"]["moviepy"] == 0
  turns = captured_video_args["script_template"]
  assert [(t.voice, t.script, t.pause_sec_after) for t in turns] == [
    (gen_audio.Voice.GEMINI_LEDA, "{setup_text}", 1.0),
    (gen_audio.Voice.GEMINI_PUCK, "what?", 1.0),
    (gen_audio.Voice.GEMINI_LEDA, "{punchline_text}", None),
  ]
  assert captured_video_args[
    "audio_model"].value == "gemini-2.5-flash-preview-tts"
  assert captured_video_args["temp_output"] is True
  assert captured_video_args["teller_character_def_id"] == "char-teller"
  assert captured_video_args["listener_character_def_id"] == "char-listener"


def test_joke_creation_process_handles_joke_video_op_invalid_script_template(
  monkeypatch, ):
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
    "generate_joke_video",
    should_not_run,
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.JOKE_VIDEO.value,
        "joke_id": "j-video-invalid-template",
        "teller_character_def_id": "char-teller",
        "listener_character_def_id": "char-listener",
        "script_template": {
          "voice": "GEMINI_LEDA",
          "script": "{setup_text}",
        },
      }))

  assert resp.status_code == 400
  payload = resp.get_json()["data"]
  assert payload["error_type"] == "invalid_request"
  assert "script_template must be a list" in payload["error"]


def test_joke_creation_process_handles_joke_video_op_requires_teller_character(
  monkeypatch, ):
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "admin-user",
  )

  joke = models.PunnyJoke(
    key="j-video-missing-teller",
    setup_text="Setup",
    punchline_text="Punch",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, "get_punny_joke",
                      lambda _joke_id: joke)

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_video",
    lambda *_args, **_kwargs: (_ for _ in ()).throw(
      AssertionError("generate_joke_video should not be called")),
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.JOKE_VIDEO.value,
        "joke_id": "j-video-missing-teller",
        "listener_character_def_id": "char-listener",
      }))

  assert resp.status_code == 400
  payload = resp.get_json()["data"]
  assert payload["error_type"] == "invalid_request"
  assert "teller_character_def_id is required" in payload["error"]


def test_joke_creation_process_handles_joke_video_op_allows_missing_listener_character(
  monkeypatch, ):
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "admin-user",
  )

  joke = models.PunnyJoke(
    key="j-video-missing-listener",
    setup_text="Setup",
    punchline_text="Punch",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, "get_punny_joke",
                      lambda _joke_id: joke)

  captured_video_args: dict[str, object] = {}

  def fake_generate_video(
    _joke,
    *,
    teller_character_def_id=None,
    listener_character_def_id=None,
    temp_output=False,
    script_template=None,
    audio_model=None,
    allow_partial=False,
  ):
    captured_video_args["teller_character_def_id"] = teller_character_def_id
    captured_video_args["listener_character_def_id"] = listener_character_def_id
    _ = temp_output
    _ = script_template
    _ = audio_model
    _ = allow_partial
    return joke_creation_fns.joke_operations.JokeVideoResult(
      video_gcs_uri="gs://public/video/joke.mp4",
      dialog_audio_gcs_uri=None,
      intro_audio_gcs_uri=None,
      setup_audio_gcs_uri=None,
      response_audio_gcs_uri=None,
      punchline_audio_gcs_uri=None,
      audio_generation_metadata=None,
      video_generation_metadata=models.GenerationMetadata(),
    )

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_video",
    fake_generate_video,
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.JOKE_VIDEO.value,
        "joke_id": "j-video-optional-listener",
        "teller_character_def_id": "char-teller",
      }))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert payload["video_gcs_uri"] == "gs://public/video/joke.mp4"
  assert captured_video_args["teller_character_def_id"] == "char-teller"
  assert captured_video_args["listener_character_def_id"] is None


def test_joke_creation_process_handles_joke_video_op_returns_partial_when_video_fails(
  monkeypatch, ):
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "admin-user",
  )

  joke = models.PunnyJoke(
    key="j-video-2",
    setup_text="Setup",
    punchline_text="Punch",
    setup_image_url="https://images.example.com/setup.png",
    punchline_image_url="https://images.example.com/punchline.png",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, "get_punny_joke",
                      lambda _joke_id: joke)

  audio_metadata = models.SingleGenerationMetadata(model_name="gemini-tts")

  generation_metadata = models.GenerationMetadata()
  generation_metadata.add_generation(audio_metadata)
  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_video",
    lambda *_args, **_kwargs: joke_creation_fns.joke_operations.
    JokeVideoResult(
      video_gcs_uri=None,
      dialog_audio_gcs_uri="gs://public/audio/dialog.wav",
      intro_audio_gcs_uri="gs://public/audio/intro.wav",
      setup_audio_gcs_uri="gs://public/audio/setup.wav",
      response_audio_gcs_uri="gs://public/audio/response.wav",
      punchline_audio_gcs_uri="gs://public/audio/punchline.wav",
      audio_generation_metadata=audio_metadata,
      video_generation_metadata=generation_metadata,
      error="Error generating video: video boom",
      error_stage="video_generation",
    ),
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.JOKE_VIDEO.value,
        "joke_id": "j-video-2",
        "teller_character_def_id": "char-teller",
        "listener_character_def_id": "char-listener",
        "allow_partial": True,
      }))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert payload["video_gcs_uri"] is None
  assert payload["dialog_audio_gcs_uri"] == "gs://public/audio/dialog.wav"
  assert payload["setup_audio_gcs_uri"] == "gs://public/audio/setup.wav"
  assert payload["response_audio_gcs_uri"] == "gs://public/audio/response.wav"
  assert payload[
    "punchline_audio_gcs_uri"] == "gs://public/audio/punchline.wav"
  assert payload["audio_generation_metadata"]["model_name"] == "gemini-tts"
  assert payload["error_stage"] == "video_generation"
  assert "Error generating video" in payload["error"]
  assert payload["video_generation_metadata"]["generations"][0][
    "model_name"] == "gemini-tts"


def test_joke_creation_process_handles_joke_video_op_returns_partial_when_audio_split_fails(
  monkeypatch, ):
  monkeypatch.setattr(
    joke_creation_fns,
    'get_user_id',
    lambda req, allow_unauthenticated=False, require_admin=False: "admin-user",
  )

  joke = models.PunnyJoke(
    key="j-video-3",
    setup_text="Setup",
    punchline_text="Punch",
    setup_image_url="https://images.example.com/setup.png",
    punchline_image_url="https://images.example.com/punchline.png",
  )
  monkeypatch.setattr(joke_creation_fns.firestore, "get_punny_joke",
                      lambda _joke_id: joke)

  audio_metadata = models.SingleGenerationMetadata(model_name="gemini-tts")

  generation_metadata = models.GenerationMetadata()
  generation_metadata.add_generation(audio_metadata)
  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "generate_joke_video",
    lambda *_args, **_kwargs: joke_creation_fns.joke_operations.
    JokeVideoResult(
      video_gcs_uri=None,
      dialog_audio_gcs_uri="gs://public/audio/dialog.wav",
      intro_audio_gcs_uri=None,
      setup_audio_gcs_uri=None,
      response_audio_gcs_uri=None,
      punchline_audio_gcs_uri=None,
      audio_generation_metadata=audio_metadata,
      video_generation_metadata=generation_metadata,
      error=
      "Generated dialog audio but could not produce all four split clips.",
      error_stage="audio_split",
    ),
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.JOKE_VIDEO.value,
        "joke_id": "j-video-3",
        "teller_character_def_id": "char-teller",
        "listener_character_def_id": "char-listener",
        "allow_partial": True,
      }))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert payload["video_gcs_uri"] is None
  assert payload["dialog_audio_gcs_uri"] == "gs://public/audio/dialog.wav"
  assert payload["setup_audio_gcs_uri"] is None
  assert payload["response_audio_gcs_uri"] is None
  assert payload["punchline_audio_gcs_uri"] is None
  assert payload["audio_generation_metadata"]["model_name"] == "gemini-tts"
  assert payload["error_stage"] == "audio_split"


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


def test_joke_creation_process_handles_animation_laugh_op(monkeypatch):
  """ANIMATION_LAUGH should return a generated PosableCharacterSequence."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")

  generated_sequence = posable_character_sequence.PosableCharacterSequence(
    sequence_left_eye_open=[
      posable_character_sequence.SequenceBooleanEvent(
        start_time=0.0,
        end_time=1.0,
        value=False,
      )
    ],
    sequence_sound_events=[
      posable_character_sequence.SequenceSoundEvent(
        start_time=0.0,
        end_time=1.0,
        gcs_uri="gs://audio/laugh.wav",
        volume=1.0,
      )
    ],
  )

  monkeypatch.setattr(
    joke_creation_fns.joke_operations,
    "build_laugh_sequence",
    lambda audio_gcs_uri: generated_sequence
    if audio_gcs_uri == "gs://audio/laugh.wav" else None,
  )

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={
        "op": joke_creation_fns.JokeCreationOp.ANIMATION_LAUGH.value,
        "audio_gcs_uri": "gs://audio/laugh.wav",
      }))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert len(payload["sequence_sound_events"]) == 1
  assert payload["sequence_sound_events"][0][
    "gcs_uri"] == "gs://audio/laugh.wav"
  assert payload["sequence_left_eye_open"][0]["value"] is False


def test_joke_creation_process_animation_laugh_requires_audio_gcs_uri(
    monkeypatch):
  """ANIMATION_LAUGH should require audio_gcs_uri."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(
      data={"op": joke_creation_fns.JokeCreationOp.ANIMATION_LAUGH.value}))

  data = resp.get_json()["data"]
  assert "error" in data
  assert "audio_gcs_uri is required" in data["error"]


def _character_uri_payload(file_identifier: str = "char") -> dict[str, str]:
  base = f"gs://images.quillsstorybook.com/_joke_assets/characters/{file_identifier}"
  return {
    "head_gcs_uri": f"{base}/{file_identifier}_head.png",
    "surface_line_gcs_uri": f"{base}/{file_identifier}_surface_line.png",
    "left_hand_gcs_uri": f"{base}/{file_identifier}_hand_left.png",
    "right_hand_gcs_uri": f"{base}/{file_identifier}_hand_right.png",
    "mouth_open_gcs_uri": f"{base}/{file_identifier}_mouth_open.png",
    "mouth_closed_gcs_uri": f"{base}/{file_identifier}_mouth_closed.png",
    "mouth_o_gcs_uri": f"{base}/{file_identifier}_mouth_o.png",
    "left_eye_open_gcs_uri": f"{base}/{file_identifier}_eye_left_open.png",
    "left_eye_closed_gcs_uri": f"{base}/{file_identifier}_eye_left_closed.png",
    "right_eye_open_gcs_uri": f"{base}/{file_identifier}_eye_right_open.png",
    "right_eye_closed_gcs_uri":
    f"{base}/{file_identifier}_eye_right_closed.png",
  }


def test_joke_creation_process_handles_character_def_op_create(monkeypatch):
  """CHARACTER op should upsert a character definition with provided ID."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")

  captured: dict = {}

  def fake_upsert(char_def):
    captured["char_def"] = char_def
    return char_def

  monkeypatch.setattr(joke_creation_fns.firestore,
                      "upsert_posable_character_def", fake_upsert)
  monkeypatch.setattr(joke_creation_fns.cloud_storage,
                      "download_image_from_gcs",
                      lambda _uri: Image.new("RGBA", (640, 360), (0, 0, 0, 0)))

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(data={
      "op": joke_creation_fns.JokeCreationOp.CHARACTER.value,
      "character_id": "new-char-1",
      "name": "New Guy",
      **_character_uri_payload("new_guy"),
    }, ))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert payload["key"] == "new-char-1"
  assert captured["char_def"].key == "new-char-1"
  assert captured["char_def"].name == "New Guy"
  assert captured["char_def"].width == 640
  assert captured["char_def"].height == 360
  assert captured["char_def"].head_gcs_uri.endswith("new_guy_head.png")


def test_joke_creation_process_character_def_op_requires_character_id(
    monkeypatch):
  """CHARACTER op should require a character_id."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")
  monkeypatch.setattr(joke_creation_fns.cloud_storage,
                      "download_image_from_gcs",
                      lambda _uri: Image.new("RGBA", (640, 360), (0, 0, 0, 0)))

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(data={
      "op": joke_creation_fns.JokeCreationOp.CHARACTER.value,
      "name": "Missing ID",
      **_character_uri_payload("new_guy_missing_id"),
    }, ))

  assert resp.status_code == 400
  payload = resp.get_json()["data"]
  assert "character_id is required" in payload["error"]


def test_joke_creation_process_handles_character_def_op_update(monkeypatch):
  """CHARACTER op should upsert character definition when ID provided."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")

  captured: dict = {}

  def fake_upsert(char_def):
    captured["char_def"] = char_def
    return char_def

  monkeypatch.setattr(joke_creation_fns.firestore,
                      "upsert_posable_character_def", fake_upsert)
  monkeypatch.setattr(joke_creation_fns.cloud_storage,
                      "download_image_from_gcs",
                      lambda _uri: Image.new("RGBA", (500, 300), (0, 0, 0, 0)))

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(data={
      "op": joke_creation_fns.JokeCreationOp.CHARACTER.value,
      "character_id": "existing-char-1",
      "name": "Updated Guy",
      **_character_uri_payload("updated_guy"),
    }, ))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert payload["key"] == "existing-char-1"
  assert captured["char_def"].key == "existing-char-1"
  assert captured["char_def"].name == "Updated Guy"
  assert captured["char_def"].width == 500
  assert captured["char_def"].height == 300


def test_joke_creation_process_handles_character_def_op_upserts_missing_character(
    monkeypatch):
  """CHARACTER op should upsert even when ID does not exist yet."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")

  captured: dict = {}

  def fake_upsert(char_def):
    captured["char_def"] = char_def
    return char_def

  monkeypatch.setattr(joke_creation_fns.firestore,
                      "upsert_posable_character_def", fake_upsert)
  monkeypatch.setattr(joke_creation_fns.cloud_storage,
                      "download_image_from_gcs",
                      lambda _uri: Image.new("RGBA", (500, 300), (0, 0, 0, 0)))

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(data={
      "op": joke_creation_fns.JokeCreationOp.CHARACTER.value,
      "character_id": "missing-char",
      "name": "Ghost",
      **_character_uri_payload("ghost"),
    }, ))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert payload["key"] == "missing-char"
  assert captured["char_def"].key == "missing-char"


def test_joke_creation_process_character_def_op_rejects_mismatched_dimensions(
    monkeypatch):
  """CHARACTER op should fail when asset dimensions do not match."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")

  def _download_image(uri: str):
    if uri.endswith("_head.png"):
      return Image.new("RGBA", (600, 400), (0, 0, 0, 0))
    return Image.new("RGBA", (500, 300), (0, 0, 0, 0))

  monkeypatch.setattr(joke_creation_fns.cloud_storage,
                      "download_image_from_gcs", _download_image)

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(data={
      "op": joke_creation_fns.JokeCreationOp.CHARACTER.value,
      "character_id": "mismatch-char",
      "name": "Mismatch",
      **_character_uri_payload("mismatch"),
    }, ))

  assert resp.status_code == 400
  payload = resp.get_json()["data"]
  assert "matching dimensions" in payload["error"]


def test_joke_creation_process_character_def_op_allows_surface_line_dimension_mismatch(
    monkeypatch):
  """CHARACTER op should allow surface line assets to differ in dimensions."""
  monkeypatch.setattr(joke_creation_fns, "get_user_id",
                      lambda *_args, **_kwargs: "admin-user")

  captured: dict = {}

  def fake_upsert(char_def):
    captured["char_def"] = char_def
    return char_def

  monkeypatch.setattr(joke_creation_fns.firestore,
                      "upsert_posable_character_def", fake_upsert)

  def _download_image(uri: str):
    # Standard sprite size for all character parts.
    if uri.endswith("_surface_line.png"):
      # Surface line is a thin overlay and is allowed to differ in dimensions.
      return Image.new("RGBA", (452, 9), (0, 0, 0, 0))
    return Image.new("RGBA", (500, 350), (0, 0, 0, 0))

  monkeypatch.setattr(joke_creation_fns.cloud_storage,
                      "download_image_from_gcs", _download_image)

  resp = joke_creation_fns.joke_creation_process(
    DummyReq(data={
      "op": joke_creation_fns.JokeCreationOp.CHARACTER.value,
      "character_id": "new-char-surface-line-mismatch",
      "name": "Surface Line Mismatch OK",
      **_character_uri_payload("surface_line_mismatch_ok"),
    }, ))

  assert resp.status_code == 200
  payload = resp.get_json()["data"]
  assert payload["key"] == "new-char-surface-line-mismatch"
  assert captured["char_def"].width == 500
  assert captured["char_def"].height == 350
