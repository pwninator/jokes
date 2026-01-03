"""Tests for Cloud Function entry point glue in web_fns.

Route behavior is covered by tests colocated with the Flask modules under
`py_quill/web/`.
"""

from __future__ import annotations

import flask

from functions import web_fns
from web.app import app as web_app


def test_web_fns_exports_flask_app():
  assert isinstance(web_fns.app, flask.Flask)
  assert web_fns.app is web_app


