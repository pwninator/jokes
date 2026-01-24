"""Tests for admin joke feed helpers."""

from __future__ import annotations

import datetime

from common import models
from web.routes.admin import joke_feed_utils


def test_parse_category_filter_handles_blank():
  assert joke_feed_utils.parse_category_filter(None) is None
  assert joke_feed_utils.parse_category_filter("") is None
  assert joke_feed_utils.parse_category_filter("  ") is None
  assert joke_feed_utils.parse_category_filter(" cats ") == "cats"


def test_is_future_daily_accepts_naive_timestamp():
  now_utc = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
  joke = models.PunnyJoke(setup_text="setup", punchline_text="punchline")
  joke.state = models.JokeState.DAILY
  joke.public_timestamp = datetime.datetime(2024, 1, 2)

  assert joke_feed_utils.is_future_daily(joke, now_utc=now_utc) is True


def test_build_edit_payload_dedupes_and_sets_thumbs():
  joke = models.PunnyJoke(setup_text="setup", punchline_text="punchline")
  joke.key = "joke-1"
  joke.seasonal = "Fall"
  joke.tags = ["cozy", "pumpkin"]
  joke.setup_image_url = (
    "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/path/setup.png"
  )
  joke.punchline_image_url = (
    "https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/path/punch.png"
  )
  joke.all_setup_image_urls = [joke.setup_image_url, joke.setup_image_url]
  joke.all_punchline_image_urls = [joke.punchline_image_url]

  payload = joke_feed_utils.build_edit_payload(joke, thumb_size=123)

  assert payload["joke_id"] == "joke-1"
  assert payload["seasonal"] == "Fall"
  assert payload["tags"] == "cozy, pumpkin"
  assert payload["setup_images"][0]["url"] == joke.setup_image_url
  assert "width=123" in payload["setup_images"][0]["thumb_url"]
  assert len(payload["setup_images"]) == 1


def test_build_feed_entries_wraps_jokes():
  now_utc = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
  future_ts = datetime.datetime(2024, 1, 3, tzinfo=datetime.timezone.utc)
  joke = models.PunnyJoke(setup_text="setup", punchline_text="punchline")
  joke.key = "joke-2"
  joke.state = models.JokeState.DAILY
  joke.public_timestamp = future_ts

  entries = joke_feed_utils.build_feed_entries(
    [(joke, "cursor-1")],
    now_utc=now_utc,
  )

  assert len(entries) == 1
  entry = entries[0]
  assert entry.joke is joke
  assert entry.cursor == "cursor-1"
  assert entry.is_future_daily is True
  assert entry.edit_payload["joke_id"] == "joke-2"
