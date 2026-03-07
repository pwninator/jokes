"""Utility cloud functions for Firestore migrations."""

from __future__ import annotations

import datetime
import json
import tempfile
import traceback
from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np
from common import models
from firebase_functions import https_fn, logger, options
from functions.function_utils import get_bool_param, get_int_param, get_param
from google.cloud.firestore import FieldFilter, Query
from moviepy.video.io.VideoFileClip import VideoFileClip
from PIL import Image
from services import cloud_storage, firestore
from storage import joke_videos_firestore

_DEFAULT_REEL_TELLER_CHARACTER_DEF_ID = "cat_orange_tabby"
_DEFAULT_REEL_LISTENER_CHARACTER_DEF_ID = "dog_beagle"


def _https_response(*args: Any, **kwargs: Any) -> Any:
  """Build an https function response without private type references."""
  response_ctor = getattr(https_fn, "Response")
  return response_ctor(*args, **kwargs)


@dataclass
class _MigrationStats:
  posts_processed: int = 0
  distinct_jokes_found: int = 0
  joke_videos_created: int = 0
  jokes_skipped_existing_joke_video: int = 0
  jokes_skipped_missing_joke_id: int = 0
  jokes_skipped_missing_video_uri: int = 0
  jokes_skipped_missing_joke_text: int = 0
  jokes_skipped_preview_extraction_failure: int = 0
  jokes_skipped_create_failure: int = 0
  last_post_id: str | None = None
  errors: list[str] = field(default_factory=list)


@https_fn.on_request(
  memory=options.MemoryOption.GB_4,
  timeout_sec=1800,
)
def run_firestore_migration(req: Any) -> Any:
  """Run Firestore migrations.

  Current migration:
  - Backfill top-level `joke_videos` docs from existing JOKE_REEL_VIDEO posts.
  """
  if req.path == "/__/health":
    return _https_response("OK", status=200)

  if req.method != "GET":
    return _https_response(
      json.dumps({
        "error": "Only GET requests are supported",
        "success": False
      }),
      status=405,
      mimetype="application/json",
    )

  try:
    dry_run = get_bool_param(req, "dry_run", True)
    limit = get_int_param(req, "limit", 0)
    start_after = str(get_param(req, "start_after", "") or "")

    html_response = run_joke_video_backfill_from_social_posts(
      dry_run=dry_run,
      limit=limit,
      start_after=start_after,
    )
    return _https_response(html_response, status=200, mimetype="text/html")
  except Exception as exc:  # pylint: disable=broad-except
    logger.error(f"Firestore migration failed: {exc}")
    logger.error(traceback.format_exc())
    return _https_response(
      json.dumps({
        "success": False,
        "error": str(exc),
        "message": "Failed to run Firestore migration"
      }),
      status=500,
      mimetype="application/json",
    )


def run_joke_video_backfill_from_social_posts(*, dry_run: bool, limit: int,
                                              start_after: str) -> str:
  """Backfill `joke_videos` documents from existing reel social posts."""
  logger.info(
    "Starting joke_videos backfill from social posts",
    extra={
      "json_fields": {
        "dry_run": dry_run,
        "limit": limit,
        "start_after": start_after,
      }
    },
  )

  query = (firestore.db().collection("joke_social_posts").where(
    filter=FieldFilter(
      "type",
      "==",
      models.JokeSocialPostType.JOKE_REEL_VIDEO.value,
    )).order_by("creation_time", direction=Query.DESCENDING))

  if start_after:
    start_doc = firestore.db().collection("joke_social_posts").document(
      start_after).get()
    if getattr(start_doc, "exists", False):
      query = query.start_after(start_doc)
  if limit > 0:
    query = query.limit(limit)

  stats = _MigrationStats()
  latest_post_by_joke_id: dict[str, tuple[dict[str, object],
                                          dict[str, object]]] = {}

  for post_doc in list(query.stream()):
    post_snapshot: Any = post_doc
    stats.posts_processed += 1
    stats.last_post_id = str(getattr(post_snapshot, "id", "") or "")

    if not getattr(post_snapshot, "exists", False):
      continue
    raw_post_data: Any = post_snapshot.to_dict()
    if not isinstance(raw_post_data, dict):
      continue
    post_data = cast(dict[str, object], raw_post_data)

    raw_jokes_any: Any = post_data.get("jokes")
    if not isinstance(raw_jokes_any, list) or not raw_jokes_any:
      stats.jokes_skipped_missing_joke_id += 1
      continue
    raw_jokes_list = cast(list[object], raw_jokes_any)
    first_joke_raw = raw_jokes_list[0]
    if not isinstance(first_joke_raw, dict):
      stats.jokes_skipped_missing_joke_id += 1
      continue
    first_joke = cast(dict[str, object], first_joke_raw)

    joke_id = _coerce_str(first_joke.get("key"))
    if not joke_id:
      stats.jokes_skipped_missing_joke_id += 1
      continue
    if joke_id in latest_post_by_joke_id:
      continue

    latest_post_by_joke_id[joke_id] = (post_data, first_joke)

  stats.distinct_jokes_found = len(latest_post_by_joke_id)

  for joke_id, (post_data, joke_data) in latest_post_by_joke_id.items():
    existing_joke_video = joke_videos_firestore.get_latest_joke_video_for_joke(
      joke_id)
    if existing_joke_video is not None:
      stats.jokes_skipped_existing_joke_video += 1
      continue

    video_gcs_uri = _extract_social_post_video_uri(post_data)
    if not video_gcs_uri:
      stats.jokes_skipped_missing_video_uri += 1
      continue

    setup_text = _coerce_str(joke_data.get("setup_text"))
    punchline_text = _coerce_str(joke_data.get("punchline_text"))
    if not setup_text or not punchline_text:
      joke = firestore.get_punny_joke(joke_id)
      if joke:
        setup_text = setup_text or (joke.setup_text or "").strip()
        punchline_text = punchline_text or (joke.punchline_text or "").strip()
    if not setup_text or not punchline_text:
      stats.jokes_skipped_missing_joke_text += 1
      continue

    creation_time_raw = post_data.get("creation_time")
    creation_time = (creation_time_raw if isinstance(
      creation_time_raw, datetime.datetime) else None)

    script_intro = _coerce_str(post_data.get("reel_intro_script"))
    script_response = _coerce_str(post_data.get("reel_response_script"))

    preview_image_gcs_uri: str | None = None
    if not dry_run:
      try:
        preview_image = _extract_first_frame_image_from_video_gcs(
          video_gcs_uri)
        try:
          preview_image_gcs_uri, _ = cloud_storage.upload_image_to_gcs(
            preview_image,
            f"joke_video_preview_{joke_id}",
            "png",
          )
        finally:
          preview_image.close()
      except Exception as exc:  # pylint: disable=broad-except
        stats.jokes_skipped_preview_extraction_failure += 1
        stats.errors.append(
          f"Joke {joke_id}: preview extraction failed ({exc})")
        logger.error(
          "Failed to extract preview frame during joke_video migration",
          extra={
            "json_fields": {
              "joke_id": joke_id,
              "video_gcs_uri": video_gcs_uri,
              "error": str(exc),
            }
          },
        )
        continue

    joke_video = models.JokeVideo(
      joke_id=joke_id,
      creation_time=creation_time,
      video_gcs_uri=video_gcs_uri,
      preview_image_gcs_uri=preview_image_gcs_uri,
      script_intro=script_intro,
      script_setup=setup_text,
      script_response=script_response,
      script_punchline=punchline_text,
      teller_character_def_id=_DEFAULT_REEL_TELLER_CHARACTER_DEF_ID,
      listener_character_def_id=_DEFAULT_REEL_LISTENER_CHARACTER_DEF_ID,
      generation_metadata=models.GenerationMetadata(),
    )

    if dry_run:
      stats.joke_videos_created += 1
      continue

    saved = joke_videos_firestore.create_joke_video(joke_video)
    if not saved:
      stats.jokes_skipped_create_failure += 1
      stats.errors.append(f"Joke {joke_id}: failed to create joke_video doc")
      continue
    stats.joke_videos_created += 1

  return _build_html_report(dry_run=dry_run, stats=stats)


def _extract_social_post_video_uri(post_data: dict[str, object]) -> str:
  for key in (
      "instagram_video_gcs_uri",
      "facebook_video_gcs_uri",
      "pinterest_video_gcs_uri",
  ):
    value = post_data.get(key)
    if isinstance(value, str) and value.strip():
      return value.strip()
  return ""


def _coerce_str(value: object | None) -> str:
  if isinstance(value, str):
    return value.strip()
  return ""


def _build_html_report(*, dry_run: bool, stats: _MigrationStats) -> str:
  """Build a simple HTML report of migration results."""
  html = "<html><body>"
  html += "<h1>Joke Video Backfill Results</h1>"
  html += f"<h2>Dry Run: {dry_run}</h2>"

  html += "<h3>Stats</h3>"
  html += "<ul>"
  html += f"<li>Posts Processed: {stats.posts_processed}</li>"
  html += f"<li>Distinct Jokes Found: {stats.distinct_jokes_found}</li>"
  html += "<li>Joke Videos Created (or would create): "
  html += f"{stats.joke_videos_created}</li>"
  html += "<li>Skipped (already has joke video): "
  html += f"{stats.jokes_skipped_existing_joke_video}</li>"
  html += "<li>Skipped (missing joke id): "
  html += f"{stats.jokes_skipped_missing_joke_id}</li>"
  html += "<li>Skipped (missing video URI): "
  html += f"{stats.jokes_skipped_missing_video_uri}</li>"
  html += "<li>Skipped (missing joke text): "
  html += f"{stats.jokes_skipped_missing_joke_text}</li>"
  html += "<li>Skipped (preview extraction failure): "
  html += f"{stats.jokes_skipped_preview_extraction_failure}</li>"
  html += "<li>Skipped (create failure): "
  html += f"{stats.jokes_skipped_create_failure}</li>"
  if stats.last_post_id:
    html += f"<li>Last Post ID: {stats.last_post_id}</li>"
  html += "</ul>"

  if stats.errors:
    html += f"<h3 style='color:red'>Errors ({len(stats.errors)})</h3>"
    html += "<ul>"
    for error in stats.errors:
      html += f"<li>{error}</li>"
    html += "</ul>"

  html += "</body></html>"
  return html


def _extract_first_frame_image_from_video_bytes(
    video_bytes: bytes) -> Image.Image:
  """Decode video bytes and return the first frame as a PIL image."""
  if not video_bytes:
    raise ValueError("video_bytes is required")

  with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_file:
    _ = temp_file.write(video_bytes)
    temp_file.flush()
    clip: Any | None = None
    frame: Any = None
    try:
      clip = VideoFileClip(temp_file.name)
      frame = clip.get_frame(0.0)
    except Exception as exc:  # pylint: disable=broad-except
      raise ValueError("Could not extract first video frame") from exc
    finally:
      if clip is not None:
        clip.close()

  frame_array = np.asarray(frame)
  if frame_array.dtype != np.uint8:
    if np.issubdtype(frame_array.dtype, np.floating):
      frame_array = np.clip(frame_array * 255.0, 0, 255).astype(np.uint8)
    else:
      frame_array = np.clip(frame_array, 0, 255).astype(np.uint8)
  return Image.fromarray(frame_array).convert("RGB")


def _extract_first_frame_image_from_video_gcs(
    video_gcs_uri: str) -> Image.Image:
  """Download a video from GCS and return its first frame as a PIL image."""
  video_bytes = cloud_storage.download_bytes_from_gcs(video_gcs_uri)
  return _extract_first_frame_image_from_video_bytes(video_bytes)
