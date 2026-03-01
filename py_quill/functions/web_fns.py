"""Web Cloud Function entry point.

This module intentionally stays small and delegates the Flask app/routes to
`py_quill/web/` so web traffic handling doesn't grow into a monolith.
"""

from __future__ import annotations

import flask
from firebase_functions import https_fn, options
from web.app import app


@https_fn.on_request(
  memory=options.MemoryOption.GB_2,
  min_instances=1,
  timeout_sec=30,
)
def web(req: flask.Request) -> flask.Response:
  """A web page that displays jokes based on a search query."""
  with app.request_context(req.environ):
    return app.full_dispatch_request()
