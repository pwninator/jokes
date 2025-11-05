"""Automated joke scheduling and maintenance functions."""

from __future__ import annotations

import datetime
import random

from common import joke_category_operations, joke_operations, models
from firebase_functions import https_fn, logger, options, scheduler_fn
from functions.function_utils import error_response, success_response
from services import firestore

_RECENT_STATS_DAILY_DECAY_FACTOR = 0.9
_MAX_FIRESTORE_WRITE_BATCH_SIZE = 100
_LAST_RECENT_STATS_UPDATE_TIME_FIELD_NAME = "last_recent_stats_update_time"

MIN_VIEWS_FOR_FRACTIONS = 20


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
    maintenance_stats = _joke_daily_maintenance_internal(run_time_utc)
    return success_response({
      "message": "Daily maintenance completed successfully",
      "stats": maintenance_stats
    })
  except Exception as exc:  # pylint: disable=broad-except
    return error_response(f'Failed to run daily maintenance: {exc}')


def _joke_daily_maintenance_internal(
    run_time_utc: datetime.datetime) -> dict[str, int]:
  """Run daily maintenance tasks for jokes.
  
  Returns:
    Combined dictionary with all maintenance statistics from joke updates and category cache refresh
  """

  joke_stats = _update_joke_attributes(run_time_utc)

  # After updating jokes (including is_public), refresh cached category results
  category_stats = joke_category_operations.refresh_category_caches()

  # Combine all statistics
  combined_stats = {**joke_stats, **category_stats}

  logger.info(f"Daily maintenance completed with stats: {combined_stats}")
  return combined_stats


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


def _update_joke_attributes(run_time_utc: datetime.datetime) -> dict[str, int]:
  """Apply exponential decay to recent counters across all jokes.
  
  Returns:
    Dictionary with maintenance statistics: jokes_decayed, public_updated, jokes_skipped, jokes_boosted
  """

  db_client = firestore.db()
  jokes_collection = db_client.collection("jokes")
  joke_docs = jokes_collection.stream()

  batch = db_client.batch()
  writes_in_batch = 0
  jokes_decayed = 0
  public_updated = 0
  jokes_skipped = 0
  jokes_boosted = 0

  public_joke_ids = set[str]()

  for joke_doc in joke_docs:
    if not joke_doc.exists:
      continue
    joke_data = joke_doc.to_dict() or {}
    payload: dict[str, object] = {}

    # Update is_public according to state and public_timestamp
    expected_is_public = _expected_is_public(joke_data, run_time_utc)
    if expected_is_public:
      public_joke_ids.add(joke_doc.id)

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

    # Boost num_saved_users_fraction for jokes with low views
    num_viewed_users = joke_data.get("num_viewed_users", 0)
    if not isinstance(num_viewed_users, (int, float)):
      num_viewed_users = 0
    num_viewed_users = int(num_viewed_users)

    if num_viewed_users < MIN_VIEWS_FOR_FRACTIONS:
      current_fraction = joke_data.get("num_saved_users_fraction")
      if current_fraction is None or not isinstance(current_fraction,
                                                    (int, float)):
        current_fraction = 0.0
      current_fraction = float(current_fraction)

      boost_amount = random.uniform(0.0, 0.02)
      new_fraction = current_fraction + boost_amount
      payload["num_saved_users_fraction"] = new_fraction
      jokes_boosted += 1

    if not payload:
      # No updates to apply, skip this joke
      jokes_skipped += 1
    else:
      batch.update(joke_doc.reference, payload)
      writes_in_batch += 1

    # Sync joke to search collection (merge payload into joke_data for updated values)
    updated_joke_data = {**joke_data, **payload} if payload else joke_data
    try:
      joke = models.PunnyJoke.from_firestore_dict(
        updated_joke_data,
        joke_doc.id,
      )
      joke_operations.sync_joke_to_search_collection(joke=joke,
                                                     new_embedding=None)
    except Exception as sync_error:  # pylint: disable=broad-except
      logger.warn(
        f"Failed to sync joke {joke_doc.id} to search collection: {sync_error}"
      )

    if writes_in_batch >= _MAX_FIRESTORE_WRITE_BATCH_SIZE:
      logger.info(f"Committing batch of {writes_in_batch} writes")
      batch.commit()
      batch = db_client.batch()
      writes_in_batch = 0

  if writes_in_batch:
    logger.info(f"Committing final batch of {writes_in_batch} writes")
    batch.commit()

  if public_joke_ids:
    logger.info(f"Public joke IDs: {public_joke_ids}")
    firestore.update_public_joke_ids(public_joke_ids)

  logger.info(
    f"Joke daily maintenance completed: {jokes_decayed} recent stats decayed, {public_updated} is_public updated, {jokes_skipped} jokes skipped, {jokes_boosted} jokes boosted"
  )

  return {
    "jokes_decayed": jokes_decayed,
    "public_updated": public_updated,
    "jokes_skipped": jokes_skipped,
    "jokes_boosted": jokes_boosted,
    "num_public_jokes": len(public_joke_ids),
  }
