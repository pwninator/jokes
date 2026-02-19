"""Operations for jokes."""

from __future__ import annotations

import array
import datetime
import random
import sys
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from common import (audio_operations, audio_timing, image_generation, models,
                    utils)
from common.posable_character import MouthState, PosableCharacter, Transform
from common.posable_character_sequence import (
  PosableCharacterSequence, SequenceBooleanEvent, SequenceMouthEvent,
  SequenceSoundEvent, SequenceSubtitleEvent, SequenceTransformEvent)
from firebase_functions import logger
from functions.prompts import joke_operation_prompts
from google.cloud.firestore_v1.vector import Vector
from PIL import Image
from services import (audio_client, audio_voices, cloud_storage, firestore,
                      gen_video, image_client, image_editor,
                      mouth_event_detection)

_IMAGE_UPSCALE_FACTOR = "x2"
_HIGH_QUALITY_UPSCALE_FACTOR = "x2"

_JOKE_AUDIO_RESPONSE_GAP_SEC = 0.8
_JOKE_AUDIO_PUNCHLINE_GAP_SEC = 1.0
_JOKE_AUDIO_INTRO_LINE = "Hey... want to hear a joke?"
_LIP_SYNC_METADATA_INTRO = "animation_lip_sync_intro"
_LIP_SYNC_METADATA_SETUP = "animation_lip_sync_setup"
_LIP_SYNC_METADATA_RESPONSE = "animation_lip_sync_response"
_LIP_SYNC_METADATA_PUNCHLINE = "animation_lip_sync_punchline"
_MIN_POSITIVE_WORD_DURATION_SEC = 0.02
_MIN_SPEECH_CLIP_DURATION_SEC = 0.05

DEFAULT_JOKE_AUDIO_SPEAKER_1_NAME = "Sam"
DEFAULT_JOKE_AUDIO_SPEAKER_1_VOICE = audio_voices.Voice.GEMINI_LEDA
DEFAULT_JOKE_AUDIO_SPEAKER_2_NAME = "Riley"
DEFAULT_JOKE_AUDIO_SPEAKER_2_VOICE = audio_voices.Voice.GEMINI_PUCK

# Preferred dialog template format (turn-based). Each script may include
# {setup_text} and/or {punchline_text} placeholders.
DEFAULT_JOKE_AUDIO_TURNS_TEMPLATE: list[audio_client.DialogTurn] = [
  audio_client.DialogTurn(
    voice=DEFAULT_JOKE_AUDIO_SPEAKER_1_VOICE,
    script="[playfully] Hey!",
    pause_sec_after=1.0,
  ),
  audio_client.DialogTurn(
    voice=DEFAULT_JOKE_AUDIO_SPEAKER_1_VOICE,
    script="{setup_text}",
    pause_sec_after=1.0,
  ),
  audio_client.DialogTurn(
    voice=DEFAULT_JOKE_AUDIO_SPEAKER_2_VOICE,
    script="[curiously] I don't know. What?",
    pause_sec_after=1.0,
  ),
  audio_client.DialogTurn(
    voice=DEFAULT_JOKE_AUDIO_SPEAKER_1_VOICE,
    script="[excitedly, holding back laughter] {punchline_text}",
  ),
]

_MIME_TYPE_CONFIG: dict[str, tuple[str, str]] = {
  "image/png": ("PNG", "png"),
  "image/jpeg": ("JPEG", "jpg"),
}

# Envelope frame hop in seconds.
# Effect: lower tracks rapid peaks better; higher smooths timing and reduces CPU.
# Tune when peaks are missed because laughter pulses are very short or overly dense.
# Typical range: 0.005 to 0.030 sec.
_LAUGH_ENVELOPE_HOP_SEC = 0.01

# Smoothing window size (frames) applied to the amplitude envelope.
# Effect: higher suppresses jitter/noise but can flatten small laughs.
# Tune when detection is too noisy (increase) or too sluggish/misses weak peaks (decrease).
# Typical range: 1 to 7 frames.
_LAUGH_SMOOTH_WINDOW_FRAMES = 3

# Percentile used to estimate active-region noise floor.
# Effect: higher raises baseline and can ignore quiet laughs; lower is more sensitive.
# Tune when quiet laugh tails are dropped (decrease) or background noise triggers activity (increase).
# Typical range: 5 to 30.
_LAUGH_ACTIVE_NOISE_PERCENTILE = 15.0

# Percentile used to estimate active-region peak level.
# Effect: controls estimated dynamic range; higher is less affected by mid-level energy.
# Tune when dynamic range estimation is unstable across recordings.
# Typical range: 85 to 99.
_LAUGH_ACTIVE_PEAK_PERCENTILE = 95.0

# Fraction of dynamic range added above noise floor for activity threshold.
# Effect: higher requires stronger energy to consider audio "active."
# Tune when initial/trailing silence leaks into activity (increase) or weak laughs are missed (decrease).
# Typical range: 0.05 to 0.30.
_LAUGH_ACTIVE_THRESHOLD_FRACTION = 0.12

# Absolute minimum amplitude delta added above noise floor for activity threshold.
# Effect: floor guardrail against very low-level hum being marked active.
# Tune when low-level noise still creates fake activity (increase) or quiet files detect nothing (decrease).
# Typical range: 100 to 2000 (16-bit PCM amplitude units).
_LAUGH_ACTIVE_MIN_DELTA = 300.0

# Window (seconds) around a candidate peak used to find local valleys for prominence.
# Effect: larger window measures prominence against broader context, reducing micro-peaks.
# Tune when tiny ripples are over-counted (increase) or close laugh syllables collapse (decrease).
# Typical range: 0.08 to 0.40 sec.
_LAUGH_LOCAL_VALLEY_WINDOW_SEC = 0.20

# Minimum prominence as fraction of estimated dynamic range.
# Effect: higher keeps only stronger peaks; lower allows weaker pulses.
# Tune when decaying laugh tails are missed (decrease) or noise peaks slip in (increase).
# Typical range: 0.03 to 0.35.
_LAUGH_MIN_PROMINENCE_FRACTION = 0.10

# Absolute minimum prominence in amplitude units.
# Effect: hard floor so tiny fluctuations are never considered peaks.
# Tune when quiet recordings need more sensitivity (decrease) or noisy clips need stricter filtering (increase).
# Typical range: 50 to 3000 (16-bit PCM amplitude units).
_LAUGH_MIN_PROMINENCE_ABS = 250.0

# Minimum allowed spacing between accepted peaks.
# Effect: higher merges nearby peaks; lower captures rapid "ha-ha" bursts.
# Tune when peak count is too high from double-detections (increase) or too low for fast laughter (decrease).
# Typical range: 0.05 to 0.35 sec.
_LAUGH_MIN_PEAK_SPACING_SEC = 0.10


@dataclass(frozen=True)
class JokeAudioTiming:
  """Optional per-clip timing metadata for mouth animation."""

  intro: list[audio_timing.WordTiming] | None = None
  setup: list[audio_timing.WordTiming] | None = None
  response: list[audio_timing.WordTiming] | None = None
  punchline: list[audio_timing.WordTiming] | None = None


@dataclass(frozen=True)
class JokeAudioResult:
  """Result of generating joke audio (full dialog + split clips)."""

  dialog_gcs_uri: str
  intro_gcs_uri: str | None
  setup_gcs_uri: str | None
  response_gcs_uri: str | None
  punchline_gcs_uri: str | None
  generation_metadata: models.GenerationMetadata
  clip_timing: JokeAudioTiming | None = None


@dataclass(frozen=True)
class JokeAudioTranscripts:
  """Resolved transcript text for each lip-sync segment."""

  intro: str
  setup: str
  response: str
  punchline: str


@dataclass(frozen=True)
class JokeLipSyncResult:
  """Resolved joke audio clips + lip-sync sequences."""

  dialog_gcs_uri: str
  intro_audio_gcs_uri: str | None
  setup_audio_gcs_uri: str | None
  response_audio_gcs_uri: str | None
  punchline_audio_gcs_uri: str | None
  transcripts: JokeAudioTranscripts
  intro_sequence: PosableCharacterSequence | None
  setup_sequence: PosableCharacterSequence | None
  response_sequence: PosableCharacterSequence | None
  punchline_sequence: PosableCharacterSequence | None
  audio_generation_metadata: models.GenerationMetadata | None
  partial_error: str | None = None


@dataclass(frozen=True)
class JokeVideoResult:
  """Result payload for joke video generation."""

  video_gcs_uri: str | None
  dialog_audio_gcs_uri: str | None
  intro_audio_gcs_uri: str | None
  setup_audio_gcs_uri: str | None
  response_audio_gcs_uri: str | None
  punchline_audio_gcs_uri: str | None
  audio_generation_metadata: models.GenerationMetadata | None
  video_generation_metadata: models.GenerationMetadata
  error: str | None = None
  error_stage: str | None = None


class JokeOperationsError(Exception):
  """Base exception for joke operation failures."""


class JokeNotFoundError(JokeOperationsError):
  """Exception raised when a requested joke cannot be found."""


class JokePopulationError(JokeOperationsError):
  """Exception raised for errors in joke population."""


SafetyCheckError = joke_operation_prompts.SafetyCheckError


def _create_video_character(
  character_def_id: str,
  *,
  role_name: str,
) -> PosableCharacter:
  """Build a video character from a Firestore character definition ID."""
  resolved_character_def_id = (character_def_id or "").strip()
  if not resolved_character_def_id:
    raise ValueError(f"{role_name} character definition ID is required")
  character_def = firestore.get_posable_character_def(
    resolved_character_def_id)
  if character_def is None:
    raise ValueError(f"{role_name} posable character definition not found: " +
                     resolved_character_def_id)
  return PosableCharacter.from_def(character_def)


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
    joke.seasonal = seasonal
  if tags is not None:
    if isinstance(tags, str):
      joke.tags = [t.strip() for t in tags.split(',') if t.strip()]
    else:
      joke.tags = [t.strip() for t in tags if t.strip()]
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
  setup_suggestion: str | None,
  punchline_suggestion: str | None,
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
  if not joke.setup_image_description or not joke.punchline_image_description:
    raise JokePopulationError('Joke image description generation failed')

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
  update_data: dict[str, object] = {}

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
  _ = firestore.update_punny_joke(joke_id, update_data)

  return joke


def _process_upscale_for_image(
  *,
  joke: models.PunnyJoke,
  image_role: Literal["setup", "punchline"],
  client: image_client.ImageClient[object],
  mime_type: Literal["image/png", "image/jpeg"],
  compression_quality: int | None,
  upscale_factor: Literal["x2", "x4"],
  replace_original: bool,
) -> dict[str, object]:
  """Upscale a single image (setup or punchline) and return updated fields."""
  match image_role:
    case "setup":
      source_url = joke.setup_image_url
      upscaled_attr = "setup_image_url_upscaled"
      all_urls_attr = "all_setup_image_urls"
    case "punchline":
      source_url = joke.punchline_image_url
      upscaled_attr = "punchline_image_url_upscaled"
      all_urls_attr = "all_punchline_image_urls"

  if not source_url:
    return {}

  gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(source_url)
  upscaled_image = client.upscale_image(
    upscale_factor=upscale_factor,
    mime_type=mime_type,
    compression_quality=compression_quality,
    gcs_uri=gcs_uri,
  )

  if image_role == "setup":
    joke.setup_image_url_upscaled = upscaled_image.url_upscaled
  else:
    joke.punchline_image_url_upscaled = upscaled_image.url_upscaled
  joke.generation_metadata.add_generation(upscaled_image.generation_metadata)

  update_data: dict[str, object] = {upscaled_attr: upscaled_image.url_upscaled}

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
    match image_role:
      case "setup":
        joke.set_setup_image(replacement_image, update_text=False)
        update_data["setup_image_url"] = joke.setup_image_url
      case "punchline":
        joke.set_punchline_image(replacement_image, update_text=False)
        update_data["punchline_image_url"] = joke.punchline_image_url

    update_data[all_urls_attr] = getattr(joke, all_urls_attr)

  return update_data


def _get_image_dimensions(gcs_uri: str) -> tuple[int, int]:
  """Load image dimensions from GCS."""
  with Image.open(BytesIO(
      cloud_storage.download_bytes_from_gcs(gcs_uri))) as img:
    return img.width, img.height


def _create_downscaled_image(
  *,
  joke: models.PunnyJoke,
  image_role: str,
  editor: image_editor.ImageEditor,
  target_dimensions: tuple[int, int],
  mime_type: Literal["image/png", "image/jpeg"],
  compression_quality: int | None,
  upscaled_image_gcs_uri: str,
) -> tuple[str, str]:
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
  _ = cloud_storage.upload_bytes_to_gcs(
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
  save_kwargs: dict[str, int | bool] = {}

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
  search_data = search_doc.to_dict() or {} if search_doc.exists else {}

  update_payload: dict[str, object] = {}

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
    _ = search_doc_ref.set(update_payload, merge=True)


def to_response_joke(joke: models.PunnyJoke) -> dict[str, object]:
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
  """Generate a full dialog WAV plus split clips.

  Flow:
  - Generate a single multi-speaker dialog WAV and keep its returned GCS URI.
  - Download the dialog WAV bytes for splitting.
  - Split the WAV into 4 clips: intro, setup, response, and punchline.
  - Upload all 4 clips and return their GCS URIs, plus generation metadata from
    the TTS call.

  If allow_partial is True and timing/splitting fails, returns the full
  dialog WAV (dialog_gcs_uri) and leaves split clip URIs and clip timing as
  None.
  """
  if not joke.setup_text or not joke.punchline_text:
    raise ValueError("Joke must have setup_text and punchline_text")

  joke_id_for_filename = (joke.key or str(joke.random_id) or "joke").strip()
  turns_template = script_template or DEFAULT_JOKE_AUDIO_TURNS_TEMPLATE
  dialog_turns = _render_dialog_turns_from_template(joke, turns_template)
  resolved_audio_model = audio_model or _select_audio_model_for_turns(
    dialog_turns)
  _validate_audio_model_for_turns(resolved_audio_model, dialog_turns)

  if resolved_audio_model == audio_client.AudioModel.ELEVENLABS_ELEVEN_V3:
    # `generate_joke_audio` expects a WAV so we can split on silences.
    client = audio_client.get_audio_client(
      label="generate_joke_audio",
      model=resolved_audio_model,
      output_format="wav_24000",
    )
  else:
    client = audio_client.get_audio_client(
      label="generate_joke_audio",
      model=resolved_audio_model,
    )
  audio_result = client.generate_multi_turn_dialog(
    turns=dialog_turns,
    output_filename_base=f"joke_dialog_{joke_id_for_filename}",
    temp_output=temp_output,
    label="generate_joke_audio",
    extra_log_data={
      "joke_id": joke.key,
      "turn_voices": [turn.voice.name for turn in dialog_turns],
    },
  )
  dialog_gcs_uri = audio_result.gcs_uri
  combined_generation_metadata = models.GenerationMetadata()
  combined_generation_metadata.add_generation(audio_result.metadata)

  dialog_wav_bytes = cloud_storage.get_and_convert_wave_bytes_from_gcs(
    dialog_gcs_uri)
  tts_timing = audio_result.timing
  if not tts_timing or not tts_timing.alignment_data:
    try:
      tts_timing, forced_alignment_metadata = client.create_forced_alignment(
        audio_bytes=dialog_wav_bytes,
        turns=dialog_turns,
        audio_filename=f"joke_dialog_{joke_id_for_filename}.wav",
      )
      combined_generation_metadata.add_generation(forced_alignment_metadata)
    except NotImplementedError:
      logger.info("Forced alignment is not supported for this audio client")
    except Exception as exc:  # pylint: disable=broad-except
      logger.warn("Forced alignment fallback failed: " + str(exc))

  timing: JokeAudioTiming | None = None
  intro_wav: bytes | None = None
  setup_wav: bytes | None = None
  response_wav: bytes | None = None
  punchline_wav: bytes | None = None

  if not tts_timing or len(tts_timing.voice_segments) != 4:
    if allow_partial:
      return JokeAudioResult(
        dialog_gcs_uri=dialog_gcs_uri,
        intro_gcs_uri=None,
        setup_gcs_uri=None,
        response_gcs_uri=None,
        punchline_gcs_uri=None,
        generation_metadata=combined_generation_metadata,
        clip_timing=None,
      )
    raise ValueError("Audio timing is required for joke audio generation")

  try:
    split_wavs, split_timing = _split_joke_dialog_wav_by_timing(
      dialog_wav_bytes,
      tts_timing,
    )
    if len(split_wavs) != 4 or len(split_timing) != 4:
      raise ValueError(
        f"Expected 4 split clips for joke audio, got {len(split_wavs)}")
    intro_wav = split_wavs[0]
    setup_wav = split_wavs[1]
    response_wav = split_wavs[2]
    punchline_wav = split_wavs[3]
    timing = JokeAudioTiming(
      intro=split_timing[0],
      setup=split_timing[1],
      response=split_timing[2],
      punchline=split_timing[3],
    )
  except Exception as exc:  # pylint: disable=broad-except
    if allow_partial:
      return JokeAudioResult(
        dialog_gcs_uri=dialog_gcs_uri,
        intro_gcs_uri=None,
        setup_gcs_uri=None,
        response_gcs_uri=None,
        punchline_gcs_uri=None,
        generation_metadata=combined_generation_metadata,
        clip_timing=None,
      )
    raise ValueError(
      f"Error splitting joke dialog WAV by timing: {exc}") from exc

  intro_gcs_uri = cloud_storage.upload_bytes_to_gcs(
    intro_wav,
    cloud_storage.get_audio_gcs_uri(
      f"joke_{joke_id_for_filename}_intro",
      "wav",
      temp=temp_output,
    ),
    content_type="audio/wav") if intro_wav else None

  setup_gcs_uri = cloud_storage.upload_bytes_to_gcs(
    setup_wav,
    cloud_storage.get_audio_gcs_uri(
      f"joke_{joke_id_for_filename}_setup",
      "wav",
      temp=temp_output,
    ),
    content_type="audio/wav")
  response_gcs_uri = cloud_storage.upload_bytes_to_gcs(
    response_wav,
    cloud_storage.get_audio_gcs_uri(
      f"joke_{joke_id_for_filename}_response",
      "wav",
      temp=temp_output,
    ),
    content_type="audio/wav")
  punchline_gcs_uri = cloud_storage.upload_bytes_to_gcs(
    punchline_wav,
    cloud_storage.get_audio_gcs_uri(
      f"joke_{joke_id_for_filename}_punchline",
      "wav",
      temp=temp_output,
    ),
    content_type="audio/wav")

  return JokeAudioResult(
    dialog_gcs_uri=dialog_gcs_uri,
    intro_gcs_uri=intro_gcs_uri,
    setup_gcs_uri=setup_gcs_uri,
    response_gcs_uri=response_gcs_uri,
    punchline_gcs_uri=punchline_gcs_uri,
    generation_metadata=combined_generation_metadata,
    clip_timing=timing,
  )


def _split_joke_dialog_wav_by_timing(
  dialog_wav_bytes: bytes,
  timing: audio_timing.TtsTiming,
) -> tuple[list[bytes], list[list[audio_timing.WordTiming]]]:
  """Split the joke dialog WAV using provider timing data.

  Returns one split clip per entry in `timing.voice_segments`, ordered by
  segment start time. Uses refined scan-and-split logic to find the exact
  silence between adjacent voiced segments to avoid bleeding or truncation.
  """
  alignment = timing.normalized_alignment or timing.alignment
  if not alignment or not timing.voice_segments:
    raise ValueError("Timing missing alignment or voice_segments")

  voice_segments = sorted(
    timing.voice_segments,
    key=lambda seg: (
      seg.start_time_seconds,
      seg.end_time_seconds,
      seg.dialogue_input_index,
      seg.word_start_index,
      seg.word_end_index,
    ),
  )
  segment_bounds: list[tuple[float, float, int, int]] = []
  n_words = len(alignment)
  for seg in voice_segments:
    word_start = max(0, min(int(seg.word_start_index), n_words))
    word_end = max(0, min(int(seg.word_end_index), n_words))
    if word_end < word_start:
      word_start, word_end = word_end, word_start
    segment_bounds.append((
      seg.start_time_seconds,
      seg.end_time_seconds,
      word_start,
      word_end,
    ))

  cut_points: list[float] = []
  for idx in range(len(segment_bounds) - 1):
    prev_end = segment_bounds[idx][1]
    next_start = segment_bounds[idx + 1][0]
    cut_points.append((prev_end + next_start) / 2.0)
  segments = audio_operations.split_audio(
    wav_bytes=dialog_wav_bytes,
    estimated_cut_points=cut_points,
    trim=True,
  )

  expected_segments = len(voice_segments)
  if len(segments) != expected_segments:
    raise ValueError(
      f"Expected {expected_segments} audio segments, got {len(segments)}")

  def _shift_words(
    words: list[audio_timing.WordTiming],
    *,
    offset_sec: float,
  ) -> list[audio_timing.WordTiming]:
    out: list[audio_timing.WordTiming] = []
    for word in words:
      start_time = max(0.0, word.start_time - offset_sec)
      end_time = max(start_time, word.end_time - offset_sec)
      out.append(
        audio_timing.WordTiming(
          word=word.word,
          start_time=start_time,
          end_time=end_time,
          char_timings=[
            # Alignment timestamps can drift slightly before clip-local 0 after
            # silence trimming; clamp to preserve valid non-negative windows.
            audio_timing.CharTiming(
              char=ch.char,
              start_time=max(0.0, ch.start_time - offset_sec),
              end_time=max(
                0.0,
                ch.start_time - offset_sec,
                ch.end_time - offset_sec,
              ),
            ) for ch in (word.char_timings or [])
          ],
        ))
    return out

  clip_bytes: list[bytes] = []
  clip_timing: list[list[audio_timing.WordTiming]] = []
  for idx, split_segment in enumerate(segments):
    _start, _end, word_start, word_end = segment_bounds[idx]
    clip_bytes.append(split_segment.wav_bytes)
    clip_timing.append(
      _shift_words(
        alignment[word_start:word_end],
        offset_sec=split_segment.offset_sec,
      ))

  _validate_split_clip_timing(
    clip_bytes=clip_bytes,
    clip_timing=clip_timing,
  )

  return clip_bytes, clip_timing


def _validate_split_clip_timing(
  *,
  clip_bytes: list[bytes],
  clip_timing: list[list[audio_timing.WordTiming]],
) -> None:
  """Validate split output before building lip-sync sequences."""
  if len(clip_bytes) != len(clip_timing):
    raise ValueError("Split audio output and timing output are misaligned")

  for clip_index, words in enumerate(clip_timing):
    spoken_words = [
      word for word in words if any(ch.isalnum() for ch in word.word)
    ]
    if not spoken_words:
      continue
    words_sample = [
      f"{word.word!r}@{word.start_time:.3f}-{word.end_time:.3f}"
      for word in spoken_words[:8]
    ]

    has_positive_word = any(
      (word.end_time - word.start_time) > _MIN_POSITIVE_WORD_DURATION_SEC
      for word in spoken_words)
    if not has_positive_word:
      raise ValueError(
        f"Split clip {clip_index} has no positive-duration spoken word timing. "
        f"spoken_words={words_sample}")


def get_joke_lip_sync_media(
  joke: models.PunnyJoke,
  *,
  temp_output: bool = False,
  script_template: list[audio_client.DialogTurn] | None = None,
  audio_model: audio_client.AudioModel | None = None,
  allow_partial: bool = False,
  use_audio_cache: bool = True,
) -> JokeLipSyncResult:
  """Resolve cached lip-sync sequences or generate new ones."""
  turns_template = script_template or DEFAULT_JOKE_AUDIO_TURNS_TEMPLATE
  dialog_turns = _render_dialog_turns_from_template(joke, turns_template)
  transcripts = _resolve_clip_transcripts(dialog_turns, joke)
  cached = None
  if use_audio_cache:
    cached = _load_cached_lip_sync_sequences(joke_id=joke.key,
                                             transcripts=transcripts)
  if cached:
    return JokeLipSyncResult(
      dialog_gcs_uri="",
      intro_audio_gcs_uri=_sequence_primary_audio_gcs_uri(cached["intro"]),
      setup_audio_gcs_uri=_sequence_primary_audio_gcs_uri(cached["setup"]),
      response_audio_gcs_uri=_sequence_primary_audio_gcs_uri(
        cached["response"]),
      punchline_audio_gcs_uri=_sequence_primary_audio_gcs_uri(
        cached["punchline"]),
      transcripts=transcripts,
      intro_sequence=cached["intro"],
      setup_sequence=cached["setup"],
      response_sequence=cached["response"],
      punchline_sequence=cached["punchline"],
      audio_generation_metadata=None,
    )
  return _generate_joke_lip_sync_sequences(
    joke=joke,
    temp_output=temp_output,
    script_template=dialog_turns,
    audio_model=audio_model,
    allow_partial=allow_partial,
    transcripts=transcripts,
  )


def _generate_joke_lip_sync_sequences(
  *,
  joke: models.PunnyJoke,
  temp_output: bool,
  script_template: list[audio_client.DialogTurn],
  audio_model: audio_client.AudioModel | None,
  allow_partial: bool,
  transcripts: JokeAudioTranscripts,
) -> JokeLipSyncResult:
  """Generate audio clips and build/store 4 lip-sync sequences."""
  audio_result = generate_joke_audio(
    joke,
    temp_output=temp_output,
    script_template=script_template,
    audio_model=audio_model,
    allow_partial=allow_partial,
  )
  if not all([
      audio_result.intro_gcs_uri, audio_result.setup_gcs_uri,
      audio_result.response_gcs_uri, audio_result.punchline_gcs_uri
  ]):
    partial_error = (
      "Generated dialog audio but could not produce all four split clips.")
    if allow_partial:
      return JokeLipSyncResult(
        dialog_gcs_uri=audio_result.dialog_gcs_uri,
        intro_audio_gcs_uri=audio_result.intro_gcs_uri,
        setup_audio_gcs_uri=audio_result.setup_gcs_uri,
        response_audio_gcs_uri=audio_result.response_gcs_uri,
        punchline_audio_gcs_uri=audio_result.punchline_gcs_uri,
        transcripts=transcripts,
        intro_sequence=None,
        setup_sequence=None,
        response_sequence=None,
        punchline_sequence=None,
        audio_generation_metadata=audio_result.generation_metadata,
        partial_error=partial_error,
      )
    raise ValueError(partial_error)
  if not audio_result.clip_timing:
    raise ValueError("Lip sync timing is required for sequence generation")
  if audio_result.clip_timing.intro is None:
    raise ValueError("Intro/setup split failed; expected 4 lip-sync segments")

  intro_sequence = _build_lipsync_sequence(
    audio_gcs_uri=audio_result.intro_gcs_uri,
    transcript=transcripts.intro,
    timing=audio_result.clip_timing.intro,
  )
  setup_sequence = _build_lipsync_sequence(
    audio_gcs_uri=audio_result.setup_gcs_uri,
    transcript=transcripts.setup,
    timing=audio_result.clip_timing.setup,
  )
  response_sequence = _build_lipsync_sequence(
    audio_gcs_uri=audio_result.response_gcs_uri,
    transcript=transcripts.response,
    timing=audio_result.clip_timing.response,
  )
  punchline_sequence = _build_lipsync_sequence(
    audio_gcs_uri=audio_result.punchline_gcs_uri,
    transcript=transcripts.punchline,
    timing=audio_result.clip_timing.punchline,
  )
  _store_lip_sync_sequences(
    joke_id=joke.key,
    intro_sequence=intro_sequence,
    setup_sequence=setup_sequence,
    response_sequence=response_sequence,
    punchline_sequence=punchline_sequence,
  )
  return JokeLipSyncResult(
    dialog_gcs_uri=audio_result.dialog_gcs_uri,
    intro_audio_gcs_uri=audio_result.intro_gcs_uri,
    setup_audio_gcs_uri=audio_result.setup_gcs_uri,
    response_audio_gcs_uri=audio_result.response_gcs_uri,
    punchline_audio_gcs_uri=audio_result.punchline_gcs_uri,
    transcripts=transcripts,
    intro_sequence=intro_sequence,
    setup_sequence=setup_sequence,
    response_sequence=response_sequence,
    punchline_sequence=punchline_sequence,
    audio_generation_metadata=audio_result.generation_metadata,
  )


def _store_lip_sync_sequences(
  *,
  joke_id: str | None,
  intro_sequence: PosableCharacterSequence,
  setup_sequence: PosableCharacterSequence,
  response_sequence: PosableCharacterSequence,
  punchline_sequence: PosableCharacterSequence,
) -> None:
  """Persist 4 lip-sync sequences; metadata update failure may orphan records."""
  for sequence in [
      intro_sequence, setup_sequence, response_sequence, punchline_sequence
  ]:
    sequence.key = utils.create_timestamped_firestore_key(sequence.transcript
                                                          or "")
    _ = firestore.upsert_posable_character_sequence(sequence)
  if not joke_id:
    return
  try:
    _ = firestore.update_punny_joke(
      joke_id,
      {},
      update_metadata={
        _LIP_SYNC_METADATA_INTRO: intro_sequence.key,
        _LIP_SYNC_METADATA_SETUP: setup_sequence.key,
        _LIP_SYNC_METADATA_RESPONSE: response_sequence.key,
        _LIP_SYNC_METADATA_PUNCHLINE: punchline_sequence.key,
      },
    )
  except Exception as exc:  # pylint: disable=broad-except
    logger.warn(
      f"Failed updating joke metadata with lip-sync IDs for {joke_id}: {exc}")


def _load_cached_lip_sync_sequences(
  *,
  joke_id: str | None,
  transcripts: JokeAudioTranscripts,
) -> dict[str, PosableCharacterSequence] | None:
  """Load cached lip-sync sequences when all IDs and transcripts match."""
  if not joke_id:
    return None
  try:
    metadata = firestore.get_joke_metadata(joke_id)
    intro_id = str(metadata.get(_LIP_SYNC_METADATA_INTRO) or "").strip()
    setup_id = str(metadata.get(_LIP_SYNC_METADATA_SETUP) or "").strip()
    response_id = str(metadata.get(_LIP_SYNC_METADATA_RESPONSE) or "").strip()
    punchline_id = str(metadata.get(_LIP_SYNC_METADATA_PUNCHLINE)
                       or "").strip()
    if not all([intro_id, setup_id, response_id, punchline_id]):
      return None
    intro_sequence = firestore.get_posable_character_sequence(intro_id)
    setup_sequence = firestore.get_posable_character_sequence(setup_id)
    response_sequence = firestore.get_posable_character_sequence(response_id)
    punchline_sequence = firestore.get_posable_character_sequence(punchline_id)
  except Exception:  # pylint: disable=broad-except
    return None
  if intro_sequence is None or setup_sequence is None or response_sequence is None or punchline_sequence is None:
    return None
  checks = [
    (intro_sequence.transcript, transcripts.intro),
    (setup_sequence.transcript, transcripts.setup),
    (response_sequence.transcript, transcripts.response),
    (punchline_sequence.transcript, transcripts.punchline),
  ]
  if any(
      _normalize_transcript_for_matching(a) !=
      _normalize_transcript_for_matching(b) for a, b in checks):
    return None
  return {
    "intro": intro_sequence,
    "setup": setup_sequence,
    "response": response_sequence,
    "punchline": punchline_sequence,
  }


def _resolve_clip_transcripts(
  dialog_turns: list[audio_client.DialogTurn],
  joke: models.PunnyJoke,
) -> JokeAudioTranscripts:
  """Resolve exact transcript text for intro/setup/response/punchline segments."""
  if len(dialog_turns) >= 4:
    return JokeAudioTranscripts(
      intro=dialog_turns[0].script,
      setup=dialog_turns[1].script,
      response=dialog_turns[2].script,
      punchline=dialog_turns[3].script,
    )
  return JokeAudioTranscripts(
    intro=_JOKE_AUDIO_INTRO_LINE,
    setup=joke.setup_text or "",
    response="what?",
    punchline=joke.punchline_text or "",
  )


def _normalize_transcript_for_matching(value: str | None) -> str:
  return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def _sequence_primary_audio_gcs_uri(
    sequence: PosableCharacterSequence | None) -> str | None:
  if sequence is None:
    return None
  if not sequence.sequence_sound_events:
    return None
  return sequence.sequence_sound_events[0].gcs_uri


def _build_lipsync_sequence(
  *,
  audio_gcs_uri: str | None,
  transcript: str,
  timing: list[audio_timing.WordTiming] | None,
) -> PosableCharacterSequence:
  """Build a lip-sync sequence for a single clip using timing data."""
  if not audio_gcs_uri:
    raise ValueError("audio_gcs_uri is required")
  sound_end = _resolve_sound_event_end_time_sec(
    audio_gcs_uri=audio_gcs_uri,
    timing=timing,
  )
  sound_events = [
    SequenceSoundEvent(
      start_time=0.0,
      end_time=sound_end,
      gcs_uri=audio_gcs_uri,
      volume=1.0,
    )
  ]
  subtitle_text = utils.strip_stage_directions(transcript)
  subtitle_events = [
    SequenceSubtitleEvent(
      start_time=0.0,
      end_time=sound_end,
      text=subtitle_text,
    )
  ] if subtitle_text else []
  mouth_events: list[SequenceMouthEvent] = []
  if timing:
    detected_events = mouth_event_detection.detect_mouth_events(
      b"",
      mode="timing",
      transcript=transcript,
      timing=timing,
    )
    for event in detected_events:
      start_time = max(0.0, event.start_time)
      end_time = min(sound_end, event.end_time)
      if end_time <= start_time:
        continue
      mouth_events.append(
        SequenceMouthEvent(
          start_time=start_time,
          end_time=end_time,
          mouth_state=event.mouth_shape,
        ))
  sequence = PosableCharacterSequence(
    transcript=transcript,
    sequence_mouth_state=mouth_events,
    sequence_sound_events=sound_events,
    sequence_subtitle_events=subtitle_events,
  )
  sequence.validate()
  return sequence


def build_laugh_sequence(
  audio_gcs_uri: str,
  laugh_translate_y: int = 10,
) -> PosableCharacterSequence:
  """Build a laughter animation sequence from audio waveform peaks."""
  resolved_audio_uri = audio_gcs_uri.strip()
  if not resolved_audio_uri:
    raise ValueError("audio_gcs_uri is required")

  try:
    audio_bytes = cloud_storage.get_and_convert_wave_bytes_from_gcs(
      resolved_audio_uri)
  except Exception as exc:  # pylint: disable=broad-except
    raise ValueError(
      f"Could not load laugh audio from {resolved_audio_uri}") from exc

  envelope, frame_hop_sec, duration_sec = _decode_wav_to_peak_envelope(
    audio_bytes)
  duration_sec = max(0.01, duration_sec)
  active_start_idx, active_end_idx, _ = _find_active_window(envelope)
  peak_times = _detect_laugh_peak_times(
    envelope=envelope,
    frame_hop_sec=frame_hop_sec,
    active_start_idx=active_start_idx,
    active_end_idx=active_end_idx,
    duration_sec=duration_sec,
  )

  sequence = PosableCharacterSequence(
    transcript="laugh",
    sequence_left_eye_open=[
      SequenceBooleanEvent(
        start_time=0.0,
        end_time=duration_sec,
        value=False,
      )
    ],
    sequence_right_eye_open=[
      SequenceBooleanEvent(
        start_time=0.0,
        end_time=duration_sec,
        value=False,
      )
    ],
    sequence_mouth_state=[
      SequenceMouthEvent(
        start_time=0.0,
        end_time=duration_sec,
        mouth_state=MouthState.OPEN,
      )
    ],
    sequence_head_transform=_build_laugh_head_transform_events(
      peak_times=peak_times,
      active_start_idx=active_start_idx,
      active_end_idx=active_end_idx,
      frame_hop_sec=frame_hop_sec,
      duration_sec=duration_sec,
      laugh_translate_y=laugh_translate_y,
    ),
    sequence_sound_events=[
      SequenceSoundEvent(
        start_time=0.0,
        end_time=duration_sec,
        gcs_uri=resolved_audio_uri,
        volume=1.0,
      )
    ],
  )
  sequence.validate()
  return sequence


def _build_laugh_head_transform_events(
  *,
  peak_times: list[float],
  active_start_idx: int,
  active_end_idx: int,
  frame_hop_sec: float,
  duration_sec: float,
  laugh_translate_y: float,
) -> list[SequenceTransformEvent]:
  """Build head transform events that bob up at peaks and return to baseline."""
  if not peak_times:
    return []

  events: list[SequenceTransformEvent] = []
  active_start_time = (0.0 if active_end_idx < active_start_idx else _to_time(
    active_start_idx,
    frame_hop_sec,
    duration_sec,
  ))
  active_end_time = (duration_sec
                     if active_end_idx < active_start_idx else _to_time(
                       active_end_idx,
                       frame_hop_sec,
                       duration_sec,
                     ))

  first_peak = max(0.0, peak_times[0])
  first_start = min(first_peak, max(0.0, active_start_time))
  if first_start >= first_peak:
    first_start = max(0.0, first_peak - max(frame_hop_sec, 0.01))
  _append_head_transform_event(
    events,
    start_time=first_start,
    end_time=first_peak,
    target_translate_y=laugh_translate_y,
  )

  for idx in range(len(peak_times) - 1):
    current_peak = peak_times[idx]
    next_peak = peak_times[idx + 1]
    midpoint = (current_peak + next_peak) / 2.0
    _append_head_transform_event(
      events,
      start_time=current_peak,
      end_time=midpoint,
      target_translate_y=0.0,
    )
    _append_head_transform_event(
      events,
      start_time=midpoint,
      end_time=next_peak,
      target_translate_y=laugh_translate_y,
    )

  last_peak = peak_times[-1]
  active_end_time = max(active_end_time, last_peak + frame_hop_sec)
  tail_midpoint = min(duration_sec, (last_peak + active_end_time) / 2.0)
  _append_head_transform_event(
    events,
    start_time=last_peak,
    end_time=tail_midpoint,
    target_translate_y=0.0,
  )
  return events


def _append_head_transform_event(
  events: list[SequenceTransformEvent],
  *,
  start_time: float,
  end_time: float,
  target_translate_y: float,
) -> None:
  start_time = max(0.0, start_time)
  end_time = max(0.0, end_time)
  if end_time <= start_time:
    return
  events.append(
    SequenceTransformEvent(
      start_time=start_time,
      end_time=end_time,
      target_transform=Transform(translate_y=target_translate_y, ),
    ))


def _decode_wav_to_peak_envelope(
  audio_bytes: bytes, ) -> tuple[list[float], float, float]:
  """Decode WAV bytes and return a smoothed per-frame amplitude envelope."""
  try:
    params, frames = audio_operations.read_wav_bytes(audio_bytes)
  except Exception as exc:  # pylint: disable=broad-except
    raise ValueError("Could not decode WAV audio for laugh sequence") from exc

  framerate = int(params.framerate)
  nframes = int(params.nframes)
  nchannels = int(params.nchannels)
  sampwidth = int(params.sampwidth)

  if framerate <= 0:
    raise ValueError("WAV framerate must be positive")
  if nframes <= 0:
    raise ValueError("WAV audio has no frames")
  if sampwidth != 2:
    raise ValueError(
      f"Unsupported WAV sample width for laugh analysis: {sampwidth}")

  samples = array.array("h")
  samples.frombytes(frames)
  if sys.byteorder == "big":
    samples.byteswap()
  if not samples:
    raise ValueError("WAV audio has no samples")

  frame_hop_samples = max(1, int(round(framerate * _LAUGH_ENVELOPE_HOP_SEC)))
  frame_hop_sec = frame_hop_samples / framerate
  samples_per_frame = max(1, frame_hop_samples * max(1, nchannels))
  total_samples = len(samples)

  envelope: list[float] = []
  frame_start = 0
  while frame_start < total_samples:
    frame_end = min(total_samples, frame_start + samples_per_frame)
    peak = 0.0
    for sample_index in range(frame_start, frame_end):
      value = abs(int(samples[sample_index]))
      if value > peak:
        peak = value
    envelope.append(peak)
    frame_start = frame_end

  if not envelope:
    raise ValueError("Could not compute laugh envelope from WAV audio")

  smoothed_envelope = _moving_average(
    envelope,
    window_frames=_LAUGH_SMOOTH_WINDOW_FRAMES,
  )
  duration_sec = nframes / framerate
  return smoothed_envelope, frame_hop_sec, duration_sec


def _find_active_window(envelope: list[float]) -> tuple[int, int, float]:
  """Find the start/end frame indices containing non-silent laugh activity."""
  if not envelope:
    return 0, -1, 0.0

  noise_floor = _percentile(envelope, _LAUGH_ACTIVE_NOISE_PERCENTILE)
  peak_level = _percentile(envelope, _LAUGH_ACTIVE_PEAK_PERCENTILE)
  dynamic_range = max(1.0, peak_level - noise_floor)
  threshold = max(
    noise_floor + (dynamic_range * _LAUGH_ACTIVE_THRESHOLD_FRACTION),
    noise_floor + _LAUGH_ACTIVE_MIN_DELTA,
  )

  active_indices = [
    idx for idx, value in enumerate(envelope) if value >= threshold
  ]
  if not active_indices:
    return 0, -1, threshold
  return min(active_indices), max(active_indices), threshold


def _detect_laugh_peak_times(
  *,
  envelope: list[float],
  frame_hop_sec: float,
  active_start_idx: int,
  active_end_idx: int,
  duration_sec: float,
) -> list[float]:
  """Detect dominant laugh peaks across changing amplitude levels."""
  if not envelope or active_end_idx < active_start_idx:
    return []

  active_values = envelope[active_start_idx:active_end_idx + 1]
  if not active_values:
    return []

  noise_floor = _percentile(active_values, _LAUGH_ACTIVE_NOISE_PERCENTILE)
  peak_level = _percentile(active_values, _LAUGH_ACTIVE_PEAK_PERCENTILE)
  dynamic_range = max(1.0, peak_level - noise_floor)
  min_prominence = max(
    dynamic_range * _LAUGH_MIN_PROMINENCE_FRACTION,
    _LAUGH_MIN_PROMINENCE_ABS,
  )
  valley_window_frames = max(
    1, int(round(_LAUGH_LOCAL_VALLEY_WINDOW_SEC / max(frame_hop_sec, 1e-6))))

  peak_candidates: list[int] = []
  for idx in range(active_start_idx, active_end_idx + 1):
    current = envelope[idx]
    previous = envelope[idx - 1] if idx > 0 else current
    following = envelope[idx + 1] if idx < (len(envelope) - 1) else current
    is_local_peak = current >= previous and current > following
    if not is_local_peak or current <= noise_floor:
      continue

    left_start = max(active_start_idx, idx - valley_window_frames)
    right_end = min(active_end_idx, idx + valley_window_frames)
    left_valley = min(v for v in envelope[left_start:idx + 1])
    right_valley = min(v for v in envelope[idx:right_end + 1])
    prominence = current - max(left_valley, right_valley)
    if prominence >= min_prominence:
      peak_candidates.append(idx)

  min_spacing_frames = max(
    1, int(round(_LAUGH_MIN_PEAK_SPACING_SEC / max(frame_hop_sec, 1e-6))))
  peak_indices = _coalesce_peaks_with_min_spacing(
    peak_candidates,
    envelope=envelope,
    min_spacing_frames=min_spacing_frames,
  )

  if not peak_indices:
    strongest_idx = max(
      range(active_start_idx, active_end_idx + 1),
      key=lambda idx: envelope[idx],
    )
    peak_indices = [int(strongest_idx)]

  return [
    _to_time(idx, frame_hop_sec, duration_sec) for idx in sorted(peak_indices)
  ]


def _coalesce_peaks_with_min_spacing(
  peak_indices: list[int],
  *,
  envelope: list[float],
  min_spacing_frames: int,
) -> list[int]:
  """Keep strongest peaks while enforcing minimum spacing in frames."""
  if not peak_indices:
    return []
  spacing = max(1, int(min_spacing_frames))
  unique_peaks = sorted(set(int(idx) for idx in peak_indices))
  by_strength = sorted(unique_peaks, key=lambda idx: (-envelope[idx], idx))
  selected: list[int] = []
  for candidate in by_strength:
    if all(
        abs(int(candidate) - int(chosen)) >= spacing for chosen in selected):
      selected.append(int(candidate))
  return sorted(selected)


def _to_time(
  frame_index: int,
  frame_hop_sec: float,
  duration_sec: float,
) -> float:
  """Convert frame index to clip time (seconds)."""
  center_time = (frame_index + 0.5) * frame_hop_sec
  return min(duration_sec, max(0.0, center_time))


def _moving_average(values: list[float], *, window_frames: int) -> list[float]:
  """Return centered moving-average smoothed values."""
  if not values:
    return []
  if window_frames <= 1:
    return list(values)
  half_window = max(0, int(window_frames) // 2)
  smoothed: list[float] = []
  for idx in range(len(values)):
    start = max(0, idx - half_window)
    end = min(len(values), idx + half_window + 1)
    subset = values[start:end]
    smoothed.append(sum(subset) / len(subset))
  return smoothed


def _percentile(values: list[float], percentile: float) -> float:
  """Compute percentile using linear interpolation between nearest ranks."""
  if not values:
    return 0.0
  ordered = sorted(values)
  if len(ordered) == 1:
    return ordered[0]
  p = max(0.0, min(100.0, percentile))
  position = (p / 100.0) * (len(ordered) - 1)
  lower_index = int(position)
  upper_index = min(len(ordered) - 1, lower_index + 1)
  lower_value = ordered[lower_index]
  upper_value = ordered[upper_index]
  weight = position - lower_index
  return (lower_value * (1.0 - weight)) + (upper_value * weight)


def _resolve_sound_event_end_time_sec(
  *,
  audio_gcs_uri: str,
  timing: list[audio_timing.WordTiming] | None,
) -> float:
  """Return sound event end time, preferring actual audio duration."""
  audio_duration_sec = _get_audio_duration_sec_from_gcs(audio_gcs_uri)
  if audio_duration_sec is not None:
    return max(0.01, audio_duration_sec)
  return max(0.01, _timing_duration_sec(timing))


def _get_audio_duration_sec_from_gcs(audio_gcs_uri: str) -> float | None:
  """Load clip bytes and compute duration (seconds), or None on failure."""
  try:
    audio_bytes = cloud_storage.get_and_convert_wave_bytes_from_gcs(
      audio_gcs_uri)
    duration_sec = audio_operations.get_wav_duration_sec(audio_bytes)
    if duration_sec <= 0:
      return None
    return duration_sec
  except Exception as exc:  # pylint: disable=broad-except
    logger.warn(f"Falling back to timing duration for {audio_gcs_uri}: "
                f"could not read audio duration ({exc})")
    return None


def _timing_duration_sec(
    timing: list[audio_timing.WordTiming] | None) -> float:
  if not timing:
    return 0.01
  latest_end = 0.0
  for word_timing in timing:
    latest_end = max(latest_end, word_timing.end_time)
  return latest_end


def _validate_sequence_ready_for_video(
  *,
  label: str,
  sequence: PosableCharacterSequence,
) -> None:
  """Validate a speaking sequence before composing the final video script."""
  if not sequence.sequence_sound_events:
    raise ValueError(f"{label} sequence is missing sound events")
  primary_sound = sequence.sequence_sound_events[0]
  sound_duration_sec = max(0.0,
                           primary_sound.end_time - primary_sound.start_time)

  transcript = sequence.transcript or ""
  spoken_tokens = [
    token for token in transcript.split() if any(ch.isalnum() for ch in token)
  ]
  if len(spoken_tokens) < 3:
    return
  transcript_sample = " ".join(spoken_tokens[:12])
  primary_sound_data = (
    f"{primary_sound.start_time:.3f}-{primary_sound.end_time:.3f} "
    f"uri={primary_sound.gcs_uri}")

  if sound_duration_sec < _MIN_SPEECH_CLIP_DURATION_SEC:
    raise ValueError(
      f"{label} sequence sound duration is implausibly short ({sound_duration_sec:.3f}s). "
      f"sound_event={primary_sound_data} transcript_sample={transcript_sample!r}"
    )

  has_positive_mouth_event = any(
    (event.end_time - event.start_time) > _MIN_POSITIVE_WORD_DURATION_SEC
    for event in sequence.sequence_mouth_state)
  if not has_positive_mouth_event:
    raise ValueError(
      f"{label} sequence has spoken transcript but no usable mouth events. "
      f"sound_event={primary_sound_data} transcript_sample={transcript_sample!r}"
    )


def generate_joke_video(
  joke: models.PunnyJoke,
  teller_character_def_id: str,
  listener_character_def_id: str | None = None,
  temp_output: bool = False,
  script_template: list[audio_client.DialogTurn] | None = None,
  audio_model: audio_client.AudioModel | None = None,
  allow_partial: bool = False,
  use_audio_cache: bool = True,
) -> JokeVideoResult:
  """Generate joke video using cached or newly-generated lip-sync sequences."""
  if not joke.setup_text or not joke.punchline_text:
    raise ValueError("Joke must have setup_text and punchline_text")

  setup_image_url = joke.setup_image_url_upscaled or joke.setup_image_url
  punchline_image_url = (joke.punchline_image_url_upscaled
                         or joke.punchline_image_url)
  if not setup_image_url or not punchline_image_url:
    raise ValueError("Joke must have setup and punchline images")
  setup_image_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    setup_image_url)
  punchline_image_gcs_uri = cloud_storage.extract_gcs_uri_from_image_url(
    punchline_image_url)
  turns_template = script_template or DEFAULT_JOKE_AUDIO_TURNS_TEMPLATE
  rendered_turns = _render_dialog_turns_from_template(joke, turns_template)
  teller_voice, listener_voice = _resolve_joke_video_voices(rendered_turns)
  teller_character = _create_video_character(
    teller_character_def_id,
    role_name="Teller",
  )

  lip_sync = get_joke_lip_sync_media(
    joke=joke,
    temp_output=temp_output,
    script_template=turns_template,
    audio_model=audio_model,
    allow_partial=allow_partial,
    use_audio_cache=use_audio_cache,
  )
  generation_metadata = models.GenerationMetadata()
  generation_metadata.add_generation(lip_sync.audio_generation_metadata)

  if lip_sync.partial_error:
    return JokeVideoResult(
      video_gcs_uri=None,
      dialog_audio_gcs_uri=lip_sync.dialog_gcs_uri,
      intro_audio_gcs_uri=lip_sync.intro_audio_gcs_uri,
      setup_audio_gcs_uri=lip_sync.setup_audio_gcs_uri,
      response_audio_gcs_uri=lip_sync.response_audio_gcs_uri,
      punchline_audio_gcs_uri=lip_sync.punchline_audio_gcs_uri,
      audio_generation_metadata=lip_sync.audio_generation_metadata,
      video_generation_metadata=generation_metadata,
      error=lip_sync.partial_error,
      error_stage="audio_split",
    )

  if (lip_sync.setup_sequence is None or lip_sync.punchline_sequence is None
      or lip_sync.setup_audio_gcs_uri is None
      or lip_sync.punchline_audio_gcs_uri is None):
    raise ValueError("Missing required setup/punchline lip-sync data")
  setup_sequence = lip_sync.setup_sequence
  punchline_sequence = lip_sync.punchline_sequence
  has_listener = lip_sync.response_sequence is not None
  if lip_sync.intro_sequence is not None:
    _validate_sequence_ready_for_video(
      label="intro",
      sequence=lip_sync.intro_sequence,
    )
  _validate_sequence_ready_for_video(
    label="setup",
    sequence=setup_sequence,
  )
  if lip_sync.response_sequence is not None:
    _validate_sequence_ready_for_video(
      label="response",
      sequence=lip_sync.response_sequence,
    )
  _validate_sequence_ready_for_video(
    label="punchline",
    sequence=punchline_sequence,
  )

  listener_character = None
  if has_listener:
    if not listener_character_def_id:
      raise ValueError("Listener character definition ID is required")
    listener_character = _create_video_character(
      listener_character_def_id,
      role_name="Listener",
    )
  video_gcs_uri, video_generation_metadata = gen_video.create_portrait_character_video(
    setup_image_gcs_uri=setup_image_gcs_uri,
    punchline_image_gcs_uri=punchline_image_gcs_uri,
    teller_character=teller_character,
    teller_voice=teller_voice,
    listener_character=listener_character,
    listener_voice=listener_voice if has_listener else None,
    intro_sequence=lip_sync.intro_sequence,
    setup_sequence=setup_sequence,
    response_sequence=lip_sync.response_sequence,
    punchline_sequence=punchline_sequence,
    output_filename_base=
    f"joke_video_{(joke.key or '{}'.format(joke.random_id or 'joke')).strip()}",
    temp_output=temp_output,
  )
  generation_metadata.add_generation(video_generation_metadata)
  return JokeVideoResult(
    video_gcs_uri=video_gcs_uri,
    dialog_audio_gcs_uri=lip_sync.dialog_gcs_uri,
    intro_audio_gcs_uri=lip_sync.intro_audio_gcs_uri,
    setup_audio_gcs_uri=lip_sync.setup_audio_gcs_uri,
    response_audio_gcs_uri=lip_sync.response_audio_gcs_uri,
    punchline_audio_gcs_uri=lip_sync.punchline_audio_gcs_uri,
    audio_generation_metadata=lip_sync.audio_generation_metadata,
    video_generation_metadata=generation_metadata,
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


def _resolve_joke_video_voices(
  turns: list[audio_client.DialogTurn],
) -> tuple[audio_voices.Voice, audio_voices.Voice]:
  """Resolve teller/listener voices from ordered rendered dialog turns."""
  if not turns:
    raise ValueError("At least one rendered dialog turn is required")

  distinct_voices: list[audio_voices.Voice] = []
  for turn in turns:
    if turn.voice not in distinct_voices:
      distinct_voices.append(turn.voice)

  teller_voice = distinct_voices[0]
  listener_voice = (distinct_voices[1]
                    if len(distinct_voices) > 1 else distinct_voices[0])
  return teller_voice, listener_voice


def _select_audio_model_for_turns(
  turns: list[audio_client.DialogTurn], ) -> audio_client.AudioModel:
  """Select an AudioModel based on the turn voice types."""
  voices = [turn.voice for turn in turns]
  if not voices:
    raise ValueError("No dialog turns provided")

  if all(v.model is audio_voices.VoiceModel.GEMINI for v in voices):
    return audio_client.AudioModel.GEMINI_2_5_FLASH_TTS
  if all(v.model is audio_voices.VoiceModel.ELEVENLABS for v in voices):
    return audio_client.AudioModel.ELEVENLABS_ELEVEN_V3

  raise ValueError(
    "All dialog turns must use the same Voice model (GEMINI or ELEVENLABS)")


def _validate_audio_model_for_turns(
  audio_model: audio_client.AudioModel,
  turns: list[audio_client.DialogTurn],
) -> None:
  voices = [turn.voice for turn in turns]
  if audio_model in (
      audio_client.AudioModel.GEMINI_2_5_FLASH_TTS,
      audio_client.AudioModel.GEMINI_2_5_PRO_TTS,
  ):
    if not voices:
      raise ValueError(f"Audio model {audio_model.value} requires Voice turns")
    if any(v.model is not audio_voices.VoiceModel.GEMINI for v in voices):
      raise ValueError(
        "generate_joke_audio currently supports GEMINI voices only for Gemini audio models"
      )
    return

  if audio_model == audio_client.AudioModel.ELEVENLABS_ELEVEN_V3:
    if not voices:
      raise ValueError(
        f"Audio model {audio_model.value} requires at least one dialog turn")
    if not all(v.model is audio_voices.VoiceModel.ELEVENLABS for v in voices):
      raise ValueError(
        f"Audio model {audio_model.value} requires ELEVENLABS Voice turns")
    return
