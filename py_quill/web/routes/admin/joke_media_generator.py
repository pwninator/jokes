"""Admin route for generating joke audio + video."""

from __future__ import annotations

import flask

from common import joke_operations
from functions import auth_helpers, joke_creation_fns
from services import gen_audio
from web.routes import web_bp
from web.routes.admin import joke_feed_utils


@web_bp.route('/admin/joke-media-generator', methods=['GET'])
@auth_helpers.require_admin
def admin_joke_media_generator():
  """Render the joke media generator (generation happens client-side)."""
  gemini_voices = gen_audio.Voice.voices_for_model(gen_audio.VoiceModel.GEMINI)
  gemini_voice_options = [{
    "value": voice.name,
    "label": f"{voice.voice_name} ({voice.gender.value})",
  } for voice in gemini_voices]
  return flask.render_template(
    'admin/joke_media_generator.html',
    site_name='Snickerdoodle',
    joke_creation_url=joke_feed_utils.joke_creation_url(),
    joke_audio_op=joke_creation_fns.JokeCreationOp.JOKE_AUDIO.value,
    joke_video_op=joke_creation_fns.JokeCreationOp.JOKE_VIDEO.value,
    default_script_template=joke_operations.DEFAULT_JOKE_AUDIO_SCRIPT_TEMPLATE,
    default_speaker1_name=joke_operations.DEFAULT_JOKE_AUDIO_SPEAKER_1_NAME,
    default_speaker1_voice=joke_operations.DEFAULT_JOKE_AUDIO_SPEAKER_1_VOICE.name,
    default_speaker2_name=joke_operations.DEFAULT_JOKE_AUDIO_SPEAKER_2_NAME,
    default_speaker2_voice=joke_operations.DEFAULT_JOKE_AUDIO_SPEAKER_2_VOICE.name,
    gemini_voices=gemini_voice_options,
    error_message=None,
  )
