"""Firestore helpers for the `joke_videos` collection."""
# pylint: disable=duplicate-code

from typing import cast

from common import models, utils
from firebase_functions import logger
from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter, Query
from services import firestore


def create_joke_video(joke_video: models.JokeVideo) -> models.JokeVideo | None:
  """Create a joke_videos document with a timestamped key."""
  joke_id = (joke_video.joke_id or "").strip()
  if not joke_id:
    raise ValueError("JokeVideo.joke_id is required")
  video_gcs_uri = (joke_video.video_gcs_uri or "").strip()
  if not video_gcs_uri:
    raise ValueError("JokeVideo.video_gcs_uri is required")

  doc_id = utils.create_timestamped_firestore_key(joke_id)
  doc_ref = firestore.db().collection("joke_videos").document(doc_id)
  if doc_ref.get().exists:
    return None

  payload = joke_video.to_dict()
  if joke_video.creation_time is None:
    payload["creation_time"] = SERVER_TIMESTAMP
  else:
    payload["creation_time"] = joke_video.creation_time

  _ = doc_ref.set(payload)
  joke_video.key = doc_id
  return joke_video


def get_latest_joke_video_for_joke(joke_id: str) -> models.JokeVideo | None:
  """Fetch the newest joke video doc for a joke id."""
  normalized_joke_id = (joke_id or "").strip()
  if not normalized_joke_id:
    return None

  query = (firestore.db().collection("joke_videos").where(
    filter=FieldFilter("joke_id", "==", normalized_joke_id)).order_by(
      "creation_time",
      direction=Query.DESCENDING,
    ).limit(1))
  docs = list(query.stream())
  if not docs:
    return None
  doc = cast(object, docs[0])
  doc_id = cast(str, getattr(doc, "id", ""))
  if not doc_id:
    return None
  if not bool(getattr(doc, "exists", False)):
    return None
  to_dict_fn = getattr(doc, "to_dict", None)
  if not callable(to_dict_fn):
    return None
  raw_data = to_dict_fn() or {}
  if not isinstance(raw_data, dict):
    return None
  data = cast(dict[str, object], raw_data)
  try:
    return models.JokeVideo.from_firestore_dict(data, key=doc_id)
  except ValueError as exc:
    logger.warn(f"Skipping invalid joke video {doc_id}: {exc}")
    return None


def get_recent_joke_videos(*, limit: int = 10) -> list[models.JokeVideo]:
  """Fetch recently created joke videos in descending creation order."""
  safe_limit = max(1, int(limit))
  query = (firestore.db().collection("joke_videos").order_by(
    "creation_time",
    direction=Query.DESCENDING,
  ).limit(safe_limit))
  entries: list[models.JokeVideo] = []
  docs = cast(list[object], list(query.stream()))
  for doc in docs:
    doc_id = cast(str, getattr(doc, "id", ""))
    if not doc_id:
      continue
    if not bool(getattr(doc, "exists", False)):
      continue
    to_dict_fn = getattr(doc, "to_dict", None)
    if not callable(to_dict_fn):
      continue
    raw_data = to_dict_fn() or {}
    if not isinstance(raw_data, dict):
      continue
    data = cast(dict[str, object], raw_data)
    try:
      joke_video = models.JokeVideo.from_firestore_dict(data, key=doc_id)
    except ValueError as exc:
      logger.warn(f"Skipping invalid joke video {doc_id}: {exc}")
      continue
    entries.append(joke_video)
  return entries
