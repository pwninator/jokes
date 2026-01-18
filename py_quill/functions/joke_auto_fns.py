"""Automated joke scheduling and maintenance functions."""

from __future__ import annotations

import datetime
from collections import deque

from common import joke_category_operations, joke_operations, models
from firebase_functions import https_fn, logger, options, scheduler_fn
from functions.function_utils import error_response, success_response
from services import firestore

_RECENT_STATS_DAILY_DECAY_FACTOR = 0.9
_MAX_FIRESTORE_WRITE_BATCH_SIZE = 100
_LAST_RECENT_STATS_UPDATE_TIME_FIELD_NAME = "last_recent_stats_update_time"


@scheduler_fn.on_schedule(
  # Runs at every hour PST every day
  schedule="0 * * * *",
  timezone="America/Los_Angeles",
  memory=options.MemoryOption.GB_1,
  timeout_sec=1800,
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
  timeout_sec=1800,
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

  joke_stats, jokes_by_id = _update_joke_attributes(run_time_utc)

  # After updating jokes (including is_public), refresh cached category results
  category_stats = joke_category_operations.refresh_category_caches(
    jokes_by_id=jokes_by_id)

  # Rebuild the cached category index document used by the admin UI.
  categories_index_stats = joke_category_operations.rebuild_joke_categories_index(
    jokes_by_id=jokes_by_id)

  # Combine all statistics
  combined_stats = {**joke_stats, **category_stats, **categories_index_stats}

  logger.info(f"Joke maintenance completed with stats: {combined_stats}")
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


def _build_book_id_index(db_client) -> tuple[dict[str, str], int]:
  """Return a map of joke_id -> book_id based on joke_books documents."""
  book_id_by_joke: dict[str, str] = {}
  duplicate_jokes = 0
  for book_doc in db_client.collection("joke_books").stream():
    if not getattr(book_doc, "exists", False):
      continue
    book_data = book_doc.to_dict() or {}
    joke_ids = book_data.get("jokes")
    if not isinstance(joke_ids, list):
      continue
    for joke_id in joke_ids:
      if not joke_id:
        continue
      joke_key = str(joke_id).strip()
      if not joke_key:
        continue
      existing_book = book_id_by_joke.get(joke_key)
      if existing_book and existing_book != book_doc.id:
        duplicate_jokes += 1
        logger.warn(
          f"Joke {joke_key} appears in multiple books: {existing_book}, {book_doc.id}"
        )
        continue
      book_id_by_joke[joke_key] = book_doc.id
  return book_id_by_joke, duplicate_jokes


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


def _update_joke_attributes(
  run_time_utc: datetime.datetime
) -> tuple[dict[str, int], dict[str, models.PunnyJoke]]:
  """Apply exponential decay to recent counters across all jokes.
  
  Returns:
    Tuple of:
      - Dictionary with maintenance statistics: jokes_decayed, public_updated, jokes_skipped
      - Dictionary of all jokes (after applying any computed payload) keyed by joke id
  """

  db_client = firestore.db()
  jokes_collection = db_client.collection("jokes")
  book_id_by_joke, duplicate_book_jokes = _build_book_id_index(db_client)
  joke_docs = jokes_collection.stream()

  batch = db_client.batch()
  writes_in_batch = 0
  jokes_decayed = 0
  public_updated = 0
  book_id_updated = 0
  jokes_skipped = 0

  public_jokes: list[models.PunnyJoke] = []
  jokes_by_id: dict[str, models.PunnyJoke] = {}

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

    # Best-effort category_id maintenance:
    # - If a joke is public and has no category_id, mark it uncategorized.
    # - Category cache refresh may later overwrite this to a real category id.
    if expected_is_public:
      current_category_id = joke_data.get("category_id")
      if not isinstance(current_category_id,
                        str) or not current_category_id.strip():
        payload["category_id"] = firestore.UNCATEGORIZED_CATEGORY_ID

    expected_book_id = book_id_by_joke.get(joke_doc.id)
    has_book_id = "book_id" in joke_data
    current_book_id = joke_data.get("book_id")
    if isinstance(current_book_id, str):
      current_book_id = current_book_id.strip() or None
    else:
      current_book_id = None
    if expected_book_id is None:
      if not has_book_id or current_book_id is not None:
        payload["book_id"] = None
        book_id_updated += 1
    elif current_book_id != expected_book_id:
      payload["book_id"] = expected_book_id
      book_id_updated += 1

    # Decay recent stats if needed
    should_skip_decay = _should_skip_recent_update(joke_data, run_time_utc)
    if not should_skip_decay:
      decay_payload = _build_recent_decay_payload(joke_data)
      payload.update(decay_payload)
      jokes_decayed += 1

    # Create the final joke model object once, including any potential updates.
    final_joke_data = {**joke_data, **payload}
    try:
      joke = models.PunnyJoke.from_firestore_dict(final_joke_data, joke_doc.id)
    except Exception as parse_error:
      logger.warn(
        f"Failed to parse joke {joke_doc.id}, skipping: {parse_error}")
      continue  # Skip malformed documents
    jokes_by_id[joke_doc.id] = joke

    # Perform actions based on the final state.
    if payload:
      batch.update(joke_doc.reference, payload)
      writes_in_batch += 1
    else:
      jokes_skipped += 1

    if joke.state != models.JokeState.DRAFT:
      try:
        joke_operations.sync_joke_to_search_collection(joke=joke,
                                                       new_embedding=None)
      except Exception as sync_error:
        logger.warn(
          f"Failed to sync joke {joke_doc.id} to search collection: {sync_error}"
        )

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
    f"Joke daily maintenance completed: {jokes_decayed} recent stats decayed, {public_updated} is_public updated, {book_id_updated} book_id updated, {jokes_skipped} jokes skipped"
  )

  return {
    "jokes_decayed": jokes_decayed,
    "public_updated": public_updated,
    "book_id_updated": book_id_updated,
    "duplicate_book_jokes": duplicate_book_jokes,
    "jokes_skipped": jokes_skipped,
    "num_public_jokes": len(public_jokes),
  }, jokes_by_id


def build_joke_feed(jokes: list[models.PunnyJoke]) -> list[models.PunnyJoke]:
  """Reorders the input list of jokes to build a feed.

  The returned list contains all input jokes, ordered as follows:
  1. The 10 jokes with the highest `num_saved_users_fraction` appear first,
     sorted in descending order of that fraction.
  2. The remaining jokes follow, arranged in an alternating pattern of:
     a. The highest-ranked joke not yet included in the list.
     b. The lowest-viewed joke (by `num_viewed_users`) from the remaining pool.

  If the input contains fewer than 10 jokes, the entire list is simply sorted
  by `num_saved_users_fraction` in descending order.
  """
  if not jokes:
    return []

  sorted_by_fraction = deque[models.PunnyJoke](sorted(
    jokes, key=lambda j: j.num_saved_users_fraction, reverse=True))
  sorted_by_views = deque[models.PunnyJoke](sorted(
    jokes, key=lambda j: j.num_viewed_users))
  unused_ids = {id(joke) for joke in jokes}
  result_list: list[models.PunnyJoke] = []

  def _pop_next(queue: deque[models.PunnyJoke]) -> models.PunnyJoke | None:
    while queue:
      candidate = queue.popleft()
      candidate_id = id(candidate)
      if candidate_id in unused_ids:
        unused_ids.remove(candidate_id)
        return candidate
    return None

  top_pick_count = min(10, len(jokes))
  for _ in range(top_pick_count):
    next_joke = _pop_next(sorted_by_fraction)
    if next_joke is None:
      break
    result_list.append(next_joke)

  while unused_ids:
    ranked_joke = _pop_next(sorted_by_fraction)
    if ranked_joke:
      result_list.append(ranked_joke)

    if not unused_ids:
      break

    lowest_viewed_joke = _pop_next(sorted_by_views)
    if lowest_viewed_joke:
      result_list.append(lowest_viewed_joke)

  return result_list
