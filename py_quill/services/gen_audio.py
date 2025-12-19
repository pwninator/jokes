"""Audio generation service using Google Cloud Text-to-Speech."""

from __future__ import annotations

import enum
import random
import re
import time
import traceback
from typing import Any

from common import config, models, utils
from firebase_functions import logger
from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted
from google.cloud import texttospeech
from services import cloud_storage


class Error(Exception):
  """Base class for exceptions in this module."""


class GenAudioError(Error):
  """Exception raised for errors during audio generation."""


class LanguageCode(enum.Enum):
  """Supported language codes for audio generation."""
  EN_US = "en-US"
  EN_GB = "en-GB"


class VoiceModel(enum.Enum):
  """Voice model types."""
  CHIRP3 = "chirp3"
  NEURAL2 = "neural2"
  STANDARD = "standard"


class VoiceGender(enum.Enum):
  """Voice genders."""
  FEMALE = "female"
  MALE = "male"


class Voice(enum.Enum):
  """Available Text-to-Speech voices with their attributes."""

  def __init__(
    self,
    voice_name: str,
    language: LanguageCode,
    model: VoiceModel,
    gender: VoiceGender,
  ):
    self._voice_name = voice_name
    self._language = language
    self._model = model
    self._gender = gender

  @property
  def voice_name(self) -> str:
    """Get the voice ID."""
    return self._voice_name

  @property
  def language(self) -> LanguageCode:
    """Get the language code."""
    return self._language

  @property
  def model(self) -> VoiceModel:
    """Get the voice model."""
    return self._model

  @property
  def gender(self) -> VoiceGender:
    """Get the voice gender."""
    return self._gender

  # UK Voices
  EN_GB_STANDARD_FEMALE_1 = ("en-GB-Standard-C", LanguageCode.EN_GB,
                             VoiceModel.STANDARD, VoiceGender.FEMALE)
  EN_GB_STANDARD_MALE_1 = ("en-GB-Standard-B", LanguageCode.EN_GB,
                           VoiceModel.STANDARD, VoiceGender.MALE)
  EN_GB_NEURAL2_FEMALE_1 = ("en-GB-Neural2-F", LanguageCode.EN_GB,
                            VoiceModel.NEURAL2, VoiceGender.FEMALE)
  EN_GB_NEURAL2_MALE_1 = ("en-GB-Neural2-D", LanguageCode.EN_GB,
                          VoiceModel.NEURAL2, VoiceGender.MALE)
  EN_GB_CHIRP3_HD_FEMALE_LEDA = ("en-GB-Chirp3-HD-Leda", LanguageCode.EN_GB,
                                 VoiceModel.CHIRP3, VoiceGender.FEMALE)
  EN_GB_CHIRP3_HD_MALE_FENRIR = ("en-GB-Chirp3-HD-Fenrir", LanguageCode.EN_GB,
                                 VoiceModel.CHIRP3, VoiceGender.MALE)

  # US Voices
  EN_US_STANDARD_FEMALE_1 = ("en-US-Standard-F", LanguageCode.EN_US,
                             VoiceModel.STANDARD, VoiceGender.FEMALE)
  EN_US_STANDARD_MALE_1 = ("en-US-Standard-I", LanguageCode.EN_US,
                           VoiceModel.STANDARD, VoiceGender.MALE)
  EN_US_NEURAL2_FEMALE_1 = ("en-US-Neural2-C", LanguageCode.EN_US,
                            VoiceModel.NEURAL2, VoiceGender.FEMALE)
  EN_US_NEURAL2_MALE_1 = ("en-US-Neural2-A", LanguageCode.EN_US,
                          VoiceModel.NEURAL2, VoiceGender.MALE)
  EN_US_CHIRP3_HD_FEMALE_LEDA = ("en-US-Chirp3-HD-Leda", LanguageCode.EN_US,
                                 VoiceModel.CHIRP3, VoiceGender.FEMALE)
  EN_US_CHIRP3_HD_MALE_CHARON = ("en-US-Chirp3-HD-Charon", LanguageCode.EN_US,
                                 VoiceModel.CHIRP3, VoiceGender.MALE)


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
