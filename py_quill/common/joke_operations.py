"""Operations for jokes."""

from __future__ import annotations

import datetime
import random
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Literal, Tuple

from common import audio_operations, audio_timing, image_generation, models
from common.posable_character import PosableCharacter
from common.posable_characters import PosableCat
from firebase_functions import logger
from functions.prompts import joke_operation_prompts
from google.cloud.firestore_v1.vector import Vector
from PIL import Image
from services import (audio_client, cloud_storage, firestore, gen_audio,
                      gen_video, image_client, image_editor)

_IMAGE_UPSCALE_FACTOR = "x2"
_HIGH_QUALITY_UPSCALE_FACTOR = "x2"

_JOKE_AUDIO_RESPONSE_GAP_SEC = 0.8
_JOKE_AUDIO_PUNCHLINE_GAP_SEC = 1.0
_JOKE_VIDEO_FOOTER_BACKGROUND_GCS_URI = (
  "gs://images.quillsstorybook.com/_joke_assets/blank_paper.png")

DEFAULT_JOKE_AUDIO_SCRIPT_TEMPLATE = """You are generating audio. DO NOT speak any instructions.
ONLY speak the lines under TRANSCRIPT, using the specified speakers.

AUDIO PROFILE:
- Two 8-year-old kids on a school playground at recess.
- Natural, clear kid voices. Light and playful.

TRANSCRIPT:
Sam: [playfully, slightly slowly to build intrigue] Hey... want to hear a joke? {setup_text}
[1 second silence]
Riley: [curiously] what?
[1 second silence]
Sam: [excitedly, holding back laughter] {punchline_text}
Riley: [giggles]
"""

DEFAULT_JOKE_AUDIO_SPEAKER_1_NAME = "Sam"
DEFAULT_JOKE_AUDIO_SPEAKER_1_VOICE = gen_audio.Voice.GEMINI_LEDA
DEFAULT_JOKE_AUDIO_SPEAKER_2_NAME = "Riley"
DEFAULT_JOKE_AUDIO_SPEAKER_2_VOICE = gen_audio.Voice.GEMINI_PUCK

# Preferred dialog template format (turn-based). Each script may include
# {setup_text} and/or {punchline_text} placeholders.
DEFAULT_JOKE_AUDIO_TURNS_TEMPLATE: list[audio_client.DialogTurn] = [
  audio_client.DialogTurn(
    voice=DEFAULT_JOKE_AUDIO_SPEAKER_1_VOICE,
    script=
    "[playfully, slightly slowly to build intrigue] Hey... want to hear a joke? {setup_text}",
    pause_sec_after=1.0,
  ),
  audio_client.DialogTurn(
    voice=DEFAULT_JOKE_AUDIO_SPEAKER_2_VOICE,
    script="[curiously] what?",
    pause_sec_after=1.0,
  ),
  audio_client.DialogTurn(
    voice=DEFAULT_JOKE_AUDIO_SPEAKER_1_VOICE,
    script="[excitedly, holding back laughter] {punchline_text}",
  ),
]

_MIME_TYPE_CONFIG: dict[str, Tuple[str, str]] = {
  "image/png": ("PNG", "png"),
  "image/jpeg": ("JPEG", "jpg"),
}


@dataclass(frozen=True)
class JokeAudioTiming:
  """Optional per-clip timing metadata for mouth animation."""

  setup: list[audio_timing.WordTiming] | None = None
  response: list[audio_timing.WordTiming] | None = None
  punchline: list[audio_timing.WordTiming] | None = None


@dataclass(frozen=True)
class JokeAudioResult:
  """Result of generating joke audio (full dialog + split clips)."""

  dialog_gcs_uri: str
  setup_gcs_uri: str | None
  response_gcs_uri: str | None
  punchline_gcs_uri: str | None
  generation_metadata: models.SingleGenerationMetadata
  clip_timing: JokeAudioTiming | None = None


class JokeOperationsError(Exception):
  """Base exception for joke operation failures."""


class JokeNotFoundError(JokeOperationsError):
  """Exception raised when a requested joke cannot be found."""


class JokePopulationError(JokeOperationsError):
  """Exception raised for errors in joke population."""


SafetyCheckError = joke_operation_prompts.SafetyCheckError


def initialize_joke(
  *,
  joke_id: str | None,
  user_id: str | None,
  admin_owned: bool,
  setup_text: str | None = None,
  punchline_text: str | None = None,
  seasonal: str | None = None,
  tags: list[str] | str | None = None,
  setup_scene_idea: str | None = None,
  punchline_scene_idea: str | None = None,
  setup_image_description: str | None = None,
  punchline_image_description: str | None = None,
  setup_image_url: str | None = None,
  punchline_image_url: str | None = None,
) -> models.PunnyJoke:
  """Load or create a joke and apply the provided overrides."""
  joke: models.PunnyJoke | None = None
  if joke_id:
    joke = firestore.get_punny_joke(joke_id)
    if not joke:
      raise JokeNotFoundError(f'Joke not found: {joke_id}')
  else:
    setup_text = setup_text.strip() if setup_text else None
    punchline_text = (punchline_text.strip() if punchline_text else None)
    if not setup_text:
      raise ValueError('Setup text is required')
    if not punchline_text:
      raise ValueError('Punchline text is required')
    if not user_id:
      raise ValueError('user_id is required when creating a joke')
    owner_user_id = "ADMIN" if admin_owned else user_id
    joke = models.PunnyJoke(
      setup_text=setup_text,
      punchline_text=punchline_text,
      owner_user_id=owner_user_id,
      state=models.JokeState.DRAFT,
      random_id=random.randint(0, 2**31 - 1),
    )

  if setup_text is not None:
    joke.setup_text = setup_text
  if punchline_text is not None:
    joke.punchline_text = punchline_text
  if seasonal is not None:
    seasonal_value = str(seasonal).strip()
    joke.seasonal = seasonal_value or None
  if tags is not None:
    if isinstance(tags, str):
      joke.tags = [t.strip() for t in tags.split(',') if t.strip()]
    else:
      joke.tags = [str(t).strip() for t in tags if str(t).strip()]
  if setup_scene_idea is not None:
    joke.setup_scene_idea = setup_scene_idea
  if punchline_scene_idea is not None:
    joke.punchline_scene_idea = punchline_scene_idea
  if setup_image_description is not None:
    joke.setup_image_description = setup_image_description
  if punchline_image_description is not None:
    joke.punchline_image_description = punchline_image_description
  if setup_image_url is not None:
    if setup_image_url != joke.setup_image_url:
      joke.setup_image_url_upscaled = None
    joke.setup_image_url = setup_image_url
    if setup_image_url and setup_image_url not in joke.all_setup_image_urls:
      joke.all_setup_image_urls.append(setup_image_url)
  if punchline_image_url is not None:
    if punchline_image_url != joke.punchline_image_url:
      joke.punchline_image_url_upscaled = None
    joke.punchline_image_url = punchline_image_url
    if (punchline_image_url
        and punchline_image_url not in joke.all_punchline_image_urls):
      joke.all_punchline_image_urls.append(punchline_image_url)

  return joke


def regenerate_scene_ideas(joke: models.PunnyJoke) -> models.PunnyJoke:
  """Generate fresh scene ideas from the joke's text."""
  if not joke.setup_text or not joke.punchline_text:
    raise ValueError('Setup and punchline text are required to build scenes')

  (
    setup_scene_idea,
    punchline_scene_idea,
    idea_generation_metadata,
  ) = joke_operation_prompts.generate_joke_scene_ideas(
    setup_text=joke.setup_text,
    punchline_text=joke.punchline_text,
  )

  joke.setup_scene_idea = setup_scene_idea
  joke.punchline_scene_idea = punchline_scene_idea
  joke.generation_metadata.add_generation(idea_generation_metadata)
  return joke


def modify_image_scene_ideas(
  joke: models.PunnyJoke,
  setup_suggestion: str,
  punchline_suggestion: str,
) -> models.PunnyJoke:
  """Update a joke's image scene ideas using the provided suggestions."""
  if not joke.setup_text or not joke.punchline_text:
    raise ValueError('Joke is missing text required to edit scene ideas')
  if not joke.setup_scene_idea or not joke.punchline_scene_idea:
    raise ValueError('Joke must have existing scene ideas to edit')

  setup_instruction = setup_suggestion.strip() if setup_suggestion else ''
  punchline_instruction = (punchline_suggestion.strip()
                           if punchline_suggestion else '')

  if not (setup_instruction or punchline_instruction):
    raise ValueError('At least one suggestion is required to modify scenes')

  (
    updated_setup_scene,
    updated_punchline_scene,
    metadata,
  ) = joke_operation_prompts.modify_scene_ideas_with_suggestions(
    setup_text=joke.setup_text,
    punchline_text=joke.punchline_text,
    current_setup_scene_idea=joke.setup_scene_idea,
    current_punchline_scene_idea=joke.punchline_scene_idea,
    setup_suggestion=setup_instruction,
    punchline_suggestion=punchline_instruction,
  )

  joke.setup_scene_idea = updated_setup_scene
  joke.punchline_scene_idea = updated_punchline_scene
  joke.generation_metadata.add_generation(metadata)

  return joke


def generate_image_descriptions(joke: models.PunnyJoke) -> models.PunnyJoke:
  """Ensure the joke has detailed image descriptions derived from scene ideas."""
  if not joke.setup_text or not joke.punchline_text:
    raise JokePopulationError('Joke is missing setup or punchline text')
  if not joke.setup_scene_idea or not joke.punchline_scene_idea:
    raise JokePopulationError('Joke is missing scene ideas')

  setup_description, punchline_description, metadata = (
    joke_operation_prompts.generate_detailed_image_descriptions(
      setup_text=joke.setup_text,
      punchline_text=joke.punchline_text,
      setup_scene_idea=joke.setup_scene_idea,
      punchline_scene_idea=joke.punchline_scene_idea,
    ))

  joke.setup_image_description = setup_description
  joke.punchline_image_description = punchline_description
  joke.generation_metadata.add_generation(metadata)
  return joke


def generate_joke_images(joke: models.PunnyJoke,
                         image_quality: str) -> models.PunnyJoke:
  """Populate a joke with new images using the image generation service."""
  if not joke.setup_text:
    raise JokePopulationError('Joke is missing setup text')
  if not joke.punchline_text:
    raise JokePopulationError('Joke is missing punchline text')
  if not joke.setup_image_description or not joke.punchline_image_description:
    joke = generate_image_descriptions(joke)

  setup_image, punchline_image = image_generation.generate_pun_images(
    setup_text=joke.setup_text,
    setup_image_description=joke.setup_image_description,
    punchline_text=joke.punchline_text,
    punchline_image_description=joke.punchline_image_description,
    image_quality=image_quality,
  )

  joke.set_setup_image(setup_image)
  joke.set_punchline_image(punchline_image)

  joke.setup_image_url_upscaled = None
  joke.punchline_image_url_upscaled = None

  if joke.state == models.JokeState.DRAFT:
    joke.state = models.JokeState.UNREVIEWED

  return joke


def upscale_joke(
  joke_id: str,
  mime_type: Literal["image/png", "image/jpeg"] = "image/png",
  *,
  compression_quality: int | None = None,
  overwrite: bool = False,
  high_quality: bool = False,
) -> models.PunnyJoke:
  """Upscales a joke's images.

  If overwrite is False, this function is idempotent. If the joke already
  has upscaled URLs, it will return immediately.

  Args:
    joke_id: The ID of the joke to upscale.
    mime_type: The MIME type of the image.
    compression_quality: The compression quality of the image.
    overwrite: Whether to force re-upscaling even if URLs already exist.
    high_quality: Whether to use high-quality upscaling and replace base images.
  """
  joke = firestore.get_punny_joke(joke_id)
  if not joke:
    raise ValueError(f'Joke not found: {joke_id}')

  setup_needs_upscale = bool(joke.setup_image_url and
                             (overwrite or not joke.setup_image_url_upscaled))
  punchline_needs_upscale = bool(
    joke.punchline_image_url
    and (overwrite or not joke.punchline_image_url_upscaled))

  if not (setup_needs_upscale or punchline_needs_upscale):
    return joke

  model = (image_client.ImageModel.IMAGEN_4_UPSCALE
           if high_quality else image_client.ImageModel.IMAGEN_1)
  upscale_factor = (_HIGH_QUALITY_UPSCALE_FACTOR
                    if high_quality else _IMAGE_UPSCALE_FACTOR)
  client = image_client.get_client(
    label="upscale_joke_high" if high_quality else "upscale_joke_standard",
    model=model,
    file_name_base="upscaled_joke_image",
  )
  if joke.generation_metadata is None:
    joke.generation_metadata = models.GenerationMetadata()

  update_data: dict[str, Any] = {}

  if setup_needs_upscale:
    update_data.update(
      _process_upscale_for_image(
        joke=joke,
        image_role="setup",
        client=client,
        mime_type=mime_type,
        compression_quality=compression_quality,
        upscale_factor=upscale_factor,
        replace_original=high_quality,
      ))

  if punchline_needs_upscale:
    update_data.update(
      _process_upscale_for_image(
        joke=joke,
        image_role="punchline",
        client=client,
        mime_type=mime_type,
        compression_quality=compression_quality,
        upscale_factor=upscale_factor,
        replace_original=high_quality,
      ))

  update_data["generation_metadata"] = joke.generation_metadata.as_dict
  firestore.update_punny_joke(joke.key, update_data)

  return joke


def _process_upscale_for_image(
  *,
  joke: models.PunnyJoke,
  image_role: Literal["setup", "punchline"],
  client: image_client.ImageClient,
  mime_type: Literal["image/png", "image/jpeg"],
  compression_quality: int | None,
  upscale_factor: Literal["x2", "x4"],
  replace_original: bool,
) -> dict[str, Any]:
  """Upscale a single image (setup or punchline) and return updated fields."""
  url_attr = f"{image_role}_image_url"
  upscaled_attr = f"{image_role}_image_url_upscaled"
  all_urls_attr = f"all_{image_role}_image_urls"
  set_method = getattr(joke,
                       f"set_{image_role}_image") if replace_original else None

  source_url = getattr(joke, url_attr)
  if not source_url:
    return {}

  gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(source_url)
  upscaled_image = client.upscale_image(
    upscale_factor=upscale_factor,
    mime_type=mime_type,
    compression_quality=compression_quality,
    gcs_uri=gcs_uri,
  )

  setattr(joke, upscaled_attr, upscaled_image.url_upscaled)
  joke.generation_metadata.add_generation(upscaled_image.generation_metadata)

  update_data: dict[str, Any] = {
    upscaled_attr: getattr(joke, upscaled_attr),
  }

  if replace_original and upscaled_image.gcs_uri_upscaled:
    original_dimensions = _get_image_dimensions(gcs_uri)
    downscaled_gcs_uri, downscaled_url = _create_downscaled_image(
      joke=joke,
      image_role=image_role,
      editor=image_editor.ImageEditor(),
      target_dimensions=original_dimensions,
      mime_type=mime_type,
      compression_quality=compression_quality,
      upscaled_image_gcs_uri=upscaled_image.gcs_uri_upscaled,
    )
    replacement_image = models.Image(
      url=downscaled_url,
      gcs_uri=downscaled_gcs_uri,
      url_upscaled=upscaled_image.url_upscaled,
      gcs_uri_upscaled=upscaled_image.gcs_uri_upscaled,
      generation_metadata=models.GenerationMetadata(),  # Already added above
    )
    set_method(replacement_image, update_text=False)
    update_data[url_attr] = getattr(joke, url_attr)
    update_data[all_urls_attr] = getattr(joke, all_urls_attr)

  return update_data


def _get_image_dimensions(gcs_uri: str) -> Tuple[int, int]:
  """Load image dimensions from GCS."""
  with Image.open(BytesIO(
      cloud_storage.download_bytes_from_gcs(gcs_uri))) as img:
    return img.width, img.height


def _create_downscaled_image(
  *,
  joke: models.PunnyJoke,
  image_role: str,
  editor: image_editor.ImageEditor,
  target_dimensions: Tuple[int, int],
  mime_type: Literal["image/png", "image/jpeg"],
  compression_quality: int | None,
  upscaled_image_gcs_uri: str,
) -> Tuple[str, str]:
  """Create a downscaled image that matches the original dimensions."""
  upscaled_image = cloud_storage.download_image_from_gcs(
    upscaled_image_gcs_uri)
  target_width, target_height = target_dimensions

  if upscaled_image.width == 0 or upscaled_image.height == 0:
    raise ValueError("Upscaled image has invalid dimensions")

  scale_factor = min(
    target_width / upscaled_image.width,
    target_height / upscaled_image.height,
  )
  scaled_image = editor.scale_image(upscaled_image, scale_factor)
  if (scaled_image.width, scaled_image.height) != target_dimensions:
    scaled_image = scaled_image.resize(
      size=target_dimensions,
      resample=Image.Resampling.LANCZOS,
    )

  image_bytes = _image_to_bytes(
    scaled_image,
    mime_type=mime_type,
    compression_quality=compression_quality,
  )

  _, extension = _MIME_TYPE_CONFIG[mime_type]
  file_base = f"{joke.key or 'joke'}_{image_role}_hq"
  downscaled_gcs_uri = cloud_storage.get_image_gcs_uri(file_base, extension)
  cloud_storage.upload_bytes_to_gcs(
    content_bytes=image_bytes,
    gcs_uri=downscaled_gcs_uri,
    content_type=mime_type,
  )
  downscaled_url = cloud_storage.get_final_image_url(downscaled_gcs_uri,
                                                     width=target_width)
  return downscaled_gcs_uri, downscaled_url


def _image_to_bytes(
  image: Image.Image,
  *,
  mime_type: Literal["image/png", "image/jpeg"],
  compression_quality: int | None,
) -> bytes:
  """Serialize an image to bytes according to the provided MIME type."""
  format_name, _ = _MIME_TYPE_CONFIG[mime_type]
  save_kwargs: dict[str, Any] = {}

  if mime_type == "image/jpeg":
    if image.mode not in ("RGB", "L"):
      image = image.convert("RGB")
    save_kwargs["quality"] = compression_quality or 95
    save_kwargs["optimize"] = True
  elif mime_type == "image/png" and image.mode == "CMYK":
    image = image.convert("RGBA")

  buffer = BytesIO()
  image.save(buffer, format=format_name, **save_kwargs)
  return buffer.getvalue()


def sync_joke_to_search_collection(
  joke: models.PunnyJoke,
  new_embedding: Vector | None,
) -> None:
  """Syncs joke data to the joke_search collection document."""
  if not joke.key:
    return

  joke_id = joke.key
  search_doc_ref = firestore.db().collection("joke_search").document(joke_id)
  search_doc = search_doc_ref.get()
  search_data = search_doc.to_dict() if search_doc.exists else {}

  update_payload = {}

  # 1. Sync embedding
  if new_embedding:
    update_payload["text_embedding"] = new_embedding

  # 2. Sync state
  if search_data.get("state") != joke.state.value:
    update_payload["state"] = joke.state.value

  # 3. Sync is_public
  if search_data.get("is_public") != joke.is_public:
    update_payload["is_public"] = joke.is_public

  # 4. Sync public_timestamp
  if search_data.get("public_timestamp") != joke.public_timestamp:
    update_payload["public_timestamp"] = joke.public_timestamp

  # 5. Sync num_saved_users_fraction
  if search_data.get(
      "num_saved_users_fraction") != joke.num_saved_users_fraction:
    update_payload["num_saved_users_fraction"] = joke.num_saved_users_fraction

  # 6. Sync num_shared_users_fraction
  if search_data.get(
      "num_shared_users_fraction") != joke.num_shared_users_fraction:
    update_payload[
      "num_shared_users_fraction"] = joke.num_shared_users_fraction

  # 7. Sync popularity_score
  if search_data.get("popularity_score") != joke.popularity_score:
    update_payload["popularity_score"] = joke.popularity_score

  # 8. Sync book_id (explicitly write nulls when missing)
  if "book_id" not in search_data or search_data.get(
      "book_id") != joke.book_id:
    update_payload["book_id"] = joke.book_id

  if update_payload:
    logger.info(
      f"Syncing joke to joke_search collection: {joke_id} with payload keys {update_payload.keys()}"
    )
    search_doc_ref.set(update_payload, merge=True)


def to_response_joke(joke: models.PunnyJoke) -> dict[str, Any]:
  """Convert a PunnyJoke to a dictionary suitable for API responses."""
  joke_dict = joke.to_dict(include_key=True)

  # Convert datetime objects to strings (e.g. DatetimeWithNanoseconds from Firestore is not serializable)
  for key, value in joke_dict.items():
    if isinstance(value, datetime.datetime):
      joke_dict[key] = value.isoformat()

  return joke_dict


def generate_joke_metadata(joke: models.PunnyJoke) -> models.PunnyJoke:
  """Generate seasonal info and tags for a joke."""
  if not joke.setup_text or not joke.punchline_text:
    # Skip metadata generation if text is incomplete (e.g. drafts)
    return joke

  seasonal, tags, metadata = joke_operation_prompts.generate_joke_metadata(
    setup_text=joke.setup_text,
    punchline_text=joke.punchline_text,
  )

  joke.seasonal = seasonal
  joke.tags = tags
  joke.generation_metadata.add_generation(metadata)
  return joke


def generate_joke_audio(
  joke: models.PunnyJoke,
  temp_output: bool = False,
  script_template: list[audio_client.DialogTurn] | None = None,
  audio_model: audio_client.AudioModel | None = None,
  allow_partial: bool = False,
) -> JokeAudioResult:
  """Generate a full dialog WAV plus split clips and upload as public files.

  Flow:
  - Generate a single multi-speaker dialog WAV in the *temp* bucket.
  - Upload the full dialog WAV to the public audio bucket.
  - Split the WAV on the two ~1s silent pauses into 3 clips:
    setup, response ("what?"), punchline (including giggles).
  - Upload all 3 clips to the public audio bucket and return their GCS URIs,
    plus the generation metadata from the TTS call.

  If allow_partial is True and the silence splitting fails, returns the full
  dialog WAV (dialog_gcs_uri) and leaves the split clip URIs as None.
  """
  if not joke.setup_text or not joke.punchline_text:
    raise ValueError("Joke must have setup_text and punchline_text")

  joke_id_for_filename = (joke.key or str(joke.random_id or "joke")).strip()
  turns_template = script_template or DEFAULT_JOKE_AUDIO_TURNS_TEMPLATE
  dialog_turns = _render_dialog_turns_from_template(joke, turns_template)
  resolved_audio_model = audio_model or _select_audio_model_for_turns(
    dialog_turns)
  _validate_audio_model_for_turns(resolved_audio_model, dialog_turns)

  audio_client_kwargs: dict[str, Any] = {}
  if resolved_audio_model == audio_client.AudioModel.ELEVENLABS_ELEVEN_V3:
    # `generate_joke_audio` expects a WAV so we can split on silences.
    audio_client_kwargs["output_format"] = "wav_24000"

  client = audio_client.get_audio_client(
    label="generate_joke_audio",
    model=resolved_audio_model,
    **audio_client_kwargs,
  )
  audio_result = client.generate_multi_turn_dialog(
    turns=dialog_turns,
    output_filename_base=f"joke_dialog_{joke_id_for_filename}",
    temp_output=temp_output,
    label="generate_joke_audio",
    extra_log_data={
      "joke_id":
      joke.key,
      "turn_voices":
      [str(turn.voice.name) for turn in dialog_turns],
    },
  )
  temp_dialog_gcs_uri = audio_result.gcs_uri
  audio_generation_metadata = audio_result.metadata

  dialog_wav_bytes = cloud_storage.download_bytes_from_gcs(temp_dialog_gcs_uri)

  dialog_gcs_uri = cloud_storage.get_audio_gcs_uri(
    f"joke_{joke_id_for_filename}_dialog",
    "wav",
  )
  cloud_storage.upload_bytes_to_gcs(dialog_wav_bytes,
                                    dialog_gcs_uri,
                                    content_type="audio/wav")

  timing: JokeAudioTiming | None = None
  setup_wav: bytes | None = None
  response_wav: bytes | None = None
  punchline_wav: bytes | None = None

  if audio_result.timing:
    try:
      setup_wav, response_wav, punchline_wav, timing = _split_joke_dialog_wav_by_timing(
        dialog_wav_bytes,
        audio_result.timing,
      )
    except Exception as exc:  # pylint: disable=broad-except
      logger.error(f"Error splitting joke dialog WAV by timing: {exc}")
      setup_wav = None
      response_wav = None
      punchline_wav = None
      timing = None

  if setup_wav is None or response_wav is None or punchline_wav is None:
    try:
      setup_wav, response_wav, punchline_wav = audio_operations.split_wav_on_silence(
        dialog_wav_bytes,
        silence_duration_sec=1.0,
      )
      timing = None
    except Exception as exc:  # pylint: disable=broad-except
      logger.error(f"Error splitting joke dialog WAV: {exc}")
      if allow_partial:
        return JokeAudioResult(
          dialog_gcs_uri=dialog_gcs_uri,
          setup_gcs_uri=None,
          response_gcs_uri=None,
          punchline_gcs_uri=None,
          generation_metadata=audio_generation_metadata,
          clip_timing=None,
        )
      raise

  setup_gcs_uri = cloud_storage.get_audio_gcs_uri(
    f"joke_{joke_id_for_filename}_setup",
    "wav",
  )
  response_gcs_uri = cloud_storage.get_audio_gcs_uri(
    f"joke_{joke_id_for_filename}_response",
    "wav",
  )
  punchline_gcs_uri = cloud_storage.get_audio_gcs_uri(
    f"joke_{joke_id_for_filename}_punchline",
    "wav",
  )

  cloud_storage.upload_bytes_to_gcs(setup_wav,
                                    setup_gcs_uri,
                                    content_type="audio/wav")
  cloud_storage.upload_bytes_to_gcs(response_wav,
                                    response_gcs_uri,
                                    content_type="audio/wav")
  cloud_storage.upload_bytes_to_gcs(punchline_wav,
                                    punchline_gcs_uri,
                                    content_type="audio/wav")

  return JokeAudioResult(
    dialog_gcs_uri=dialog_gcs_uri,
    setup_gcs_uri=setup_gcs_uri,
    response_gcs_uri=response_gcs_uri,
    punchline_gcs_uri=punchline_gcs_uri,
    generation_metadata=audio_generation_metadata,
    clip_timing=timing,
  )


def _split_joke_dialog_wav_by_timing(
  dialog_wav_bytes: bytes,
  timing: audio_timing.TtsTiming,
) -> tuple[bytes, bytes, bytes, JokeAudioTiming | None]:
  """Split the 3-turn joke dialog WAV using provider timing data.

  Uses `timing.voice_segments` to find the time bounds for each dialogue turn
  (setup, response, punchline). Then uses refined scan-and-split logic to
  find the exact silence between turns to avoid bleeding or truncation.
  """
  alignment = timing.normalized_alignment or timing.alignment
  if alignment is None or not timing.voice_segments:
    raise ValueError("timing missing alignment or voice_segments")

  segments_by_turn: dict[int, list[audio_timing.VoiceSegment]] = {}
  for seg in timing.voice_segments:
    segments_by_turn.setdefault(int(seg.dialogue_input_index), []).append(seg)

  def _turn_bounds(turn_index: int) -> tuple[float, float, int, int]:
    segs = segments_by_turn.get(turn_index) or []
    if not segs:
      raise ValueError(f"missing voice segments for turn {turn_index}")
    start_sec = min(float(s.start_time_seconds) for s in segs)
    end_sec = max(float(s.end_time_seconds) for s in segs)
    word_start = min(int(s.word_start_index) for s in segs)
    word_end = max(int(s.word_end_index) for s in segs)
    return start_sec, end_sec, word_start, word_end

  _setup_start, setup_end, setup_w0, setup_w1 = _turn_bounds(0)
  response_start, response_end, response_w0, response_w1 = _turn_bounds(1)
  punch_start, _punch_end, punch_w0, punch_w1 = _turn_bounds(2)

  # Gap 1: between Setup end and Response start
  gap1_center = (setup_end + response_start) / 2

  # Gap 2: between Response end and Punchline start
  gap2_center = (response_end + punch_start) / 2

  segments = audio_operations.split_audio(
    wav_bytes=dialog_wav_bytes,
    estimated_cut_points=[gap1_center, gap2_center],
    trim=True,
  )

  if len(segments) != 3:
    raise ValueError(f"Expected 3 audio segments, got {len(segments)}")

  setup_seg, response_seg, punchline_seg = segments[0], segments[1], segments[2]

  def _shift_words(
    words: list[audio_timing.WordTiming],
    *,
    offset_sec: float,
  ) -> list[audio_timing.WordTiming]:
    offset_sec = float(offset_sec)
    out: list[audio_timing.WordTiming] = []
    for word in words:
      out.append(
        audio_timing.WordTiming(
          word=str(word.word),
          start_time=float(word.start_time) - offset_sec,
          end_time=float(word.end_time) - offset_sec,
          char_timings=[
            audio_timing.CharTiming(
              char=str(ch.char),
              start_time=float(ch.start_time) - offset_sec,
              end_time=float(ch.end_time) - offset_sec,
            ) for ch in (word.char_timings or [])
          ],
        ))
    return out

  return (
    setup_seg.wav_bytes,
    response_seg.wav_bytes,
    punchline_seg.wav_bytes,
    JokeAudioTiming(
      setup=_shift_words(alignment[setup_w0:setup_w1],
                         offset_sec=setup_seg.offset_sec),
      response=_shift_words(alignment[response_w0:response_w1],
                            offset_sec=response_seg.offset_sec),
      punchline=_shift_words(alignment[punch_w0:punch_w1],
                             offset_sec=punchline_seg.offset_sec),
    ),
  )


def generate_joke_video_from_audio_uris(
  joke: models.PunnyJoke,
  *,
  setup_audio_gcs_uri: str,
  response_audio_gcs_uri: str,
  punchline_audio_gcs_uri: str,
  clip_timing: JokeAudioTiming | None = None,
  audio_generation_metadata: models.SingleGenerationMetadata | None = None,
  temp_output: bool = False,
  is_test: bool = False,
  character_class: type[PosableCharacter] | None = PosableCat,
) -> tuple[str, models.GenerationMetadata]:
  """Generate a portrait video for a joke using existing audio clips."""
  if not joke.setup_text or not joke.punchline_text:
    raise ValueError("Joke must have setup_text and punchline_text")

  setup_image_gcs_uri: str | None = None
  punchline_image_gcs_uri: str | None = None
  if not is_test:
    setup_image_url = joke.setup_image_url_upscaled or joke.setup_image_url
    punchline_image_url = (joke.punchline_image_url_upscaled
                           or joke.punchline_image_url)
    if not setup_image_url or not punchline_image_url:
      raise ValueError("Joke must have setup and punchline images")

    setup_image_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
      setup_image_url)
    punchline_image_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
      punchline_image_url)

  setup_duration_sec = audio_operations.get_wav_duration_sec(
    cloud_storage.download_bytes_from_gcs(setup_audio_gcs_uri))
  response_duration_sec = audio_operations.get_wav_duration_sec(
    cloud_storage.download_bytes_from_gcs(response_audio_gcs_uri))
  punchline_duration_sec = audio_operations.get_wav_duration_sec(
    cloud_storage.download_bytes_from_gcs(punchline_audio_gcs_uri))

  response_start_sec = setup_duration_sec + _JOKE_AUDIO_RESPONSE_GAP_SEC
  punchline_start_sec = response_start_sec + response_duration_sec + _JOKE_AUDIO_PUNCHLINE_GAP_SEC
  total_duration_sec = punchline_start_sec + punchline_duration_sec + 2.0

  setup_transcript = f"Hey want to hear a joke? {joke.setup_text}"
  response_transcript = "what?"
  # Note: Punchline transcript excludes laughter which is handled by audio fallback.
  punchline_transcript = joke.punchline_text

  setup_punchline_audio = [
    (setup_audio_gcs_uri, 0.0, setup_transcript,
     clip_timing.setup if clip_timing else None),
    (punchline_audio_gcs_uri, punchline_start_sec, punchline_transcript,
     clip_timing.punchline if clip_timing else None),
  ]
  response_audio = [
    (response_audio_gcs_uri, response_start_sec, response_transcript,
     clip_timing.response if clip_timing else None),
  ]

  if character_class is None:
    character_dialogs = [(None, setup_punchline_audio + response_audio)]
  else:
    character_dialogs = [
      (character_class(), setup_punchline_audio),
      (character_class(), response_audio),
    ]

  joke_id_for_filename = (joke.key or str(joke.random_id or "joke")).strip()
  if is_test:
    video_gcs_uri, video_generation_metadata = (
      gen_video.create_portrait_character_test_video(
        character_dialogs=character_dialogs,
        footer_background_gcs_uri=_JOKE_VIDEO_FOOTER_BACKGROUND_GCS_URI,
        total_duration_sec=total_duration_sec,
        output_filename_base=f"joke_video_test_{joke_id_for_filename}",
        temp_output=temp_output,
      ))
  else:
    assert setup_image_gcs_uri is not None
    assert punchline_image_gcs_uri is not None
    joke_images = [
      (setup_image_gcs_uri, 0.0),
      (punchline_image_gcs_uri, punchline_start_sec),
    ]
    video_gcs_uri, video_generation_metadata = (
      gen_video.create_portrait_character_video(
        joke_images=joke_images,
        character_dialogs=character_dialogs,
        footer_background_gcs_uri=_JOKE_VIDEO_FOOTER_BACKGROUND_GCS_URI,
        total_duration_sec=total_duration_sec,
        output_filename_base=f"joke_video_{joke_id_for_filename}",
        temp_output=temp_output,
      ))

  generation_metadata = models.GenerationMetadata()
  generation_metadata.add_generation(audio_generation_metadata)
  generation_metadata.add_generation(video_generation_metadata)
  return video_gcs_uri, generation_metadata


def generate_joke_video(
  joke: models.PunnyJoke,
  temp_output: bool = False,
  is_test: bool = False,
  script_template: list[audio_client.DialogTurn] | None = None,
  audio_model: audio_client.AudioModel | None = None,
  character_class: type[PosableCharacter] | None = PosableCat,
) -> tuple[str, models.GenerationMetadata]:
  """Generate a portrait video for a joke with synced audio."""
  if not joke.setup_text or not joke.punchline_text:
    raise ValueError("Joke must have setup_text and punchline_text")

  if not is_test:
    setup_image_url = joke.setup_image_url_upscaled or joke.setup_image_url
    punchline_image_url = (joke.punchline_image_url_upscaled
                           or joke.punchline_image_url)
    if not setup_image_url or not punchline_image_url:
      raise ValueError("Joke must have setup and punchline images")

  audio_result = generate_joke_audio(
    joke,
    temp_output=temp_output,
    script_template=script_template,
    audio_model=audio_model,
  )
  return generate_joke_video_from_audio_uris(
    joke,
    setup_audio_gcs_uri=audio_result.setup_gcs_uri,
    response_audio_gcs_uri=audio_result.response_gcs_uri,
    punchline_audio_gcs_uri=audio_result.punchline_gcs_uri,
    clip_timing=audio_result.clip_timing,
    audio_generation_metadata=audio_result.generation_metadata,
    temp_output=temp_output,
    is_test=is_test,
    character_class=character_class,
  )


def _render_dialog_turns_from_template(
  joke: models.PunnyJoke,
  turns_template: list[audio_client.DialogTurn],
) -> list[audio_client.DialogTurn]:
  """Render dialog turns from a turn template (scripts may include placeholders)."""
  if not turns_template:
    raise ValueError("script_template must have at least one dialog turn")

  rendered: list[audio_client.DialogTurn] = []
  for idx, turn in enumerate(turns_template):
    if not isinstance(turn, audio_client.DialogTurn):
      raise ValueError(f"Dialog turn template {idx + 1} is invalid: {turn}")

    template_script = (turn.script or "").strip()
    if not template_script:
      raise ValueError(
        f"Dialog turn template {idx + 1} script must be non-empty")

    try:
      rendered_script = template_script.format(
        setup_text=joke.setup_text,
        punchline_text=joke.punchline_text,
      )
    except KeyError as exc:
      raise ValueError(
        f"Dialog turn template {idx + 1} uses unsupported placeholder: {exc}"
      ) from exc

    rendered.append(
      audio_client.DialogTurn(
        voice=turn.voice,
        script=rendered_script,
        pause_sec_before=turn.pause_sec_before,
        pause_sec_after=turn.pause_sec_after,
      ))

  return rendered


def _select_audio_model_for_turns(
  turns: list[audio_client.DialogTurn], ) -> audio_client.AudioModel:
  """Select an AudioModel based on the turn voice types."""
  voices = [turn.voice for turn in turns]
  if not voices:
    raise ValueError("No dialog turns provided")

  if all(isinstance(v, gen_audio.Voice) for v in voices):
    if all(v.model is gen_audio.VoiceModel.GEMINI for v in voices):
      return audio_client.AudioModel.GEMINI_2_5_FLASH_TTS
    if all(v.model is gen_audio.VoiceModel.ELEVENLABS for v in voices):
      return audio_client.AudioModel.ELEVENLABS_ELEVEN_V3
    raise ValueError(
      "All dialog turns must use the same Voice model (GEMINI or ELEVENLABS)")

  if all(isinstance(v, str) for v in voices):
    return audio_client.AudioModel.ELEVENLABS_ELEVEN_V3

  if all(
    (isinstance(v, str) or (isinstance(v, gen_audio.Voice)
                            and v.model is gen_audio.VoiceModel.ELEVENLABS))
      for v in voices):
    return audio_client.AudioModel.ELEVENLABS_ELEVEN_V3

  raise ValueError(
    "All dialog turns must use the same voice type (all gen_audio.Voice or all voice_id strings)"
  )


def _validate_audio_model_for_turns(
  audio_model: audio_client.AudioModel,
  turns: list[audio_client.DialogTurn],
) -> None:
  voices = [turn.voice for turn in turns]
  if audio_model in (
      audio_client.AudioModel.GEMINI_2_5_FLASH_TTS,
      audio_client.AudioModel.GEMINI_2_5_PRO_TTS,
  ):
    if not voices or not all(isinstance(v, gen_audio.Voice) for v in voices):
      raise ValueError(
        f"Audio model {audio_model.value} requires gen_audio.Voice turns")
    if any(v.model is not gen_audio.VoiceModel.GEMINI for v in voices):
      raise ValueError(
        "generate_joke_audio currently supports GEMINI voices only for Gemini audio models"
      )
    return

  if audio_model == audio_client.AudioModel.ELEVENLABS_ELEVEN_V3:
    if not voices:
      raise ValueError(
        f"Audio model {audio_model.value} requires at least one dialog turn")
    if not all(
        isinstance(v, str) or (isinstance(v, gen_audio.Voice)
                               and v.model is gen_audio.VoiceModel.ELEVENLABS)
        for v in voices):
      raise ValueError(
        f"Audio model {audio_model.value} requires ELEVENLABS Voice turns or voice_id string turns"
      )
    return

  raise ValueError(f"Unsupported audio model: {audio_model.value}")


def _resolve_speakers(
  speakers: dict[str, gen_audio.Voice] | None, ) -> dict[str, gen_audio.Voice]:
  """Resolve speakers from input or defaults."""
  if not speakers:
    return {
      DEFAULT_JOKE_AUDIO_SPEAKER_1_NAME: DEFAULT_JOKE_AUDIO_SPEAKER_1_VOICE,
      DEFAULT_JOKE_AUDIO_SPEAKER_2_NAME: DEFAULT_JOKE_AUDIO_SPEAKER_2_VOICE,
    }

  normalized: dict[str, gen_audio.Voice] = {}
  for speaker, voice in speakers.items():
    speaker = str(speaker).strip()
    if not speaker or voice is None:
      raise ValueError("Speakers dict must include both speaker and voice")
    if not isinstance(voice, gen_audio.Voice):
      raise ValueError("Speakers dict voices must be gen_audio.Voice values")
    if speaker in normalized:
      raise ValueError(f"Duplicate speaker name: {speaker}")
    normalized[speaker] = voice

  if len(normalized) > 2:
    raise ValueError("Speakers supports up to 2 speakers")

  return normalized
