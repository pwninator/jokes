"""Admin social routes."""

from __future__ import annotations

import flask
from common import models, utils
from functions import auth_helpers
from services import firestore
from web.routes import web_bp


@web_bp.route('/admin/social')
@auth_helpers.require_admin
def admin_social():
  """Render the social feed with public daily + published jokes."""
  social_posts = firestore.get_joke_social_posts()

  return flask.render_template(
    'admin/social.html',
    site_name='Snickerdoodle',
    joke_creation_url=utils.joke_creation_big_url(),
    social_posts=social_posts,
    post_type_options=[t.value for t in models.JokeSocialPostType],
    default_post_type=models.JokeSocialPostType.JOKE_REEL_VIDEO.value,
  )
