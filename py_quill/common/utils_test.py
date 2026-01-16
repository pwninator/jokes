"""Tests for the utils module."""

from common import utils


def test_format_image_url_updates_params():
  """Updates provided params and preserves others for a valid CDN URL."""
  input_url = ("https://images.quillsstorybook.com/cdn-cgi/image/"
               "width=1024,format=auto,quality=75/path/to/image.png")

  result = utils.format_image_url(
    input_url,
    image_format="webp",
    quality=90,
    width=800,
  )

  assert result.startswith("https://images.quillsstorybook.com/cdn-cgi/image/")
  assert result.endswith("/path/to/image.png")
  assert "format=webp" in result
  assert "quality=90" in result
  assert "width=800" in result


def test_format_image_url_non_cdn_returns_original():
  """Non-CDN URLs are returned unchanged."""
  input_url = "https://example.com/images/cat.png"
  result = utils.format_image_url(input_url, image_format="webp", width=800)
  assert result == input_url


def test_format_image_url_invalid_missing_object_path_raises():
  """Missing object path after params raises ValueError."""
  invalid_cdn = ("https://images.quillsstorybook.com/cdn-cgi/image/"
                 "width=1024,format=auto,quality=75")
  try:
    utils.format_image_url(invalid_cdn)
    assert False, "Expected ValueError for invalid CDN URL without object path"
  except ValueError:
    pass


def test_format_image_url_ignores_zero_and_empty_overrides():
  """Zero/empty override values are ignored; existing values remain."""
  input_url = ("https://images.quillsstorybook.com/cdn-cgi/image/"
               "width=600,format=auto,quality=70/img.png")

  result = utils.format_image_url(
    input_url,
    image_format="",
    quality=0,
    width=0,
  )

  assert "width=600" in result
  assert "quality=70" in result
  assert "format=auto" in result
  assert "width=0" not in result
  assert "quality=0" not in result


def test_format_image_url_remove_existing_replaces_params():
  """remove_existing=True discards previous params before applying overrides."""
  input_url = ("https://images.quillsstorybook.com/cdn-cgi/image/"
               "width=900,format=auto,quality=80/path/to/img.png")

  result = utils.format_image_url(
    input_url,
    image_format="png",
    quality=100,
    width=None,
    remove_existing=True,
  )

  assert "width=900" not in result
  assert "format=png" in result
  assert "quality=100" in result
  assert result.endswith("/path/to/img.png")


def test_format_image_url_adds_missing_params():
  """Adds new params when they were not present in the original set."""
  input_url = ("https://images.quillsstorybook.com/cdn-cgi/image/"
               "format=auto/photo.jpg")

  result = utils.format_image_url(input_url, width=500)

  assert result.endswith("/photo.jpg")
  assert "format=auto" in result
  assert "width=500" in result


def test_get_text_slug_default_removes_non_alphanumeric():
  """Default behavior returns an alphanumeric-only slug."""
  result = utils.get_text_slug("What's the time?")
  assert result == "whatsthetime"


def test_get_text_slug_human_readable_separates_words():
  """Human-readable slugs use underscores only for whitespace."""
  result = utils.get_text_slug("What's the time?", human_readable=True)
  assert result == "whats_the_time"


def test_get_text_slug_human_readable_cleans_punctuation():
  """Punctuation is removed without creating extra separators."""
  result = utils.get_text_slug("He said 'hi!' and 'hello?'",
                               human_readable=True)
  assert result == "he_said_hi_and_hello"
