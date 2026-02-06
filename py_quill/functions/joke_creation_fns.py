"""Cloud functions for orchestrating joke creation workflows."""

from __future__ import annotations

import json
import traceback
from enum import Enum

from agents import constants
from common import (image_generation, joke_notes_sheet_operations,
                    joke_operations, models, utils)
from firebase_functions import https_fn, logger, options
from functions import social_fns
from functions.function_utils import (AuthError, error_response,
                                      get_bool_param, get_list_param,
                                      get_param, get_user_id,
                                      handle_cors_preflight,
                                      handle_health_check, success_response)
from services import audio_client, firestore, gen_audio


class JokeCreationOp(str, Enum):
  """Supported joke creation operations."""
  PROC = "proc"
  JOKE_IMAGE = "joke_image"
  JOKE_AUDIO = "joke_audio"
  JOKE_VIDEO = "joke_video"
  SOCIAL = "social"
  PRINTABLE_NOTE = "printable_note"


@https_fn.on_request(
  memory=options.MemoryOption.GB_2,
  min_instances=1,
  timeout_sec=600,
)
def joke_creation_process(req: https_fn.Request) -> https_fn.Response:
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
  script_template: object | None, ) -> list[audio_client.DialogTurn] | None:
  """Parse dialog turn templates from request payload."""
  if script_template is None:
    return None

  raw = script_template
  if isinstance(raw, str):
    if not raw.strip():
      return None
    try:
      raw = json.loads(raw)
    except json.JSONDecodeError as exc:
      raise ValueError(
        "script_template must be a JSON array of dialog turns") from exc

  if not isinstance(raw, list):
    raise ValueError("script_template must be a list of dialog turns")

  turns: list[audio_client.DialogTurn] = []
  for idx, item in enumerate(raw):
    if not isinstance(item, dict):
      raise ValueError(f"Dialog turn {idx + 1} must be an object")

    voice_raw = (item.get("voice") if isinstance(item, dict) else None)
    script_raw = (item.get("script") if isinstance(item, dict) else None)
    pause_after_raw = (item.get("pause_sec_after")
                       if isinstance(item, dict) else None)

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

    parsed_voice: object
    try:
      parsed_voice = gen_audio.Voice.from_identifier(voice_str)
    except ValueError:
      parsed_voice = voice_str

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


def _handle_admin_request(req: https_fn.Request) -> https_fn.Response | None:
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
      get_user_id(req, allow_unauthenticated=False, require_admin=True)
  except AuthError:
    return error_response('Unauthorized', status=403, req=req)

  return None


def _run_joke_image_tuner(req: https_fn.Request) -> https_fn.Response:
  """Generate setup/punchline images for prompt tuning."""

  setup_prompt = (get_param(req, 'setup_image_prompt') or "").strip()
  punchline_prompt = (get_param(req, 'punchline_image_prompt') or "").strip()
  if not setup_prompt or not punchline_prompt:
    return error_response(
      'setup_image_prompt and punchline_image_prompt are required',
      error_type='invalid_request',
      status=400,
      req=req,
    )

  image_quality = get_param(req, 'image_quality', 'medium_mini')
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


def _run_joke_audio_tuner(req: https_fn.Request) -> https_fn.Response:
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

  script_template = _parse_dialog_turn_templates(
    get_param(req, 'script_template'))
  audio_model_value = (get_param(req, 'audio_model') or "").strip()
  audio_model = None
  if audio_model_value:
    try:
      audio_model = audio_client.AudioModel(audio_model_value)
    except ValueError as exc:
      raise ValueError(f"Invalid audio_model: {audio_model_value}") from exc

  allow_partial = get_bool_param(req, "allow_partial", False)

  try:
    audio_result = joke_operations.generate_joke_audio(
      joke,
      temp_output=True,
      script_template=script_template,
      audio_model=audio_model,
      allow_partial=allow_partial,
    )

    payload: dict[str, object] = {
      "dialog_audio_gcs_uri": audio_result.dialog_gcs_uri,
      "setup_audio_gcs_uri": audio_result.setup_gcs_uri,
      "response_audio_gcs_uri": audio_result.response_gcs_uri,
      "punchline_audio_gcs_uri": audio_result.punchline_gcs_uri,
      "audio_generation_metadata":
      audio_result.generation_metadata.as_dict
      if audio_result.generation_metadata else {},
    }
    if allow_partial and (not audio_result.setup_gcs_uri
                          or not audio_result.response_gcs_uri
                          or not audio_result.punchline_gcs_uri):
      payload["error"] = (
        "Generated dialog audio but could not split on silence; returning the full dialog WAV only."
      )
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


def _run_joke_video_tuner(req: https_fn.Request) -> https_fn.Response:
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

  script_template = _parse_dialog_turn_templates(
    get_param(req, 'script_template'))
  audio_model_value = (get_param(req, 'audio_model') or "").strip()
  audio_model = None
  if audio_model_value:
    try:
      audio_model = audio_client.AudioModel(audio_model_value)
    except ValueError as exc:
      raise ValueError(f"Invalid audio_model: {audio_model_value}") from exc

  allow_partial = get_bool_param(req, "allow_partial", False)

  audio_generation_metadata = None
  generation_metadata = models.GenerationMetadata()
  try:
    audio_result = joke_operations.generate_joke_audio(
      joke,
      temp_output=True,
      script_template=script_template,
      audio_model=audio_model,
      allow_partial=allow_partial,
    )
    audio_generation_metadata = audio_result.generation_metadata
    generation_metadata.add_generation(audio_result.generation_metadata)

    if (not audio_result.setup_gcs_uri or not audio_result.response_gcs_uri
        or not audio_result.punchline_gcs_uri):
      if allow_partial:
        return success_response(
          {
            "dialog_audio_gcs_uri": audio_result.dialog_gcs_uri,
            "setup_audio_gcs_uri": audio_result.setup_gcs_uri,
            "response_audio_gcs_uri": audio_result.response_gcs_uri,
            "punchline_audio_gcs_uri": audio_result.punchline_gcs_uri,
            "audio_generation_metadata":
            audio_result.generation_metadata.as_dict
            if audio_result.generation_metadata else {},
            "video_generation_metadata": generation_metadata.as_dict,
            "error":
            "Generated dialog audio but could not split on silence; returning the full dialog WAV only.",
            "error_stage": "audio_split",
          },
          req=req,
        )

      return error_response(
        "Audio generation did not return split clip URIs",
        error_type="internal_error",
        req=req,
      )

    try:
      video_gcs_uri, generation_metadata = (
        joke_operations.generate_joke_video_from_audio_uris(
          joke,
          setup_audio_gcs_uri=audio_result.setup_gcs_uri,
          response_audio_gcs_uri=audio_result.response_gcs_uri,
          punchline_audio_gcs_uri=audio_result.punchline_gcs_uri,
          clip_timing=audio_result.clip_timing,
          audio_generation_metadata=audio_generation_metadata,
          temp_output=True,
          is_test=True,
        ))
    except Exception as exc:  # pylint: disable=broad-except
      error_string = f"Error generating video: {exc}"
      logger.error(f"{error_string}\n{traceback.format_exc()}")
      if allow_partial:
        return success_response(
          {
            "dialog_audio_gcs_uri": audio_result.dialog_gcs_uri,
            "setup_audio_gcs_uri": audio_result.setup_gcs_uri,
            "response_audio_gcs_uri": audio_result.response_gcs_uri,
            "punchline_audio_gcs_uri": audio_result.punchline_gcs_uri,
            "audio_generation_metadata":
            audio_result.generation_metadata.as_dict
            if audio_result.generation_metadata else {},
            "video_generation_metadata": generation_metadata.as_dict,
            "error": error_string,
            "error_stage": "video_generation",
          },
          req=req,
        )
      raise

    return success_response(
      {
        "video_gcs_uri": video_gcs_uri,
        "dialog_audio_gcs_uri": audio_result.dialog_gcs_uri,
        "setup_audio_gcs_uri": audio_result.setup_gcs_uri,
        "response_audio_gcs_uri": audio_result.response_gcs_uri,
        "punchline_audio_gcs_uri": audio_result.punchline_gcs_uri,
        "audio_generation_metadata":
        audio_result.generation_metadata.as_dict
        if audio_result.generation_metadata else {},
        "video_generation_metadata":
        generation_metadata.as_dict if generation_metadata else {},
      },
      req=req,
    )
  except ValueError as exc:
    return error_response(str(exc),
                          error_type='invalid_request',
                          status=400,
                          req=req)
  except Exception as exc:  # pylint: disable=broad-except
    if allow_partial:
      error_string = f"Error handling joke video tuning: {str(exc)}"
      logger.error(f"{error_string}\n{traceback.format_exc()}")
      return success_response(
        {
          "video_generation_metadata": generation_metadata.as_dict,
          "error": error_string,
          "error_stage": "internal_error",
        },
        req=req,
      )

    error_string = (f"Error handling joke video tuning: {str(exc)}\n"
                    f"{traceback.format_exc()}")
    logger.error(error_string)
    return error_response(error_string, error_type='internal_error', req=req)


def _run_joke_creation_proc(req: https_fn.Request) -> https_fn.Response:
  """Handle joke creation process."""
  try:
    user_id = get_user_id(req, allow_unauthenticated=False)
  except AuthError:
    return error_response('User not authenticated', status=401, req=req)

  # Joke input data
  joke_id = get_param(req, 'joke_id')
  setup_text = get_param(req, 'setup_text')
  punchline_text = get_param(req, 'punchline_text')
  setup_scene_idea = get_param(req, 'setup_scene_idea')
  punchline_scene_idea = get_param(req, 'punchline_scene_idea')
  setup_image_description = get_param(req, 'setup_image_description')
  punchline_image_description = get_param(req, 'punchline_image_description')
  setup_image_url = get_param(req, 'setup_image_url')
  punchline_image_url = get_param(req, 'punchline_image_url')
  raw_seasonal = get_param(req, 'seasonal')
  raw_tags = get_param(req, 'tags')
  admin_owned = get_bool_param(req, 'admin_owned', False)

  # Modifiers
  setup_suggestion = get_param(req, 'setup_suggestion')
  punchline_suggestion = get_param(req, 'punchline_suggestion')
  image_quality = get_param(req, 'image_quality', 'medium_mini')

  # Action flags
  regenerate_scene_ideas = get_bool_param(req, 'regenerate_scene_ideas', False)
  generate_descriptions = get_bool_param(req, 'generate_descriptions', False)
  populate_images = get_bool_param(req, 'populate_images', False)

  book_page_ready: bool | None = get_param(req, 'book_page_ready')
  if book_page_ready is not None:
    book_page_ready = get_bool_param(req, 'book_page_ready')

  if image_quality not in image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY:
    return error_response(
      f'Invalid image_quality: {image_quality}. Must be one of: '
      f'{", ".join(image_generation.PUN_IMAGE_CLIENTS_BY_QUALITY.keys())}',
      req=req,
      status=400)

  seasonal_provided = raw_seasonal is not None
  seasonal_value = None
  seasonal_arg = None
  if seasonal_provided:
    seasonal_value = str(raw_seasonal).strip() or None
    seasonal_arg = seasonal_value if seasonal_value is not None else ''

  tags = None
  tags_provided = raw_tags is not None
  if tags_provided:
    if isinstance(raw_tags, str):
      raw_tags_value = raw_tags.strip()
      tags = [
        t.strip() for t in raw_tags_value.replace('\n', ',').split(',')
        if t.strip()
      ]
    else:
      try:
        tags = [str(t).strip() for t in raw_tags if str(t).strip()]
      except TypeError:
        tags = []

  # Joke initialization and patching
  try:
    init_kwargs = {
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
    if seasonal_provided:
      init_kwargs["seasonal"] = seasonal_arg
    if tags_provided:
      init_kwargs["tags"] = tags
    joke = joke_operations.initialize_joke(**init_kwargs)
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

  if seasonal_provided:
    joke.seasonal = seasonal_value
  if tags_provided:
    joke.tags = tags

  # Generate metadata if text is provided
  if setup_text or punchline_text:
    joke = joke_operations.generate_joke_metadata(joke)
    if seasonal_provided:
      joke.seasonal = seasonal_value
    if tags_provided:
      joke.tags = tags

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


def _run_printable_sheet_proc(req: https_fn.Request) -> https_fn.Response:
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
