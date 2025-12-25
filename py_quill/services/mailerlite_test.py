"""Tests for mailerlite service wrapper."""

from services import mailerlite


def test_create_subscriber_builds_expected_payload():
  captured = {}

  class _FakeSubscribers:

    def create(self, email, **kwargs):
      captured["email"] = email
      captured["kwargs"] = kwargs
      return {"data": {"id": "sub_1"}}

  class _FakeClient:

    def __init__(self):
      self.subscribers = _FakeSubscribers()

  client = mailerlite.MailerLiteClient(client=_FakeClient(), api_key="test")
  resp = client.create_subscriber(
    email="Test@Example.com",
    country_code="DE",
    group_id="174",
  )

  assert resp["data"]["id"] == "sub_1"
  assert captured["email"] == "test@example.com"
  assert captured["kwargs"]["fields"]["country"] == "DE"
  assert captured["kwargs"]["groups"] == [174]


def test_add_to_group_uses_add_subscribers_when_available():
  captured = {}

  class _FakeSubscribers:

    def update(self, email, **kwargs):
      captured["email"] = email
      captured["kwargs"] = kwargs
      return {"ok": True}

  class _FakeClient:

    def __init__(self):
      self.subscribers = _FakeSubscribers()

  client = mailerlite.MailerLiteClient(client=_FakeClient(), api_key="test")
  resp = client.add_to_group(subscriber_id="test@example.com", group_id="174")
  assert resp["ok"] is True
  assert captured["email"] == "test@example.com"
  assert captured["kwargs"]["groups"] == [174]


