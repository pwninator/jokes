"""Tests for Firestore migrations in util_fns.py."""

from unittest.mock import MagicMock, patch, call

from functions import util_fns


def _build_docs(doc_pairs: list[tuple[str, dict]]):
  docs = []
  for doc_id, data in doc_pairs:
    doc = MagicMock()
    doc.id = doc_id
    doc.to_dict.return_value = data
    docs.append(doc)
  return docs


def _build_query(docs: list[MagicMock]):
  query = MagicMock()
  query.order_by.return_value = query
  query.start_after.return_value = query
  query.limit.return_value = query
  query.stream.return_value = docs
  return query


def test_sync_dry_run_does_not_write():
  # Book 1 has Joke 1 (missing book_id), Joke 2 (correct book_id)
  books = _build_docs([
      ("b1", {"jokes": ["j1", "j2"]}),
  ])

  # Jokes
  j1 = MagicMock()
  j1.id = "j1"
  j1.exists = True
  j1.to_dict.return_value = {} # Missing book_id

  j2 = MagicMock()
  j2.id = "j2"
  j2.exists = True
  j2.to_dict.return_value = {"book_id": "b1"} # Correct

  db_mock = MagicMock()
  books_collection = MagicMock()
  books_collection.order_by.return_value = _build_query(books)

  db_mock.collection.side_effect = lambda name: books_collection if name == 'joke_books' else MagicMock()

  # Mock get_all to return our jokes
  # Note: logic calls get_all with references.
  db_mock.get_all.return_value = [j1, j2]

  batch = MagicMock()
  db_mock.batch.return_value = batch

  with patch('functions.util_fns.db', return_value=db_mock):
    html = util_fns.run_joke_book_id_sync(
      dry_run=True,
      limit=0,
      start_after="",
    )

  batch.commit.assert_not_called()

  assert "Dry Run: True" in html
  assert "Jokes Updated (or would update): 1" in html # j1 would be updated
  assert "Jokes Already Correct: 1" in html # j2 is correct


def test_sync_writes_updates():
  # Book 1 has Joke 1 (wrong book_id)
  books = _build_docs([
      ("b1", {"jokes": ["j1"]}),
  ])

  j1 = MagicMock()
  j1.id = "j1"
  j1.exists = True
  j1.to_dict.return_value = {"book_id": "b2"} # Wrong
  j1.reference = MagicMock()

  db_mock = MagicMock()
  books_collection = MagicMock()
  books_collection.order_by.return_value = _build_query(books)
  db_mock.collection.side_effect = lambda name: books_collection if name == 'joke_books' else MagicMock()
  db_mock.get_all.return_value = [j1]

  batch = MagicMock()
  db_mock.batch.return_value = batch

  with patch('functions.util_fns.db', return_value=db_mock):
    html = util_fns.run_joke_book_id_sync(
      dry_run=False,
      limit=0,
      start_after="",
    )

  batch.update.assert_called_with(j1.reference, {'book_id': 'b1'})
  batch.commit.assert_called_once()

  assert "Dry Run: False" in html
  assert "Jokes Updated (or would update): 1" in html
  assert "Discrepancies (1)" in html
  assert "Joke j1 has book_id=b2" in html


def test_sync_handles_missing_jokes():
  books = _build_docs([
      ("b1", {"jokes": ["j1"]}),
  ])

  j1 = MagicMock()
  j1.id = "j1"
  j1.exists = False # Missing

  db_mock = MagicMock()
  books_collection = MagicMock()
  books_collection.order_by.return_value = _build_query(books)
  db_mock.collection.side_effect = lambda name: books_collection if name == 'joke_books' else MagicMock()
  db_mock.get_all.return_value = [j1]

  with patch('functions.util_fns.db', return_value=db_mock):
    html = util_fns.run_joke_book_id_sync(
      dry_run=False,
      limit=0,
      start_after="",
    )

  assert "Missing Joke Docs: 1" in html
  assert "Book b1 references missing joke j1" in html
