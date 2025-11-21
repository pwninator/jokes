"""Tests for Firestore migrations in util_fns.py."""

from unittest.mock import MagicMock, patch

from google.cloud.firestore import DELETE_FIELD

from functions import util_fns

BOOK_ID = "20251115_064522__bbcourirwogb9x6wuqwa"
MONKEY_JOKE_ID = "a_monkey__what_kind_of_key_opens_a_banan"
HIP_HOP_JOKE_ID = "hip_hop__what_is_a_rabbit_s_favourite_s"
SHELLFIES_JOKE_ID = "shell_fies__what_kind_of_photos_do_turtles"
REMOVED_JOKE_ID = (
  "you_might_step_in_a_poodle__why_should_you_be_careful_when"
)


def _build_book_ref(*, exists: bool, jokes_data):
  book_ref = MagicMock()
  book_doc = MagicMock()
  book_doc.exists = exists
  if exists:
    book_doc.to_dict.return_value = {'jokes': jokes_data}
  book_ref.get.return_value = book_doc
  return book_ref


def test_run_joke_book_migration_returns_error_when_book_missing():
  db_mock = MagicMock()
  book_collection = MagicMock()
  book_ref = _build_book_ref(exists=False, jokes_data=[])
  book_collection.document.return_value = book_ref

  db_mock.collection.side_effect = lambda name: book_collection if name == 'joke_books' else MagicMock()

  with patch('functions.util_fns.db', return_value=db_mock):
    html = util_fns.run_joke_book_migration(dry_run=False)

  assert "Status: Failed" in html
  assert f"Joke book {BOOK_ID} not found" in html
  book_ref.update.assert_not_called()


def test_run_joke_book_migration_fails_when_jokes_field_not_list():
  db_mock = MagicMock()
  book_collection = MagicMock()
  book_ref = _build_book_ref(exists=True, jokes_data='not-a-list')
  book_collection.document.return_value = book_ref

  db_mock.collection.side_effect = lambda name: book_collection if name == 'joke_books' else MagicMock()

  with patch('functions.util_fns.db', return_value=db_mock):
    html = util_fns.run_joke_book_migration(dry_run=False)

  assert "Status: Failed" in html
  assert "Jokes field is not a list" in html
  book_ref.update.assert_not_called()


def test_run_joke_book_migration_dry_run_skips_firestore_updates():
  db_mock = MagicMock()
  book_collection = MagicMock()
  original_jokes = [
      MONKEY_JOKE_ID,
      "duplicate_joke",
      "duplicate_joke",
      REMOVED_JOKE_ID,
  ]
  book_ref = _build_book_ref(exists=True, jokes_data=original_jokes)
  book_collection.document.return_value = book_ref

  def _collection_side_effect(name):
    if name == 'joke_books':
      return book_collection
    raise AssertionError(f"Unexpected collection requested: {name}")

  db_mock.collection.side_effect = _collection_side_effect

  with patch('functions.util_fns.db', return_value=db_mock):
    html = util_fns.run_joke_book_migration(dry_run=True)

  book_ref.update.assert_not_called()
  assert "Dry Run: True" in html
  assert "Cleared Book Page URLs" in html


def test_run_joke_book_migration_updates_book_and_clears_metadata():
  db_mock = MagicMock()
  book_collection = MagicMock()
  jokes_collection = MagicMock()

  original_jokes = [
      "existing_joke",
      "duplicate_joke",
      "another_joke",
      REMOVED_JOKE_ID,
      "duplicate_joke",
  ]
  book_ref = _build_book_ref(exists=True, jokes_data=original_jokes)
  book_collection.document.return_value = book_ref

  metadata_refs: dict[str, MagicMock] = {}

  def _build_metadata_chain(joke_id: str):
    metadata_doc = metadata_refs.get(joke_id)
    if metadata_doc is None:
      metadata_doc = MagicMock()
      metadata_refs[joke_id] = metadata_doc

    metadata_collection = MagicMock()
    metadata_collection.document.return_value = metadata_doc

    joke_doc = MagicMock()
    joke_doc.collection.return_value = metadata_collection
    return joke_doc

  jokes_collection.document.side_effect = _build_metadata_chain

  def _collection_side_effect(name):
    if name == 'joke_books':
      return book_collection
    if name == 'jokes':
      return jokes_collection
    raise AssertionError(f"Unexpected collection requested: {name}")

  db_mock.collection.side_effect = _collection_side_effect

  with patch('functions.util_fns.db', return_value=db_mock):
    html = util_fns.run_joke_book_migration(dry_run=False)

  book_ref.update.assert_called_once()
  update_payload = book_ref.update.call_args.args[0]
  updated_jokes = update_payload['jokes']

  expected_ids = {
      MONKEY_JOKE_ID,
      "existing_joke",
      "duplicate_joke",
      "another_joke",
      HIP_HOP_JOKE_ID,
      SHELLFIES_JOKE_ID,
  }

  assert updated_jokes[0] == MONKEY_JOKE_ID
  assert set(updated_jokes) == expected_ids
  assert REMOVED_JOKE_ID not in updated_jokes

  assert set(metadata_refs) == set(updated_jokes)
  for metadata_doc in metadata_refs.values():
    metadata_doc.update.assert_called_once_with({
        'book_page_setup_image_url': DELETE_FIELD,
        'book_page_punchline_image_url': DELETE_FIELD,
    })

  assert "Status: Success" in html
  assert "Cleared Book Page URLs (" in html
