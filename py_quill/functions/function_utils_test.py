"""Tests for function_utils parameter helpers."""

import pytest

from functions import function_utils


class FakeArgs:

  def __init__(self, data: dict[str, object] | None = None) -> None:
    self._data = data or {}

  def get(self, key: str, default=None):  # pragma: no cover - simple helper
    return self._data.get(key, default)

  def __contains__(self, key: str) -> bool:  # pragma: no cover - simple helper
    return key in self._data


class FakeRequest:

  def __init__(self,
               *,
               json_data: dict | None = None,
               args: dict[str, object] | None = None,
               headers: dict[str, str] | None = None) -> None:
    self._json_data = json_data
    self.args = FakeArgs(args)
    self.is_json = json_data is not None
    self.headers = headers or {}

  def get_json(self):
    return self._json_data


def _json_request(data: dict | None = None) -> FakeRequest:
  return FakeRequest(json_data={'data': data or {}})


def _query_request(args: dict[str, object] | None = None) -> FakeRequest:
  return FakeRequest(args=args)


def test_get_param_returns_value_from_json_request():
  req = _json_request({'foo': 'bar'})

  assert function_utils.get_param(req, 'foo') == 'bar'


def test_get_param_raises_when_required_missing_json():
  req = _json_request()

  with pytest.raises(ValueError, match="Missing required parameter 'foo'"):
    function_utils.get_param(req, 'foo', required=True)


def test_get_param_raises_when_required_missing_query():
  req = _query_request()

  with pytest.raises(ValueError, match="Missing required parameter 'foo'"):
    function_utils.get_param(req, 'foo', required=True)


def test_get_param_returns_default_when_optional_missing():
  req = _query_request()

  assert function_utils.get_param(req, 'foo', default='fallback') == 'fallback'


def test_get_bool_param_returns_default_when_required_missing():
  req = _query_request()

  # When required=True but default is provided, return default instead of raising
  assert function_utils.get_bool_param(req, 'flag', required=True) is False


def test_get_bool_param_parses_true_strings():
  req = _query_request({'flag': 'true'})

  assert function_utils.get_bool_param(req, 'flag') is True


def test_get_int_param_returns_default_when_required_missing():
  req = _json_request()

  # When required=True but default is provided, return default instead of raising
  assert function_utils.get_int_param(req, 'count', required=True) == 0


def test_get_float_param_returns_default_when_required_missing():
  req = _query_request()

  # When required=True but default is provided, return default instead of raising
  assert function_utils.get_float_param(req, 'ratio', required=True) == 0.0


def test_get_user_id_uses_session_cookie_when_authorization_missing(
    monkeypatch):
  monkeypatch.setattr(function_utils.auth,
                      "verify_session_cookie",
                      lambda cookie, check_revoked=True: {"uid": "cookie-uid"})

  req = FakeRequest(headers={"Cookie": "__session=fake_session_cookie"})

  assert function_utils.get_user_id(
    req, allow_unauthenticated=False) == "cookie-uid"


def test_get_user_id_prefers_authorization_header(monkeypatch):

  def fake_verify_id_token(token):
    assert token == "id-token-123"
    return {"uid": "bearer-uid"}

  monkeypatch.setattr(function_utils.auth, "verify_id_token",
                      fake_verify_id_token)
  monkeypatch.setattr(function_utils.auth,
                      "verify_session_cookie",
                      lambda cookie, check_revoked=True: {"uid": "cookie-uid"})

  req = FakeRequest(headers={"Authorization": "Bearer id-token-123"})

  assert function_utils.get_user_id(
    req, allow_unauthenticated=False) == "bearer-uid"


def test_get_user_id_require_admin_for_bearer_token(monkeypatch):
  def fake_verify_id_token(token):
    assert token == "id-token-123"
    return {"uid": "bearer-uid", "role": "admin"}

  monkeypatch.setattr(function_utils.auth, "verify_id_token",
                      fake_verify_id_token)

  req = FakeRequest(headers={"Authorization": "Bearer id-token-123"})

  assert function_utils.get_user_id(req, require_admin=True) == "bearer-uid"


def test_get_user_id_require_admin_rejects_non_admin_token(monkeypatch):
  def fake_verify_id_token(token):
    assert token == "id-token-123"
    return {"uid": "bearer-uid", "role": "user"}

  monkeypatch.setattr(function_utils.auth, "verify_id_token",
                      fake_verify_id_token)

  req = FakeRequest(headers={"Authorization": "Bearer id-token-123"})

  with pytest.raises(function_utils.AuthError):
    function_utils.get_user_id(req, require_admin=True)


def test_get_user_id_require_admin_with_session_cookie(monkeypatch):
  monkeypatch.setattr(function_utils.auth, "verify_session_cookie",
                      lambda cookie, check_revoked=True: {
                        "uid": "cookie-uid",
                        "role": "admin"
                      })

  req = FakeRequest(headers={"Cookie": "__session=fake_session_cookie"})

  assert function_utils.get_user_id(req, require_admin=True) == "cookie-uid"
