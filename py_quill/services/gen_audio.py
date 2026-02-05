"""Audio generation service using Google Cloud Text-to-Speech."""

from __future__ import annotations

import enum
import io
import random
import re
import time
import traceback
import wave
from typing import Any

from common import config, models, utils
from firebase_functions import logger
from google import genai
from google.genai import types as genai_types
from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted
from google.cloud import texttospeech
from services import cloud_storage
from services.audio_voices import Voice, VoiceModel


class Error(Exception):
  """Base class for exceptions in this module."""


class GenAudioError(Error):
  """Exception raised for errors during audio generation."""


# Pricing per character (USD)
# Source: https://cloud.google.com/text-to-speech/pricing
_TTS_COST_PER_CHARACTER = {
  VoiceModel.STANDARD: 4.0 / 1_000_000,
  VoiceModel.NEURAL2: 16.0 / 1_000_000,
  VoiceModel.CHIRP3: 30.0 / 1_000_000,
}

# Location required by the Long Audio API
# See: https://cloud.google.com/text-to-speech/docs/global-endpoints
_TTS_PARENT_LOCATION = f"projects/{config.PROJECT_ID}/locations/{config.PROJECT_LOCATION}"

# Map AudioEncoding to file extensions
_AUDIO_ENCODING_EXTENSIONS = {
  texttospeech.AudioEncoding.LINEAR16: ".wav",
  texttospeech.AudioEncoding.MP3: ".mp3",
  texttospeech.AudioEncoding.OGG_OPUS: ".ogg",
}

_SSML_REPLACEMENTS = (
  ("&", "&amp;"),
  ('"', "&quot;"),
  ("'", "&apos;"),
  ("<", "&lt;"),
  (">", "&gt;"),
  ("\n\n", '\n<break time="1000ms"/>\n'),
  ("...", '<break time="500ms"/>'),
)

_SSML_UNSUPPORTED_ERROR_MSG = "does not support SSML input"

_GEMINI_AUDIO_SAMPLE_RATE_HZ = 24000
_GEMINI_AUDIO_SAMPLE_WIDTH_BYTES = 2
_GEMINI_AUDIO_CHANNELS = 1


class GeminiTtsModel(str, enum.Enum):
  """Gemini TTS model names."""

  GEMINI_2_5_FLASH_TTS = "gemini-2.5-flash-preview-tts"
  GEMINI_2_5_PRO_TTS = "gemini-2.5-pro-preview-tts"


_GEMINI_TTS_GENERATION_COSTS_USD_PER_TOKEN: dict[GeminiTtsModel, dict[
  str, float]] = {
    # https://ai.google.dev/gemini-api/docs/pricing (Speech generation)
    GeminiTtsModel.GEMINI_2_5_FLASH_TTS: {
      "prompt_tokens": 0.50 / 1_000_000,
      "output_tokens": 10.00 / 1_000_000,
    },
    GeminiTtsModel.GEMINI_2_5_PRO_TTS: {
      "prompt_tokens": 1.00 / 1_000_000,
      "output_tokens": 20.00 / 1_000_000,
    },
  }


def _pcm_to_wav_bytes(
  pcm_bytes: bytes,
  *,
  sample_rate_hz: int,
  sample_width_bytes: int,
  channels: int,
) -> bytes:
  buffer = io.BytesIO()
  with wave.open(buffer, "wb") as wf:
    # pylint: disable=no-member
    wf.setnchannels(int(channels))
    wf.setsampwidth(int(sample_width_bytes))
    wf.setframerate(int(sample_rate_hz))
    wf.writeframes(pcm_bytes)
    # pylint: enable=no-member
  return buffer.getvalue()


def _extract_token_counts(response: object) -> dict[str, int]:
  usage = getattr(response, "usage_metadata", None)
  prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
  cached_tokens = int(getattr(usage, "cached_content_token_count", 0) or 0)
  output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
  return {
    "prompt_tokens": prompt_tokens,
    "cached_content_tokens": cached_tokens,
    "output_tokens": output_tokens,
  }


def _extract_pcm_bytes(response: object) -> bytes:
  try:
    data = response.candidates[0].content.parts[0].inline_data.data
  except Exception as exc:
    raise GenAudioError(
      f"Gemini response missing inline audio data: {exc}") from exc

  if isinstance(data, bytes):
    return data
  if isinstance(data, str):
    return data.encode("utf-8")
  raise GenAudioError(f"Gemini response inline audio is unexpected type: {type(data)}")


def _get_gemini_tts_cost(
  *,
  model: GeminiTtsModel,
  token_counts: dict[str, int],
) -> float:
  costs = _GEMINI_TTS_GENERATION_COSTS_USD_PER_TOKEN.get(model)
  if not costs:
    return 0.0
  return (float(costs.get("prompt_tokens", 0.0)) *
          int(token_counts.get("prompt_tokens", 0)) +
          float(costs.get("output_tokens", 0.0)) *
          int(token_counts.get("output_tokens", 0)))


def generate_multi_turn_dialog_old(
  *,
  script: str,
  speakers: dict[str, Voice],
  output_filename_base: str,
  model: GeminiTtsModel = GeminiTtsModel.GEMINI_2_5_FLASH_TTS,
) -> tuple[str, models.SingleGenerationMetadata]:
  """Generate multi-speaker dialog audio with explicit speaker labels via Gemini."""
  normalized_script = (script or "").strip()
  if not normalized_script:
    raise GenAudioError("script must be non-empty")

  if not speakers or not isinstance(speakers, dict):
    raise GenAudioError("speakers must be a non-empty dict")

  speaker_items = [(str(name).strip(), voice) for name, voice in speakers.items()]
  speaker_items = [(name, voice) for name, voice in speaker_items if name]
  if len(speaker_items) > 2:
    raise GenAudioError("Gemini multi-speaker audio supports up to 2 speakers")

  for name, voice in speaker_items:
    if not isinstance(voice, Voice) or voice.model is not VoiceModel.GEMINI:
      raise GenAudioError("Gemini multi-speaker audio requires GEMINI voices")
    if not voice.voice_name:
      raise GenAudioError(f"Speaker {name} voice must have a voice_name")

  if utils.is_emulator():
    logger.info("Running in emulator mode. Returning a test audio file.")
    test_uri = cloud_storage.get_audio_gcs_uri(output_filename_base, "wav")
    return test_uri, models.SingleGenerationMetadata()

  start_time = time.perf_counter()
  client = genai.Client(api_key=config.get_gemini_api_key())
  speaker_voice_configs = [
    genai_types.SpeakerVoiceConfig(
      speaker=speaker_name,
      voice_config=genai_types.VoiceConfig(
        prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
          voice_name=voice.voice_name)))
    for speaker_name, voice in speaker_items
  ]

  response = client.models.generate_content(
    model=model.value,
    contents=normalized_script,
    config=genai_types.GenerateContentConfig(
      response_modalities=["AUDIO"],
      speech_config=genai_types.SpeechConfig(
        multi_speaker_voice_config=genai_types.MultiSpeakerVoiceConfig(
          speaker_voice_configs=speaker_voice_configs)),
    ),
  )

  token_counts = _extract_token_counts(response)
  pcm_bytes = _extract_pcm_bytes(response)
  wav_bytes = _pcm_to_wav_bytes(
    pcm_bytes,
    sample_rate_hz=_GEMINI_AUDIO_SAMPLE_RATE_HZ,
    sample_width_bytes=_GEMINI_AUDIO_SAMPLE_WIDTH_BYTES,
    channels=_GEMINI_AUDIO_CHANNELS,
  )

  token_counts["characters"] = len(normalized_script)
  token_counts["audio_pcm_bytes"] = len(pcm_bytes)
  token_counts["audio_wav_bytes"] = len(wav_bytes)

  gcs_uri = cloud_storage.get_audio_gcs_uri(output_filename_base, "wav")
  cloud_storage.upload_bytes_to_gcs(wav_bytes, gcs_uri, content_type="audio/wav")

  generation_time_sec = time.perf_counter() - start_time
  cost = _get_gemini_tts_cost(model=model, token_counts=token_counts)
  metadata = models.SingleGenerationMetadata(
    label="generate_multi_turn_dialog_old",
    model_name=model.value,
    token_counts=token_counts,
    generation_time_sec=generation_time_sec,
    cost=cost,
  )
  return gcs_uri, metadata


def generate_multi_turn_dialog(
  *,
  script: str,
  speakers: dict[str, Voice],
  output_filename_base: str,
  model: GeminiTtsModel = GeminiTtsModel.GEMINI_2_5_FLASH_TTS,
) -> tuple[str, models.SingleGenerationMetadata]:
  """Generate multi-speaker dialog audio (legacy wrapper)."""
  return generate_multi_turn_dialog_old(
    script=script,
    speakers=speakers,
    output_filename_base=output_filename_base,
    model=model,
  )


def text_to_speech(
  text: str,
  output_filename_base: str,
  label: str,
  voice: Voice,
  audio_encoding: texttospeech.AudioEncoding = texttospeech.AudioEncoding.
  LINEAR16,
  timeout_sec: int = 300,
  max_retries: int = 3,
  extra_log_data: dict[str, Any] | None = None,
) -> tuple[str, models.SingleGenerationMetadata]:
  """
    Synthesizes text, writing the resulting audio to a GCS URI.

    Args:
        text: The text to synthesize (up to 1 million bytes).
        output_filename_base: The desired base filename for the output audio in GCS
            (e.g., "story_audio"). The appropriate extension (.wav, .mp3) will be added.
        label: A label for logging and metadata.
        voice: The desired voice, including attributes like language, model, gender.
        audio_encoding: The encoding for the output audio file.
        timeout_sec: Timeout for the long-running operation in seconds.
        max_retries: Maximum number of retries for API calls.
        extra_log_data: Extra log data to include in the log
    Returns:
        A tuple containing:
          - The full GCS URI of the generated audio file (e.g., gs://gen_audio/story_audio.wav).
          - A SingleGenerationMetadata object with details about the generation.

    Raises:
        GenAudioError: If audio synthesis fails or encoding is unsupported.
  """
  if voice.model is VoiceModel.GEMINI:
    raise GenAudioError(
      "Gemini prebuilt voices are only supported via generate_multi_turn_dialog"
    )

  if utils.is_emulator():
    logger.info('Running in emulator mode. Returning a test audio file.')
    random_suffix = f"{random.randint(1, 10):02d}"
    test_uri = f"gs://test_story_audio_data/test_page_audio_{random_suffix}.wav"
    return test_uri, models.SingleGenerationMetadata()

  start_time = time.perf_counter()
  sanitized_text = _sanitize_text_for_tts(text)
  logger.info(
    f"TTS start: {label} ({voice.name}) - {len(sanitized_text)} chars")

  # Determine file extension and construct full filename/URI
  if audio_encoding not in _AUDIO_ENCODING_EXTENSIONS:
    raise GenAudioError(f"Unsupported audio encoding: {audio_encoding.name}")

  retry_count = 0
  initial_delay = 5
  backoff_factor = 2
  max_delay = 60
  use_ssml = True  # Start by attempting SSML

  file_extension = _AUDIO_ENCODING_EXTENSIONS[audio_encoding]
  while retry_count <= max_retries:
    output_gcs_uri = cloud_storage.get_audio_gcs_uri(output_filename_base,
                                                     file_extension)

    try:
      audio_config = texttospeech.AudioConfig(audio_encoding=audio_encoding)

      # Make the API call using the helper function
      _ = _synthesize_long_audio_request(
        input_text=sanitized_text,
        use_ssml=use_ssml,
        voice=voice,
        audio_config=audio_config,
        output_gcs_uri=output_gcs_uri,
        timeout_sec=timeout_sec,
        retry_num=retry_count,
      )

      generation_time_sec = time.perf_counter() - start_time

      # Calculate cost
      num_chars = len(sanitized_text)
      cost_per_char = _TTS_COST_PER_CHARACTER.get(voice.model, 0.0)
      cost = num_chars * cost_per_char

      metadata = models.SingleGenerationMetadata(
        label=label,
        model_name=voice.voice_name,
        token_counts={'characters': num_chars},
        generation_time_sec=generation_time_sec,
        cost=cost,
        retry_count=retry_count,
      )

      _log_tts_response(sanitized_text, output_gcs_uri, metadata,
                        extra_log_data)

      return output_gcs_uri, metadata

    # Catch retryable errors
    except (GoogleAPICallError, TimeoutError, ResourceExhausted) as e:
      is_ssml_error = (isinstance(e, GoogleAPICallError)
                       and _SSML_UNSUPPORTED_ERROR_MSG in str(e))

      # If it's the specific SSML error and we were using SSML,
      # switch to plain text and try again immediately within the same retry count.
      if is_ssml_error and use_ssml:
        use_ssml = False
        # We don't increment retry_count here, just switch the input type for the *next*
        # loop iteration.
        continue  # Skip backoff and retry immediately with plain text

      # Handle other retryable errors or SSML error when already using plain text
      logger.error(
        f"TTS failed (retry {retry_count}) with error:\n{traceback.format_exc()}"
      )

      retry_count += 1
      if retry_count > max_retries:
        raise GenAudioError(
          f"TTS failed after {retry_count - 1} retries: {e}") from e

      delay = min(max_delay,
                  initial_delay * (backoff_factor**(retry_count - 1)))
      logger.warn(
        f"Retrying TTS for {label} in {delay} seconds... ({retry_count}/{max_retries})"
      )
      time.sleep(delay)
    except Exception as e:
      logger.error(
        f"An unexpected error occurred during audio synthesis: {e}\n{traceback.format_exc()}"
      )
      raise GenAudioError(f"An unexpected error occurred: {e}") from e

  # Should not be reached if retry logic is correct, but raise error just in case
  raise GenAudioError(
    f"TTS failed definitively after {max_retries} retries for label: {label}")


def _synthesize_long_audio_request(
  *,
  input_text: str,
  use_ssml: bool,
  voice: Voice,
  audio_config: texttospeech.AudioConfig,
  output_gcs_uri: str,
  timeout_sec: int,
  retry_num: int,
) -> Any:
  """Makes a single request to the TextToSpeechLongAudioSynthesizeClient.

  Args:
    input_text: The text content (either plain or SSML).
    use_ssml: Whether the input_text is SSML or plain text.
    voice: The voice configuration.
    audio_config: The audio output configuration.
    output_gcs_uri: The GCS URI for the output file.
    timeout_sec: Timeout for the operation.
    retry_num: The current retry attempt number (for logging).

  Returns:
    The operation result.

  Raises:
    GoogleAPICallError: If the API call fails.
    TimeoutError: If the operation times out.
  """

  client = texttospeech.TextToSpeechLongAudioSynthesizeClient()

  if use_ssml:
    ssml_text = input_text
    for old, new in _SSML_REPLACEMENTS:
      ssml_text = ssml_text.replace(old, new)
    ssml_text = f"<speak>{ssml_text}</speak>"
    synthesis_input = texttospeech.SynthesisInput(ssml=ssml_text)
  else:
    synthesis_input = texttospeech.SynthesisInput(text=input_text)

  tts_voice = texttospeech.VoiceSelectionParams(
    language_code=voice.language.value, name=voice.voice_name)

  request = texttospeech.SynthesizeLongAudioRequest(
    parent=_TTS_PARENT_LOCATION,
    input=synthesis_input,
    audio_config=audio_config,
    voice=tts_voice,
    output_gcs_uri=output_gcs_uri,
  )

  operation = client.synthesize_long_audio(request=request)
  input_type = "SSML" if use_ssml else "Text"
  logger.info(f"Waiting for operation {operation.operation.name} "
              f"(retry {retry_num}, input: {input_type})...")
  # Result is expected to be empty for successful synthesis
  return operation.result(timeout=timeout_sec)


def _log_tts_response(
  text: str,
  gcs_uri: str,
  metadata: models.SingleGenerationMetadata,
  extra_log_data: dict[str, Any] | None = None,
) -> None:
  """Log the TTS response and metadata, similar to LLM client."""
  usage_str = "\n".join(f"{k}: {v}" for k, v in metadata.token_counts.items())

  num_chars = metadata.token_counts.get('characters', '?')
  log_parts = []
  log_parts.append(f"""
============================== Input Text ({num_chars} chars) ==============================
{text}
""")

  log_parts.append(f"""
============================== Output GCS URI ==============================
{gcs_uri}
""")

  log_parts.append(f"""
============================== Metadata ==============================
Voice: {metadata.model_name}
Generation time: {metadata.generation_time_sec:.2f} seconds
Retry count: {metadata.retry_count}
Generation cost: ${metadata.cost:.6f}
{usage_str}
""")

  header = f"TTS done: {metadata.label} ({metadata.model_name})"
  combined_log = header + "\n" + "\n\n".join(log_parts)

  log_extra_data = {
    "generation_cost_usd": metadata.cost,
    "generation_time_sec": metadata.generation_time_sec,
    "retry_count": metadata.retry_count,
    "model_name": metadata.model_name,
    "label": metadata.label,
    **metadata.token_counts,
    **(extra_log_data or {}),
  }

  # Log combined if under limit, otherwise log parts separately
  if len(combined_log) <= 65_000:
    logger.info(combined_log, extra={"json_fields": log_extra_data})
  else:
    num_parts = len(log_parts)
    for i, part in enumerate(log_parts):
      is_last_part = i == (num_parts - 1)
      if is_last_part:
        logger.info(f"{header}\n{part}", extra={"json_fields": log_extra_data})
      else:
        logger.info(f"{header}\n{part}")


def _sanitize_text_for_tts(text: str) -> str:
  """Sanitize text for TTS by replacing phrases that TTS has trouble with."""
  # Remove asterisks
  sanitized = text.replace("*", "")

  # Convert all caps words (5+ letters) to lowercase
  # Use single backslash for \b in raw strings
  sanitized = re.sub(r"\b[A-Z]{5,}\b", lambda match: match.group(0).lower(),
                     sanitized)

  # Replace 3+ consecutive repeated characters with 2
  # Use single backslash for \1 in raw strings
  sanitized = re.sub(r"(.)\1{2,}", r"\1\1", sanitized)

  return sanitized
