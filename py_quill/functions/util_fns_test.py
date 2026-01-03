"""Tests for Firestore migrations in util_fns.py."""

from unittest.mock import MagicMock, patch

from functions import util_fns


def _build_docs(doc_pairs: list[tuple[str, dict]]):
  docs = []
  for doc_id, data in doc_pairs:
    doc = MagicMock()
    doc.id = doc_id
    doc.exists = True
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


def test_backfill_dry_run_does_not_write():
  docs = _build_docs([
      ("j1", {"setup_text": "Setup", "punchline_text": "Punch", "tags": []}),
      ("j2", {
        "setup_text": "Setup 2",
        "punchline_text": "Punch 2",
        "tags": ["tagged"]
      }),
  ])

  db_mock = MagicMock()
  jokes_collection = MagicMock()
  jokes_collection.order_by.return_value = _build_query(docs)
  db_mock.collection.return_value = jokes_collection

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    with patch('functions.util_fns.joke_operations.generate_joke_metadata') as generate_mock:
      with patch('functions.util_fns.firestore.upsert_punny_joke') as upsert_mock:
        html = util_fns.run_joke_metadata_backfill(
          dry_run=True,
          limit=0,
          start_after="",
        )

  generate_mock.assert_not_called()
  upsert_mock.assert_not_called()

  assert "Dry Run: True" in html
  assert "Jokes Missing Tags: 1" in html
  assert "Jokes Updated (or would update): 1" in html
  assert "Jokes Skipped (already tagged): 1" in html


def test_backfill_writes_updates():
  docs = _build_docs([
      ("j1", {"setup_text": "Setup", "punchline_text": "Punch", "tags": []}),
      ("j2", {
        "setup_text": "Setup 2",
        "punchline_text": "Punch 2",
        "tags": ["tagged"]
      }),
  ])

  db_mock = MagicMock()
  jokes_collection = MagicMock()
  jokes_collection.order_by.return_value = _build_query(docs)
  db_mock.collection.return_value = jokes_collection

  def _generate_with_tags(joke):
    joke.tags = ["new-tag"]
    return joke

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    with patch(
        'functions.util_fns.joke_operations.generate_joke_metadata',
        side_effect=_generate_with_tags,
    ) as generate_mock:
      with patch('functions.util_fns.firestore.upsert_punny_joke') as upsert_mock:
        html = util_fns.run_joke_metadata_backfill(
          dry_run=False,
          limit=0,
          start_after="",
        )

  generate_mock.assert_called_once()
  upsert_mock.assert_called_once()
  assert upsert_mock.call_args.kwargs["operation"] == "BACKFILL_METADATA"

  assert "Dry Run: False" in html
  assert "Jokes Missing Tags: 1" in html
  assert "Jokes Updated (or would update): 1" in html
  assert "Jokes Skipped (already tagged): 1" in html


def test_backfill_handles_generation_errors():
  docs = _build_docs([
      ("j1", {"setup_text": "Setup", "punchline_text": "Punch", "tags": []}),
      ("j2", {"setup_text": "Setup 2", "punchline_text": "Punch 2", "tags": []}),
  ])

  db_mock = MagicMock()
  jokes_collection = MagicMock()
  jokes_collection.order_by.return_value = _build_query(docs)
  db_mock.collection.return_value = jokes_collection

  def _generate_with_errors(joke):
    if joke.key == "j1":
      raise ValueError("boom")
    joke.tags = ["ok"]
    return joke

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    with patch(
        'functions.util_fns.joke_operations.generate_joke_metadata',
        side_effect=_generate_with_errors,
    ):
      with patch('functions.util_fns.firestore.upsert_punny_joke') as upsert_mock:
        html = util_fns.run_joke_metadata_backfill(
          dry_run=False,
          limit=0,
          start_after="",
        )

  upsert_mock.assert_called_once()
  assert "Errors (1)" in html
  assert "Joke j1: boom" in html
