"""Admin route for generating joke audio + video."""

from __future__ import annotations

import flask

from common import joke_operations
from functions import auth_helpers, joke_creation_fns
from services import audio_client, gen_audio
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

  elevenlabs_voices = gen_audio.Voice.voices_for_model(
    gen_audio.VoiceModel.ELEVENLABS)
  elevenlabs_voice_options = [{
    "value": voice.name,
    "label": f"{voice.name.replace('ELEVENLABS_', '').replace('_', ' ').title()} ({voice.gender.value})",
  } for voice in elevenlabs_voices]

  audio_model_options = [{
    "value": model.value,
    "label": model.name.replace("_", " ").title(),
  } for model in audio_client.AudioModel]

  default_dialog_turns = []
  for turn in joke_operations.DEFAULT_JOKE_AUDIO_TURNS_TEMPLATE[:3]:
    default_dialog_turns.append({
      "voice": str(getattr(turn.voice, "name", turn.voice)),
      "script": turn.script,
      "pause_sec_after": turn.pause_sec_after,
    })
  return flask.render_template(
    'admin/joke_media_generator.html',
    site_name='Snickerdoodle',
    joke_creation_url=joke_feed_utils.joke_creation_url(),
    joke_audio_op=joke_creation_fns.JokeCreationOp.JOKE_AUDIO.value,
    joke_video_op=joke_creation_fns.JokeCreationOp.JOKE_VIDEO.value,
    default_dialog_turns=default_dialog_turns,
    audio_models=audio_model_options,
    default_audio_model=audio_client.AudioModel.GEMINI_2_5_FLASH_TTS.value,
    gemini_voices=gemini_voice_options,
    elevenlabs_voices=elevenlabs_voice_options,
    error_message=None,
  )
