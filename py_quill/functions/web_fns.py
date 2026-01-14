"""Web Cloud Function entry point.

This module intentionally stays small and delegates the Flask app/routes to
`py_quill/web/` so web traffic handling doesn't grow into a monolith.
"""

from __future__ import annotations

from firebase_functions import https_fn, options

from web.app import app


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  min_instances=1,
  timeout_sec=30,
)
def web(req: https_fn.Request) -> https_fn.Response:
  """A web page that displays jokes based on a search query."""
  # SEO Canonicalization: Enforce strict Host header check.
  # We want to redirect traffic from the raw Cloud Function URL (*.run.app)
  # and the 'www' subdomain to the naked domain.
  # We allow localhost and 127.0.0.1 for local development.
  hostname = req.host.split(':')[0]
  allowed_hosts = {'snickerdoodlejokes.com', 'localhost', '127.0.0.1'}

  if hostname not in allowed_hosts:
    target_url = f'https://snickerdoodlejokes.com{req.path}'
    if req.query_string:
      target_url += f'?{req.query_string.decode("utf-8")}'

    return https_fn.Response(
      status=301,
      headers={'Location': target_url}
    )

  with app.request_context(req.environ):
    return app.full_dispatch_request()
