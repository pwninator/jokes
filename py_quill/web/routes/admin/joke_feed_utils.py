"""Shared helpers for admin joke feeds."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from common import models, utils

_DEFAULT_THUMB_SIZE = 180


@dataclass(frozen=True)
class JokeFeedEntry:
  joke: models.PunnyJoke
  cursor: str
  is_future_daily: bool
  edit_payload: dict


def parse_category_filter(value: str | None) -> str | None:
  category_id = (value or "").strip()
  return category_id or None


def _dedupe_keep_order(values: list[str]) -> list[str]:
  seen: set[str] = set()
  result: list[str] = []
  for value in values:
    if not value:
      continue
    if value in seen:
      continue
    seen.add(value)
    result.append(value)
  return result


def is_future_daily(joke: models.PunnyJoke, *,
                    now_utc: datetime.datetime) -> bool:
  if joke.state != models.JokeState.DAILY:
    return False
  public_ts = getattr(joke, "public_timestamp", None)
  if public_ts is None:
    return False
  if not isinstance(public_ts, datetime.datetime):
    return False
  if public_ts.tzinfo is None:
    # Treat naive timestamps as UTC.
    public_ts = public_ts.replace(tzinfo=datetime.timezone.utc)
  return public_ts > now_utc


def build_edit_payload(joke: models.PunnyJoke,
                       *,
                       thumb_size: int = _DEFAULT_THUMB_SIZE) -> dict:
  setup_urls = list(getattr(joke, "all_setup_image_urls", None) or [])
  punchline_urls = list(getattr(joke, "all_punchline_image_urls", None) or [])

  if joke.setup_image_url:
    setup_urls = [joke.setup_image_url, *setup_urls]
  if joke.punchline_image_url:
    punchline_urls = [joke.punchline_image_url, *punchline_urls]

  setup_urls = _dedupe_keep_order(setup_urls)
  punchline_urls = _dedupe_keep_order(punchline_urls)

  return {
    "joke_id":
    joke.key,
    "setup_text":
    joke.setup_text,
    "punchline_text":
    joke.punchline_text,
    "seasonal":
    joke.seasonal,
    "tags":
    list(joke.tags or []),
    "setup_scene_idea":
    joke.setup_scene_idea,
    "punchline_scene_idea":
    joke.punchline_scene_idea,
    "setup_image_description":
    joke.setup_image_description,
    "punchline_image_description":
    joke.punchline_image_description,
    "setup_image_url":
    joke.setup_image_url,
    "punchline_image_url":
    joke.punchline_image_url,
    "setup_images": [{
      "url":
      url,
      "thumb_url":
      utils.format_image_url(url, width=thumb_size),
    } for url in setup_urls],
    "punchline_images": [{
      "url":
      url,
      "thumb_url":
      utils.format_image_url(url, width=thumb_size),
    } for url in punchline_urls],
  }


def build_feed_entries(
  joke_entries: list[tuple[models.PunnyJoke, str]],
  *,
  now_utc: datetime.datetime,
  thumb_size: int = _DEFAULT_THUMB_SIZE,
) -> list[JokeFeedEntry]:
  """Build a list of joke feed entries."""
  return [
    JokeFeedEntry(
      joke=joke,
      cursor=cursor,
      is_future_daily=is_future_daily(joke, now_utc=now_utc),
      edit_payload=build_edit_payload(joke, thumb_size=thumb_size),
    ) for joke, cursor in joke_entries
  ]
