"""Operations for jokes."""

from __future__ import annotations

import array
import datetime
import io
import random
import wave
from io import BytesIO
from typing import Any, Literal, Tuple

from common import image_generation, models
from firebase_functions import logger
from functions.prompts import joke_operation_prompts
from google.cloud.firestore_v1.vector import Vector
from PIL import Image
from services import (cloud_storage, firestore, gen_audio, image_client,
                      image_editor)

_IMAGE_UPSCALE_FACTOR = "x2"
_HIGH_QUALITY_UPSCALE_FACTOR = "x2"

_MIME_TYPE_CONFIG: dict[str, Tuple[str, str]] = {
  "image/png": ("PNG", "png"),
  "image/jpeg": ("JPEG", "jpg"),
}


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
) -> tuple[str, str, str, str, models.SingleGenerationMetadata]:
  """Generate a full dialog WAV plus split clips and upload as public files.

  Flow:
  - Generate a single multi-speaker dialog WAV in the *temp* bucket.
  - Upload the full dialog WAV to the public audio bucket.
  - Split the WAV on the two ~1s silent pauses into 3 clips:
    setup, response ("what?"), punchline (including giggles).
  - Upload all 3 clips to the public audio bucket and return their GCS URIs,
    plus the generation metadata from the TTS call.
  """
  if not joke.setup_text or not joke.punchline_text:
    raise ValueError("Joke must have setup_text and punchline_text")

  joke_id_for_filename = (joke.key or str(joke.random_id or "joke")).strip()
  script = _build_kid_dialog_script(joke)

  temp_dialog_gcs_uri, audio_generation_metadata = (
    gen_audio.generate_multi_turn_dialog(
      script=script,
      speakers={
        "Sam": "Leda",  # Youthful
        "Riley": "Puck",  # Upbeat
      },
      output_filename_base=f"joke_dialog_{joke_id_for_filename}",
      temp_output=True,
    ))

  dialog_wav_bytes = cloud_storage.download_bytes_from_gcs(temp_dialog_gcs_uri)
  setup_wav, response_wav, punchline_wav = _split_wav_bytes_on_two_pauses(
    dialog_wav_bytes,
    silence_duration_sec=1.0,
  )

  dialog_gcs_uri = cloud_storage.get_audio_gcs_uri(
    f"joke_{joke_id_for_filename}_dialog",
    "wav",
  )
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

  cloud_storage.upload_bytes_to_gcs(dialog_wav_bytes,
                                    dialog_gcs_uri,
                                    content_type="audio/wav")
  cloud_storage.upload_bytes_to_gcs(setup_wav,
                                    setup_gcs_uri,
                                    content_type="audio/wav")
  cloud_storage.upload_bytes_to_gcs(response_wav,
                                    response_gcs_uri,
                                    content_type="audio/wav")
  cloud_storage.upload_bytes_to_gcs(punchline_wav,
                                    punchline_gcs_uri,
                                    content_type="audio/wav")

  return (dialog_gcs_uri, setup_gcs_uri, response_gcs_uri, punchline_gcs_uri,
          audio_generation_metadata)


def _build_kid_dialog_script(joke: models.PunnyJoke) -> str:
  """Build a Gemini TTS prompt for a 2-kid dialog with exact pauses."""
  # The Gemini TTS models generally follow this kind of "director + transcript"
  # structure (see docs). We keep the transcript speaker-labeled and ask the
  # model to only speak the transcript portion.
  return f"""You are generating audio. DO NOT speak any instructions.
ONLY speak the lines under TRANSCRIPT, using the specified speakers.

AUDIO PROFILE:
- Two 8-year-old kids on a school playground at recess.
- Natural, clear kid voices. Light and playful.

TRANSCRIPT:
Sam: [playfully, slightly slowly to build intrigue] Hey... want to hear a joke? {joke.setup_text}
[1 second silence]
Riley: [curiously] what?
[1 second silence]
Sam: [excitedly, holding back laughter] {joke.punchline_text}
Riley: [giggles]
"""


def _split_wav_bytes_on_two_pauses(
  wav_bytes: bytes,
  *,
  silence_duration_sec: float,
) -> tuple[bytes, bytes, bytes]:
  """Split a WAV into 3 clips using the first two interior long silent runs."""
  params, frames = _read_wav_bytes(wav_bytes)
  frame_size_bytes = int(params.nchannels) * int(params.sampwidth)
  silence_frames = max(
    1, int(round(int(params.framerate) * silence_duration_sec)))

  silent_frames_mask = _compute_silent_frame_mask(
    frames,
    params=params,
    silence_abs_amplitude_threshold=250,
  )
  runs = _find_silent_runs(silent_frames_mask, min_run_frames=silence_frames)

  # Prefer pauses between utterances, not leading/trailing.
  nframes = int(params.nframes)
  interior_runs = [(start, end) for start, end in runs
                   if start > 0 and end < nframes]
  if len(interior_runs) < 2:
    raise ValueError(
      f"Expected at least 2 interior silence runs of ~{silence_duration_sec}s; found {len(interior_runs)}"
    )

  (run1_start, run1_end), (run2_start,
                           run2_end) = interior_runs[0], interior_runs[1]
  if not (0 <= run1_start < run1_end <= run2_start < run2_end <= nframes):
    raise ValueError("Detected silence runs are not ordered as expected")

  setup_frames = frames[:run1_start * frame_size_bytes]
  response_frames = frames[run1_end * frame_size_bytes:run2_start *
                           frame_size_bytes]
  punchline_frames = frames[run2_end * frame_size_bytes:]

  if not setup_frames or not response_frames or not punchline_frames:
    raise ValueError("Split produced an empty clip")

  return (
    _write_wav_bytes(params=params, frames=setup_frames),
    _write_wav_bytes(params=params, frames=response_frames),
    _write_wav_bytes(params=params, frames=punchline_frames),
  )


def _read_wav_bytes(wav_bytes: bytes) -> tuple[Any, bytes]:
  """Parse WAV bytes into (params, raw PCM frame bytes)."""
  with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
    # pylint: disable=no-member
    params = wf.getparams()
    nframes = wf.getnframes()
    frames = wf.readframes(nframes)
    # pylint: enable=no-member

  if getattr(params, "comptype", None) != "NONE":
    raise ValueError(
      f"Unsupported WAV compression: {getattr(params, 'comptype', None)}")

  expected_len = int(params.nframes) * int(params.nchannels) * int(
    params.sampwidth)
  if expected_len and len(frames) != expected_len:
    raise ValueError(
      f"Unexpected WAV frame byte length: expected={expected_len} got={len(frames)}"
    )
  return params, frames


def _write_wav_bytes(*, params: Any, frames: bytes) -> bytes:
  """Write WAV bytes from params + raw frame bytes."""
  buffer = io.BytesIO()
  with wave.open(buffer, "wb") as wf:
    # pylint: disable=no-member
    wf.setnchannels(int(params.nchannels))
    wf.setsampwidth(int(params.sampwidth))
    wf.setframerate(int(params.framerate))
    wf.writeframes(frames)
    # pylint: enable=no-member
  return buffer.getvalue()


def _compute_silent_frame_mask(
  frames: bytes,
  *,
  params: Any,
  silence_abs_amplitude_threshold: int,
) -> list[bool]:
  """Return a per-frame boolean mask for silence detection.

  This is intentionally lightweight (stdlib only). We treat a frame as silent
  when its peak absolute amplitude is below an adaptive threshold derived from
  the audio itself. This is more robust than a fixed threshold when "silence"
  contains quiet room tone.
  """
  nchannels = int(params.nchannels)
  sampwidth = int(params.sampwidth)
  nframes = int(params.nframes)

  frame_size_bytes = nchannels * sampwidth
  if nframes == 0:
    return []
  if len(frames) != nframes * frame_size_bytes:
    raise ValueError("Frame byte length does not match WAV params")

  # Gemini output is LINEAR16 (signed int16). Support that robustly.
  if sampwidth == 2:
    import sys

    samples = array.array("h")
    samples.frombytes(frames)
    if sys.byteorder == "big":
      # WAV PCM is little-endian. Ensure consistent interpretation.
      samples.byteswap()

    # Compute a per-frame peak amplitude.
    peaks: list[int] = [0] * nframes
    sample_index = 0
    for frame_index in range(nframes):
      peak = 0
      for _ch in range(nchannels):
        sample = samples[sample_index]
        sample_index += 1
        value = abs(int(sample))
        if value > peak:
          peak = value
      peaks[frame_index] = peak

    # Adaptive threshold: sample peaks to estimate noise floor.
    step = max(1, nframes // 5000)
    sampled = [peaks[i] for i in range(0, nframes, step)]
    sampled.sort()
    if not sampled:
      return [True] * nframes

    def percentile(p: float) -> int:
      idx = int(round((len(sampled) - 1) * p))
      idx = max(0, min(idx, len(sampled) - 1))
      return int(sampled[idx])

    p10 = percentile(0.10)
    p50 = percentile(0.50)

    # If the file has long quiet regions, p10 approximates the noise floor.
    # Use both p10 and p50 so we don't classify everything as silence in cases
    # where the whole file is quiet.
    adaptive_threshold = max(
      int(silence_abs_amplitude_threshold),
      int(round(p10 * 1.8)),
      int(round(p50 * 0.05)),
    )

    return [peak <= adaptive_threshold for peak in peaks]

  # Fallback: treat only all-zero frames as silence.
  zero_frame = b"\x00" * frame_size_bytes
  silent = [False] * nframes
  for frame_index in range(nframes):
    chunk = frames[frame_index * frame_size_bytes:(frame_index + 1) *
                   frame_size_bytes]
    silent[frame_index] = chunk == zero_frame
  return silent


def _find_silent_runs(
  mask: list[bool],
  *,
  min_run_frames: int,
) -> list[tuple[int, int]]:
  """Return [(start_frame, end_frame_exclusive)] for silent runs >= min_run."""
  runs: list[tuple[int, int]] = []
  i = 0
  n = len(mask)
  while i < n:
    if not mask[i]:
      i += 1
      continue
    start = i
    while i < n and mask[i]:
      i += 1
    end = i
    if (end - start) >= min_run_frames:
      runs.append((start, end))
  return runs
