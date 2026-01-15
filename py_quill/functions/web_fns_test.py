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


def _assert_dispatch_for_host(hostname: str) -> None:
  req = mock.Mock(spec=https_fn.Request)
  req.host = hostname
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


def test_web_dispatches_for_canonical_domain():
  _assert_dispatch_for_host('snickerdoodlejokes.com')


def test_web_dispatches_for_localhost():
  _assert_dispatch_for_host('localhost:8080')


def test_web_dispatches_for_loopback_ip():
  _assert_dispatch_for_host('127.0.0.1:5000')


def test_web_dispatches_for_www_subdomain():
  _assert_dispatch_for_host('www.snickerdoodlejokes.com')


def test_web_dispatches_for_function_host():
  _assert_dispatch_for_host('bad-host.run.app')
