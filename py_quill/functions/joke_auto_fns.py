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

  public_jokes: list[models.PunnyJoke] = []

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

    # Create the final joke model object once, including any potential updates.
    final_joke_data = {**joke_data, **payload}
    try:
      joke = models.PunnyJoke.from_firestore_dict(final_joke_data, joke_doc.id)
    except Exception as parse_error:
      logger.warn(f"Failed to parse joke {joke_doc.id}, skipping: {parse_error}")
      continue  # Skip malformed documents

    # Perform actions based on the final state.
    if payload:
      batch.update(joke_doc.reference, payload)
      writes_in_batch += 1
      try:
        joke_operations.sync_joke_to_search_collection(joke=joke, new_embedding=None)
      except Exception as sync_error:
        logger.warn(
            f"Failed to sync updated joke {joke_doc.id} to search collection: {sync_error}"
        )
    else:
      jokes_skipped += 1

    # Add to public feed if the joke is public in its final state.
    if joke.is_public:
      public_jokes.append(joke)

    if writes_in_batch >= _MAX_FIRESTORE_WRITE_BATCH_SIZE:
      logger.info(f"Committing batch of {writes_in_batch} writes")
      batch.commit()
      batch = db_client.batch()
      writes_in_batch = 0

  if writes_in_batch:
    logger.info(f"Committing final batch of {writes_in_batch} writes")
    batch.commit()

  if public_jokes:
    logger.info(f"Public jokes found: {len(public_jokes)}")
    sorted_feed = build_joke_feed(public_jokes)
    firestore.update_joke_feed(
      [j.get_minimal_joke_data() for j in sorted_feed])

  logger.info(
    f"Joke daily maintenance completed: {jokes_decayed} recent stats decayed, {public_updated} is_public updated, {jokes_skipped} jokes skipped, {jokes_boosted} jokes boosted"
  )

  return {
    "jokes_decayed": jokes_decayed,
    "public_updated": public_updated,
    "jokes_skipped": jokes_skipped,
    "jokes_boosted": jokes_boosted,
    "num_public_jokes": len(public_jokes),
  }


def build_joke_feed(jokes: list[models.PunnyJoke]) -> list[models.PunnyJoke]:
  """Reorders the input list of jokes to build a feed.

  The returned list contains all input jokes, ordered as follows:
  1. The 10 jokes with the highest `num_saved_users_fraction` appear first,
     sorted in descending order of that fraction.
  2. The remaining jokes follow, arranged in an alternating pattern of:
     a. The highest-ranked joke not yet included in the list.
     b. A randomly selected joke from the remaining pool.

  If the input contains fewer than 10 jokes, the entire list is simply sorted
  by `num_saved_users_fraction` in descending order.
  """
  if not jokes:
    return []

  # Create a copy to avoid modifying the original list, then sort
  source_list = sorted(
    jokes,
    key=lambda j: j.num_saved_users_fraction,
    reverse=True,
  )

  result_list = source_list[:10]
  source_list = source_list[10:]  # The remaining jokes

  while source_list:
    # 1. Add the next-highest-ranked joke
    result_list.append(source_list.pop(0))

    # 2. Add a random joke from the remaining pool, if any exist
    if source_list:
      random_index = random.randint(0, len(source_list) - 1)
      result_list.append(source_list.pop(random_index))

  return result_list
