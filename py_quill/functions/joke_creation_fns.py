"""Cloud functions for orchestrating joke creation workflows."""

from __future__ import annotations

import json
import traceback
from enum import Enum
from typing import cast

import flask
from agents import constants
from common import (image_generation, joke_notes_sheet_operations,
                    joke_operations, models, posable_character_sequence, utils)
from firebase_functions import https_fn, logger, options
from functions import social_fns
from functions.function_utils import (AuthError, error_response,
                                      get_bool_param, get_list_param,
                                      get_param, get_str_param, get_user_id,
                                      handle_cors_preflight,
                                      handle_health_check, success_response)
from services import audio_client, audio_voices, cloud_storage, firestore


class JokeCreationOp(str, Enum):
  """Supported joke creation operations."""
  PROC = "proc"
  JOKE_IMAGE = "joke_image"
  JOKE_AUDIO = "joke_audio"
  JOKE_VIDEO = "joke_video"
  SOCIAL = "social"
  PRINTABLE_NOTE = "printable_note"
  ANIMATION = "animation"
  ANIMATION_LAUGH = "animation_laugh"
  CHARACTER = "character"


@https_fn.on_request(
  memory=options.MemoryOption.GB_2,
  min_instances=1,
  timeout_sec=600,
)
def joke_creation_process(req: flask.Request) -> flask.Response:
  """Handle joke creation scenarios for text entry, suggestions, and images."""
  try:
    if response := _handle_admin_request(req):
      return response

    op_value = get_param(req, "op", JokeCreationOp.PROC.value)
    try:
      op = JokeCreationOp(op_value)
    except ValueError:
      return error_response(f'Unsupported op: {op_value}',
                            error_type='unsupported_operation',
                            req=req,
                            status=400)
    if op == JokeCreationOp.PROC:
      return _run_joke_creation_proc(req)
    if op == JokeCreationOp.JOKE_IMAGE:
      return _run_joke_image_tuner(req)
    if op == JokeCreationOp.JOKE_AUDIO:
      return _run_joke_audio_tuner(req)
    if op == JokeCreationOp.JOKE_VIDEO:
      return _run_joke_video_tuner(req)
    if op == JokeCreationOp.SOCIAL:
      return social_fns.run_social_post_creation_process(req)
    if op == JokeCreationOp.PRINTABLE_NOTE:
      return _run_printable_sheet_proc(req)
    if op == JokeCreationOp.ANIMATION:
      return _run_character_animation_op(req)
    if op == JokeCreationOp.ANIMATION_LAUGH:
      return _run_character_animation_laugh(req)
    if op == JokeCreationOp.CHARACTER:
      return _run_character_def_op(req)

    return error_response(f'Unsupported op: {op_value}',
                          error_type='unsupported_operation',
                          req=req,
                          status=400)

  except joke_operations.SafetyCheckError as exc:
    error_string = f"Safety check failed: {str(exc)}"
    logger.error(error_string)
    return error_response(error_string, error_type='safety_failed', req=req)
  except Exception as exc:  # pylint: disable=broad-except
    error_string = (f"Error handling joke_creation_process: {str(exc)}\n"
                    f"{traceback.format_exc()}")
    logger.error(error_string)
    return error_response(error_string,
                          error_type='internal_error',
                          req=req,
                          status=500)


def _select_image_client(image_quality: str):
  if utils.is_emulator():
    return image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY["low"]
  if image_quality in image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY:
    return image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY[image_quality]
  raise ValueError(f"Invalid image quality: {image_quality}")


def _filter_reference_images(selected_urls: list[str],
                             allowed_urls: list[str]) -> list[str]:
  allowed = set(allowed_urls)
  return [url for url in selected_urls if url in allowed]


def _parse_dialog_turn_templates(
  script_template: list[dict[str, object]] | None,
) -> list[audio_client.DialogTurn] | None:
  """Parse dialog turn templates from request payload."""
  if script_template is None:
    return None

  turns: list[audio_client.DialogTurn] = []
  for idx, item in enumerate(script_template):
    voice_raw = item.get("voice")
    script_raw = item.get("script")
    pause_after_raw = item.get("pause_sec_after")

    voice_str = str(voice_raw or "").strip()
    script_str = str(script_raw or "").strip()
    pause_after_str = str(
      pause_after_raw).strip() if pause_after_raw is not None else ""

    if not voice_str and not script_str and not pause_after_str:
      continue

    if not voice_str:
      raise ValueError(f"Dialog turn {idx + 1} voice is required")
    if not script_str:
      raise ValueError(f"Dialog turn {idx + 1} script is required")

    parsed_voice: audio_voices.Voice
    try:
      parsed_voice = audio_voices.Voice.from_identifier(voice_str)
    except ValueError as exc:
      raise ValueError(
        f"Dialog turn {idx + 1} voice must be a valid voice identifier"
      ) from exc

    pause_after: float | None = None
    if pause_after_raw is not None and pause_after_str:
      try:
        pause_after = float(pause_after_str)
      except ValueError as exc:
        raise ValueError(
          f"Dialog turn {idx + 1} pause_sec_after must be a number") from exc
      if pause_after < 0:
        raise ValueError(f"Dialog turn {idx + 1} pause_sec_after must be >= 0")

    turns.append(
      audio_client.DialogTurn(
        voice=parsed_voice,
        script=script_str,
        pause_sec_after=pause_after,
      ))

  if not turns:
    return None
  return turns


def _parse_tuner_audio_options(
  req: flask.Request,
) -> tuple[list[audio_client.DialogTurn] | None, audio_client.AudioModel
           | None, bool]:
  """Parse shared audio-related options for audio/video tuner endpoints."""
  raw_script_template = get_param(req, 'script_template')
  script_template_input: list[dict[str, object]] | None = None
  if raw_script_template is not None:
    if not isinstance(raw_script_template, list):
      raise ValueError("script_template must be a list")
    list_script_template: list[object] = cast(list[object],
                                              raw_script_template)
    for idx, item in enumerate(list_script_template):
      if not isinstance(item, dict):
        raise ValueError(f"Dialog turn {idx + 1} must be an object")
    script_template_input = cast(list[dict[str, object]], list_script_template)

  script_template = _parse_dialog_turn_templates(script_template_input)
  audio_model_value = (get_param(req, 'audio_model') or "").strip()
  audio_model = None
  if audio_model_value:
    try:
      audio_model = audio_client.AudioModel(audio_model_value)
    except ValueError as exc:
      raise ValueError(f"Invalid audio_model: {audio_model_value}") from exc
  allow_partial = get_bool_param(req, "allow_partial", False)
  return script_template, audio_model, allow_partial


def _handle_admin_request(req: flask.Request) -> flask.Response | None:
  if response := handle_cors_preflight(req):
    return response
  if response := handle_health_check(req):
    return response

  if req.method not in ['GET', 'POST']:
    return error_response(f'Method not allowed: {req.method}',
                          req=req,
                          status=405)

  try:
    if not utils.is_emulator():
      _ = get_user_id(req, allow_unauthenticated=False, require_admin=True)
  except AuthError:
    return error_response('Unauthorized', status=403, req=req)

  return None


def _run_joke_image_tuner(req: flask.Request) -> flask.Response:
  """Generate setup/punchline images for prompt tuning."""

  setup_prompt = get_str_param(req, 'setup_image_prompt')
  punchline_prompt = get_str_param(req, 'punchline_image_prompt')
  if not setup_prompt or not punchline_prompt:
    return error_response(
      'setup_image_prompt and punchline_image_prompt are required',
      error_type='invalid_request',
      status=400,
      req=req,
    )

  image_quality = get_str_param(req, 'image_quality',
                                'medium_mini') or 'medium_mini'
  selected_setup_reference_images = _filter_reference_images(
    get_list_param(req, 'setup_reference_images'),
    constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS,
  )
  selected_punchline_reference_images = _filter_reference_images(
    get_list_param(req, 'punchline_reference_images'),
    constants.STYLE_REFERENCE_SIMPLE_IMAGE_URLS,
  )
  include_setup_image_reference = get_bool_param(req, 'include_setup_image',
                                                 False)

  try:
    client = _select_image_client(image_quality)
    setup_image = client.generate_image(
      setup_prompt,
      selected_setup_reference_images or None,
      save_to_firestore=False,
    )
    if not setup_image or not setup_image.url:
      raise ValueError(f"Generated setup image has no URL: {setup_image}")

    previous_image_reference = None
    custom_temp_data = setup_image.custom_temp_data
    if custom_temp_data and custom_temp_data.get("image_generation_call_id"):
      previous_image_reference = custom_temp_data["image_generation_call_id"]
    elif setup_image.gcs_uri:
      previous_image_reference = setup_image.gcs_uri

    punchline_reference_images = selected_punchline_reference_images[:]
    if include_setup_image_reference and previous_image_reference:
      punchline_reference_images.append(previous_image_reference)

    punchline_image = client.generate_image(
      punchline_prompt,
      punchline_reference_images or None,
      save_to_firestore=False,
    )
    if not punchline_image or not punchline_image.url:
      raise ValueError(
        f"Generated punchline image has no URL: {punchline_image}")

    return success_response(
      {
        "setup_image_url": setup_image.url,
        "punchline_image_url": punchline_image.url,
      },
      req=req,
    )
  except ValueError as exc:
    return error_response(str(exc),
                          error_type='invalid_request',
                          status=400,
                          req=req)
  except Exception as exc:  # pylint: disable=broad-except
    error_string = (f"Error handling joke image tuning: {str(exc)}\n"
                    f"{traceback.format_exc()}")
    logger.error(error_string)
    return error_response(error_string, error_type='internal_error', req=req)


def _run_joke_audio_tuner(req: flask.Request) -> flask.Response:
  """Generate joke audio clips (setup/response/punchline) for tuning."""
  if req.method != 'POST':
    return error_response(f'Method not allowed: {req.method}',
                          req=req,
                          status=405)

  joke_id = (get_param(req, 'joke_id') or '').strip()
  if not joke_id:
    return error_response(
      'joke_id is required',
      error_type='invalid_request',
      status=400,
      req=req,
    )

  joke = firestore.get_punny_joke(joke_id)
  if not joke:
    return error_response(
      f'Joke not found: {joke_id}',
      error_type='not_found',
      status=404,
      req=req,
    )

  try:
    script_template, audio_model, allow_partial = _parse_tuner_audio_options(
      req)
    lip_sync = joke_operations.get_joke_lip_sync_media(
      joke,
      temp_output=True,
      script_template=script_template,
      audio_model=audio_model,
      allow_partial=allow_partial,
    )

    payload: dict[str, object] = {
      "dialog_audio_gcs_uri": lip_sync.dialog_gcs_uri,
      "intro_audio_gcs_uri": lip_sync.intro_audio_gcs_uri,
      "setup_audio_gcs_uri": lip_sync.setup_audio_gcs_uri,
      "response_audio_gcs_uri": lip_sync.response_audio_gcs_uri,
      "punchline_audio_gcs_uri": lip_sync.punchline_audio_gcs_uri,
      "audio_generation_metadata": lip_sync.audio_generation_metadata.as_dict
      if lip_sync.audio_generation_metadata else {},
    }
    if allow_partial and lip_sync.partial_error:
      payload["error"] = lip_sync.partial_error
      payload["error_stage"] = "audio_split"

    return success_response(
      payload,
      req=req,
    )
  except ValueError as exc:
    return error_response(str(exc),
                          error_type='invalid_request',
                          status=400,
                          req=req)
  except Exception as exc:  # pylint: disable=broad-except
    error_string = (f"Error handling joke audio tuning: {str(exc)}\n"
                    f"{traceback.format_exc()}")
    logger.error(error_string)
    return error_response(error_string, error_type='internal_error', req=req)


def _run_joke_video_tuner(req: flask.Request) -> flask.Response:
  """Generate joke video for prompt tuning."""
  if req.method != 'POST':
    return error_response(f'Method not allowed: {req.method}',
                          req=req,
                          status=405)

  joke_id = (get_param(req, 'joke_id') or '').strip()
  if not joke_id:
    return error_response(
      'joke_id is required',
      error_type='invalid_request',
      status=400,
      req=req,
    )

  joke = firestore.get_punny_joke(joke_id)
  if not joke:
    return error_response(
      f'Joke not found: {joke_id}',
      error_type='not_found',
      status=404,
      req=req,
    )

  try:
    script_template, audio_model, allow_partial = _parse_tuner_audio_options(
      req)
    result = joke_operations.generate_joke_video(
      joke,
      temp_output=True,
      script_template=script_template,
      audio_model=audio_model,
      allow_partial=allow_partial,
    )

    return success_response(
      {
        "video_gcs_uri": result.video_gcs_uri,
        "dialog_audio_gcs_uri": result.dialog_audio_gcs_uri,
        "intro_audio_gcs_uri": result.intro_audio_gcs_uri,
        "setup_audio_gcs_uri": result.setup_audio_gcs_uri,
        "response_audio_gcs_uri": result.response_audio_gcs_uri,
        "punchline_audio_gcs_uri": result.punchline_audio_gcs_uri,
        "audio_generation_metadata": result.audio_generation_metadata.as_dict
        if result.audio_generation_metadata else {},
        "video_generation_metadata": result.video_generation_metadata.as_dict
        if result.video_generation_metadata else {},
        "error": result.error,
        "error_stage": result.error_stage,
      },
      req=req,
    )
  except ValueError as exc:
    return error_response(str(exc),
                          error_type='invalid_request',
                          status=400,
                          req=req)
  except Exception as exc:  # pylint: disable=broad-except
    error_string = (f"Error handling joke video tuning: {str(exc)}\n"
                    f"{traceback.format_exc()}")
    logger.error(error_string)
    return error_response(error_string, error_type='internal_error', req=req)


def _run_joke_creation_proc(req: flask.Request) -> flask.Response:
  """Handle joke creation process."""
  try:
    user_id = get_user_id(req, allow_unauthenticated=False)
  except AuthError:
    return error_response('User not authenticated', status=401, req=req)

  # Joke input data
  joke_id = get_str_param(req, 'joke_id')
  setup_text = get_str_param(req, 'setup_text')
  punchline_text = get_str_param(req, 'punchline_text')
  setup_scene_idea = get_str_param(req, 'setup_scene_idea')
  punchline_scene_idea = get_str_param(req, 'punchline_scene_idea')
  setup_image_description = get_str_param(req, 'setup_image_description')
  punchline_image_description = get_str_param(req,
                                              'punchline_image_description')
  setup_image_url = get_str_param(req, 'setup_image_url')
  punchline_image_url = get_str_param(req, 'punchline_image_url')
  seasonal = get_str_param(req, 'seasonal')
  if seasonal:
    seasonal = seasonal.strip()
  tags_str = get_str_param(req, 'tags')
  admin_owned = get_bool_param(req, 'admin_owned', False)

  # Modifiers
  setup_suggestion = get_str_param(req, 'setup_suggestion')
  punchline_suggestion = get_str_param(req, 'punchline_suggestion')
  image_quality = get_str_param(req, 'image_quality', 'medium_mini')

  # Action flags
  regenerate_scene_ideas = get_bool_param(req, 'regenerate_scene_ideas', False)
  generate_descriptions = get_bool_param(req, 'generate_descriptions', False)
  populate_images = get_bool_param(req, 'populate_images', False)

  book_page_ready: bool | None = get_param(req, 'book_page_ready')
  if book_page_ready is not None:
    book_page_ready = get_bool_param(req, 'book_page_ready')

  if image_quality not in image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY:
    return error_response(
      f'Invalid image_quality: {image_quality}. Must be one of: ' +
      f'{", ".join(image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY.keys())}',
      req=req,
      status=400)

  tags = None
  if tags_str is not None:
    tags = [
      t.strip() for t in tags_str.replace('\n', ',').split(',') if t.strip()
    ]

  # Joke initialization and patching
  init_kwargs: dict[str, object] = {
    "joke_id": joke_id,
    "user_id": user_id,
    "admin_owned": admin_owned,
    "setup_text": setup_text,
    "punchline_text": punchline_text,
    "setup_scene_idea": setup_scene_idea,
    "punchline_scene_idea": punchline_scene_idea,
    "setup_image_description": setup_image_description,
    "punchline_image_description": punchline_image_description,
    "setup_image_url": setup_image_url,
    "punchline_image_url": punchline_image_url,
  }
  if seasonal is not None:
    init_kwargs["seasonal"] = seasonal
  if tags is not None:
    init_kwargs["tags"] = tags
  try:
    joke = joke_operations.initialize_joke(
      **init_kwargs)  # pyright: ignore[reportArgumentType]
  except joke_operations.JokeNotFoundError as exc:
    return error_response(str(exc), req=req, status=404)
  except ValueError:
    return error_response(
      'Unsupported parameter combination for joke creation',
      error_type='unsupported_parameters',
      req=req,
      status=400)

  operation = None
  has_suggestions = bool(setup_suggestion or punchline_suggestion)

  # Generate metadata if text is provided
  if setup_text or punchline_text:
    joke = joke_operations.generate_joke_metadata(joke)

  # Generate scene ideas for new jokes or when requested
  if (not joke_id) or regenerate_scene_ideas:
    operation = "CREATE"
    joke = joke_operations.regenerate_scene_ideas(joke)

  # Apply scene idea suggestions
  if has_suggestions:
    operation = "UPDATE_SCENE_IDEAS"
    joke = joke_operations.modify_image_scene_ideas(
      joke,
      setup_suggestion,
      punchline_suggestion,
    )

  # Generate image descriptions if requested
  if generate_descriptions:
    operation = "GENERATE_IMAGE_DESCRIPTIONS"
    joke = joke_operations.generate_image_descriptions(joke)

  # Generate images if descriptions changed or requested
  if generate_descriptions or populate_images:
    operation = "GENERATE_IMAGES"
    joke = joke_operations.generate_joke_images(joke, image_quality)

  update_metadata = None
  if book_page_ready is not None:
    update_metadata = {'book_page_ready': book_page_ready}
  if saved_joke := firestore.upsert_punny_joke(
      joke, operation=operation, update_metadata=update_metadata):
    return success_response(
      {"joke_data": joke_operations.to_response_joke(saved_joke)},
      req=req,
    )
  else:
    return error_response('Failed to save joke', req=req, status=500)


def _run_printable_sheet_proc(req: flask.Request) -> flask.Response:
  """Create a manual printable notes sheet from selected jokes."""

  if req.method != 'POST':
    return error_response(f'Method not allowed: {req.method}',
                          req=req,
                          status=405)

  joke_ids = get_list_param(req, 'joke_ids')
  sheet_slug = (get_param(req, 'sheet_slug') or '').strip()
  if not sheet_slug:
    return error_response('sheet_slug is required',
                          error_type='invalid_request',
                          status=400,
                          req=req)
  if len(joke_ids) != 5:
    return error_response('joke_ids must contain exactly 5 items',
                          error_type='invalid_request',
                          status=400,
                          req=req)

  jokes = firestore.get_punny_jokes(joke_ids)
  if len(jokes) != len(joke_ids):
    return error_response('One or more joke_ids were not found',
                          error_type='invalid_request',
                          status=404,
                          req=req)

  sheet = joke_notes_sheet_operations.ensure_joke_notes_sheet(
    jokes,
    sheet_slug=sheet_slug,
  )
  return success_response(
    {
      "sheet_id": sheet.key,
      "sheet_slug": sheet.sheet_slug,
      "pdf_gcs_uri": sheet.pdf_gcs_uri,
      "image_gcs_uri": sheet.image_gcs_uri,
    },
    req=req,
  )


def _run_character_animation_op(req: flask.Request) -> flask.Response:
  """Upsert a character animation sequence."""
  if req.method != 'POST':
    return error_response(f'Method not allowed: {req.method}',
                          req=req,
                          status=405)

  sequence_data = get_param(req, "sequence_data")
  sequence_id = (get_param(req, "sequence_id") or "").strip()

  if not sequence_data:
    return error_response("sequence_data is required",
                          error_type="invalid_request",
                          status=400,
                          req=req)

  try:
    if isinstance(sequence_data, str):
      sequence_data = json.loads(sequence_data)

    sequence = posable_character_sequence.PosableCharacterSequence.from_dict(
      sequence_data, key=sequence_id or None)

    saved_sequence = firestore.upsert_posable_character_sequence(sequence)

    return success_response(
      saved_sequence.to_dict(include_key=True),
      req=req,
    )
  except ValueError as exc:
    return error_response(str(exc),
                          error_type="invalid_request",
                          status=400,
                          req=req)
  except Exception as exc:  # pylint: disable=broad-except
    error_string = (f"Error upserting character sequence: {str(exc)}\n"
                    f"{traceback.format_exc()}")
    logger.error(error_string)
    return error_response(error_string, error_type="internal_error", req=req)


def _run_character_animation_laugh(req: flask.Request) -> flask.Response:
  """Build a laugh sequence from audio and return it for editor overwrite."""
  if req.method != 'POST':
    return error_response(f'Method not allowed: {req.method}',
                          req=req,
                          status=405)

  audio_gcs_uri = (get_param(req, "audio_gcs_uri") or "").strip()
  if not audio_gcs_uri:
    return error_response("audio_gcs_uri is required",
                          error_type="invalid_request",
                          status=400,
                          req=req)

  try:
    sequence = joke_operations.build_laugh_sequence(
      audio_gcs_uri=audio_gcs_uri, )
    return success_response(
      sequence.to_dict(include_key=True),
      req=req,
    )
  except ValueError as exc:
    return error_response(str(exc),
                          error_type="invalid_request",
                          status=400,
                          req=req)
  except Exception as exc:  # pylint: disable=broad-except
    error_string = (f"Error building laugh animation sequence: {str(exc)}\n"
                    f"{traceback.format_exc()}")
    logger.error(error_string)
    return error_response(error_string, error_type="internal_error", req=req)


def _run_character_def_op(req: flask.Request) -> flask.Response:
  """Upsert a posable character definition."""
  if req.method != 'POST':
    return error_response(f'Method not allowed: {req.method}',
                          req=req,
                          status=405)

  character_id = (get_param(req, "character_id") or "").strip()
  if not character_id:
    # Check for 'key' as an alias
    character_id = (get_param(req, "key") or "").strip()
  if not character_id:
    return error_response("character_id is required",
                          error_type="invalid_request",
                          status=400,
                          req=req)

  # Extract fields
  name = (get_param(req, "name") or "").strip()
  head_gcs_uri = (get_param(req, "head_gcs_uri") or "").strip()
  surface_line_gcs_uri = (get_param(req, "surface_line_gcs_uri") or "").strip()
  left_hand_gcs_uri = (get_param(req, "left_hand_gcs_uri") or "").strip()
  right_hand_gcs_uri = (get_param(req, "right_hand_gcs_uri") or "").strip()
  mouth_open_gcs_uri = (get_param(req, "mouth_open_gcs_uri") or "").strip()
  mouth_closed_gcs_uri = (get_param(req, "mouth_closed_gcs_uri") or "").strip()
  mouth_o_gcs_uri = (get_param(req, "mouth_o_gcs_uri") or "").strip()
  left_eye_open_gcs_uri = (get_param(req, "left_eye_open_gcs_uri")
                           or "").strip()
  left_eye_closed_gcs_uri = (get_param(req, "left_eye_closed_gcs_uri")
                             or "").strip()
  right_eye_open_gcs_uri = (get_param(req, "right_eye_open_gcs_uri")
                            or "").strip()
  right_eye_closed_gcs_uri = (get_param(req, "right_eye_closed_gcs_uri")
                              or "").strip()

  try:
    asset_uris = {
      "head_gcs_uri": head_gcs_uri,
      "surface_line_gcs_uri": surface_line_gcs_uri,
      "left_hand_gcs_uri": left_hand_gcs_uri,
      "right_hand_gcs_uri": right_hand_gcs_uri,
      "mouth_open_gcs_uri": mouth_open_gcs_uri,
      "mouth_closed_gcs_uri": mouth_closed_gcs_uri,
      "mouth_o_gcs_uri": mouth_o_gcs_uri,
      "left_eye_open_gcs_uri": left_eye_open_gcs_uri,
      "left_eye_closed_gcs_uri": left_eye_closed_gcs_uri,
      "right_eye_open_gcs_uri": right_eye_open_gcs_uri,
      "right_eye_closed_gcs_uri": right_eye_closed_gcs_uri,
    }
    width_int, height_int = _validate_character_assets_and_get_dimensions(
      asset_uris)

    char_def = models.PosableCharacterDef(
      key=character_id,
      name=name or None,
      width=width_int,
      height=height_int,
      head_gcs_uri=head_gcs_uri,
      surface_line_gcs_uri=surface_line_gcs_uri,
      left_hand_gcs_uri=left_hand_gcs_uri,
      right_hand_gcs_uri=right_hand_gcs_uri,
      mouth_open_gcs_uri=mouth_open_gcs_uri,
      mouth_closed_gcs_uri=mouth_closed_gcs_uri,
      mouth_o_gcs_uri=mouth_o_gcs_uri,
      left_eye_open_gcs_uri=left_eye_open_gcs_uri,
      left_eye_closed_gcs_uri=left_eye_closed_gcs_uri,
      right_eye_open_gcs_uri=right_eye_open_gcs_uri,
      right_eye_closed_gcs_uri=right_eye_closed_gcs_uri,
    )

    saved_def = firestore.upsert_posable_character_def(char_def)

    return success_response(
      saved_def.to_dict(include_key=True),
      req=req,
    )

  except ValueError as exc:
    return error_response(str(exc),
                          error_type="invalid_request",
                          status=400,
                          req=req)
  except Exception as exc:  # pylint: disable=broad-except
    error_string = (f"Error upserting character def: {str(exc)}\n"
                    f"{traceback.format_exc()}")
    logger.error(error_string)
    return error_response(error_string, error_type="internal_error", req=req)


def _validate_character_assets_and_get_dimensions(
  asset_uris: dict[str, str], ) -> tuple[int, int]:
  """Verify character assets exist, are valid images, and share dimensions.

  Note: `surface_line_gcs_uri` is allowed to have different dimensions than the
  other sprites (it is a thin overlay).
  """
  expected_size: tuple[int, int] | None = None
  expected_field: str | None = None

  for field_name, uri in asset_uris.items():
    if not uri:
      raise ValueError(f"{field_name} is required")

    image = None
    try:
      image = cloud_storage.download_image_from_gcs(uri)
      # Force decode to fail early on invalid/corrupt images.
      image.load()  # pyright: ignore[reportUnusedCallResult]
      size = image.size
    except Exception as exc:  # pylint: disable=broad-except
      raise ValueError(
        f"Invalid or missing image for {field_name}: {uri}") from exc
    finally:
      if image is not None:
        image.close()

    if expected_size is None:
      expected_size = size
      expected_field = field_name
      continue

    if field_name == "surface_line_gcs_uri":
      continue

    if size != expected_size:
      raise ValueError(
        "All character assets must have matching dimensions. " +
        f"{field_name} is {size[0]}x{size[1]}, " +
        f"but {expected_field} is {expected_size[0]}x{expected_size[1]}.")

  if expected_size is None:
    raise ValueError("At least one character asset URI is required")

  return expected_size
