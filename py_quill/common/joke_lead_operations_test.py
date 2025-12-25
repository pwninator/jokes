"""Tests for joke_lead_operations."""

import datetime
from unittest.mock import Mock

from common import joke_lead_operations


def test_create_lead_creates_subscriber_then_writes_firestore(monkeypatch):
  calls: dict[str, object] = {}

  class _FakeMailerLiteClient:

    def create_subscriber(self, **kwargs):
      calls["create_subscriber"] = kwargs
      return {"data": {"id": "sub_123"}}

  fake_doc = Mock()
  fake_collection = Mock()
  fake_collection.document.return_value = fake_doc
  fake_db = Mock()
  fake_db.collection.return_value = fake_collection

  monkeypatch.setattr(joke_lead_operations.mailerlite, "MailerLiteClient",
                      lambda: _FakeMailerLiteClient())
  monkeypatch.setattr(joke_lead_operations.firestore, "db", lambda: fake_db)

  lead = joke_lead_operations.create_lead(
    email="Test@Example.com",
    country_code="DE",
    signup_source="lunchbox",
    group_id=joke_lead_operations.GROUP_SNICKERDOODLE_CLUB,
  )

  assert calls["create_subscriber"]["email"] == "test@example.com"
  assert calls["create_subscriber"]["country_code"] == "DE"
  assert calls["create_subscriber"][
    "group_id"] == joke_lead_operations.GROUP_SNICKERDOODLE_CLUB

  fake_db.collection.assert_called_once_with("joke_leads")
  fake_collection.document.assert_called_once_with("test@example.com")
  fake_doc.set.assert_called_once()
  stored_doc = fake_doc.set.call_args.args[0]
  assert stored_doc["email"] == "test@example.com"
  assert stored_doc["country_code"] == "DE"
  assert stored_doc["signup_source"] == "lunchbox"
  assert stored_doc["signup_date"]
  assert stored_doc["mailerlite_subscriber_id"] == "sub_123"
  assert isinstance(stored_doc["timestamp"], datetime.datetime)

  assert lead["email"] == "test@example.com"


def test_create_lead_does_not_write_firestore_when_mailerlite_fails(
    monkeypatch):

  class _FakeMailerLiteClient:

    def create_subscriber(self, **_kwargs):
      raise RuntimeError("MailerLite error")

  fake_db = Mock()
  monkeypatch.setattr(joke_lead_operations.mailerlite, "MailerLiteClient",
                      lambda: _FakeMailerLiteClient())
  monkeypatch.setattr(joke_lead_operations.firestore, "db", lambda: fake_db)

  try:
    joke_lead_operations.create_lead(
      email="test@example.com",
      country_code="US",
      signup_source="lunchbox",
    )
    assert False, "Expected exception"
  except RuntimeError:
    pass

  fake_db.collection.assert_not_called()
