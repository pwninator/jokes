"""Tests for Firestore migrations in util_fns.py."""

from unittest.mock import MagicMock, patch

from google.cloud.firestore_v1.vector import Vector

from functions import util_fns


def _build_docs(doc_pairs: list[tuple[str, dict]]):
  docs = []
  for doc_id, data in doc_pairs:
    doc = MagicMock()
    doc.id = doc_id
    doc.to_dict.return_value = data
    docs.append(doc)
  return docs


def _build_jokes_query(docs: list[MagicMock]):
  query = MagicMock()
  query.order_by.return_value = query
  query.start_after.return_value = query
  query.limit.return_value = query
  query.stream.return_value = docs
  return query


def test_run_joke_search_backfill_dry_run_does_not_write():
  jokes_query = _build_jokes_query(
    _build_docs([
      (
        "j1",
        {
          "state": "PUBLISHED",
          "is_public": True,
          "zzz_joke_text_embedding": Vector([1.0, 2.0]),
        },
      ),
    ]))

  db_mock = MagicMock()
  jokes_collection = MagicMock()
  jokes_collection.order_by.return_value = jokes_query
  search_collection = MagicMock()
  db_mock.collection.side_effect = (lambda name: jokes_collection
                                    if name == 'jokes' else search_collection)

  with patch('functions.util_fns.db', return_value=db_mock):
    html = util_fns.run_joke_search_backfill(
      dry_run=True,
      limit=0,
      start_after="",
    )

  search_collection.document.assert_not_called()
  assert "Dry Run: True" in html
  assert "Processed" in html
  assert "Written" in html


def test_run_joke_search_backfill_writes_expected_payload():
  jokes_query = _build_jokes_query(
    _build_docs([
      (
        "j1",
        {
          "state": "PUBLISHED",
          "is_public": True,
          "public_timestamp": "ts",
          "num_saved_users_fraction": 0.5,
          "num_shared_users_fraction": 0.25,
          "popularity_score": 12.0,
          "zzz_joke_text_embedding": Vector([1.0, 2.0]),
        },
      ),
    ]))

  db_mock = MagicMock()
  jokes_collection = MagicMock()
  jokes_collection.order_by.return_value = jokes_query

  search_doc = MagicMock()
  search_collection = MagicMock()
  search_collection.document.return_value = search_doc

  db_mock.collection.side_effect = (lambda name: jokes_collection
                                    if name == 'jokes' else search_collection)

  with patch('functions.util_fns.db', return_value=db_mock):
    html = util_fns.run_joke_search_backfill(
      dry_run=False,
      limit=0,
      start_after="",
    )

  search_collection.document.assert_called_once_with("j1")
  search_doc.set.assert_called_once()
  payload = search_doc.set.call_args.args[0]
  assert isinstance(payload["text_embedding"], Vector)
  assert payload["state"] == "PUBLISHED"
  assert payload["is_public"] is True
  assert payload["public_timestamp"] == "ts"
  assert payload["num_saved_users_fraction"] == 0.5
  assert payload["num_shared_users_fraction"] == 0.25
  assert payload["popularity_score"] == 12.0
  assert "Status: Success" in html


def test_run_joke_search_backfill_skips_missing_embedding():
  jokes_query = _build_jokes_query(
    _build_docs([
      ("j_missing", {
        "state": "PUBLISHED",
        "is_public": True,
      }),
      ("j_good", {
        "state": "PUBLISHED",
        "is_public": True,
        "zzz_joke_text_embedding": Vector([1.0, 2.0]),
      }),
    ]))

  db_mock = MagicMock()
  jokes_collection = MagicMock()
  jokes_collection.order_by.return_value = jokes_query

  search_doc = MagicMock()
  search_collection = MagicMock()
  search_collection.document.return_value = search_doc

  db_mock.collection.side_effect = (lambda name: jokes_collection
                                    if name == 'jokes' else search_collection)

  with patch('functions.util_fns.db', return_value=db_mock):
    html = util_fns.run_joke_search_backfill(
      dry_run=False,
      limit=0,
      start_after="",
    )

  search_collection.document.assert_called_once_with("j_good")
  assert "Skipped (missing embedding)" in html
