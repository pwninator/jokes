"""Flask app initialization for Snickerdoodle web layer."""

from __future__ import annotations

import os

import flask
# Import route modules for side-effects (route registration on `web_bp`).
# These are intentionally unused imports, but must remain at module scope so
# all routes exist when Cloud Functions dispatches the request.
import web.routes.about as _about  # noqa: E402,F401
import web.routes.admin.books as _admin_books  # noqa: E402,F401
import web.routes.admin.categories as _admin_categories  # noqa: E402,F401
import web.routes.admin.dashboard as _admin_dashboard  # noqa: E402,F401
import web.routes.auth as _auth  # noqa: E402,F401
import web.routes.lunchbox as _lunchbox  # noqa: E402,F401
import web.routes.notes as _notes  # noqa: E402,F401
import web.routes.public as _public  # noqa: E402,F401
import web.routes.redirects as _redirects  # noqa: E402,F401
from common import utils
from common import amazon_redirect
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


@app.context_processor
def _inject_template_globals() -> dict[str, str]:
  """Inject shared template variables such as compiled CSS and CF origin."""
  # Resolve navigation book link
  country_code = _redirects.resolve_request_country_code(flask.request)
  redirect_config = amazon_redirect.AMAZON_REDIRECTS['book-animal-jokes']
  amazon_url, _, _ = redirect_config.resolve_target_url(
    requested_country_code=country_code,
    source='web_book_page',
  )

  return {
    'site_css': _SITE_CSS,
    'functions_origin': utils.cloud_functions_base_url(),
    'nav_amazon_book_url': amazon_url,
  }


# Register blueprint at import time so Cloud Functions can dispatch.
app.register_blueprint(web_bp)
