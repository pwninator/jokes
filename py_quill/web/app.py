"""Flask app initialization for Snickerdoodle web layer."""

from __future__ import annotations

import datetime
import os
from typing import Any

import flask
# Import route modules for side-effects (route registration on `web_bp`).
# These are intentionally unused imports, but must remain at module scope so
# all routes exist when Cloud Functions dispatches the request.
# pyright: reportUnusedImport=false
# pyright: reportUnusedFunction=false
import web.routes.about as _about
import web.routes.admin.admin_books as _admin_books
import web.routes.admin.admin_jokes as _admin_jokes
import web.routes.admin.categories as _admin_categories
import web.routes.admin.character_animator as _character_animator
import web.routes.admin.dashboard as _admin_dashboard
import web.routes.admin.image_prompt_tuner as _admin_image_prompt_tuner
import web.routes.admin.joke_media_generator as _admin_joke_media_generator
import web.routes.admin.joke_picker_api as _admin_joke_picker_api
import web.routes.admin.printable_notes as _admin_printable_notes
import web.routes.admin.rhyming_words as _admin_rhyming_words
import web.routes.admin.social as _admin_social
import web.routes.auth as _auth
import web.routes.books as _books
import web.routes.jokes as _jokes
import web.routes.lunchbox as _lunchbox
import web.routes.notes as _notes
import web.routes.public as _public
import web.routes.redirects as _redirects
from common import utils
from firebase_functions import logger
from web.routes import web_bp

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')
_STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')


def _load_css(filename: str) -> str:
  """Load a CSS file from the static directory."""
  css_path = os.path.join(_STATIC_DIR, 'css', filename)
  try:
    with open(css_path, 'r', encoding='utf-8') as css_file:
      return css_file.read()
  except FileNotFoundError:
    logger.error(f'Stylesheet missing at {css_path}')
    return ''


_BASE_CSS = _load_css('base.css')
_SITE_CSS = _BASE_CSS + _load_css('style.css')

app = flask.Flask(__name__,
                  template_folder=_TEMPLATES_DIR,
                  static_folder=_STATIC_DIR)


@app.before_request
def _strip_trailing_slash() -> flask.Response | None:
  path = flask.request.path
  if path != "/" and path.endswith("/"):
    canonical_path = path.rstrip("/") or "/"
    query_string = flask.request.query_string
    if query_string:
      canonical_path = (f"{canonical_path}?"
                        f"{query_string.decode('utf-8', 'ignore')}")
    return flask.redirect(canonical_path,
                          code=308)  # pyright: ignore[reportReturnType]
  return None


@app.template_filter('format_image_url')
def _format_image_url_filter(image_url: str, **kwargs: dict[str, Any]) -> str:
  """Jinja filter for formatting image CDN URLs."""
  return utils.format_image_url(
    image_url, **kwargs)  # pyright: ignore[reportArgumentType]


@app.context_processor
def _inject_template_globals() -> dict[str, Any]:
  """Inject shared template variables such as compiled CSS and CF origin."""
  return {
    'site_css': _SITE_CSS,
    'functions_origin': utils.cloud_functions_base_url(),
    'format_image_url': utils.format_image_url,
    'now_utc': datetime.datetime.now(datetime.timezone.utc),
  }


# Register blueprint at import time so Cloud Functions can dispatch.
app.register_blueprint(web_bp)
