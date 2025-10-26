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
  logger.info(f"Found {len(schedule_ids)} joke schedules to process")
  for schedule_id in schedule_ids:
    try:
      logger.info(
        f"Sending daily joke notification for schedule: {schedule_id}")
      _send_daily_joke_notification(
        scheduled_time_utc,
        schedule_name=schedule_id,
      )
    except Exception as schedule_error:  # pylint: disable=broad-except
      logger.error(
        f"Failed sending jokes for schedule {schedule_id}: {schedule_error}")


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
  logger.info(
    f"Sending daily joke notification for {schedule_name} at {now.isoformat()}")

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
    logger.info(
      f"It's 9am PST, sending additional notification for {schedule_name}")
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
  logger.info(f"Getting joke for {schedule_name} on {joke_date}")
  jokes = firestore.get_daily_jokes(schedule_name, joke_date, 1)
  joke = jokes[0] if jokes else None
  if not joke:
    logger.error(f"No joke found for {joke_date}")
    return
  logger.info(f"Joke found for {joke_date}: {joke.key}")

  if notification_hour is not None and topic_suffix is not None:
    topic_name = f"{schedule_name}_{notification_hour:02d}{topic_suffix}"
  else:
    topic_name = schedule_name
  logger.info(f"Sending joke notification to topic: {topic_name}")
  firebase_cloud_messaging.send_punny_joke_notification(topic_name, joke)


@scheduler_fn.on_schedule(
  # Runs at 12:00 AM PST every day
  schedule="0 0 * * *",
  timezone="America/Los_Angeles",
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def joke_daily_maintenance_scheduler(
    event: scheduler_fn.ScheduledEvent) -> None:
  """Scheduled function that performs daily maintenance tasks for jokes."""

  scheduled_time_utc = event.schedule_time
  if scheduled_time_utc is None:
    scheduled_time_utc = datetime.datetime.now(datetime.timezone.utc)

  _joke_daily_maintenance_internal(scheduled_time_utc)


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def joke_daily_maintenance_http(req: https_fn.Request) -> https_fn.Response:
  """HTTP endpoint to trigger daily maintenance tasks for jokes."""
  del req
  try:
    run_time_utc = datetime.datetime.now(datetime.timezone.utc)
    _joke_daily_maintenance_internal(run_time_utc)
    return success_response({"message": "Recent joke stats decayed"})
  except Exception as exc:  # pylint: disable=broad-except
    return error_response(f'Failed to decay recent joke stats: {exc}')


def _joke_daily_maintenance_internal(run_time_utc: datetime.datetime) -> None:
  """Apply exponential decay to recent counters across all jokes."""
  db_client = firestore.db()
  jokes_collection = db_client.collection("jokes")
  joke_docs = jokes_collection.stream()

  batch = db_client.batch()
  writes_in_batch = 0
  jokes_decayed = 0
  public_updated = 0
  jokes_skipped = 0

  for joke_doc in joke_docs:
    if not joke_doc.exists:
      continue
    joke_data = joke_doc.to_dict() or {}
    payload: dict[str, object] = {}

    # Update is_public according to state and public_timestamp
    expected_is_public = _expected_is_public(joke_data, run_time_utc)
    current_is_public = joke_data.get("is_public")
    if not isinstance(current_is_public,
                      bool) or current_is_public != expected_is_public:
      payload["is_public"] = expected_is_public
      public_updated += 1

    # Decay recent stats if needed
    should_skip_decay = _should_skip_recent_update(joke_data, run_time_utc)
    if not should_skip_decay:
      decay_payload = _build_recent_decay_payload(joke_data)
      if not decay_payload:
        raise ValueError(
          f"No payload to decay recent stats for joke: {joke_doc.reference}")
      payload.update(decay_payload)
      jokes_decayed += 1

    if not payload:
      # No updates to apply, skip this joke
      jokes_skipped += 1
      continue

    batch.update(joke_doc.reference, payload)
    writes_in_batch += 1

    if writes_in_batch >= _MAX_FIRESTORE_WRITE_BATCH_SIZE:
      logger.info(f"Committing batch of {writes_in_batch} writes")
      batch.commit()
      batch = db_client.batch()
      writes_in_batch = 0

  if writes_in_batch:
    logger.info(f"Committing final batch of {writes_in_batch} writes")
    batch.commit()

  logger.info(
    f"Joke daily maintenance completed: {jokes_decayed} recent stats decayed, {public_updated} is_public updated, {jokes_skipped} jokes skipped"
  )


def _decay_recent_joke_stats_internal(
  run_time_utc: datetime.datetime, ) -> None:
  """Backward-compatible alias for legacy invocations."""
  _joke_daily_maintenance_internal(run_time_utc)


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


def _to_utc_datetime(value: object) -> datetime.datetime | None:
  """Normalize Firestore timestamp values to timezone-aware UTC datetimes."""
  if not isinstance(value, datetime.datetime):
    return None
  if value.tzinfo is None:
    return value.replace(tzinfo=datetime.timezone.utc)
  return value.astimezone(datetime.timezone.utc)


def _expected_is_public(
  data: dict[str, object],
  now_utc: datetime.datetime,
) -> bool:
  """Determine whether a joke should currently be public."""
  state_value = data.get("state")
  try:
    state = models.JokeState(state_value)
  except Exception:  # pylint: disable=broad-except
    return False

  if state == models.JokeState.PUBLISHED:
    return True
  if state == models.JokeState.DAILY:
    public_timestamp = _to_utc_datetime(data.get("public_timestamp"))
    return bool(public_timestamp and public_timestamp <= now_utc)
  return False


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
      f"Unable to coerce counter value {value} (type {type(value)}) to float")
    return None


def _get_joke_embedding(
    joke: models.PunnyJoke) -> tuple[Vector, models.GenerationMetadata]:
  """Get an embedding for a joke."""
  return search.get_embedding(
    text=f"{joke.setup_text} {joke.punchline_text}",
    task_type=search.TaskType.RETRIEVAL_DOCUMENT,
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
      f"Syncing joke to search subcollection: {joke_id} with payload keys {update_payload.keys()}"
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
    logger.info(f"Joke document deleted: {event.params['joke_id']}")
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
    logger.info(
      f"New joke created, calculating embedding for: {after_joke.key}")
  elif (after_joke.zzz_joke_text_embedding is None
        or isinstance(after_joke.zzz_joke_text_embedding, list)):
    should_update_embedding = True
    logger.info(
      f"Joke missing embedding, calculating embedding for: {after_joke.key}")
  elif (before_joke.setup_text != after_joke.setup_text
        or before_joke.punchline_text != after_joke.punchline_text):
    should_update_embedding = True
    logger.info(
      f"Joke text changed, recalculating embedding for: {after_joke.key}")
  else:
    logger.info(
      f"Joke updated without text change, skipping embedding update for: {after_joke.key}"
    )

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
    embedding, metadata = _get_joke_embedding(after_joke)
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
        f"Joke num_saved_users_fraction mismatch, updating from {after_joke.num_saved_users_fraction} to {num_saved_users_fraction} for: {after_joke.key}"
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
        f"Joke num_shared_users_fraction mismatch, updating from {after_joke.num_shared_users_fraction} to {num_shared_users_fraction} for: {after_joke.key}"
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
      f"Joke popularity_score mismatch, updating from {after_joke.popularity_score} to {popularity_score} for: {after_joke.key}"
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
    logger.info(
      f"Joke tags changed, updating from {after_joke.tags} to {tags_lowered} for: {after_joke.key}"
    )

  _sync_joke_to_search_subcollection(
    joke=after_joke,
    new_embedding=new_embedding,
  )

  if update_data and after_joke.key:
    firestore.update_punny_joke(after_joke.key, update_data)

    if should_update_embedding:
      logger.info(f"Successfully updated embedding for joke: {after_joke.key}")
