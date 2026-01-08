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
    "setup_scene_idea": "Setup concept",
    "punchline_scene_idea": "Punchline concept",
  }
  joke = models.PunnyJoke.from_firestore_dict(data, key="abc")
  assert joke.state == models.JokeState.DRAFT
  assert joke.setup_scene_idea == "Setup concept"
  assert joke.punchline_scene_idea == "Punchline concept"


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
  joke.setup_scene_idea = "Setup idea"
  joke.punchline_scene_idea = "Punchline idea"

  md = models.GenerationMetadata()
  md.add_generation(
    models.SingleGenerationMetadata(label="x", model_name="m", cost=1.0))
  joke.generation_metadata = md

  d1 = joke.to_dict(include_key=False)
  assert d1["state"] == "DRAFT"
  assert "key" not in d1
  assert d1["setup_scene_idea"] == "Setup idea"
  assert d1["punchline_scene_idea"] == "Punchline idea"
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


def test_get_minimal_joke_data_returns_correct_fields():
  """Test that get_minimal_joke_data returns a dictionary with the correct fields."""
  joke = models.PunnyJoke(
    key="joke123",
    setup_text="Why did the scarecrow win an award?",
    punchline_text="Because he was outstanding in his field.",
    setup_image_url="http://example.com/setup.png",
    punchline_image_url="http://example.com/punchline.png",
    pun_theme="awards",
    num_viewed_users=100,
  )
  minimal_data = joke.get_minimal_joke_data()
  expected_keys = {
    "key",
    "setup_text",
    "punchline_text",
    "setup_image_url",
    "punchline_image_url",
  }
  assert set(minimal_data.keys()) == expected_keys
  assert minimal_data["key"] == "joke123"
  assert minimal_data["setup_text"] == "Why did the scarecrow win an award?"
  assert minimal_data[
    "punchline_text"] == "Because he was outstanding in his field."
  assert minimal_data["setup_image_url"] == "http://example.com/setup.png"
  assert minimal_data[
    "punchline_image_url"] == "http://example.com/punchline.png"


def test_get_minimal_joke_data_with_none_values():
  """Test that get_minimal_joke_data handles None values correctly."""
  joke = models.PunnyJoke(setup_text="setup", punchline_text="punchline")
  # key, setup_image_url, and punchline_image_url are None by default
  minimal_data = joke.get_minimal_joke_data()
  expected_keys = {
    "key",
    "setup_text",
    "punchline_text",
    "setup_image_url",
    "punchline_image_url",
  }
  assert set(minimal_data.keys()) == expected_keys
  assert minimal_data["key"] is None
  assert minimal_data["setup_text"] == "setup"
  assert minimal_data["punchline_text"] == "punchline"
  assert minimal_data["setup_image_url"] is None
  assert minimal_data["punchline_image_url"] is None


def test_get_minimal_joke_data_with_partial_image_urls():
  """Test that get_minimal_joke_data handles partial image URLs."""
  joke = models.PunnyJoke(
    key="joke456",
    setup_text="Why did the chicken cross the road?",
    punchline_text="To get to the other side.",
    setup_image_url="http://example.com/setup.png",
    # punchline_image_url is None
  )
  minimal_data = joke.get_minimal_joke_data()
  assert minimal_data["key"] == "joke456"
  assert minimal_data["setup_text"] == "Why did the chicken cross the road?"
  assert minimal_data["punchline_text"] == "To get to the other side."
  assert minimal_data["setup_image_url"] == "http://example.com/setup.png"
  assert minimal_data["punchline_image_url"] is None


def test_jokesheet_slug_builds_from_category_and_index():
  sheet = models.JokeSheet(category_id="reptiles_and_dinosaurs", index=2)
  assert sheet.slug == "free-reptiles-and-dinosaurs-jokes-3"


def test_jokesheet_display_index_returns_one_based_value():
  sheet = models.JokeSheet(category_id="cats", index=0)
  assert sheet.display_index == 1
  sheet = models.JokeSheet(category_id="cats", index=None)
  assert sheet.display_index is None


def test_jokesheet_slug_none_when_missing_fields():
  sheet = models.JokeSheet(category_id=None, index=2)
  assert sheet.slug is None
  sheet = models.JokeSheet(category_id="cats", index=None)
  assert sheet.slug is None


def test_jokesheet_parse_slug_returns_category_and_index():
  category_id, index = models.JokeSheet.parse_slug(
    "free-reptiles-and-dinosaurs-jokes-3")
  assert category_id == "reptiles_and_dinosaurs"
  assert index == 2


def test_jokesheet_parse_slug_rejects_invalid_slug():
  category_id, index = models.JokeSheet.parse_slug("bad-slug")
  assert category_id is None
  assert index is None
  category_id, index = models.JokeSheet.parse_slug(
    "free-animals-jokes-0")
  assert category_id is None
  assert index is None


def test_jokecategory_from_firestore_parses_negative_tags():
  data = {
    "display_name": "Cats",
    "negative_tags": ["nsfw", "  politics  ", 123],
  }
  category = models.JokeCategory.from_firestore_dict(data, key="cats")
  assert category.negative_tags == ["nsfw", "politics"]
