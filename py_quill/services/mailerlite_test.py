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

  assert resp.id == "sub_1"
  assert captured["email"] == "test@example.com"
  assert captured["kwargs"]["fields"]["country"] == "DE"
  assert captured["kwargs"]["groups"] == [174]


def test_get_subscriber_by_email_returns_none_on_404():

  class _FakeResponse:

    def __init__(self, status_code, payload):
      self.status_code = status_code
      self._payload = payload

    def json(self):
      return self._payload

  class _FakeApiClient:

    def __init__(self):
      self.calls = []

    def request(self, method, path):
      self.calls.append((method, path))
      return _FakeResponse(404, {"message": "Not found"})

  class _FakeSubscribers:
    base_api_url = "api/subscribers"

    def __init__(self):
      self.api_client = _FakeApiClient()

  class _FakeClient:

    def __init__(self):
      self.subscribers = _FakeSubscribers()

  client = mailerlite.MailerLiteClient(client=_FakeClient(), api_key="test")
  resp = client.get_subscriber_by_email(email="Test@Example.com")
  assert resp is None


def test_get_subscriber_by_email_returns_payload():

  class _FakeResponse:

    def __init__(self, status_code, payload):
      self.status_code = status_code
      self._payload = payload

    def json(self):
      return self._payload

  class _FakeApiClient:

    def request(self, method, path):
      return _FakeResponse(200, {"data": {"id": "sub_1"}})

  class _FakeSubscribers:
    base_api_url = "api/subscribers"

    def __init__(self):
      self.api_client = _FakeApiClient()

  class _FakeClient:

    def __init__(self):
      self.subscribers = _FakeSubscribers()

  client = mailerlite.MailerLiteClient(client=_FakeClient(), api_key="test")
  resp = client.get_subscriber_by_email(email="test@example.com")
  assert resp.id == "sub_1"


