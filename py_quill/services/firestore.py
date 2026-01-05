"""Firestore operations."""

import datetime
import pprint
from typing import Any, Collection
from zoneinfo import ZoneInfo

from common import models, utils
from firebase_admin import firestore, firestore_async
from firebase_functions import logger
from google.cloud.firestore import (SERVER_TIMESTAMP, DocumentReference,
                                    FieldFilter, Query, Transaction,
                                    transactional)

_db = None  # pylint: disable=invalid-name
_async_db = None  # pylint: disable=invalid-name

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
}


def get_async_db() -> firestore_async.client:
  """Get the firestore async client."""
  global _async_db
  if _async_db is None:
    _async_db = firestore_async.client()
  return _async_db


def db() -> firestore.client:
  """Get the firestore client."""
  global _db  # pylint: disable=global-statement
  if _db is None:
    _db = firestore.client()
  return _db


def _prepare_jokes_query(states: list[models.JokeState] | None, *,
                         async_mode: bool):
  """Build a Firestore query for jokes filtered by the given states."""
  if not states:
    states = [models.JokeState.DAILY, models.JokeState.PUBLISHED]
  state_values = [s.value for s in states]
  client = get_async_db() if async_mode else db()
  return client.collection('jokes').where(
    filter=FieldFilter('state', 'in', state_values))


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


def upsert_joke_sheet(
  joke_ids: list[str],
  *,
  category_id: str | None = None,
) -> str:
  """Ensure a joke_sheets document exists for the given joke IDs.

  Creates a new document in the 'joke_sheets' collection with an auto-generated
  ID if one does not already exist for the given `joke_str`.

  The document contains fields:
    - joke_str: comma-separated list of joke IDs (sorted).
    - joke_ids: list of joke IDs (sorted).
    - category_id: optional category document id for the sheet.

  Returns:
    The Firestore document ID for the joke_sheets document.
  """
  if not joke_ids:
    raise ValueError("joke_ids is required")

  if category_id is not None:
    category_id = str(category_id).strip() or None

  normalized_ids = [str(jid).strip() for jid in joke_ids if str(jid).strip()]
  if not normalized_ids:
    raise ValueError("joke_ids is required")

  sorted_ids = sorted(normalized_ids)
  joke_str = ",".join(sorted_ids)
  payload = {
    'joke_str': joke_str,
    'joke_ids': sorted_ids,
  }
  if category_id is not None:
    payload["category_id"] = category_id

  collection_ref = db().collection('joke_sheets')
  existing = (collection_ref.where(
    filter=FieldFilter('joke_str', '==', joke_str)).limit(1).get())
  for doc in existing:
    if getattr(doc, 'exists', False):
      # Backfill new fields for older docs.
      doc_dict = doc.to_dict() if hasattr(doc, 'to_dict') else None
      if (not isinstance(doc_dict, dict)
          or doc_dict.get('joke_ids') != sorted_ids
          or (category_id is not None
              and doc_dict.get("category_id") != category_id)):
        doc_ref = getattr(doc, 'reference', None)
        if doc_ref is not None:
          doc_ref.set(payload, merge=True)
      return doc.id

  _, doc_ref = collection_ref.add(payload)
  return doc_ref.id


def get_joke_sheets_by_category(category_id: str) -> list[models.JokeSheet]:
  """Fetch all joke sheets associated with a category.

  Note: `category_id` is a single string field and may be overwritten if multiple
  categories share a sheet. This helper returns the current set of sheets whose
  `category_id` matches the provided category id.
  """
  category_id = (category_id or "").strip()
  if not category_id:
    return []

  docs = (db().collection("joke_sheets").where(
    filter=FieldFilter("category_id", "==", category_id)).stream())
  return [
    models.JokeSheet.from_firestore_dict(doc.to_dict(), key=doc.id)
    for doc in docs if doc.exists and doc.to_dict() is not None
  ]


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
) -> list[models.JokeCategory]:
  """Get all joke categories from the 'joke_categories' collection.

  Args:
    fetch_cached_jokes: When True, also fetch `category_jokes/cache` and populate
      `category.jokes` from the cached joke payload.
  """
  docs = db().collection('joke_categories').stream()
  categories: list[models.JokeCategory] = []
  for doc in docs:
    if not doc.exists:
      continue
    data = doc.to_dict() or {}
    category = models.JokeCategory.from_firestore_dict(data, key=doc.id)
    if (not category.display_name and not category.joke_description_query
        and not category.seasonal_name and not category.tags):
      continue

    if fetch_cached_jokes:
      category_ref = db().collection('joke_categories').document(doc.id)
      _populate_category_cached_jokes(category, category_ref)

    categories.append(category)
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
    joke = models.PunnyJoke(
      key=joke_data.get('joke_id'),
      setup_text=joke_data.get('setup', ''),
      punchline_text=joke_data.get('punchline', ''),
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
  search_distance: float | None = None,
  tags: list[str] | None = None,
  image_description: str | None = None,
) -> str:
  """Create a new joke category and return its document ID.

  Raises:
    ValueError: if required fields are missing or category already exists.
  """
  display_name = (display_name or '').strip()
  joke_description_query = (joke_description_query or '').strip()
  seasonal_name = (seasonal_name or '').strip()
  tags = list(tags) if isinstance(tags, list) else []
  image_description = (image_description or '').strip()
  state = (state or 'PROPOSED').strip()
  search_distance = float(
    search_distance) if search_distance is not None else None

  if not display_name:
    raise ValueError("display_name is required")

  normalized_tags: list[str] = []
  seen = set()
  for t in tags:
    if not isinstance(t, str):
      continue
    tag = t.strip()
    if not tag or tag in seen:
      continue
    seen.add(tag)
    normalized_tags.append(tag)

  if not joke_description_query and not seasonal_name and not normalized_tags:
    raise ValueError(
      "Provide at least one of joke_description_query, seasonal_name, or tags")

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
    search_distance=search_distance,
    tags=normalized_tags,
    state=state,
    image_description=image_description or None,
  )
  payload: dict[str, Any] = category.to_dict()

  ref.set(payload, merge=True)
  return category_id


def get_uncategorized_public_jokes(
  all_categories: list[models.JokeCategory], ) -> list[models.PunnyJoke]:
  """Get all public jokes not in any category cache."""
  categorized_ids: set[str] = set()
  for category in all_categories:
    for joke in category.jokes:
      if joke.key:
        categorized_ids.add(joke.key)

  query = db().collection('jokes').where(
    filter=FieldFilter('is_public', '==', True))
  docs = query.stream()

  results: list[models.PunnyJoke] = []
  for doc in docs:
    if not getattr(doc, 'exists', False):
      continue
    if doc.id in categorized_ids:
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
def _initialize_user_in_transaction(transaction: Transaction,
                                    user_id_internal: str,
                                    email: str | None = None) -> bool:
  """The actual logic to be executed within the transaction.

  Returns:
      bool: True if a new document was created, False otherwise.
  """
  user_ref = db().collection('users').document(user_id_internal)
  snapshot = user_ref.get(transaction=transaction)

  if snapshot.exists:
    logger.info(
      f"User document already exists for {user_id_internal}, skipping creation."
    )
    return False  # Indicate no creation happened

  # Data to set, include email if provided
  user_data = {
    'user_type': 'USER',
    'preferences': {},
    'num_sparks': 1000,
    'num_premium_sparks': 0,
    'onboarding_completed': False,
    'created_at': SERVER_TIMESTAMP,
    'last_modified_at': SERVER_TIMESTAMP,
  }
  if email:
    user_data['email'] = email

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
