"""Tests for joke_lead_operations."""

import datetime
from unittest.mock import Mock

from common import joke_lead_operations
from services import mailerlite


def test_create_lead_creates_subscriber_then_writes_firestore(monkeypatch):
  calls: dict[str, object] = {}

  class _FakeMailerLiteClient:

    def create_subscriber(self, **kwargs):
      calls["create_subscriber"] = kwargs
      return mailerlite.Subscriber(id="sub_123")

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


def test_ensure_users_subscribed_creates_missing_subscriber(monkeypatch):
  calls: dict[str, object] = {}

  class _FakeMailerLiteClient:

    def get_subscriber_by_email(self, *, email):
      calls["lookup_email"] = email
      return None

    def create_subscriber(self, **kwargs):
      calls["create_subscriber"] = kwargs
      return mailerlite.Subscriber(id="sub_456")

  monkeypatch.setattr(joke_lead_operations.mailerlite, "MailerLiteClient",
                      lambda: _FakeMailerLiteClient())
  user_doc = Mock()
  user_doc.exists = True
  user_doc.id = "user_1"
  user_doc.to_dict.return_value = {
    "email": "Test@Example.com",
    "mailerlite_subscriber_id": None,
  }

  updated = {}

  def _fake_update_user(user_id, subscriber_id):
    updated["user_id"] = user_id
    updated["subscriber_id"] = subscriber_id

  lead_calls = []

  def _fake_ensure_lead(**kwargs):
    lead_calls.append(kwargs)

  monkeypatch.setattr(
    joke_lead_operations.firestore,
    "get_users_missing_mailerlite_subscriber_id",
    lambda limit=None: [user_doc],
  )
  monkeypatch.setattr(joke_lead_operations.firestore,
                      "update_user_mailerlite_subscriber_id",
                      _fake_update_user)
  monkeypatch.setattr(joke_lead_operations.firestore, "ensure_joke_lead_doc",
                      _fake_ensure_lead)

  stats = joke_lead_operations.ensure_users_subscribed()

  assert calls["lookup_email"] == "test@example.com"
  assert calls["create_subscriber"]["email"] == "test@example.com"
  assert calls["create_subscriber"]["group_id"] == joke_lead_operations.GROUP_SNICKERDOODLE_CLUB

  assert updated["user_id"] == "user_1"
  assert updated["subscriber_id"] == "sub_456"

  assert stats["users_processed"] == 1
  assert stats["subscribers_created"] == 1
  assert stats["users_updated"] == 1

  assert len(lead_calls) == 1


def test_ensure_users_subscribed_uses_existing_subscriber(monkeypatch):
  calls: dict[str, object] = {}

  class _FakeMailerLiteClient:

    def get_subscriber_by_email(self, *, email):
      calls["lookup_email"] = email
      return mailerlite.Subscriber(id="sub_999", status="unsubscribed")

    def create_subscriber(self, **_kwargs):
      raise AssertionError("create_subscriber should not be called")

  monkeypatch.setattr(joke_lead_operations.mailerlite, "MailerLiteClient",
                      lambda: _FakeMailerLiteClient())
  user_doc = Mock()
  user_doc.exists = True
  user_doc.id = "user_2"
  user_doc.to_dict.return_value = {
    "email": "user@example.com",
    "mailerlite_subscriber_id": None,
  }

  updated = {}

  def _fake_update_user(user_id, subscriber_id):
    updated["user_id"] = user_id
    updated["subscriber_id"] = subscriber_id

  lead_calls = []

  def _fake_ensure_lead(**kwargs):
    lead_calls.append(kwargs)

  monkeypatch.setattr(
    joke_lead_operations.firestore,
    "get_users_missing_mailerlite_subscriber_id",
    lambda limit=None: [user_doc],
  )
  monkeypatch.setattr(joke_lead_operations.firestore,
                      "update_user_mailerlite_subscriber_id",
                      _fake_update_user)
  monkeypatch.setattr(joke_lead_operations.firestore, "ensure_joke_lead_doc",
                      _fake_ensure_lead)

  stats = joke_lead_operations.ensure_users_subscribed()

  assert calls["lookup_email"] == "user@example.com"
  assert updated["user_id"] == "user_2"
  assert updated["subscriber_id"] == "sub_999"
  assert stats["subscribers_found"] == 1
  assert stats["users_updated"] == 1
  assert len(lead_calls) == 1
