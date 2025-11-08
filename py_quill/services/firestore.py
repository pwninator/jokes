"""Firestore operations."""

import datetime
import pprint
from typing import Any, Collection

from common import models, utils
from firebase_admin import firestore, firestore_async
from firebase_functions import logger
from google.cloud.firestore import (SERVER_TIMESTAMP, DocumentReference,
                                    FieldFilter, Query, Transaction,
                                    transactional)

_db = None  # pylint: disable=invalid-name
_async_db = None  # pylint: disable=invalid-name


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


def get_all_punny_jokes() -> list[models.PunnyJoke]:
  """Get all punny jokes from the 'jokes' collection."""
  docs = db().collection('jokes').stream()
  jokes = [
    models.PunnyJoke.from_firestore_dict(doc.to_dict(), key=doc.id)
    for doc in docs if doc.exists and doc.to_dict() is not None
  ]
  return jokes


def get_all_joke_categories() -> list[models.JokeCategory]:
  """Get all joke categories from the 'joke_categories' collection."""
  docs = db().collection('joke_categories').stream()
  categories: list[models.JokeCategory] = []
  for doc in docs:
    if not doc.exists:
      continue
    data = doc.to_dict() or {}
    display_name = data.get('display_name', '')
    joke_description_query = data.get('joke_description_query', '')
    image_description = data.get('image_description')
    if not display_name and not joke_description_query:
      continue
    categories.append(
      models.JokeCategory(
        display_name=display_name,
        joke_description_query=joke_description_query,
        image_description=image_description,
      ))
  return categories


async def upsert_joke_categories(
    categories: list[models.JokeCategory]) -> None:
  """Upsert joke categories into the 'joke_categories' collection.

  Args:
      categories: List of JokeCategory objects to upsert.
  """
  if not categories:
    return

  # Validate and prepare payloads first to avoid partial writes
  prepared: list[tuple[str, dict[str, str]]] = []
  for category in categories:
    display_name = (category.display_name or '').strip()
    description_query = (category.joke_description_query or '').strip()
    image_description = (category.image_description or '').strip()
    if not display_name or not description_query:
      raise ValueError(
        "JokeCategory must have non-empty display_name and joke_description_query"
      )
    payload: dict[str, str] = {
      'display_name': display_name,
      'joke_description_query': description_query,
    }
    if image_description:
      payload['image_description'] = image_description
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


def get_daily_joke(
  schedule_name: str,
  joke_date: datetime.date,
) -> models.PunnyJoke | None:
  """Backward-compatible wrapper returning a single joke for `joke_date`."""
  jokes = get_daily_jokes(schedule_name, joke_date, 1)
  return jokes[0] if jokes else None


def upsert_punny_joke(punny_joke: models.PunnyJoke) -> models.PunnyJoke | None:
  """Create or update a punny joke."""

  # If joke has a key, try to update existing, otherwise create new
  if punny_joke.key:
    update_punny_joke(punny_joke.key, punny_joke.to_dict(include_key=False))
    return punny_joke

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
  joke_data['creation_time'] = SERVER_TIMESTAMP
  joke_data['last_modification_time'] = SERVER_TIMESTAMP

  joke_ref.set(joke_data)

  punny_joke.key = custom_id
  return punny_joke


def update_punny_joke(joke_id: str, update_data: dict[str, Any]) -> None:
  """Update a punny joke with the given ID and data."""
  joke_ref = db().collection('jokes').document(joke_id)
  if not joke_ref.get().exists:
    raise ValueError(f"Joke {joke_id} not found in Firestore")
  state_value = update_data.get('state')
  resolved_state: models.JokeState | None = None
  if isinstance(state_value, models.JokeState):
    resolved_state = state_value
    update_data['state'] = state_value.value
  elif isinstance(state_value, str):
    try:
      resolved_state = models.JokeState(state_value)
    except ValueError:
      resolved_state = None
  if resolved_state is not None:
    update_data['is_public'] = resolved_state == models.JokeState.PUBLISHED
  update_data['last_modification_time'] = SERVER_TIMESTAMP
  joke_ref.update(update_data)


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


def _upsert_joke_user_usage_logic(transaction: Transaction,
                                  user_id: str,
                                  now_utc: datetime.datetime | None = None,
                                  *,
                                  client_num_days_used: int | None = None,
                                  client_num_saved: int | None = None,
                                  client_num_viewed: int | None = None,
                                  client_num_navigated: int | None = None,
                                  client_num_shared: int | None = None,
                                  requested_review: bool | None = None) -> int:
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
  client_updates: dict[str, int | bool] = {}
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
  if requested_review is not None:
    client_updates['requested_review'] = requested_review

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
    requested_review: bool | None = None) -> int:
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
    requested_review=requested_review,
  )


def upsert_joke_user_usage(user_id: str,
                           now_utc: datetime.datetime | None = None,
                           *,
                           client_num_days_used: int | None = None,
                           client_num_saved: int | None = None,
                           client_num_viewed: int | None = None,
                           client_num_navigated: int | None = None,
                           client_num_shared: int | None = None,
                           requested_review: bool | None = None) -> int:
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
    requested_review=requested_review,
  )
