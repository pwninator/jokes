"""Automated joke scheduling and maintenance functions."""

from __future__ import annotations

import datetime
import math
import zoneinfo

from common import models
from firebase_functions import (firestore_fn, https_fn, logger, options,
                                scheduler_fn)
from functions.function_utils import error_response, success_response
from google.cloud.firestore_v1.vector import Vector
from services import firebase_cloud_messaging, firestore, search

_RECENT_STATS_DAILY_DECAY_FACTOR = 0.9
_MAX_FIRESTORE_WRITE_BATCH_SIZE = 100
_LAST_RECENT_STATS_UPDATE_TIME_FIELD_NAME = "last_recent_stats_update_time"


@scheduler_fn.on_schedule(
  schedule="0 * * * *",
  timezone="Etc/GMT+12",
  memory=options.MemoryOption.GB_1,
  timeout_sec=300,
)
def send_daily_joke_scheduler(event: scheduler_fn.ScheduledEvent) -> None:
  """Scheduled function that sends daily joke notifications."""

  scheduled_time_utc = event.schedule_time
  if scheduled_time_utc is None:
    scheduled_time_utc = datetime.datetime.now(datetime.timezone.utc)
  _notify_all_joke_schedules(scheduled_time_utc)


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=300,
)
def send_daily_joke_http(req: https_fn.Request) -> https_fn.Response:
  """Send a daily joke notification to subscribers."""

  del req

  try:
    # Get current UTC time
    utc_now = datetime.datetime.now(datetime.timezone.utc)

    _notify_all_joke_schedules(utc_now)
  except Exception as e:
    return error_response(f'Failed to send daily joke notification: {str(e)}')

  return success_response({"message": "Daily joke notification sent"})


def _notify_all_joke_schedules(scheduled_time_utc: datetime.datetime) -> None:
  """Iterate all schedules and send notifications for each.

  Args:
      scheduled_time_utc: The scheduled time from the scheduler event.
  """
  schedule_ids = firestore.list_joke_schedules()
  logger.info("Found %s joke schedules to process", len(schedule_ids))
  for schedule_id in schedule_ids:
    try:
      logger.info("Sending daily joke notification for schedule: %s",
                  schedule_id)
      _send_daily_joke_notification(
        scheduled_time_utc,
        schedule_name=schedule_id,
      )
    except Exception as schedule_error:  # pylint: disable=broad-except
      logger.error("Failed sending jokes for schedule %s: %s", schedule_id,
                   schedule_error)


def _send_daily_joke_notification(
  now: datetime.datetime,
  schedule_name: str = "daily_jokes",
) -> None:
  """Send a daily joke notification to subscribers.

  At each hour of the day, we send two notifications: one for the current date,
  and one for the next date. The dates are at UTC-12. Clients subscribe to the
  topic for the hour they want to receive notifications, using either the "c" or
  "n" variety depending on whether their local timezone is one day ahead of
  UTC-12 or not.

  Args:
      now: The current datetime when this was executed (any timezone)
      schedule_name: The name of the joke schedule to use
  """
  logger.info("Sending daily joke notification for %s at %s", schedule_name,
              now)

  if now.tzinfo is None:
    raise ValueError(
      f"now must have timezone information, got naive datetime: {now}")

  now_utc = now.astimezone(datetime.timezone.utc)
  utc_minus_12 = now_utc - datetime.timedelta(hours=12)
  hour_utc_minus_12 = utc_minus_12.hour
  date_utc_minus_12 = utc_minus_12.date()

  _send_single_joke_notification(
    schedule_name=schedule_name,
    joke_date=date_utc_minus_12,
    notification_hour=hour_utc_minus_12,
    topic_suffix="c",
  )

  _send_single_joke_notification(
    schedule_name=schedule_name,
    joke_date=date_utc_minus_12 + datetime.timedelta(days=1),
    notification_hour=hour_utc_minus_12,
    topic_suffix="n",
  )

  pst_timezone = zoneinfo.ZoneInfo("America/Los_Angeles")
  now_pst = now.astimezone(pst_timezone)

  if now_pst.hour == 9:
    logger.info("It's 9am PST, sending additional notification for %s",
                schedule_name)
    _send_single_joke_notification(
      schedule_name=schedule_name,
      joke_date=now_pst.date(),
    )


def _send_single_joke_notification(
  schedule_name: str,
  joke_date: datetime.date,
  notification_hour: int | None = None,
  topic_suffix: str | None = None,
) -> None:
  """Send a joke notification for a given date."""
  logger.info("Getting joke for %s on %s", schedule_name, joke_date)
  jokes = firestore.get_daily_jokes(schedule_name, joke_date, 1)
  joke = jokes[0] if jokes else None
  if not joke:
    logger.error("No joke found for %s", joke_date)
    return
  logger.info("Joke found for %s: %s", joke_date, joke)

  if notification_hour is not None and topic_suffix is not None:
    topic_name = f"{schedule_name}_{notification_hour:02d}{topic_suffix}"
  else:
    topic_name = schedule_name
  logger.info("Sending joke notification to topic: %s", topic_name)
  firebase_cloud_messaging.send_punny_joke_notification(topic_name, joke)


@scheduler_fn.on_schedule(
  # Runs at 12:00 AM PST every day
  schedule="0 0 * * *",
  timezone="America/Los_Angeles",
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def decay_recent_joke_stats_scheduler(
    event: scheduler_fn.ScheduledEvent) -> None:
  """Scheduled function that decays recent user counters once per day."""

  scheduled_time_utc = event.schedule_time
  if scheduled_time_utc is None:
    scheduled_time_utc = datetime.datetime.now(datetime.timezone.utc)

  _decay_recent_joke_stats_internal(scheduled_time_utc)


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def decay_recent_joke_stats_http(req: https_fn.Request) -> https_fn.Response:
  """HTTP endpoint to trigger recent counter decay."""
  del req
  try:
    run_time_utc = datetime.datetime.now(datetime.timezone.utc)
    _decay_recent_joke_stats_internal(run_time_utc)
    return success_response({"message": "Recent joke stats decayed"})
  except Exception as exc:  # pylint: disable=broad-except
    return error_response(f'Failed to decay recent joke stats: {exc}')


def _decay_recent_joke_stats_internal(run_time_utc: datetime.datetime) -> None:
  """Apply exponential decay to recent counters across all jokes."""
  db_client = firestore.db()
  jokes_collection = db_client.collection("jokes")
  joke_docs = jokes_collection.stream()

  batch = db_client.batch()
  writes_in_batch = 0

  for joke_doc in joke_docs:
    if not joke_doc.exists:
      continue
    joke_data = joke_doc.to_dict() or {}

    if _should_skip_recent_update(joke_data, run_time_utc):
      continue

    payload = _build_recent_decay_payload(joke_data)
    if not payload:
      continue

    batch.update(joke_doc.reference, payload)
    writes_in_batch += 1

    if writes_in_batch >= _MAX_FIRESTORE_WRITE_BATCH_SIZE:
      batch.commit()
      batch = db_client.batch()
      writes_in_batch = 0

  if writes_in_batch:
    batch.commit()


def _should_skip_recent_update(
  data: dict[str, object],
  run_time_utc: datetime.datetime,
) -> bool:
  """Return True when the previous update was within the skip threshold."""
  last_update = data.get(_LAST_RECENT_STATS_UPDATE_TIME_FIELD_NAME)
  if not isinstance(last_update, datetime.datetime):
    return False

  if last_update.tzinfo is None:
    last_update = last_update.replace(tzinfo=datetime.timezone.utc)
  else:
    last_update = last_update.astimezone(datetime.timezone.utc)

  return (run_time_utc - last_update) < datetime.timedelta(hours=22)


def _build_recent_decay_payload(data: dict[str, object]) -> dict[str, object]:
  """Construct the payload that applies decay to the supplied joke data."""
  payload: dict[str, object] = {}

  for field_name in (
      "num_viewed_users_recent",
      "num_saved_users_recent",
      "num_shared_users_recent",
  ):
    original_value = data.get(field_name)
    if original_value is None:
      continue
    elif not isinstance(original_value, (int, float)):
      raise ValueError(
        f"Unexpected {field_name} type {type(original_value)} when decaying recent counters"
      )

    original_value = float(original_value)
    decayed_value = max(0.0, original_value * _RECENT_STATS_DAILY_DECAY_FACTOR)
    payload[field_name] = decayed_value

  payload[
    _LAST_RECENT_STATS_UPDATE_TIME_FIELD_NAME] = firestore.SERVER_TIMESTAMP
  return payload


# --- Joke write trigger --------------------------------------------------------


def _coerce_counter_to_float(value: object) -> float | None:
  """Best-effort conversion of Firestore counter values to floats."""
  if value is None:
    return None
  if isinstance(value, bool):
    return float(int(value))
  if isinstance(value, (int, float)):
    return float(value)
  try:
    return float(value)
  except (TypeError, ValueError):
    logger.warn(
      "Unable to coerce counter value %r (type %s) to float",
      value,
      type(value),
    )
    return None


def get_joke_embedding(
    joke: models.PunnyJoke) -> tuple[Vector, models.GenerationMetadata]:
  """Get an embedding for a joke."""
  return search.get_embedding(
    text=f"{joke.setup_text} {joke.punchline_text}",
    task_type=search.TaskType.RETRIEVAL_DOCUMENT,
    model="gemini-embedding-001",
    output_dimensionality=2048,
  )


def _sync_joke_to_search_subcollection(
  joke: models.PunnyJoke,
  new_embedding: Vector | None,
) -> None:
  """Syncs joke data to a search subcollection document."""
  if not joke.key:
    return

  joke_id = joke.key
  search_doc_ref = firestore.db().collection("jokes").document(
    joke_id).collection("search").document("search")
  search_doc = search_doc_ref.get()
  search_data = search_doc.to_dict() if search_doc.exists else {}

  update_payload = {}

  # 1. Sync embedding
  if new_embedding:
    update_payload["text_embedding"] = new_embedding
  elif "text_embedding" not in search_data and joke.zzz_joke_text_embedding:
    update_payload["text_embedding"] = joke.zzz_joke_text_embedding

  # 2. Sync state
  if search_data.get("state") != joke.state.value:
    update_payload["state"] = joke.state.value

  # 3. Sync public_timestamp
  if search_data.get("public_timestamp") != joke.public_timestamp:
    update_payload["public_timestamp"] = joke.public_timestamp

  # 4. Sync num_saved_users_fraction
  if search_data.get(
      "num_saved_users_fraction") != joke.num_saved_users_fraction:
    update_payload["num_saved_users_fraction"] = joke.num_saved_users_fraction

  # 5. Sync num_shared_users_fraction
  if search_data.get(
      "num_shared_users_fraction") != joke.num_shared_users_fraction:
    update_payload[
      "num_shared_users_fraction"] = joke.num_shared_users_fraction

  # 6. Sync popularity_score
  if search_data.get("popularity_score") != joke.popularity_score:
    update_payload["popularity_score"] = joke.popularity_score

  if update_payload:
    logger.info(
      "Syncing joke to search subcollection: %s with payload keys %s",
      joke_id,
      list(update_payload.keys()),
    )
    search_doc_ref.set(update_payload, merge=True)


@firestore_fn.on_document_written(
  document="jokes/{joke_id}",
  memory=options.MemoryOption.GB_1,
  timeout_sec=300,
)
def on_joke_write(event: firestore_fn.Event[firestore_fn.Change]) -> None:
  """A cloud function that triggers on joke document changes."""
  if not event.data.after:
    logger.info("Joke document deleted: %s", event.params["joke_id"])
    return

  after_data = event.data.after.to_dict() or {}
  after_joke = models.PunnyJoke.from_firestore_dict(after_data,
                                                    event.params["joke_id"])

  before_joke = None
  if event.data.before:
    before_data = event.data.before.to_dict()
    before_joke = models.PunnyJoke.from_firestore_dict(before_data,
                                                       event.params["joke_id"])

  should_update_embedding = False

  # Check if embedding needs updating
  if after_joke.state == models.JokeState.DRAFT:
    should_update_embedding = False
  elif not before_joke:
    should_update_embedding = True
    logger.info("New joke created, calculating embedding for: %s",
                after_joke.key)
  elif (after_joke.zzz_joke_text_embedding is None
        or isinstance(after_joke.zzz_joke_text_embedding, list)):
    should_update_embedding = True
    logger.info("Joke missing embedding, calculating embedding for: %s",
                after_joke.key)
  elif (before_joke.setup_text != after_joke.setup_text
        or before_joke.punchline_text != after_joke.punchline_text):
    should_update_embedding = True
    logger.info("Joke text changed, recalculating embedding for: %s",
                after_joke.key)
  else:
    logger.info(
      "Joke updated without text change, skipping embedding update for: %s",
      after_joke.key)

  if after_joke.state == models.JokeState.DRAFT:
    return

  update_data: dict[str, object] = {}
  new_embedding = None

  # Ensure recent counters exist to keep analytics in sync with Flutter app
  recent_counter_pairs = [
    ("num_viewed_users", "num_viewed_users_recent"),
    ("num_saved_users", "num_saved_users_recent"),
    ("num_shared_users", "num_shared_users_recent"),
  ]
  recent_values: dict[str, float] = {}
  for total_field, recent_field in recent_counter_pairs:
    recent_value = _coerce_counter_to_float(after_data.get(recent_field))
    needs_write = False
    if recent_value is None:
      base_value = getattr(after_joke, total_field, 0)
      recent_value = float(base_value)
      needs_write = True
    elif not isinstance(after_data.get(recent_field), float):
      needs_write = True
    if needs_write:
      update_data[recent_field] = recent_value
    after_data[recent_field] = recent_value
    recent_values[recent_field] = recent_value

  if should_update_embedding:
    embedding, metadata = get_joke_embedding(after_joke)
    new_embedding = embedding

    current_metadata = after_joke.generation_metadata
    if isinstance(current_metadata, dict):
      current_metadata = models.GenerationMetadata.from_dict(current_metadata)
    elif not current_metadata:
      current_metadata = models.GenerationMetadata()
    current_metadata.add_generation(metadata)

    update_data.update({
      "zzz_joke_text_embedding": embedding,
      "generation_metadata": current_metadata.as_dict,
    })

  if after_joke.num_viewed_users > 0:
    num_saved_users_fraction = (after_joke.num_saved_users /
                                after_joke.num_viewed_users)
    if not math.isclose(after_joke.num_saved_users_fraction,
                        num_saved_users_fraction,
                        rel_tol=1e-9,
                        abs_tol=1e-12):
      logger.info(
        "Joke num_saved_users_fraction mismatch, updating from %s to %s for: %s",
        after_joke.num_saved_users_fraction,
        num_saved_users_fraction,
        after_joke.key,
      )
      update_data["num_saved_users_fraction"] = num_saved_users_fraction
      after_joke.num_saved_users_fraction = num_saved_users_fraction

    num_shared_users_fraction = (after_joke.num_shared_users /
                                 after_joke.num_viewed_users)
    if not math.isclose(after_joke.num_shared_users_fraction,
                        num_shared_users_fraction,
                        rel_tol=1e-9,
                        abs_tol=1e-12):
      logger.info(
        "Joke num_shared_users_fraction mismatch, updating from %s to %s for: %s",
        after_joke.num_shared_users_fraction,
        num_shared_users_fraction,
        after_joke.key,
      )
      update_data["num_shared_users_fraction"] = num_shared_users_fraction
      after_joke.num_shared_users_fraction = num_shared_users_fraction

  popularity_score = 0.0
  if after_joke.num_viewed_users > 0:
    num_saves_and_shares = (after_joke.num_saved_users +
                            after_joke.num_shared_users)
    popularity_score = (num_saves_and_shares * num_saves_and_shares /
                        after_joke.num_viewed_users)
  if not math.isclose(
      after_joke.popularity_score, popularity_score, rel_tol=1e-9,
      abs_tol=1e-12):
    logger.info(
      "Joke popularity_score mismatch, updating from %s to %s for: %s",
      after_joke.popularity_score,
      popularity_score,
      after_joke.key,
    )
    update_data["popularity_score"] = popularity_score
    after_joke.popularity_score = popularity_score

  # Calculate recent popularity score using decayed counters.
  recent_viewed = recent_values["num_viewed_users_recent"]
  recent_saved = recent_values["num_saved_users_recent"]
  recent_shared = recent_values["num_shared_users_recent"]
  popularity_score_recent = 0.0
  if recent_viewed > 0:
    recent_total = recent_saved + recent_shared
    popularity_score_recent = recent_total * recent_total / recent_viewed

  existing_recent_score = _coerce_counter_to_float(
    after_data.get("popularity_score_recent"))
  if (existing_recent_score is None
      or not math.isclose(existing_recent_score,
                          popularity_score_recent,
                          rel_tol=1e-9,
                          abs_tol=1e-12)):
    update_data["popularity_score_recent"] = popularity_score_recent
    after_data["popularity_score_recent"] = popularity_score_recent

  tags_lowered = [t.lower() for t in after_joke.tags]
  if tags_lowered != after_joke.tags:
    update_data["tags"] = tags_lowered
    logger.info("Joke tags changed, updating from %s to %s for: %s",
                after_joke.tags, tags_lowered, after_joke.key)

  _sync_joke_to_search_subcollection(
    joke=after_joke,
    new_embedding=new_embedding,
  )

  if update_data and after_joke.key:
    firestore.update_punny_joke(after_joke.key, update_data)

    if should_update_embedding:
      logger.info("Successfully updated embedding for joke: %s",
                  after_joke.key)
