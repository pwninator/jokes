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
  # Enforce strict Host header check for SEO canonicalization.
  host = req.headers.get("Host", "").lower()

  # Allow custom domain and localhost (for dev).
  if (host != "snickerdoodlejokes.com" and
      not host.startswith("localhost") and
      not host.startswith("127.0.0.1")):
    target_url = f"https://snickerdoodlejokes.com{req.full_path}"
    return https_fn.Response(
        status=301,
        headers={"Location": target_url}
    )

  with app.request_context(req.environ):
    return app.full_dispatch_request()
