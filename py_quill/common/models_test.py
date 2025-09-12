"""Tests for the models module."""
import datetime

from common import models


def test_punnyjoke_default_state_unknown():
  """Test that the default state is UNKNOWN."""
  joke = models.PunnyJoke(setup_text="setup", punchline_text="punchline")
  assert joke.state == models.JokeState.UNKNOWN


def test_punnyjoke_from_firestore_maps_state_string_to_enum():
  """Test that the from_firestore_dict method maps the state string to the JokeState enum."""
  data = {
    "setup_text": "s",
    "punchline_text": "p",
    "state": "DRAFT",
  }
  joke = models.PunnyJoke.from_firestore_dict(data, key="abc")
  assert joke.state == models.JokeState.DRAFT


def test_punnyjoke_from_firestore_missing_state_defaults_unknown():
  """Test that the from_firestore_dict method defaults to UNKNOWN state if the state is missing."""
  data = {
    "setup_text": "s",
    "punchline_text": "p",
  }
  joke = models.PunnyJoke.from_firestore_dict(data, key="abc")
  assert joke.state == models.JokeState.UNKNOWN


def test_punnyjoke_to_dict_serializes_state_and_metadata_and_key_optional():
  """Test that to_dict serializes state, metadata, and handles key inclusion."""
  joke = models.PunnyJoke(setup_text="setup", punchline_text="punchline")
  joke.state = models.JokeState.DRAFT
  joke.key = "abc123"

  md = models.GenerationMetadata()
  md.add_generation(
    models.SingleGenerationMetadata(label="x", model_name="m", cost=1.0))
  joke.generation_metadata = md

  d1 = joke.to_dict(include_key=False)
  assert d1["state"] == "DRAFT"
  assert "key" not in d1
  assert isinstance(d1["generation_metadata"], dict)
  assert "generations" in d1["generation_metadata"]

  d2 = joke.to_dict(include_key=True)
  assert d2["key"] == "abc123"


def test_punnyjoke_public_timestamp_in_to_dict():
  """`public_timestamp` should be passed through as datetime in to_dict."""
  ts = datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
  joke = models.PunnyJoke(setup_text="s",
                          punchline_text="p",
                          public_timestamp=ts)

  d = joke.to_dict()
  assert "public_timestamp" in d
  assert isinstance(d["public_timestamp"], datetime.datetime)
  assert d["public_timestamp"] == ts


def test_punnyjoke_from_firestore_dict_public_timestamp_passthrough():
  """from_firestore_dict should accept datetime for public_timestamp."""
  ts = datetime.datetime(2024, 2, 3, 4, 5, 6, tzinfo=datetime.timezone.utc)
  src = {
    "setup_text": "s",
    "punchline_text": "p",
    "public_timestamp": ts,
  }
  joke = models.PunnyJoke.from_firestore_dict(src, key="k1")
  assert joke.public_timestamp == ts


def test_set_setup_image_updates_text_by_default():
  """Test that set_setup_image updates text fields by default."""
  joke = models.PunnyJoke(setup_text="s", punchline_text="p")
  image = models.Image(url="http://example.com/img.png",
                       original_prompt="orig",
                       final_prompt="final")
  joke.set_setup_image(image)
  assert joke.setup_image_url == "http://example.com/img.png"
  assert joke.setup_image_description == "orig"
  assert joke.setup_image_prompt == "final"


def test_set_setup_image_skips_text_update_when_false():
  """Test that set_setup_image skips updating text fields when update_text is False."""
  joke = models.PunnyJoke(setup_text="s",
                          punchline_text="p",
                          setup_image_description="before",
                          setup_image_prompt="before")
  image = models.Image(url="http://example.com/img.png",
                       original_prompt="after",
                       final_prompt="after")
  joke.set_setup_image(image, update_text=False)
  assert joke.setup_image_url == "http://example.com/img.png"
  assert joke.setup_image_description == "before"
  assert joke.setup_image_prompt == "before"


def test_set_punchline_image_updates_text_by_default():
  """Test that set_punchline_image updates text fields by default."""
  joke = models.PunnyJoke(setup_text="s", punchline_text="p")
  image = models.Image(url="http://example.com/img.png",
                       original_prompt="orig",
                       final_prompt="final")
  joke.set_punchline_image(image)
  assert joke.punchline_image_url == "http://example.com/img.png"
  assert joke.punchline_image_description == "orig"
  assert joke.punchline_image_prompt == "final"


def test_set_punchline_image_skips_text_update_when_false():
  """Test that set_punchline_image skips updating text fields when update_text is False."""
  joke = models.PunnyJoke(setup_text="s",
                          punchline_text="p",
                          punchline_image_description="before",
                          punchline_image_prompt="before")
  image = models.Image(url="http://example.com/img.png",
                       original_prompt="after",
                       final_prompt="after")
  joke.set_punchline_image(image, update_text=False)
  assert joke.punchline_image_url == "http://example.com/img.png"
  assert joke.punchline_image_description == "before"
  assert joke.punchline_image_prompt == "before"
