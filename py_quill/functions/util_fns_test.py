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
    doc.reference = MagicMock()
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
      ("u1", {
        "email": "one@example.com",
      }),
      ("u2", {
        "email": "two@example.com",
      }),
      ("u3", {
        "email": "three@example.com",
        "mailerlite_subscriber_id": None,
      }),
  ])

  db_mock = MagicMock()
  users_collection = MagicMock()
  users_collection.order_by.return_value = _build_query(docs)
  db_mock.collection.return_value = users_collection

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    html = util_fns.run_mailerlite_subscriber_id_backfill(
      dry_run=True,
      limit=0,
      start_after="",
    )

  for doc in docs:
    doc.reference.update.assert_not_called()

  assert "Dry Run: True" in html
  assert "Users Missing Field: 2" in html
  assert "Users Updated (or would update): 2" in html
  assert "Users Skipped (already set): 1" in html


def test_backfill_writes_updates():
  docs = _build_docs([
      ("u1", {
        "email": "one@example.com",
      }),
      ("u2", {
        "email": "two@example.com",
      }),
  ])

  db_mock = MagicMock()
  users_collection = MagicMock()
  users_collection.order_by.return_value = _build_query(docs)
  db_mock.collection.return_value = users_collection

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    html = util_fns.run_mailerlite_subscriber_id_backfill(
      dry_run=False,
      limit=0,
      start_after="",
    )

  assert docs[0].reference.update.call_count == 1
  assert docs[0].reference.update.call_args_list[0][0][0] == {
    "mailerlite_subscriber_id": None
  }
  assert docs[1].reference.update.call_count == 1

  assert "Dry Run: False" in html
  assert "Users Missing Field: 2" in html
  assert "Users Updated (or would update): 2" in html


def test_backfill_idempotent_skips_existing_fields():
  docs = _build_docs([
      ("u1", {
        "email": "one@example.com",
        "mailerlite_subscriber_id": None,
      }),
      ("u2", {
        "email": "two@example.com",
        "mailerlite_subscriber_id": "sub_123",
      }),
  ])

  db_mock = MagicMock()
  users_collection = MagicMock()
  users_collection.order_by.return_value = _build_query(docs)
  db_mock.collection.return_value = users_collection

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    html = util_fns.run_mailerlite_subscriber_id_backfill(
      dry_run=False,
      limit=0,
      start_after="",
    )

  for doc in docs:
    doc.reference.update.assert_not_called()

  assert "Users Missing Field: 0" in html
  assert "Users Updated (or would update): 0" in html
  assert "Users Skipped (already set): 2" in html


def test_backfill_handles_update_errors():
  docs = _build_docs([
      ("u1", {
        "email": "one@example.com",
      }),
      ("u2", {
        "email": "two@example.com",
      }),
  ])

  docs[0].reference.update.side_effect = ValueError("boom")

  db_mock = MagicMock()
  users_collection = MagicMock()
  users_collection.order_by.return_value = _build_query(docs)
  db_mock.collection.return_value = users_collection

  with patch('functions.util_fns.firestore.db', return_value=db_mock):
    html = util_fns.run_mailerlite_subscriber_id_backfill(
      dry_run=False,
      limit=0,
      start_after="",
    )

  assert "Errors (1)" in html
  assert "User u1: boom" in html
  assert "Users Updated (or would update): 1" in html
