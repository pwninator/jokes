"""Admin route for tuning audio prompts."""

from __future__ import annotations

import flask

from functions import auth_helpers, joke_creation_fns
from web.routes import web_bp
from web.routes.admin import joke_feed_utils


@web_bp.route('/admin/audio-prompt-tuner', methods=['GET'])
@auth_helpers.require_admin
def admin_audio_prompt_tuner():
  """Render the audio prompt tuner (generation happens client-side)."""
  return flask.render_template(
    'admin/audio_prompt_tuner.html',
    site_name='Snickerdoodle',
    joke_creation_url=joke_feed_utils.joke_creation_url(),
    joke_audio_op=joke_creation_fns.JokeCreationOp.JOKE_AUDIO.value,
    error_message=None,
  )
