"""Tests for Cloud Function entry point glue in web_fns.

Route behavior is covered by tests colocated with the Flask modules under
`py_quill/web/`.
"""

from __future__ import annotations

from unittest import mock

import flask
from firebase_functions import https_fn
from functions import web_fns
from web.app import app as web_app


def test_web_fns_exports_flask_app():
  assert isinstance(web_fns.app, flask.Flask)
  assert web_fns.app is web_app


def test_web_redirects_invalid_host():
  req = mock.Mock(spec=https_fn.Request)
  req.host = 'bad-host.run.app'
  # full_path includes query string behavior
  req.full_path = '/joke/123?q=funny'

  resp = web_fns.web(req)

  assert resp.status_code == 301
  assert resp.headers['Location'] == 'https://snickerdoodlejokes.com/joke/123?q=funny'


def test_web_redirects_www_subdomain():
  req = mock.Mock(spec=https_fn.Request)
  req.host = 'www.snickerdoodlejokes.com'
  # werkzeug full_path behavior: includes '?' if query is empty/missing?
  # Actually we are mocking it, so we define the expected behavior.
  # The real request.full_path will return /? if query is empty.
  req.full_path = '/?'

  resp = web_fns.web(req)

  assert resp.status_code == 301
  assert resp.headers['Location'] == 'https://snickerdoodlejokes.com/?'


def test_web_allows_canonical_domain():
  req = mock.Mock(spec=https_fn.Request)
  req.host = 'snickerdoodlejokes.com'
  req.environ = {}

  with mock.patch('functions.web_fns.app') as mock_app:
    mock_ctx = mock.Mock()
    mock_ctx.__enter__ = mock.Mock()
    mock_ctx.__exit__ = mock.Mock()
    mock_app.request_context.return_value = mock_ctx

    mock_response = mock.Mock(spec=https_fn.Response)
    mock_app.full_dispatch_request.return_value = mock_response

    resp = web_fns.web(req)

    assert resp is mock_response
    mock_app.request_context.assert_called_once_with({})
    mock_app.full_dispatch_request.assert_called_once()


def test_web_allows_localhost():
  req = mock.Mock(spec=https_fn.Request)
  req.host = 'localhost:8080'
  req.environ = {}

  with mock.patch('functions.web_fns.app') as mock_app:
    mock_ctx = mock.Mock()
    mock_ctx.__enter__ = mock.Mock()
    mock_ctx.__exit__ = mock.Mock()
    mock_app.request_context.return_value = mock_ctx

    web_fns.web(req)

    mock_app.full_dispatch_request.assert_called_once()


def test_web_allows_loopback_ip():
  req = mock.Mock(spec=https_fn.Request)
  req.host = '127.0.0.1:5000'
  req.environ = {}

  with mock.patch('functions.web_fns.app') as mock_app:
    mock_ctx = mock.Mock()
    mock_ctx.__enter__ = mock.Mock()
    mock_ctx.__exit__ = mock.Mock()
    mock_app.request_context.return_value = mock_ctx

    web_fns.web(req)

    mock_app.full_dispatch_request.assert_called_once()
