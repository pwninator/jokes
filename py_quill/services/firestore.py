"""Firestore operations."""

import datetime
import pprint
from typing import Any, Collection
from zoneinfo import ZoneInfo

from common import models, posable_character_sequence, utils
from firebase_admin import firestore, firestore_async
from firebase_functions import logger
from google.cloud.firestore import (SERVER_TIMESTAMP, AsyncClient, Client,
                                    DocumentReference, FieldFilter, Query,
                                    Transaction, transactional)
from google.cloud.firestore_v1.field_path import FieldPath

_db: Client | None = None  # pylint: disable=invalid-name
_async_db: AsyncClient | None = None  # pylint: disable=invalid-name

OPERATION = "_operation"
OPERATION_TIMESTAMP = "_operation_timestamp"
JOKE_FIELDS_TO_LOG = {
  # Main text fields
  "setup_text",
  "punchline_text",
  "setup_scene_idea",
  "punchline_scene_idea",
  "setup_image_description",
  "punchline_image_description",

  # Image fields
  "setup_image_url",
  "punchline_image_url",
  "setup_image_url_upscaled",
  "punchline_image_url_upscaled",

  # Metadata
  "pun_theme",
  "phrase_topic",
  "tags",
  "for_kids",
  "for_adults",
  "seasonal",
  "pun_word",
  "punned_word",

  # State fields
  "state",
  "admin_rating",
  "is_public",
  "category_id",
}

# Single source of truth for the "uncategorized" sentinel value used across
# web/admin reads and maintenance jobs.
UNCATEGORIZED_CATEGORY_ID = "_uncategorized"
AMAZON_ADS_REPORTS_COLLECTION = "amazon_ads_reports"
AMAZON_ADS_DAILY_STATS_COLLECTION = "amazon_ads_daily_stats"
AMAZON_ADS_EVENTS_COLLECTION = "amazon_ads_events"
AMAZON_KDP_DAILY_STATS_COLLECTION = "amazon_kdp_daily_stats"


def get_async_db() -> AsyncClient:
  """Get the firestore async client."""
  global _async_db
  if _async_db is None:
    _async_db = firestore_async.client()
  return _async_db


def db() -> Client:
  """Get the firestore client."""
  global _db  # pylint: disable=global-statement
  if _db is None:
    _db = firestore.client()
  return _db


def upsert_amazon_ads_report(
  report: models.AmazonAdsReport, ) -> models.AmazonAdsReport:
  """Upsert an Amazon Ads report document keyed by report_name."""
  report_name = report.report_name.strip()
  if not report_name:
    raise ValueError("AmazonAdsReport.report_name is required for upsert")

  payload = report.to_dict(include_key=False)
  _ = db().collection(AMAZON_ADS_REPORTS_COLLECTION).document(report_name).set(
    payload,
    merge=True,
  )
  report.key = report_name
  return report


def list_amazon_ads_reports(
  *,
  created_on_or_after: datetime.date,
) -> list[models.AmazonAdsReport]:
  """List report metadata with Firestore-side created_at filtering."""
  start_of_day_utc = datetime.datetime.combine(
    created_on_or_after,
    datetime.time.min,
    tzinfo=datetime.timezone.utc,
  )
  query = db().collection(AMAZON_ADS_REPORTS_COLLECTION).where(
    filter=FieldFilter("created_at", ">=", start_of_day_utc), ).order_by(
      "created_at",
      direction=Query.DESCENDING,
    )
  docs = query.stream()
  return [
    models.AmazonAdsReport.from_firestore_dict(doc.to_dict(), key=doc.id)
    for doc in docs if doc.exists and doc.to_dict() is not None
  ]


def upsert_amazon_ads_daily_stats(
  stats: list[models.AmazonAdsDailyStats],
) -> list[models.AmazonAdsDailyStats]:
  """Batch upsert daily stats keyed by date."""
  if not stats:
    return []

  db_client = db()
  batch = db_client.batch()
  collection_ref = db_client.collection(AMAZON_ADS_DAILY_STATS_COLLECTION)
  for daily_stat in stats:
    stats_key = daily_stat.date.isoformat()
    payload = daily_stat.to_dict(include_key=False)
    batch.set(
      collection_ref.document(stats_key),
      payload,
      merge=True,
    )
    daily_stat.key = stats_key
  batch.commit()
  return stats


def list_amazon_ads_daily_stats(
  *,
  start_date: datetime.date,
  end_date: datetime.date,
) -> list[models.AmazonAdsDailyStats]:
  """List daily stats with Firestore-side date range filtering."""
  if end_date < start_date:
    raise ValueError("end_date must be on or after start_date")

  query = db().collection(AMAZON_ADS_DAILY_STATS_COLLECTION).where(
    filter=FieldFilter("date", ">=",
                       start_date.isoformat()), ).where(filter=FieldFilter(
                         "date", "<=", end_date.isoformat()), ).order_by(
                           "date",
                           direction=Query.ASCENDING,
                         )
  docs = query.stream()
  return [
    models.AmazonAdsDailyStats.from_firestore_dict(
      doc.to_dict(),
      key=doc.id,
    ) for doc in docs if doc.exists and doc.to_dict() is not None
  ]


def upsert_amazon_ads_event(
  event: models.AmazonAdsEvent,
) -> models.AmazonAdsEvent:
  """Upsert a manually created Amazon Ads event."""
  payload = event.to_dict(include_key=False)

  # Use a random ID if key is not present, otherwise update existing doc.
  collection_ref = db().collection(AMAZON_ADS_EVENTS_COLLECTION)
  if event.key:
    doc_ref = collection_ref.document(event.key)
    doc_ref.set(payload, merge=True)
  else:
    _, doc_ref = collection_ref.add(payload)
    event.key = doc_ref.id

  return event


def list_amazon_ads_events(
  *,
  start_date: datetime.date,
  end_date: datetime.date,
) -> list[models.AmazonAdsEvent]:
  """List manually created Amazon Ads events within a date range."""
  if end_date < start_date:
    raise ValueError("end_date must be on or after start_date")

  query = db().collection(AMAZON_ADS_EVENTS_COLLECTION).where(
    filter=FieldFilter("date", ">=",
                       start_date.isoformat()), ).where(filter=FieldFilter(
                         "date", "<=", end_date.isoformat()), ).order_by(
                           "date",
                           direction=Query.ASCENDING,
                         )
  docs = query.stream()
  return [
    models.AmazonAdsEvent.from_firestore_dict(
      doc.to_dict(),
      key=doc.id,
    ) for doc in docs if doc.exists and doc.to_dict() is not None
  ]


def upsert_amazon_kdp_daily_stats(
  stats: list[models.AmazonKdpDailyStats],
) -> list[models.AmazonKdpDailyStats]:
  """Batch upsert KDP daily stats keyed by date."""
  if not stats:
    return []

  db_client = db()
  batch = db_client.batch()
  collection_ref = db_client.collection(AMAZON_KDP_DAILY_STATS_COLLECTION)
  for daily_stat in stats:
    stats_key = daily_stat.date.isoformat()
    payload = daily_stat.to_dict(include_key=False)
    batch.set(
      collection_ref.document(stats_key),
      payload,
      merge=True,
    )
    daily_stat.key = stats_key
  batch.commit()
  return stats


def list_amazon_kdp_daily_stats(
  *,
  start_date: datetime.date,
  end_date: datetime.date,
) -> list[models.AmazonKdpDailyStats]:
  """List KDP daily stats with Firestore-side date range filtering."""
  if end_date < start_date:
    raise ValueError("end_date must be on or after start_date")

  query = db().collection(AMAZON_KDP_DAILY_STATS_COLLECTION).where(
    filter=FieldFilter("date", ">=",
                       start_date.isoformat()), ).where(filter=FieldFilter(
                         "date", "<=", end_date.isoformat()), ).order_by(
                           "date",
                           direction=Query.ASCENDING,
                         )
  docs = query.stream()
  return [
    models.AmazonKdpDailyStats.from_firestore_dict(
      doc.to_dict(),
      key=doc.id,
    ) for doc in docs if doc.exists and doc.to_dict() is not None
  ]


def _prepare_jokes_query(
  states: list[models.JokeState] | None,
  *,
  category_id: str | None = None,
  async_mode: bool,
):
  """Build a Firestore query for jokes filtered by state (and optional category)."""
  if not states:
    states = [models.JokeState.DAILY, models.JokeState.PUBLISHED]
  state_values = [s.value for s in states]
  client = get_async_db() if async_mode else db()
  query = client.collection('jokes').where(
    filter=FieldFilter('state', 'in', state_values))
  category_id = (category_id or "").strip() or None
  if category_id:
    query = query.where(filter=FieldFilter("category_id", "==", category_id))
  return query


def get_joke_by_state(
  states: list[models.JokeState],
  cursor: str | None = None,
  limit: int = 10,
  *,
  category_id: str | None = None,
) -> tuple[list[tuple[models.PunnyJoke, str]], str | None]:
  """Fetch a page of jokes for the admin UI.

  Jokes are filtered by `states` and sorted by `creation_time` descending.

  Args:
    states: Joke lifecycle states to include (required; caller chooses defaults).
    cursor: Optional joke document id to start *after* (cursor pagination).
    limit: Maximum number of jokes to return.

  Returns:
    (entries, next_cursor):
      - entries: list of (PunnyJoke, per_item_cursor) pairs. The per-item cursor
        is the joke document id for that row (useful for client-side resume).
      - next_cursor: the document id cursor for fetching the next page, or None
        if there are no more results.
  """
  query = _prepare_jokes_query(
    states,
    category_id=category_id,
    async_mode=False,
  ).order_by(
    'creation_time',
    direction=Query.DESCENDING,
  )

  if cursor:
    try:
      snapshot = db().collection('jokes').document(cursor).get()
      if getattr(snapshot, 'exists', False):
        query = query.start_after(snapshot)
    except Exception:
      # Invalid cursor or transient Firestore issue; fall back to first page.
      pass

  docs = list(query.limit(limit + 1).stream())
  page_docs = docs[:limit]
  has_more = len(docs) > limit

  entries: list[tuple[models.PunnyJoke, str]] = []
  for doc in page_docs:
    if not getattr(doc, 'exists', False):
      continue
    payload = doc.to_dict()
    if payload is None:
      continue
    joke = models.PunnyJoke.from_firestore_dict(payload, key=doc.id)
    entries.append((joke, doc.id))

  next_cursor = page_docs[-1].id if (has_more and page_docs) else None
  return entries, next_cursor


def get_all_jokes(
    states: list[models.JokeState] | None = None) -> list[models.PunnyJoke]:
  """Get jokes from firestore filtered by state.

  Args:
      states: List of JokeState values to include. Defaults to DAILY and PUBLISHED.
  """
  docs = _prepare_jokes_query(states, async_mode=False).stream()
  return [
    models.PunnyJoke.from_firestore_dict(doc.to_dict(), key=doc.id)
    for doc in docs if doc.exists and doc.to_dict() is not None
  ]


async def get_all_jokes_async(
    states: list[models.JokeState] | None = None) -> list[models.PunnyJoke]:
  """Get jokes from firestore asynchronously filtered by state.

  Args:
      states: List of JokeState values to include. Defaults to DAILY and PUBLISHED.
  """
  docs = _prepare_jokes_query(states, async_mode=True).stream()
  return [
    models.PunnyJoke.from_firestore_dict(doc.to_dict(), key=doc.id)
    async for doc in docs if doc.exists and doc.to_dict() is not None
  ]


def get_punny_joke(joke_id: str) -> models.PunnyJoke | None:
  """Get a punny joke by ID."""
  jokes = get_punny_jokes([joke_id])
  return jokes[0] if jokes else None


def get_punny_jokes(joke_ids: Collection[str]) -> list[models.PunnyJoke]:
  """Get multiple punny jokes in a single batch read.

  Args:
      joke_ids: List of joke IDs to fetch

  Returns:
      List of PunnyJoke objects, in the same order as the input IDs where found.
      Missing IDs are omitted.
  """
  if not joke_ids:
    return []

  refs = [db().collection('jokes').document(joke_id) for joke_id in joke_ids]
  docs = db().get_all(refs)

  jokes = [
    models.PunnyJoke.from_firestore_dict(doc.to_dict(), key=doc.id)
    for doc in docs if doc.exists and doc.to_dict() is not None
  ]
  return jokes


def get_joke_social_posts(
  *,
  limit: int | None = None,
  post_type: models.JokeSocialPostType | None = None,
) -> list[models.JokeSocialPost]:
  """Fetch most recently created social posts."""
  query = db().collection('joke_social_posts').order_by(
    'creation_time',
    direction=Query.DESCENDING,
  )
  if post_type:
    query = query.where(filter=FieldFilter('type', '==', post_type.value))

  if limit:
    query = query.limit(limit)

  entries: list[models.JokeSocialPost] = []
  for doc in query.stream():
    if not doc.exists:
      continue
    data = doc.to_dict() or {}
    try:
      post = models.JokeSocialPost.from_firestore_dict(data, key=doc.id)
    except ValueError as exc:
      logger.warn(f"Skipping invalid social post {doc.id}: {exc}")
      continue
    entries.append(post)
  return entries


def get_joke_social_post(post_id: str, ) -> models.JokeSocialPost | None:
  """Fetch a social post by document id."""
  post_id = (post_id or "").strip()
  if not post_id:
    return None
  doc = db().collection('joke_social_posts').document(post_id).get()
  if not getattr(doc, 'exists', False):
    return None
  data = doc.to_dict() or {}
  try:
    return models.JokeSocialPost.from_firestore_dict(data, key=doc.id)
  except ValueError as exc:
    logger.warn(f"Skipping invalid social post {post_id}: {exc}")
    return None


def delete_joke_social_post(post_id: str) -> bool:
  """Delete a social post by Firestore document id.

  Note: Firestore does not automatically delete subcollections. We explicitly
  delete the known metadata doc used by the admin operations log.
  """
  post_id = (post_id or "").strip()
  if not post_id:
    return False

  post_ref = db().collection("joke_social_posts").document(post_id)
  snapshot = post_ref.get()
  if not getattr(snapshot, "exists", False):
    return False

  # Best-effort cleanup of known metadata doc.
  try:
    post_ref.collection("metadata").document("operations").delete()
  except Exception:  # pylint: disable=broad-except
    pass

  post_ref.delete()
  return True


def update_social_post(
  post_id: str,
  update_data: dict[str, Any],
) -> dict[str, Any]:
  """Update a social post document and return changed fields."""
  post_id = (post_id or "").strip()
  if not post_id:
    raise ValueError("post_id is required")
  if not update_data:
    raise ValueError("update_data is required")

  post_ref = db().collection('joke_social_posts').document(post_id)
  post_snapshot = post_ref.get()
  if not post_snapshot.exists:
    raise ValueError(f"Social post {post_id} not found in Firestore")

  existing_data = post_snapshot.to_dict() or {}
  update_payload = dict(update_data)
  update_payload['last_modification_time'] = SERVER_TIMESTAMP

  changed_fields: dict[str, Any] = {}
  for key, value in update_payload.items():
    if key not in existing_data or existing_data.get(key) != value:
      changed_fields[key] = value

  post_ref.update(update_payload)
  return changed_fields


def upsert_social_post(
  social_post: models.JokeSocialPost,
  operation: str | None = None,
) -> models.JokeSocialPost | None:
  """Create or update a social post."""
  if not operation:
    operation = "CREATE" if not social_post.key else "UPDATE"

  saved_post: models.JokeSocialPost | None
  if social_post.key:
    updated_fields = update_social_post(
      social_post.key,
      social_post.to_dict(),
    )
    saved_post = social_post
  else:
    joke_ids: list[str] = []
    for joke in social_post.jokes:
      if joke.key:
        joke_ids.append(joke.key)
    custom_id = utils.create_timestamped_firestore_key(
      social_post.type.value,
      *(joke_ids[:2] if joke_ids else []),
    )
    post_ref = db().collection('joke_social_posts').document(custom_id)
    if post_ref.get().exists:
      return None

    post_data = social_post.to_dict()
    updated_fields = post_data.copy()
    post_data['creation_time'] = SERVER_TIMESTAMP
    post_data['last_modification_time'] = SERVER_TIMESTAMP

    post_ref.set(post_data)
    social_post.key = custom_id
    saved_post = social_post

  # Update operations log
  if saved_post and saved_post.key:
    current_time = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    log_fields = {
      OPERATION: operation,
      OPERATION_TIMESTAMP: current_time,
    }
    for key, value in updated_fields.items():
      if value == SERVER_TIMESTAMP:
        value = "OPERATION_TIMESTAMP"
      log_fields[key] = value

    operations_ref = (db().collection('joke_social_posts').document(
      saved_post.key).collection('metadata').document('operations'))
    operations_doc = operations_ref.get()
    log_entries: list[dict[str, Any]] = []
    if operations_doc.exists:
      existing_data = operations_doc.to_dict() or {}
      existing_log = existing_data.get('log')
      if isinstance(existing_log, list):
        log_entries.extend(entry for entry in existing_log
                           if isinstance(entry, dict))

    log_entries.append(log_fields)
    operations_ref.set({'log': log_entries}, merge=True)

  return saved_post


def upsert_joke_sheet(sheet: models.JokeSheet) -> models.JokeSheet:
  """Ensure a joke_sheets document exists for the given joke sheet.

  Identity semantics:
  - Sheets are unique by `joke_str`.
  - Other fields (including category_id, pdf_gcs_uri, image_gcs_uri) may be
    overwritten by later calls for the same joke set.

  Returns:
    A JokeSheet with `key` populated to the Firestore document id.
  """
  if not sheet.joke_str:
    sheet.joke_str = ",".join(sheet.joke_ids or [])

  payload = sheet.to_dict()

  collection_ref = db().collection('joke_sheets')
  existing = (collection_ref.where(
    filter=FieldFilter('joke_str', '==', sheet.joke_str)).limit(1).get())
  for doc in existing:
    if getattr(doc, 'exists', False):
      doc_dict = doc.to_dict() if hasattr(doc, 'to_dict') else None
      needs_update = not isinstance(doc_dict, dict) or doc_dict != payload
      if needs_update:
        doc_ref = getattr(doc, 'reference', None)
        if doc_ref is not None:
          doc_ref.set(payload, merge=True)
      sheet.key = doc.id
      return sheet

  _, doc_ref = collection_ref.add(payload)
  sheet.key = doc_ref.id
  return sheet


def get_joke_sheets_by_category(
  category_id: str,
  index: int | None = None,
) -> list[models.JokeSheet]:
  """Fetch all joke sheets associated with a category.

  Note: `category_id` is a single string field and may be overwritten if multiple
  categories share a sheet. This helper returns the current set of sheets whose
  `category_id` matches the provided category id. If `index` is provided, the
  query is further filtered to that sheet index.
  """
  category_id = (category_id or "").strip()
  if not category_id:
    return []

  query = db().collection("joke_sheets").where(
    filter=FieldFilter("category_id", "==", category_id))
  if index is not None:
    query = query.where(filter=FieldFilter("index", "==", index))
  docs = query.stream()
  return [
    models.JokeSheet.from_firestore_dict(doc.to_dict(), key=doc.id)
    for doc in docs if doc.exists and doc.to_dict() is not None
  ]


def get_joke_sheet_by_slug(slug: str) -> models.JokeSheet | None:
  """Fetch a joke sheet by its custom sheet_slug field."""
  slug = (slug or "").strip()
  if not slug:
    return None

  query = db().collection("joke_sheets").where(
    filter=FieldFilter("sheet_slug", "==", slug)).limit(1)
  docs = list(query.stream())
  if not docs:
    return None

  doc = docs[0]
  if not doc.exists:
    return None
  data = doc.to_dict()
  if data is None:
    return None

  return models.JokeSheet.from_firestore_dict(data, key=doc.id)


def delete_joke_sheet(sheet_id: str) -> bool:
  """Delete a joke sheet by Firestore document id."""
  sheet_id = (sheet_id or "").strip()
  if not sheet_id:
    return False

  doc_ref = db().collection("joke_sheets").document(sheet_id)
  snapshot = doc_ref.get()
  if not getattr(snapshot, "exists", False):
    return False

  doc_ref.delete()
  return True


def get_joke_sheets_cache(
) -> list[tuple[models.JokeCategory, list[models.JokeSheet]]]:
  """Get the joke sheets cache as category and sheet objects."""
  doc = db().collection("joke_cache").document("joke_sheets").get()
  if not getattr(doc, "exists", False):
    return []

  payload = doc.to_dict() or {}
  categories = payload.get("categories")
  if not isinstance(categories, dict):
    return []

  results: list[tuple[models.JokeCategory, list[models.JokeSheet]]] = []
  for category_id, data in categories.items():
    if not isinstance(category_id, str):
      continue
    if not isinstance(data, dict):
      continue
    display_name = (data.get("category_display_name") or "").strip()
    if not display_name:
      continue
    raw_sheets = data.get("sheets")
    if not isinstance(raw_sheets, list):
      continue

    sheets: list[models.JokeSheet] = []
    for index, sheet_data in enumerate(raw_sheets):
      if not isinstance(sheet_data, dict):
        continue
      image_gcs_uri = sheet_data.get("image_gcs_uri")
      pdf_gcs_uri = sheet_data.get("pdf_gcs_uri")
      sheet_key = sheet_data.get("sheet_key")
      if not image_gcs_uri or not pdf_gcs_uri or not sheet_key:
        continue
      sheets.append(
        models.JokeSheet(
          key=sheet_key,
          category_id=category_id,
          index=index,
          image_gcs_uri=image_gcs_uri,
          pdf_gcs_uri=pdf_gcs_uri,
        ))

    if not sheets:
      continue

    results.append((
      models.JokeCategory(id=category_id, display_name=display_name),
      sheets,
    ))

  return results


def update_joke_sheets_cache(
  categories: list[models.JokeCategory],
  sheets: list[models.JokeSheet],
) -> None:
  """Update the joke sheets cache document for active categories."""

  sheets_by_category: dict[str, list[models.JokeSheet]] = {}
  for sheet in sheets:
    if not sheet.key or not sheet.category_id:
      continue
    if not sheet.image_gcs_uri or not sheet.pdf_gcs_uri:
      continue
    if not isinstance(sheet.index, int) or sheet.index < 0:
      continue
    sheets_by_category.setdefault(sheet.category_id, []).append(sheet)

  categories_payload: dict[str, dict[str, object]] = {}
  for category in categories:
    if not category.id or not category.display_name:
      continue

    ordered_sheets = sheets_by_category.get(category.id, [])
    # Use key as tiebreaker in case of index conflicts.
    ordered_sheets.sort(key=lambda s: (s.index, s.key))
    if not ordered_sheets:
      continue

    categories_payload[category.id] = {
      "category_display_name":
      category.display_name,
      "sheets": [{
        "image_gcs_uri": sheet.image_gcs_uri,
        "pdf_gcs_uri": sheet.pdf_gcs_uri,
        "sheet_key": sheet.key,
      } for sheet in ordered_sheets],
    }

  payload = {
    "refresh_timestamp": SERVER_TIMESTAMP,
    "categories": categories_payload,
  }
  db().collection("joke_cache").document("joke_sheets").set(payload)


def update_joke_categories_cache(
  jokes_by_id: dict[str, models.PunnyJoke] | None = None, ) -> int:
  """Update the cached joke category index under `joke_cache/joke_categories`.

  The document contains a minimal list of category metadata for the admin UI:
  - category_id
  - display_name
  - image_url
  - state
  - public_joke_count

  Returns:
    Number of categories written into the cache.
  """
  public_counts: dict[str, int] = {}
  if jokes_by_id:
    for joke in jokes_by_id.values():
      if not joke.is_public_and_in_public_state:
        continue
      if not joke.category_id:
        continue
      public_counts[joke.category_id] = public_counts.get(joke.category_id,
                                                          0) + 1

  docs = db().collection("joke_categories").stream()
  categories_payload: list[dict[str, object]] = []
  for doc in docs:
    if not getattr(doc, "exists", False):
      continue
    data = doc.to_dict() or {}
    display_name = (data.get("display_name") or "").strip()
    # Keep the same "skip empty categories" semantics as get_all_joke_categories.
    if (not display_name and not (data.get("joke_description_query") or "")
        and not (data.get("seasonal_name") or "") and not data.get("tags")):
      continue
    state = (data.get("state") or "").strip() or "PROPOSED"
    image_url = (data.get("image_url") or "").strip() or None
    categories_payload.append({
      "category_id":
      doc.id,
      "display_name":
      display_name,
      "image_url":
      image_url,
      "state":
      state,
      "public_joke_count":
      int(public_counts.get(doc.id, 0)),
    })

  payload = {
    "refresh_timestamp": SERVER_TIMESTAMP,
    "categories": categories_payload,
  }
  db().collection("joke_cache").document("joke_categories").set(payload)
  return len(categories_payload)


def get_all_punny_jokes() -> list[models.PunnyJoke]:
  """Get all punny jokes from the 'jokes' collection."""
  docs = db().collection('jokes').stream()
  jokes = [
    models.PunnyJoke.from_firestore_dict(doc.to_dict(), key=doc.id)
    for doc in docs if doc.exists and doc.to_dict() is not None
  ]
  return jokes


def get_all_joke_categories(
  *,
  fetch_cached_jokes: bool = False,
  use_cache: bool = False,
) -> list[models.JokeCategory]:
  """Get all joke categories from the 'joke_categories' collection.

  Args:
    fetch_cached_jokes: When True, also fetch `category_jokes/cache` and populate
      `category.jokes` from the cached joke payload.
    use_cache: When True, read the category list from `joke_cache/joke_categories`
      instead of scanning the `joke_categories` collection.
  """
  client = db()

  def _iter_categories() -> list[models.JokeCategory]:
    if use_cache:
      cache_doc = client.collection("joke_cache").document(
        "joke_categories").get()
      if not getattr(cache_doc, "exists", False):
        return []
      payload = cache_doc.to_dict() or {}
      raw_categories = payload.get("categories")
      if not isinstance(raw_categories, list):
        return []

      categories_from_cache: list[models.JokeCategory] = []
      for item in raw_categories:
        if not isinstance(item, dict):
          continue
        category_id = (item.get("category_id") or "").strip()
        if not category_id:
          continue

        # Use model helper to parse fields (handles defaults, types, and extra fields)
        item_copy = dict(item)
        item_copy.pop("category_id", None)  # Key is passed separately
        categories_from_cache.append(
          models.JokeCategory.from_firestore_dict(item_copy, key=category_id))
      return categories_from_cache

    docs = client.collection("joke_categories").stream()
    categories_from_collection: list[models.JokeCategory] = []
    for doc in docs:
      if not doc.exists:
        continue
      data = doc.to_dict() or {}
      category = models.JokeCategory.from_firestore_dict(data, key=doc.id)
      if (not category.display_name and not category.joke_description_query
          and not category.seasonal_name and not category.tags):
        continue
      categories_from_collection.append(category)
    return categories_from_collection

  categories = _iter_categories()
  if fetch_cached_jokes:
    for category in categories:
      if not category.id:
        continue
      category_ref = client.collection("joke_categories").document(category.id)
      _populate_category_cached_jokes(category, category_ref)

  return categories


def get_joke_category(category_id: str) -> models.JokeCategory | None:
  """Get a joke category by ID, populating its cached jokes."""
  if not category_id:
    return None

  category_ref = db().collection('joke_categories').document(category_id)
  category_doc = category_ref.get()

  if not category_doc.exists:
    return None

  data = category_doc.to_dict() or {}
  category = models.JokeCategory.from_firestore_dict(data, key=category_id)

  _populate_category_cached_jokes(category, category_ref)

  return category


def _populate_category_cached_jokes(
  category: models.JokeCategory,
  category_ref: DocumentReference,
) -> None:
  """Populate category.jokes from `category_jokes/cache` if present."""
  cache_doc = category_ref.collection('category_jokes').document('cache').get()
  if not cache_doc.exists:
    return
  cache_data = cache_doc.to_dict() or {}
  jokes_data = cache_data.get('jokes', [])
  if not isinstance(jokes_data, list):
    return
  for joke_data in jokes_data:
    if not isinstance(joke_data, dict):
      continue
    joke_id = joke_data.get('key')
    setup_text = joke_data.get('setup_text') or ""
    punchline_text = joke_data.get('punchline_text') or ""
    joke = models.PunnyJoke(
      key=joke_id,
      setup_text=setup_text,
      punchline_text=punchline_text,
      setup_image_url=joke_data.get('setup_image_url'),
      punchline_image_url=joke_data.get('punchline_image_url'),
    )
    category.jokes.append(joke)


def create_joke_category(
  *,
  display_name: str,
  state: str = "PROPOSED",
  joke_description_query: str | None = None,
  seasonal_name: str | None = None,
  book_id: str | None = None,
  search_distance: float | None = None,
  tags: list[str] | None = None,
  negative_tags: list[str] | None = None,
  image_description: str | None = None,
) -> str:
  """Create a new joke category and return its document ID.

  Raises:
    ValueError: if required fields are missing or category already exists.
  """
  display_name = (display_name or '').strip()
  joke_description_query = (joke_description_query or '').strip()
  seasonal_name = (seasonal_name or '').strip()
  book_id = (book_id or '').strip() or None
  tags = list(tags) if isinstance(tags, list) else []
  negative_tags = list(negative_tags) if isinstance(negative_tags,
                                                    list) else []
  image_description = (image_description or '').strip()
  state = (state or 'PROPOSED').strip()
  search_distance = float(
    search_distance) if search_distance is not None else None

  if not display_name:
    raise ValueError("display_name is required")

  def _normalize_tags(raw_tags: list[str]) -> list[str]:
    normalized: list[str] = []
    seen = set()
    for t in raw_tags:
      if not isinstance(t, str):
        continue
      tag = t.strip()
      if not tag or tag in seen:
        continue
      seen.add(tag)
      normalized.append(tag)
    return normalized

  normalized_tags = _normalize_tags(tags)
  normalized_negative_tags = _normalize_tags(negative_tags)

  if not joke_description_query and not seasonal_name and not normalized_tags and not book_id:
    raise ValueError(
      "Provide at least one of joke_description_query, seasonal_name, tags, or book_id"
    )

  # Use the same key semantics as the app (display_name-derived).
  category_id = models.JokeCategory(display_name=display_name).key

  ref = db().collection('joke_categories').document(category_id)
  if ref.get().exists:
    raise ValueError(f"Category {category_id} already exists")

  category = models.JokeCategory(
    id=None,
    display_name=display_name,
    joke_description_query=joke_description_query or None,
    seasonal_name=seasonal_name or None,
    book_id=book_id,
    search_distance=search_distance,
    tags=normalized_tags,
    negative_tags=normalized_negative_tags,
    state=state,
    image_description=image_description or None,
  )
  payload: dict[str, Any] = category.to_dict()

  ref.set(payload, merge=True)
  return category_id


def get_uncategorized_public_jokes(
  all_categories: list[models.JokeCategory], ) -> list[models.PunnyJoke]:
  """Get all public jokes not in any category (via category_id index).

  Note: `all_categories` is unused; it is kept for backwards compatibility with
  older callers that passed the category list.
  """
  del all_categories

  query = db().collection("jokes").where(
    filter=FieldFilter("is_public", "==", True))
  query = query.where(
    filter=FieldFilter("category_id", "==", UNCATEGORIZED_CATEGORY_ID))
  docs = query.stream()

  results: list[models.PunnyJoke] = []
  for doc in docs:
    if not getattr(doc, "exists", False):
      continue
    data = doc.to_dict() or {}
    results.append(models.PunnyJoke.from_firestore_dict(data, key=doc.id))

  results.sort(key=lambda j: j.num_saved_users_fraction or 0.0, reverse=True)
  return results


async def upsert_joke_categories(
    categories: list[models.JokeCategory]) -> None:
  """Upsert joke categories into the 'joke_categories' collection.

  Args:
      categories: List of JokeCategory objects to upsert.
  """
  if not categories:
    return

  # Validate and prepare payloads first to avoid partial writes
  prepared: list[tuple[str, dict[str, Any]]] = []
  for category in categories:
    if not category.display_name or (not category.joke_description_query
                                     and not category.seasonal_name
                                     and not category.tags):
      raise ValueError(
        "JokeCategory must have non-empty display_name and at least one of joke_description_query, seasonal_name, or tags"
      )

    # Serialize directly from the model. (JokeCategory.to_dict already drops
    # `id` and cached `jokes`.)
    payload = dict(category.to_dict())

    prepared.append((category.key, payload))

  client = get_async_db()
  for key, data in prepared:
    await client.collection('joke_categories').document(key).set(data,
                                                                 merge=True)


def list_joke_schedules() -> list[str]:
  """List all joke schedule IDs from Firestore.

  Returns:
      A list of document IDs from the `joke_schedules` collection.
  """
  docs = db().collection('joke_schedules').get()
  return [doc.id for doc in docs]


def _batch_doc_id(schedule_name: str, year: int, month: int) -> str:
  """Create the batch document ID for a given schedule and month."""
  return f"{schedule_name}_{year}_{month:02d}"


def _load_schedule_batch(schedule_name: str, year: int, month: int) -> dict:
  """Load a schedule batch document and return its data dict (or {})."""
  batch_doc_id = _batch_doc_id(schedule_name, year, month)
  batch_ref = db().collection('joke_schedule_batches').document(batch_doc_id)
  snapshot = batch_ref.get()
  if not snapshot.exists:
    logger.error(f"No joke schedule batch found for {batch_doc_id}")
    return {}
  return snapshot.to_dict() or {}


def _joke_from_day_data(day_data: dict | None) -> models.PunnyJoke | None:
  """Convert a single day's schedule data into a PunnyJoke, if valid."""
  if not day_data:
    return None
  key = day_data.get('joke_id')
  setup_text = day_data.get('setup')
  punchline_text = day_data.get('punchline')
  setup_image_url = day_data.get('setup_image_url')
  punchline_image_url = day_data.get('punchline_image_url')
  if (not key or not setup_text or not punchline_text or not setup_image_url
      or not punchline_image_url):
    logger.error(f"Missing data in day_data: {day_data}")
    return None
  return models.PunnyJoke(
    key=key,
    setup_text=setup_text,
    punchline_text=punchline_text,
    setup_image_url=setup_image_url,
    punchline_image_url=punchline_image_url,
  )


def get_daily_jokes(
  schedule_name: str,
  joke_date: datetime.date,
  num_jokes: int,
) -> list[models.PunnyJoke]:
  """Get up to `num_jokes` daily jokes ending on `joke_date`.

  Fetches from this month's batch and, if needed, earlier months to gather
  the requested number of jokes. Results are returned in reverse chronological
  order (newest first), so index 0 corresponds to `joke_date`.
  """
  if num_jokes <= 0:
    return []

  # Build the date range [start_date, joke_date] inclusive
  start_date = joke_date - datetime.timedelta(days=num_jokes - 1)

  # Cache batches by (year, month) to avoid duplicate reads
  batch_cache: dict[tuple[int, int], dict] = {}

  collected: list[tuple[datetime.date, models.PunnyJoke]] = []
  current = start_date
  while current <= joke_date:
    ym = (current.year, current.month)
    if ym not in batch_cache:
      batch_cache[ym] = _load_schedule_batch(schedule_name, current.year,
                                             current.month)
    batch_data = batch_cache.get(ym, {})
    jokes_dict = batch_data.get('jokes', {}) if isinstance(batch_data,
                                                           dict) else {}
    day_key = f"{current.day:02d}"
    joke = _joke_from_day_data(jokes_dict.get(day_key))
    if joke:
      collected.append((current, joke))
    else:
      logger.error(
        f"No joke scheduled for day {day_key} in {_batch_doc_id(schedule_name, current.year, current.month)}"
      )
    current += datetime.timedelta(days=1)

  # Sort by date desc to ensure reverse chronological order, then strip dates
  collected.sort(key=lambda t: t[0], reverse=True)
  return [j for _, j in collected]


def get_top_jokes(sort_field: str, limit: int) -> list[models.PunnyJoke]:
  """Get top jokes from firestore sorted by a given field.

  Args:
      sort_field: The field to sort by (e.g., 'popularity_score_recent').
      limit: The maximum number of jokes to return.
  """
  docs = (db().collection('jokes').where(
    filter=FieldFilter('is_public', '==', True)).order_by(
      sort_field, direction=Query.DESCENDING).limit(limit).stream())
  return [
    models.PunnyJoke.from_firestore_dict(doc.to_dict(), key=doc.id)
    for doc in docs if doc.exists and doc.to_dict() is not None
  ]


def get_daily_joke(
  schedule_name: str,
  joke_date: datetime.date,
) -> models.PunnyJoke | None:
  """Backward-compatible wrapper returning a single joke for `joke_date`."""
  jokes = get_daily_jokes(schedule_name, joke_date, 1)
  return jokes[0] if jokes else None


def upsert_punny_joke(
  punny_joke: models.PunnyJoke,
  operation: str | None = None,
  *,
  update_metadata: dict[str, Any] | None = None,
) -> models.PunnyJoke | None:
  """Create or update a punny joke."""

  if not operation:
    operation = "CREATE" if not punny_joke.key else "UPDATE"

  # If joke has a key, try to update existing, otherwise create new
  saved_joke: models.PunnyJoke | None
  if punny_joke.key:
    updated_fields = update_punny_joke(
      punny_joke.key,
      punny_joke.to_dict(include_key=False),
      update_metadata=update_metadata,
    )
    saved_joke = punny_joke
  else:
    # Create new joke with custom ID
    custom_id = utils.create_firestore_key(
      punny_joke.punchline_text,
      punny_joke.setup_text,
      max_length=30,
    )

    joke_ref = db().collection('jokes').document(custom_id)
    if joke_ref.get().exists:
      return None

    joke_data = punny_joke.to_dict(include_key=False)
    updated_fields = joke_data.copy()
    joke_data['creation_time'] = SERVER_TIMESTAMP
    joke_data['last_modification_time'] = SERVER_TIMESTAMP

    joke_ref.set(joke_data)

    if update_metadata:
      metadata_ref = joke_ref.collection('metadata').document('metadata')
      metadata_ref.set(update_metadata, merge=True)

    punny_joke.key = custom_id
    saved_joke = punny_joke

  if saved_joke and saved_joke.key:
    current_time = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    log_fields = {
      OPERATION: operation,
      OPERATION_TIMESTAMP: current_time,
    }
    for key, value in updated_fields.items():
      if value == SERVER_TIMESTAMP:
        # Replace SERVER_TIMESTAMP with a string literal. Readers can derive
        # the timestamp from the operation timestamp field.
        value = "OPERATION_TIMESTAMP"
      log_fields[key] = value

    # Get the existing log entries
    operations_ref = (db().collection('jokes').document(
      saved_joke.key).collection('metadata').document('operations'))
    operations_doc = operations_ref.get()
    log_entries: list[dict[str, Any]] = []
    if operations_doc.exists:
      existing_data = operations_doc.to_dict() or {}
      existing_log = existing_data.get('log')
      if isinstance(existing_log, list):
        log_entries.extend(entry for entry in existing_log
                           if isinstance(entry, dict))

    log_entries.append(log_fields)
    operations_ref.set({'log': log_entries}, merge=True)

  return saved_joke


def update_punny_joke(
  joke_id: str,
  update_data: dict[str, Any],
  *,
  update_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
  """Update a punny joke document and optionally its metadata sub-document.

  Args:
    joke_id: Firestore document ID for the joke.
    update_data: Fields to update on the primary joke document.
    update_metadata: Optional fields to merge into `metadata/metadata`.

  Returns:
    A dict containing only the keys in `update_data` whose values differ from
    the existing Firestore document.
  """
  joke_ref = db().collection('jokes').document(joke_id)
  joke_snapshot = joke_ref.get()
  if not joke_snapshot.exists:
    raise ValueError(f"Joke {joke_id} not found in Firestore")

  existing_data = joke_snapshot.to_dict() or {}

  # Avoid mutating caller-provided dict.
  update_payload = dict(update_data)

  # Resolve state enum values to string values
  state_value = update_payload.get('state')
  resolved_state: models.JokeState | None = None
  if isinstance(state_value, models.JokeState):
    resolved_state = state_value
    update_payload['state'] = state_value.value
  elif isinstance(state_value, str):
    try:
      resolved_state = models.JokeState(state_value)
    except ValueError:
      resolved_state = None
  if resolved_state is not None:
    update_payload['is_public'] = resolved_state == models.JokeState.PUBLISHED
  update_payload['last_modification_time'] = SERVER_TIMESTAMP

  changed_fields: dict[str, Any] = {}
  for key, value in update_payload.items():
    if key in JOKE_FIELDS_TO_LOG and (key not in existing_data
                                      or existing_data.get(key) != value):
      changed_fields[key] = value

  joke_ref.update(update_payload)
  if update_metadata:
    metadata_ref = joke_ref.collection('metadata').document('metadata')
    metadata_ref.set(update_metadata, merge=True)

  return changed_fields


def update_joke_feed(jokes: list[dict[str, Any]]) -> None:
  """Update the public joke feed in Firestore, chunking jokes into documents."""
  client = db()
  feed_collection = client.collection('joke_feed')
  chunk_size = 50

  for i in range(0, len(jokes), chunk_size):
    chunk = jokes[i:i + chunk_size]
    chunk_index = i // chunk_size
    doc_id = f"{chunk_index:010d}"
    doc_ref = feed_collection.document(doc_id)
    doc_ref.set({"jokes": chunk})


def get_joke_feed_page_entries(
  cursor: str | None = None,
  limit: int = 10,
) -> tuple[list[tuple[models.PunnyJoke, str | None]], str | None]:
  """Get a page of jokes from the joke_feed collection with per-joke cursors.

  Args:
    cursor: Optional cursor in format "doc_id:joke_index" (e.g., "0000000000:9").
      The joke_index is the 0-based index of the next joke to return (the first joke
      of the next page). When provided, the function will start from this joke index
      in the specified document.
      If None, starts from the first document and first joke.
    limit: Maximum number of jokes to return (default 10).

  Returns:
    Tuple of (entries, next_cursor):
      - entries: List of (PunnyJoke, cursor) pairs, where cursor is the position of
        the next joke in the feed (i.e., the cursor to resume after this joke) in
        format "doc_id:joke_index". The final entry may have cursor None if there
        is no next joke available.
      - next_cursor: Cursor in format "doc_id:joke_index" representing the next joke
        to return (the first joke of the next page), or None if no more jokes are
        available. This cursor can be used to fetch the next page starting from this joke.
  """
  client = db()
  feed_collection = client.collection('joke_feed')
  query = feed_collection.order_by(FieldPath.document_id())

  # Parse cursor if provided (format: "doc_id:joke_index")
  cursor_doc_id: str | None = None
  cursor_joke_index: int | None = None
  if cursor:
    parts = cursor.split(':', 1)
    if len(parts) == 2:
      cursor_doc_id = parts[0]
      try:
        cursor_joke_index = int(parts[1])
      except ValueError:
        # Invalid cursor format, treat as None
        cursor_doc_id = None
        cursor_joke_index = None
    else:
      # Invalid cursor format (must be "doc_id:joke_index"), treat as None
      cursor_doc_id = None
      cursor_joke_index = None

  if cursor_doc_id:
    # Start at the cursor document
    query = query.start_at([cursor_doc_id])

  # Read documents until we have limit + 1 jokes worth of data
  # We'll return only limit jokes, using the extra to determine if there are more
  entries: list[tuple[models.PunnyJoke, str | None]] = []
  next_cursor_doc_id: str | None = None
  next_cursor_joke_index: int | None = None

  docs = query.stream()
  for doc in docs:
    if not doc.exists:
      continue

    doc_data = doc.to_dict() or {}
    doc_jokes = doc_data.get('jokes', [])
    if not isinstance(doc_jokes, list):
      continue

    # If this is the cursor document, start from the cursor index
    start_index = 0
    if cursor_doc_id and doc.id == cursor_doc_id and cursor_joke_index is not None:
      # Start from the cursor index (the next joke to return)
      start_index = cursor_joke_index

    # Process jokes from this document
    for joke_index, joke_dict in enumerate(
        doc_jokes[start_index:],
        start=start_index,
    ):
      if not isinstance(joke_dict, dict):
        continue

      # Try to convert to PunnyJoke
      try:
        joke = models.PunnyJoke.from_firestore_dict(
          joke_dict,
          key=joke_dict.get('key'),
        )

        joke_position = f"{doc.id}:{joke_index}"

        # If we already have limit jokes, this is the next joke - store as cursor and break.
        if len(entries) == limit:
          next_cursor_doc_id = doc.id
          next_cursor_joke_index = joke_index
          if entries:
            # The last returned joke resumes at this next position.
            last_joke, _ = entries[-1]
            entries[-1] = (last_joke, joke_position)
          break

        # Append with placeholder cursor; we'll set each entry's cursor to the next joke's
        # position once we see the next one.
        entries.append((joke, None))
        if len(entries) >= 2:
          prev_joke, _ = entries[-2]
          entries[-2] = (prev_joke, joke_position)
      except Exception:  # pylint: disable=broad-except
        # Skip malformed jokes, but continue reading to check if there are more
        continue

    # If we've found the next joke (cursor), stop reading documents
    if next_cursor_doc_id:
      break

  # Calculate next cursor
  next_cursor = (f"{next_cursor_doc_id}:{next_cursor_joke_index}"
                 if next_cursor_doc_id else None)

  return entries, next_cursor


def get_joke_feed_page(
  cursor: str | None = None,
  limit: int = 10,
) -> tuple[list[models.PunnyJoke], str | None]:
  """Get a page of jokes from the joke_feed collection.

  Args:
    cursor: Optional cursor in format "doc_id:joke_index" (e.g., "0000000000:9").
      The joke_index is the 0-based index of the next joke to return (the first joke
      of the next page). When provided, the function will start from this joke index
      in the specified document.
      If None, starts from the first document and first joke.
    limit: Maximum number of jokes to return (default 10).

  Returns:
    Tuple of (jokes_list, next_cursor):
      - jokes_list: List of PunnyJoke objects from the feed
      - next_cursor: Cursor in format "doc_id:joke_index" representing the next joke
        to return (the first joke of the next page), or None if no more jokes are
        available. This cursor can be used to fetch the next page starting from this joke.
  """
  entries, next_cursor = get_joke_feed_page_entries(cursor=cursor, limit=limit)
  return [entry[0] for entry in entries], next_cursor


def create_character(character: models.Character) -> models.Character:
  """Create a character."""
  character_data = character.to_dict(include_key=False)
  character_data['creation_time'] = SERVER_TIMESTAMP
  character_data['last_modification_time'] = SERVER_TIMESTAMP

  # Generate custom ID: [timestamp]_[name_prefix]
  custom_id = utils.create_timestamped_firestore_key(character.name)

  char_ref = db().collection('characters').document(custom_id)
  char_ref.set(character_data)
  character.key = custom_id
  return character


def get_character(character_id: str) -> models.Character | None:
  """Get a character."""
  characters = get_characters([character_id])
  return characters[0] if characters else None


def get_characters(character_ids: Collection[str]) -> list[models.Character]:
  """Get multiple characters in a single batch read.

  Args:
      character_ids: List of character IDs to fetch

  Returns:
      List of Character objects, in the same order as the input IDs.
      If a character is not found, it will be omitted from the result list.
  """
  if not character_ids:
    return []

  refs = [db().collection('characters').document(id) for id in character_ids]
  docs = db().get_all(refs)

  characters = [
    models.Character.from_dict(doc.to_dict(), key=doc.id) for doc in docs
    if doc.exists
  ]
  return characters


def update_character(character: models.Character) -> bool:
  """Update a character."""
  char_ref = db().collection('characters').document(character.key)
  if not char_ref.get().exists:
    return False

  character_data = character.to_dict(include_key=False)
  character_data['last_modification_time'] = SERVER_TIMESTAMP
  char_ref.set(character_data)
  return True


def delete_character(character_id: str) -> bool:
  """Delete a character."""
  char_ref = db().collection('characters').document(character_id)
  if not char_ref.get().exists:
    return False
  char_ref.delete()
  return True


def upsert_posable_character_def(
  character_def: models.PosableCharacterDef, ) -> models.PosableCharacterDef:
  """Upsert a posable character definition using its existing key."""
  if not character_def.key:
    raise ValueError("PosableCharacterDef key is required for upsert")

  def_data = character_def.to_dict(include_key=False)
  def_data['last_modification_time'] = SERVER_TIMESTAMP

  def_ref = db().collection('posable_character_defs').document(
    character_def.key)
  if not def_ref.get().exists:
    def_data['creation_time'] = SERVER_TIMESTAMP
  def_ref.set(def_data, merge=True)
  return character_def


def get_posable_character_def(
  character_def_id: str, ) -> models.PosableCharacterDef | None:
  """Get a posable character definition."""
  if not character_def_id:
    return None
  doc = db().collection('posable_character_defs').document(
    character_def_id).get()
  if not getattr(doc, 'exists', False):
    return None

  return models.PosableCharacterDef.from_firestore_dict(doc.to_dict() or {},
                                                        key=doc.id)


def get_posable_character_defs() -> list[models.PosableCharacterDef]:
  """Get all posable character definitions."""
  docs = db().collection('posable_character_defs').stream()
  return [
    models.PosableCharacterDef.from_firestore_dict(doc.to_dict(), key=doc.id)
    for doc in docs if doc.exists
  ]


def get_posable_character_sequence(
  sequence_id: str,
) -> posable_character_sequence.PosableCharacterSequence | None:
  """Get a posable character sequence."""
  if not sequence_id:
    return None
  doc = db().collection('posable_character_sequences').document(
    sequence_id).get()
  if not getattr(doc, 'exists', False):
    return None

  return posable_character_sequence.PosableCharacterSequence.from_dict(
    doc.to_dict() or {}, key=doc.id)


def get_posable_character_sequences(
) -> list[posable_character_sequence.PosableCharacterSequence]:
  """Get all posable character sequences."""
  docs = db().collection('posable_character_sequences').stream()
  return [
    posable_character_sequence.PosableCharacterSequence.from_dict(
      doc.to_dict() or {}, key=doc.id) for doc in docs if doc.exists
  ]


def upsert_posable_character_sequence(
  sequence: posable_character_sequence.PosableCharacterSequence,
) -> posable_character_sequence.PosableCharacterSequence:
  """Upsert a posable character sequence."""
  sequence.validate()
  sequence_data = sequence.to_dict(include_key=False)
  sequence_data['last_modification_time'] = SERVER_TIMESTAMP

  if sequence.key:
    seq_ref = db().collection('posable_character_sequences').document(
      sequence.key)
    seq_ref.set(sequence_data, merge=True)
  else:
    sequence_data['creation_time'] = SERVER_TIMESTAMP
    _, seq_ref = db().collection('posable_character_sequences').add(
      sequence_data)
    sequence.key = seq_ref.id

  return sequence


def create_image(image: models.Image) -> models.Image:
  """Create a new image in Firestore.

  Args:
      image: The Image object to create

  Returns:
      The created Image object with its key set
  """
  image_data = image.as_dict
  image_data['creation_time'] = SERVER_TIMESTAMP
  image_data['last_modification_time'] = SERVER_TIMESTAMP
  logger.info(pprint.pformat(image_data))
  _, image_ref = db().collection('images').add(image_data)
  image.key = image_ref.id
  return image


def update_image(image: models.Image) -> models.Image:
  """Update an existing image in Firestore.

  Args:
      image: The Image object to update

  Returns:
      The updated Image object
  """
  if not image.key:
    raise ValueError("Image key is required for update")

  image_data = image.as_dict
  image_data['last_modification_time'] = SERVER_TIMESTAMP
  db().collection('images').document(image.key).update(image_data)
  return image


def get_images(image_ids: Collection[str]) -> list[models.Image]:
  """Get multiple images in a single batch read.

  Args:
      image_ids: List of image IDs to fetch

  Returns:
      List of Image objects, in the same order as the input IDs.
      If an image is not found, it will be omitted from the result list.
  """
  if not image_ids:
    return []

  refs = [db().collection('images').document(id) for id in image_ids]
  docs = db().get_all(refs)

  images = [
    models.Image.from_dict(doc.to_dict(), key=doc.id) for doc in docs
    if doc.exists
  ]
  return images


def add_book_page(book_ref: DocumentReference,
                  page: models.StoryPageData) -> DocumentReference:
  """Add a single page to a book's chapter.

  Args:
      book_ref: Reference to the book document
      page: StoryPageData object containing page text and illustration description

  Returns:
      Reference to the created page document
  """
  if not page.is_complete:
    raise ValueError(
      f"Page {page.page_number} for book {book_ref.id} is not complete: {page.as_dict}"
    )

  # Create initial chapter if it doesn't exist
  chapter_ref = book_ref.collection('chapters').document('chapter1')
  if not chapter_ref.get().exists:
    chapter_ref.set({
      'title': 'Chapter 1',
      'summary': '',  # Can be generated later if needed
      'chapter_number': 1,
      'creation_time': SERVER_TIMESTAMP,
      'last_modification_time': SERVER_TIMESTAMP,
    })

  # Create the page document
  page_ref = chapter_ref.collection('pages').document(
    f'page{page.page_number:04d}')
  page_data = page.as_dict
  page_data.update({
    'page_number': page.page_number,
    'status': 'new',
    'creation_time': SERVER_TIMESTAMP,
    'last_modification_time': SERVER_TIMESTAMP,
  })
  page_ref.set(page_data)

  return page_ref


def create_book_pages(
  book_ref: DocumentReference,
  pages: list[tuple[str, str]],
) -> list[DocumentReference]:
  """Create book pages in Firestore.

  Args:
      book_ref: Reference to the book document
      pages: List of tuples containing (page_text, illustration_desc)

  Returns:
      List of page document references.
  """
  # Create initial chapter
  chapter_ref = book_ref.collection('chapters').document('chapter1')

  # Delete existing pages if any
  existing_pages = chapter_ref.collection('pages').get()
  if existing_pages:
    batch = db().batch()
    for page in existing_pages:
      batch.delete(page.reference)
    batch.commit()

  # Create new chapter document
  chapter_ref.set({
    'title': 'Chapter 1',
    'summary': '',  # Can be generated later if needed
    'chapter_number': 1,
    'creation_time': SERVER_TIMESTAMP,
    'last_modification_time': SERVER_TIMESTAMP,
  })

  # Create new pages in batch
  batch = db().batch()
  page_refs = []

  for i, (page_text, illustration_desc) in enumerate(pages, 1):
    page_ref = chapter_ref.collection('pages').document(f'page{i:04d}')
    batch.set(
      page_ref, {
        'text': page_text,
        'illustration_description': illustration_desc,
        'page_number': i,
        'creation_time': SERVER_TIMESTAMP,
        'last_modification_time': SERVER_TIMESTAMP,
      })
    page_refs.append(page_ref)

  batch.commit()
  return page_refs


def get_recent_stories(owner_user_id: str, limit: int) -> list[dict[str, str]]:
  """Get a user's most recent stories.

  Args:
      owner_user_id: The user ID to get stories for
      limit: Maximum number of stories to return

  Returns:
      List of dicts containing story title, tagline, and learning topic,
      excluding stories with missing title or tagline.
  """
  docs = (db().collection('books').select([
    'title', 'summary', 'learning_topic'
  ]).where(filter=FieldFilter('owner_user_id', '==', owner_user_id)).order_by(
    'creation_time', direction=Query.DESCENDING).limit(limit).get())

  book_dicts = [doc.to_dict() for doc in docs]
  return [
    book for book in book_dicts if book.get('title') and book.get('summary')
  ]


@transactional
def _initialize_user_in_transaction(
  transaction: Transaction,
  user_id_internal: str,
  email: str,
) -> bool:
  """The actual logic to be executed within the transaction.

  Returns:
      bool: True if a new document was created, False otherwise.
  """
  if not email:
    # Don't initialize for users with no email
    return False

  user_ref = db().collection('users').document(user_id_internal)
  snapshot = user_ref.get(transaction=transaction)

  if snapshot.exists:
    return False  # Indicate no creation happened

  # Data to set, include email if provided
  user_data = {
    'email': email,
    'user_type': 'USER',
    'preferences': {},
    'mailerlite_subscriber_id': None,
    'created_at': SERVER_TIMESTAMP,
    'last_modified_at': SERVER_TIMESTAMP,
  }

  transaction.set(user_ref, user_data)
  logger.info(
    f"Successfully created Firestore document for user: {user_id_internal} with email: {email}"
  )
  return True  # Indicate creation happened


def initialize_user_document(user_id: str, email: str) -> bool:
  """Creates the initial Firestore user document transactionally if it doesn't exist.

  This function is idempotent and runs its core logic within a transaction.

  Args:
      user_id: The Firebase Authentication user ID.
      email: The user's email address.

  Returns:
      bool: True if a new document was created, False otherwise.

  Raises:
      Exception: If Firestore operation fails after retries.
  """
  user_id = user_id.strip()
  email = email.strip()
  if not user_id or not email:
    logger.warn(
      f"No user ID or email provided for user {user_id}. Skipping initialization."
    )
    return False

  transaction = db().transaction()
  created = _initialize_user_in_transaction(transaction, user_id, email=email)
  return created


def get_users_missing_mailerlite_subscriber_id(limit: int | None = None):
  """Return Firestore docs for users missing a MailerLite subscriber id."""
  query = db().collection('users').where(
    filter=FieldFilter('mailerlite_subscriber_id', '==', None))
  if limit and limit > 0:
    query = query.limit(int(limit))
  return query.stream()


def update_user_mailerlite_subscriber_id(
  user_id: str,
  subscriber_id: str,
) -> None:
  """Update a user's mailerlite_subscriber_id field."""
  user_id = (user_id or '').strip()
  subscriber_id = (subscriber_id or '').strip()
  if not user_id:
    raise ValueError("user_id is required")
  if not subscriber_id:
    raise ValueError("subscriber_id is required")
  db().collection('users').document(user_id).update({
    'mailerlite_subscriber_id':
    subscriber_id,
  })


def ensure_joke_lead_doc(
  *,
  email: str,
  subscriber_id: str | None,
  signup_source: str,
  country_code: str | None = None,
) -> None:
  """Upsert a joke_leads document without overwriting existing values."""
  email_norm = (email or '').strip().lower()
  if not email_norm:
    raise ValueError("email is required")

  now = datetime.datetime.now(datetime.timezone.utc)
  lead_ref = db().collection('joke_leads').document(email_norm)
  snapshot = lead_ref.get()
  existing = snapshot.to_dict() if getattr(snapshot, "exists", False) else {}
  if not isinstance(existing, dict):
    existing = {}

  payload: dict[str, Any] = {
    'email': email_norm,
  }
  if subscriber_id:
    payload['mailerlite_subscriber_id'] = subscriber_id

  if not existing.get('timestamp'):
    payload['timestamp'] = now
  if not existing.get('signup_date'):
    payload['signup_date'] = now.date().isoformat()
  if not existing.get('signup_source'):
    payload['signup_source'] = signup_source
  if country_code and not existing.get('country_code'):
    payload['country_code'] = country_code

  lead_ref.set(payload, merge=True)


def _to_utc_naive(dt: datetime.datetime) -> datetime.datetime:
  """Convert a datetime to naive UTC for arithmetic.

  If the provided datetime has tzinfo, convert to UTC and strip tzinfo.
  """
  if isinstance(dt, datetime.datetime) and dt.tzinfo is not None:
    return dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
  return dt


def _upsert_joke_user_usage_logic(
  transaction: Transaction,
  user_id: str,
  now_utc: datetime.datetime | None = None,
  *,
  client_num_days_used: int | None = None,
  client_num_saved: int | None = None,
  client_num_viewed: int | None = None,
  client_num_navigated: int | None = None,
  client_num_shared: int | None = None,
  client_num_thumbs_up: int | None = None,
  client_num_thumbs_down: int | None = None,
  requested_review: bool | None = None,
  feed_cursor: str | None = None,
  local_feed_count: int | None = None,
) -> int:
  """Transactional helper to upsert joke user usage and return final count.

  Args:
      transaction: Firestore transaction
      user_id: The Firebase Authentication user ID, used as document ID
      now_utc: Optional override for current time (UTC). Useful for tests.

  Returns:
      The final value of num_distinct_day_used after the write.
  """
  doc_ref = db().collection('joke_users').document(user_id)
  snapshot = doc_ref.get(transaction=transaction)

  # Collect client counters if provided
  client_updates: dict[str, int | bool | str] = {}
  if client_num_days_used is not None:
    client_updates['client_num_days_used'] = int(client_num_days_used)
  if client_num_saved is not None:
    client_updates['client_num_saved'] = int(client_num_saved)
  if client_num_viewed is not None:
    client_updates['client_num_viewed'] = int(client_num_viewed)
  if client_num_navigated is not None:
    client_updates['client_num_navigated'] = int(client_num_navigated)
  if client_num_shared is not None:
    client_updates['client_num_shared'] = int(client_num_shared)
  if client_num_thumbs_up is not None:
    client_updates['client_num_thumbs_up'] = int(client_num_thumbs_up)
  if client_num_thumbs_down is not None:
    client_updates['client_num_thumbs_down'] = int(client_num_thumbs_down)
  if requested_review is not None:
    client_updates['requested_review'] = requested_review
  # Always include feed_cursor and local_feed_count (may be empty/zero)
  client_updates['feed_cursor'] = (feed_cursor or '').strip()
  client_updates['local_feed_count'] = int(local_feed_count or 0)

  # Insert path
  if not snapshot.exists:
    initial = {
      'created_at': SERVER_TIMESTAMP,
      'last_login_at': SERVER_TIMESTAMP,
      'num_distinct_day_used': 1,
      **client_updates,
    }
    transaction.set(doc_ref, initial)
    return 1

  # Update path
  data = snapshot.to_dict() or {}
  created_at_val = data.get('created_at')
  last_login_at_val = data.get('last_login_at') or created_at_val
  current_count = int(data.get('num_distinct_day_used', 0) or 0)

  # If created_at is missing for an existing doc, treat as now to avoid false increments
  if not created_at_val:
    transaction.update(
      doc_ref, {
        'last_login_at': SERVER_TIMESTAMP,
        'num_distinct_day_used': max(1, current_count),
      })
    return max(1, current_count)

  # Normalize datetimes
  created_at_dt = _to_utc_naive(created_at_val)
  last_login_dt = _to_utc_naive(
    last_login_at_val) if last_login_at_val else created_at_dt
  # Use timezone-aware now in UTC, then normalize to naive UTC for arithmetic
  now_dt = _to_utc_naive(
    now_utc if now_utc else datetime.datetime.now(datetime.timezone.utc))

  # Compute whole-day buckets since creation
  seconds_per_day = 86400
  num_days_at_last_login = int(
    (last_login_dt - created_at_dt).total_seconds() // seconds_per_day)
  num_days_now = int(
    (now_dt - created_at_dt).total_seconds() // seconds_per_day)

  increment = 1 if num_days_now != num_days_at_last_login else 0
  final_count = current_count + increment

  update_payload = {
    'last_login_at': SERVER_TIMESTAMP,
    'num_distinct_day_used': final_count,
    **client_updates,
  }
  transaction.update(doc_ref, update_payload)
  return final_count


@transactional
def _upsert_joke_user_usage_in_txn(
  transaction: Transaction,
  user_id: str,
  now_utc: datetime.datetime | None = None,
  *,
  client_num_days_used: int | None = None,
  client_num_saved: int | None = None,
  client_num_viewed: int | None = None,
  client_num_navigated: int | None = None,
  client_num_shared: int | None = None,
  client_num_thumbs_up: int | None = None,
  client_num_thumbs_down: int | None = None,
  requested_review: bool | None = None,
  feed_cursor: str | None = None,
  local_feed_count: int | None = None,
) -> int:
  """Transactional wrapper that handles the transaction."""
  # The actual logic is in a separate function for testability
  return _upsert_joke_user_usage_logic(
    transaction,
    user_id,
    now_utc,
    client_num_days_used=client_num_days_used,
    client_num_saved=client_num_saved,
    client_num_viewed=client_num_viewed,
    client_num_navigated=client_num_navigated,
    client_num_shared=client_num_shared,
    client_num_thumbs_up=client_num_thumbs_up,
    client_num_thumbs_down=client_num_thumbs_down,
    requested_review=requested_review,
    feed_cursor=feed_cursor,
    local_feed_count=local_feed_count,
  )


def upsert_joke_user_usage(
  user_id: str,
  now_utc: datetime.datetime | None = None,
  *,
  client_num_days_used: int | None = None,
  client_num_saved: int | None = None,
  client_num_viewed: int | None = None,
  client_num_navigated: int | None = None,
  client_num_shared: int | None = None,
  client_num_thumbs_up: int | None = None,
  client_num_thumbs_down: int | None = None,
  requested_review: bool | None = None,
  feed_cursor: str | None = None,
  local_feed_count: int | None = None,
) -> int:
  """Create or update the joke user usage document and return final count.

  Args:
      user_id: The user ID (document ID in collection 'joke_users').
      now_utc: Optional override for current time (UTC). Useful for tests.

  Returns:
      The final value of num_distinct_day_used after the write.
  """
  user_id = user_id.strip()
  if not user_id:
    raise ValueError("user_id is required")

  transaction = db().transaction()
  return _upsert_joke_user_usage_in_txn(
    transaction,
    user_id,
    now_utc,
    client_num_days_used=client_num_days_used,
    client_num_saved=client_num_saved,
    client_num_viewed=client_num_viewed,
    client_num_navigated=client_num_navigated,
    client_num_shared=client_num_shared,
    client_num_thumbs_up=client_num_thumbs_up,
    client_num_thumbs_down=client_num_thumbs_down,
    requested_review=requested_review,
    feed_cursor=feed_cursor,
    local_feed_count=local_feed_count,
  )


def get_joke_stats_docs(limit: int = 30) -> list[dict[str, Any]]:
  """Fetch recent joke stats docs for the admin dashboard.

  Returns docs in chronological order (oldest -> newest) with 'id' populated.
  """
  safe_limit = max(0, int(limit or 0))
  if safe_limit <= 0:
    return []

  docs = (db().collection('joke_stats').order_by(
    '__name__', direction=Query.DESCENDING).limit(safe_limit).stream())

  stats_list: list[dict[str, Any]] = []
  for doc in docs:
    data = doc.to_dict() or {}
    data['id'] = doc.id
    stats_list.append(data)

  stats_list.reverse()
  return stats_list


def get_all_joke_books() -> list[dict[str, Any]]:
  """Fetch all joke books with basic metadata for the admin table view."""
  docs = db().collection('joke_books').stream()
  books: list[dict[str, Any]] = []
  for doc in docs:
    if not getattr(doc, 'exists', False):
      continue
    data = doc.to_dict() or {}
    jokes = data.get('jokes') or []
    joke_count = len(jokes) if isinstance(jokes, list) else 0
    books.append({
      'id': doc.id,
      'book_name': data.get('book_name', ''),
      'joke_count': joke_count,
      'zip_url': data.get('zip_url'),
    })

  books.sort(key=lambda book: str(book.get('book_name') or book.get('id')))
  return books


def get_joke_book(book_id: str) -> dict[str, Any] | None:
  """Fetch a single joke book doc by id (or None if missing)."""
  if not book_id:
    return None
  doc = db().collection('joke_books').document(book_id).get()
  if not getattr(doc, 'exists', False):
    return None
  data = doc.to_dict() or {}
  data['id'] = book_id
  return data


def get_joke_metadata(joke_id: str) -> dict[str, Any]:
  """Fetch `jokes/{joke_id}/metadata/metadata` (or {})."""
  if not joke_id:
    return {}
  doc = (db().collection('jokes').document(joke_id).collection(
    'metadata').document('metadata').get())
  return doc.to_dict() or {} if getattr(doc, 'exists', False) else {}


def get_joke_with_metadata(
  joke_id: str, ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
  """Fetch a joke document and its metadata sub-document."""
  if not joke_id:
    return None, {}
  joke_doc = db().collection('jokes').document(joke_id).get()
  if not getattr(joke_doc, 'exists', False):
    return None, {}
  joke_data = joke_doc.to_dict() or {}
  metadata = get_joke_metadata(joke_id)
  return joke_data, metadata


def get_joke_book_detail_raw(
  book_id: str, ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
  """Fetch a joke book and per-joke data/metadata for admin rendering.

  Returns:
    (book_data, joke_entries) where joke_entries preserves the book order and
    each entry contains: { 'id': joke_id, 'joke': <dict>, 'metadata': <dict> }.
  """
  book = get_joke_book(book_id)
  if not book:
    return None, []

  joke_ids = book.get('jokes') or []
  if not isinstance(joke_ids, list):
    joke_ids = []
  joke_ids = [str(jid) for jid in joke_ids if jid]

  if not joke_ids:
    return book, []

  client = db()
  refs = [client.collection('jokes').document(jid) for jid in joke_ids]
  docs = client.get_all(refs)
  id_to_joke: dict[str, dict[str, Any]] = {}
  for doc in docs:
    if not getattr(doc, 'exists', False):
      continue
    id_to_joke[doc.id] = doc.to_dict() or {}

  entries: list[dict[str, Any]] = []
  for jid in joke_ids:
    entries.append({
      'id': jid,
      'joke': id_to_joke.get(jid, {}),
      'metadata': get_joke_metadata(jid),
    })

  return book, entries
