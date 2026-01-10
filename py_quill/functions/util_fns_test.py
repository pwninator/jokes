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
      ("j1", {
        "setup_text": "Why did the chicken cross?",
        "punchline_text": "Punch",
      }),
      ("j2", {
        "setup_text": "What's 2 + 2?",
        "punchline_text": "Punch 2",
        "setup_text_slug": "wrongslug",
      }),
      ("j3", {
        "setup_text": "Test setup",
        "punchline_text": "Punch 3",
        "setup_text_slug": "testsetup",
      }),
  ])

  db_mock = MagicMock()
  jokes_collection = MagicMock()
  jokes_collection.order_by.return_value = _build_query(docs)
  db_mock.collection.return_value = jokes_collection

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    with patch('functions.util_fns.firestore.update_punny_joke') as update_mock:
      html = util_fns.run_setup_text_slug_backfill(
        dry_run=True,
        limit=0,
        start_after="",
      )

  update_mock.assert_not_called()

  assert "Dry Run: True" in html
  assert "Jokes Missing Slug: 1" in html
  assert "Jokes with Incorrect Slug: 1" in html
  assert "Jokes Updated (or would update): 2" in html
  assert "Jokes Skipped (already correct): 1" in html


def test_backfill_writes_updates():
  docs = _build_docs([
      ("j1", {
        "setup_text": "Why did the chicken cross?",
        "punchline_text": "Punch",
      }),
      ("j2", {
        "setup_text": "What's 2 + 2?",
        "punchline_text": "Punch 2",
        "setup_text_slug": "wrongslug",
      }),
  ])

  db_mock = MagicMock()
  jokes_collection = MagicMock()
  jokes_collection.order_by.return_value = _build_query(docs)
  db_mock.collection.return_value = jokes_collection

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    with patch('functions.util_fns.firestore.update_punny_joke') as update_mock:
      html = util_fns.run_setup_text_slug_backfill(
        dry_run=False,
        limit=0,
        start_after="",
      )

  assert update_mock.call_count == 2
  # Verify j1 gets correct slug (missing)
  assert update_mock.call_args_list[0][0][0] == "j1"
  assert update_mock.call_args_list[0][0][1] == {
    "setup_text_slug": "whydidthechickencross"
  }
  # Verify j2 gets correct slug (incorrect)
  assert update_mock.call_args_list[1][0][0] == "j2"
  assert update_mock.call_args_list[1][0][1] == {"setup_text_slug": "whats22"}

  assert "Dry Run: False" in html
  assert "Jokes Missing Slug: 1" in html
  assert "Jokes with Incorrect Slug: 1" in html
  assert "Jokes Updated (or would update): 2" in html


def test_backfill_idempotent_skips_correct_slugs():
  docs = _build_docs([
      ("j1", {
        "setup_text": "Why did the chicken cross?",
        "punchline_text": "Punch",
        "setup_text_slug": "whydidthechickencross",
      }),
      ("j2", {
        "setup_text": "What's 2 + 2?",
        "punchline_text": "Punch 2",
        "setup_text_slug": "whats22",
      }),
  ])

  db_mock = MagicMock()
  jokes_collection = MagicMock()
  jokes_collection.order_by.return_value = _build_query(docs)
  db_mock.collection.return_value = jokes_collection

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    with patch('functions.util_fns.firestore.update_punny_joke') as update_mock:
      html = util_fns.run_setup_text_slug_backfill(
        dry_run=False,
        limit=0,
        start_after="",
      )

  update_mock.assert_not_called()

  assert "Jokes Missing Slug: 0" in html
  assert "Jokes with Incorrect Slug: 0" in html
  assert "Jokes Updated (or would update): 0" in html
  assert "Jokes Skipped (already correct): 2" in html


def test_backfill_handles_update_errors():
  docs = _build_docs([
      ("j1", {
        "setup_text": "Why did the chicken cross?",
        "punchline_text": "Punch",
      }),
      ("j2", {
        "setup_text": "What's 2 + 2?",
        "punchline_text": "Punch 2",
        "setup_text_slug": "wrongslug",
      }),
  ])

  db_mock = MagicMock()
  jokes_collection = MagicMock()
  jokes_collection.order_by.return_value = _build_query(docs)
  db_mock.collection.return_value = jokes_collection

  def _update_with_errors(joke_id, update_data):
    if joke_id == "j1":
      raise ValueError("boom")

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    with patch(
        'functions.util_fns.firestore.update_punny_joke',
        side_effect=_update_with_errors,
    ) as update_mock:
      html = util_fns.run_setup_text_slug_backfill(
        dry_run=False,
        limit=0,
        start_after="",
      )

  assert update_mock.call_count == 2
  assert "Errors (1)" in html
  assert "Joke j1: boom" in html
  assert "Jokes Updated (or would update): 1" in html


def test_backfill_skips_jokes_without_setup_text():
  docs = _build_docs([
      ("j1", {
        "setup_text": "",
        "punchline_text": "Punch",
      }),
      ("j2", {
        "punchline_text": "Punch 2",
      }),
  ])

  db_mock = MagicMock()
  jokes_collection = MagicMock()
  jokes_collection.order_by.return_value = _build_query(docs)
  db_mock.collection.return_value = jokes_collection

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    with patch('functions.util_fns.firestore.update_punny_joke') as update_mock:
      html = util_fns.run_setup_text_slug_backfill(
        dry_run=False,
        limit=0,
        start_after="",
      )

  update_mock.assert_not_called()
  assert "Jokes Updated (or would update): 0" in html


def test_backfill_handles_parse_errors():
  docs = _build_docs([
      ("j1", {
        "invalid": "data",
      }),
      ("j2", {
        "setup_text": "Why did the chicken cross?",
        "punchline_text": "Punch",
      }),
  ])

  db_mock = MagicMock()
  jokes_collection = MagicMock()
  jokes_collection.order_by.return_value = _build_query(docs)
  db_mock.collection.return_value = jokes_collection

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    with patch('functions.util_fns.firestore.update_punny_joke') as update_mock:
      html = util_fns.run_setup_text_slug_backfill(
        dry_run=False,
        limit=0,
        start_after="",
      )

  # j2 should still be processed
  assert update_mock.call_count == 1
  assert "Errors (1)" in html
  assert "Parse error" in html
