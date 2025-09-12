"""Firestore operations."""

import datetime
import pprint
from typing import Any, Collection

from common import models, utils
from firebase_admin import firestore
from firebase_functions import logger
from google.cloud.firestore import (SERVER_TIMESTAMP, DocumentReference,
                                    FieldFilter, Query, Transaction,
                                    transactional)

_db = None  # pylint: disable=invalid-name


def db() -> firestore.client:
  """Get the firestore client."""
  global _db  # pylint: disable=global-statement
  if _db is None:
    _db = firestore.client()
  return _db


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


def list_joke_schedules() -> list[str]:
  """List all joke schedule IDs from Firestore.

  Returns:
      A list of document IDs from the `joke_schedules` collection.
  """
  docs = db().collection('joke_schedules').get()
  return [doc.id for doc in docs]


def get_daily_joke(
  schedule_name: str,
  joke_date: datetime.date,
) -> models.PunnyJoke | None:
  """Get the punny joke for a given date.
  
  Args:
      schedule_name: The name of the joke schedule to use
      joke_date: The date to get the joke for

  Returns:
      A PunnyJoke object for the given date, or None if not found
  """
  # Get today's date
  day_of_month = f"{joke_date.day:02d}"
  month_year = f"{joke_date.year}_{joke_date.month:02d}"

  # Construct the document ID for this schedule and month
  batch_doc_id = f"{schedule_name}_{month_year}"

  # Get the joke schedule batch document
  batch_ref = db().collection('joke_schedule_batches').document(batch_doc_id)
  batch_doc = batch_ref.get()

  if not batch_doc.exists:
    logger.error(f"No joke schedule batch found for {batch_doc_id}")
    return None

  batch_data = batch_doc.to_dict()
  jokes_dict = batch_data.get('jokes', {})

  # Get today's joke data
  todays_joke_data = jokes_dict.get(day_of_month)
  if not todays_joke_data:
    logger.error(f"No joke scheduled for day {day_of_month} in {batch_doc_id}")
    return None

  key = todays_joke_data.get('joke_id')
  setup_text = todays_joke_data.get('setup')
  punchline_text = todays_joke_data.get('punchline')
  setup_image_url = todays_joke_data.get('setup_image_url')
  punchline_image_url = todays_joke_data.get('punchline_image_url')

  if (not key or not setup_text or not punchline_text or not setup_image_url
      or not punchline_image_url):
    logger.error(f"Missing data in todays_joke_data: {todays_joke_data}")
    return None

  return models.PunnyJoke(
    key=key,
    setup_text=setup_text,
    punchline_text=punchline_text,
    setup_image_url=setup_image_url,
    punchline_image_url=punchline_image_url,
  )


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
  update_data['last_modification_time'] = SERVER_TIMESTAMP
  joke_ref.update(update_data)


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
