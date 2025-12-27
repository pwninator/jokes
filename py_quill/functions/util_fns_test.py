"""Tests for Firestore migrations in util_fns.py."""

from unittest.mock import MagicMock, patch

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


def test_cleanup_dry_run_does_not_write_but_reports_stats():
  jokes_query = _build_jokes_query(
    _build_docs([
      ("j1", {"zzz_joke_text_embedding": "anything"}),
      ("j2", {}),
    ]))

  db_mock = MagicMock()
  jokes_collection = MagicMock()
  jokes_collection.order_by.return_value = jokes_query

  joke_doc = MagicMock()
  jokes_collection.document.return_value = joke_doc

  db_mock.collection.return_value = jokes_collection

  with patch('functions.util_fns.db', return_value=db_mock):
    html = util_fns.run_jokes_embedding_cleanup(
      dry_run=True,
      limit=0,
      start_after="",
    )

  joke_doc.update.assert_not_called()
  assert "Dry Run: True" in html
  assert "Processed" in html
  assert "Would delete" in html
  assert "Deleted" in html
  assert "Skipped (field not present)" in html


def test_cleanup_writes_only_when_field_present():
  jokes_query = _build_jokes_query(
    _build_docs([
      ("j1", {"zzz_joke_text_embedding": None}),
      ("j2", {}),
    ]))

  db_mock = MagicMock()
  jokes_collection = MagicMock()
  jokes_collection.order_by.return_value = jokes_query

  joke_doc = MagicMock()
  jokes_collection.document.return_value = joke_doc

  db_mock.collection.return_value = jokes_collection

  with patch('functions.util_fns.db', return_value=db_mock):
    html = util_fns.run_jokes_embedding_cleanup(
      dry_run=False,
      limit=0,
      start_after="",
    )

  jokes_collection.document.assert_called_once_with("j1")
  joke_doc.update.assert_called_once()
  assert "Status: Success" in html
