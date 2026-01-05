"""Operations for joke category cache management."""

from __future__ import annotations

from common import config, joke_notes_sheet_operations, models
from firebase_functions import logger
from google.cloud.firestore import FieldFilter
from services import firestore, search


def refresh_category_caches() -> dict[str, int]:
  """Refresh cached joke lists for Firestore categories.

  - Processes only categories in APPROVED, SEASONAL, or PROPOSED state
  - Uses the same search semantics as the app ("jokes about {query}") with
    tight threshold and public-only filters equivalent to state and is_public
  - Stores results under: joke_categories/{category_id}/category_jokes/cache
    with a single field 'jokes' which is an array of maps containing
    {joke_id, setup, punchline, setup_image_url, punchline_image_url}
  - If a category yields no results, writes an empty array and forces state to
    PROPOSED on the category document
    
  Returns:
    Dictionary with maintenance statistics: categories_processed, categories_updated, categories_emptied, categories_failed
  """
  client = firestore.db()
  categories_collection = client.collection("joke_categories")
  docs = categories_collection.stream()

  total = 0
  updated = 0
  emptied = 0
  failed = 0

  for doc in docs:
    if not doc.exists:
      continue
    total += 1
    data = doc.to_dict() or {}

    try:
      result = refresh_single_category_cache(doc.id, data)
      if result == "updated":
        updated += 1
      elif result == "emptied":
        emptied += 1
      # If result is None, category was skipped (invalid state or missing query)
    except Exception as exc:  # pylint: disable=broad-except
      logger.error(f"Failed refreshing category cache for {doc.id}: {exc}")
      failed += 1

  logger.info(
    f"Category caches refreshed: processed={total}, updated={updated}, emptied={emptied}, failed={failed}"
  )

  return {
    "categories_processed": total,
    "categories_updated": updated,
    "categories_emptied": emptied,
    "categories_failed": failed,
  }


def refresh_single_category_cache(
    category_id: str, category_data: dict[str, object]) -> str | None:
  """Refresh cached joke list for a single category.

  Args:
    category_id: The ID of the category document
    category_data: The category document data dictionary

  Returns:
    "updated" if cache was updated with jokes, "emptied" if cache was set to empty,
    None if the category was skipped (invalid state or missing query/seasonal)
    
  Raises:
    Exception if cache refresh fails (caller should handle)
  """
  category = models.JokeCategory.from_firestore_dict(category_data,
                                                     key=category_id)

  # Filter to categories with valid state and query
  state = (category.state or "").upper()
  if state not in ("APPROVED", "SEASONAL", "PROPOSED"):
    return None

  raw_query = (category.joke_description_query or "").strip()
  seasonal_name = (category.seasonal_name or "").strip()
  tags = [t for t in (category.tags or []) if isinstance(t, str) and t.strip()]
  search_distance = category.search_distance

  client = firestore.db()

  if not raw_query and not seasonal_name and not tags:
    if state != "PROPOSED":
      # This category will break when displayed, so force state to PROPOSED
      client.collection("joke_categories").document(category_id).set(
        {"state": "PROPOSED"}, merge=True)
    return None

  jokes_by_id: dict[str, dict[str, object]] = {}

  if raw_query:
    search_query = f"jokes about {raw_query}"
    for item in search_category_jokes(
        search_query,
        category_id,
        distance_threshold=search_distance,
    ):
      joke_id = item.get("joke_id")
      if isinstance(joke_id, str) and joke_id:
        jokes_by_id[joke_id] = item

  if seasonal_name:
    for item in query_seasonal_category_jokes(client, seasonal_name):
      joke_id = item.get("joke_id")
      if isinstance(joke_id, str) and joke_id:
        jokes_by_id[joke_id] = item

  if tags:
    for item in query_tags_category_jokes(client, tags):
      joke_id = item.get("joke_id")
      if isinstance(joke_id, str) and joke_id:
        jokes_by_id[joke_id] = item

  # Re-sort the union by num_saved_users_fraction using full joke docs.
  joke_ids = list(jokes_by_id.keys())
  jokes = firestore.get_punny_jokes(joke_ids)
  jokes.sort(key=lambda j: j.num_saved_users_fraction or 0.0, reverse=True)

  # Cap cache size to 100, even if union exceeds it.
  jokes = jokes[:100]

  jokes_payload = [{
    "joke_id": j.key,
    "setup": j.setup_text,
    "punchline": j.punchline_text,
    "setup_image_url": j.setup_image_url,
    "punchline_image_url": j.punchline_image_url,
  } for j in jokes if j.key]

  # Write cache document with a sole 'jokes' field
  cache_ref = client.collection("joke_categories").document(
    category_id).collection("category_jokes").document("cache")
  cache_ref.set({"jokes": jokes_payload})
  logger.info(
    f"Category cache updated for {category_id}, with {len(jokes_payload)} jokes"
  )

  if not jokes_payload:
    # Force category state to PROPOSED when empty
    client.collection("joke_categories").document(category_id).set(
      {"state": "PROPOSED"}, merge=True)
    logger.info(
      f"Category cache emptied for {category_id}, forcing state to PROPOSED")
    return "emptied"

  _ensure_category_joke_sheets(category_id, jokes)
  return "updated"


def _ensure_category_joke_sheets(
  category_id: str,
  jokes: list[models.PunnyJoke],
) -> None:
  """Create joke sheets for all jokes in the category (in batches of 5).

  For jokes not already in a sheet for this category, creates sheets containing
  exactly 5 jokes at a time. If there are 4 or fewer uncovered jokes, does
  nothing.
  """
  category_id = (category_id or "").strip()
  if not category_id:
    return

  existing_sheets = firestore.get_joke_sheets_by_category(category_id)
  covered_ids = {
    jid
    for sheet in existing_sheets
    for jid in sheet.joke_ids if jid
  }

  uncovered = [j for j in jokes if j.key and j.key not in covered_ids]
  batch_size = 5
  num_complete_batches = len(uncovered) // batch_size
  if num_complete_batches <= 0:
    return

  for i in range(num_complete_batches):
    batch = uncovered[i * batch_size:(i + 1) * batch_size]
    batch_ids = [j.key for j in batch if j.key]
    if len(batch_ids) != batch_size:
      continue
    try:
      joke_notes_sheet_operations.get_joke_notes_sheet(
        batch_ids,
        category_id=category_id,
      )
      logger.info(
        f"Created joke sheet for category {category_id} with {len(batch_ids)} jokes"
      )
    except Exception as exc:  # pylint: disable=broad-except
      logger.error(
        f"Failed to create joke sheet for category {category_id}: {exc}")


def search_category_jokes(
  search_query: str,
  category_id: str,
  *,
  distance_threshold: float | None = None,
) -> list[dict[str, object]]:
  """Search for jokes matching a category query.

  Args:
    search_query: The search query string (e.g., "jokes about cats")
    category_id: The category ID for labeling

  Returns:
    List of joke dictionaries with keys: joke_id, setup, punchline,
    setup_image_url, punchline_image_url, sorted by num_saved_users_fraction
    in descending order.
  """
  field_filters: list[tuple[str, str, object]] = [
    ("state", "in",
     [models.JokeState.PUBLISHED.value, models.JokeState.DAILY.value]),
    ("is_public", "==", True),
  ]

  results = search.search_jokes(
    query=search_query,
    label=f"daily_cache:category:{category_id}",
    field_filters=field_filters,  # type: ignore[arg-type]
    limit=100,
    distance_threshold=distance_threshold
    if distance_threshold else config.JOKE_SEARCH_TIGHT_THRESHOLD,
  )

  # Extract joke IDs
  joke_ids = [result.joke_id for result in results if result.joke_id]

  # Fetch full jokes
  jokes = firestore.get_punny_jokes(joke_ids)

  # Sort by num_saved_users_fraction (descending)
  sorted_jokes = sorted(
    jokes,
    key=lambda j: j.num_saved_users_fraction or 0.0,
    reverse=True,
  )

  return [{
    "joke_id": j.key,
    "setup": j.setup_text,
    "punchline": j.punchline_text,
    "setup_image_url": j.setup_image_url,
    "punchline_image_url": j.punchline_image_url,
  } for j in sorted_jokes]


def query_seasonal_category_jokes(
    client, seasonal_name: str) -> list[dict[str, object]]:
  """Query jokes by seasonal name.

  Args:
    client: Firestore client instance
    seasonal_name: The seasonal name to filter by

  Returns:
    List of joke dictionaries with keys: joke_id, setup, punchline,
    setup_image_url, punchline_image_url, sorted by num_saved_users_fraction
    in descending order.
  """
  states = [models.JokeState.PUBLISHED.value, models.JokeState.DAILY.value]
  query = client.collection("jokes")
  query = query.where(filter=FieldFilter("state", "in", states))
  query = query.where(filter=FieldFilter("is_public", "==", True))
  query = query.where(filter=FieldFilter("seasonal", "==", seasonal_name))
  query = query.limit(100)

  docs = query.stream()
  docs_list = [(doc.id, doc.to_dict() or {}) for doc in docs]
  sorted_docs_list = sorted(
    docs_list,
    key=lambda item: item[1].get("num_saved_users_fraction", 0.0),
    reverse=True)

  payload = []
  for doc_id, data in sorted_docs_list:
    payload.append({
      "joke_id": doc_id,
      "setup": data.get("setup_text", ""),
      "punchline": data.get("punchline_text", ""),
      "setup_image_url": data.get("setup_image_url"),
      "punchline_image_url": data.get("punchline_image_url"),
    })
  return payload


def query_tags_category_jokes(
  client,
  tags: list[str],
) -> list[dict[str, object]]:
  """Query jokes that match any of the given tags.

  Args:
    client: Firestore client instance
    tags: List of tags; jokes are included if they contain at least one tag.

  Returns:
    List of joke dictionaries with keys: joke_id, setup, punchline,
    setup_image_url, punchline_image_url, sorted by num_saved_users_fraction
    in descending order.
  """

  def _normalize_tags(raw_tags: list[str]) -> list[str]:
    normalized: list[str] = []
    seen = set()
    for t in raw_tags or []:
      if not isinstance(t, str):
        continue
      tag = t.strip()
      if not tag or tag in seen:
        continue
      seen.add(tag)
      normalized.append(tag)
    return normalized

  def _chunks(items: list[str], size: int) -> list[list[str]]:
    if size <= 0:
      raise ValueError("chunk size must be positive")
    return [items[i:i + size] for i in range(0, len(items), size)]

  normalized_tags = _normalize_tags(tags)

  if not normalized_tags:
    return []

  states = [models.JokeState.PUBLISHED.value, models.JokeState.DAILY.value]
  docs_by_id: dict[str, dict] = {}

  # Firestore array-contains-any supports up to 10 values; partition and union.
  for chunk in _chunks(normalized_tags, 10):
    query = client.collection("jokes")
    query = query.where(filter=FieldFilter("state", "in", states))
    query = query.where(filter=FieldFilter("is_public", "==", True))
    query = query.where(
      filter=FieldFilter("tags", "array_contains_any", chunk))
    query = query.limit(100)

    for doc in query.stream():
      data = doc.to_dict() or {}
      docs_by_id[doc.id] = data

  sorted_docs_list = sorted(
    docs_by_id.items(),
    key=lambda item: item[1].get("num_saved_users_fraction", 0.0),
    reverse=True,
  )[:100]

  payload: list[dict[str, object]] = []
  for doc_id, data in sorted_docs_list:
    payload.append({
      "joke_id": doc_id,
      "setup": data.get("setup_text", ""),
      "punchline": data.get("punchline_text", ""),
      "setup_image_url": data.get("setup_image_url"),
      "punchline_image_url": data.get("punchline_image_url"),
    })
  return payload
