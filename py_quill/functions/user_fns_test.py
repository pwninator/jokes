"""Tests for user_fns."""

from unittest.mock import Mock

from functions import user_fns


class FakeUser:
  """Simple stand-in for AuthUserRecord."""

  def __init__(self,
               uid: str = "user-1",
               email: str | None = "user@example.com"):
    self.uid = uid
    self.email = email


class FakeEvent:
  """Simple stand-in for AuthBlockingEvent."""

  def __init__(self, user: FakeUser):
    self.data = user


def test_on_user_signin_initializes_user_doc(monkeypatch):
  created_calls = []

  def fake_initialize(user_id, email):
    created_calls.append((user_id, email))
    return True

  mock_logger = Mock()
  monkeypatch.setattr(user_fns.firestore_service, 'initialize_user_document',
                      fake_initialize)
  monkeypatch.setattr(user_fns, 'logger', mock_logger)

  result = user_fns.on_user_signin.__wrapped__(FakeEvent(FakeUser()))

  assert result is None
  assert created_calls == [("user-1", "user@example.com")]
  mock_logger.info.assert_called_once()


def test_on_user_signin_skips_when_no_email(monkeypatch):
  called = False

  def fake_initialize(_user_id, _email):
    nonlocal called
    called = True
    return True

  mock_logger = Mock()
  monkeypatch.setattr(user_fns.firestore_service, 'initialize_user_document',
                      fake_initialize)
  monkeypatch.setattr(user_fns, 'logger', mock_logger)

  result = user_fns.on_user_signin.__wrapped__(FakeEvent(FakeUser(email=None)))

  assert result is None
  assert called is False
  mock_logger.info.assert_not_called()


def test_on_user_signin_logs_exception(monkeypatch):
  def fake_initialize(_user_id, _email):
    raise RuntimeError("boom")

  mock_logger = Mock()
  monkeypatch.setattr(user_fns.firestore_service, 'initialize_user_document',
                      fake_initialize)
  monkeypatch.setattr(user_fns, 'logger', mock_logger)

  result = user_fns.on_user_signin.__wrapped__(FakeEvent(FakeUser()))

  assert result is None
  mock_logger.error.assert_called_once()
