"""Audio client.

Patterned after services.llm_client, but focused on audio generation.
"""
from __future__ import annotations

import base64
import io
import random
import time
import traceback
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar

import httpx
from common import config, models, utils
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError
from elevenlabs.core.http_response import HttpResponse
from elevenlabs.types.audio_with_timestamps_and_voice_segments_response_model import \
    AudioWithTimestampsAndVoiceSegmentsResponseModel
from firebase_functions import logger
from google import genai
from google.api_core.exceptions import ResourceExhausted
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from services import cloud_storage
from services.audio_voices import Voice, VoiceModel

_T = TypeVar("_T")


class Error(Exception):
  """Base class for exceptions in this module."""


class AudioGenerationError(Error):
  """Exception raised for errors during audio generation."""


class AudioModel(str, Enum):
  """Audio model names."""

  GEMINI_2_5_FLASH_TTS = "gemini-2.5-flash-preview-tts"
  GEMINI_2_5_PRO_TTS = "gemini-2.5-pro-preview-tts"
  ELEVENLABS_ELEVEN_V3 = "eleven_v3"


@dataclass(frozen=True, kw_only=True)
class DialogTurn:
  """A single dialog turn by one speaker/voice."""

  voice: Any
  script: str
  pause_sec_before: float | None = None
  pause_sec_after: float | None = None


@dataclass(frozen=True, kw_only=True)
class AudioGenerationResult:
  """Result of an audio generation call."""

  gcs_uri: str
  metadata: models.SingleGenerationMetadata


def get_audio_client(
  *,
  label: str,
  model: AudioModel,
  max_retries: int = 3,
  **kwargs: Any,
) -> AudioClient[Any]:
  """Get the appropriate audio client for the given model name."""

  if model in GeminiAudioClient.GENERATION_COSTS:
    return GeminiAudioClient(
      label=label,
      model=model,
      max_retries=max_retries,
      **kwargs,
    )
  if model in ElevenlabsAudioClient.GENERATION_COSTS:
    return ElevenlabsAudioClient(
      label=label,
      model=model,
      max_retries=max_retries,
      **kwargs,
    )
  raise ValueError(f"Unknown audio model: {model}")


class AudioClient(ABC, Generic[_T]):
  """Abstract base class for audio clients."""

  def __init__(
    self,
    *,
    label: str,
    model: AudioModel,
    max_retries: int,
  ):
    self.label = label
    self.model = model
    self.max_retries = max_retries

    self._model_client: _T | None = None

  @property
  def model_client(self) -> _T:
    """Get the underlying API client (lazily constructed)."""

    if self._model_client is None:
      self._model_client = self._create_model_client()
    return self._model_client

  @abstractmethod
  def _create_model_client(self) -> _T:
    """Create the underlying API client."""

  def generate_multi_turn_dialog(
    self,
    *,
    turns: list[DialogTurn],
    output_filename_base: str,
    temp_output: bool = False,
    label: str | None = None,
    extra_log_data: dict[str, Any] | None = None,
  ) -> AudioGenerationResult:
    """Generate a multi-turn dialog audio file.

    The base implementation handles retries, uploading, cost calculation, and
    logging. Subclasses should implement _generate_multi_turn_dialog_internal.
    """

    if utils.is_emulator():
      logger.info("Running in emulator mode. Returning a test audio file.")
      random_suffix = f"{random.randint(1, 10):02d}"
      test_uri = (
        f"gs://test_story_audio_data/test_dialog_audio_{random_suffix}.wav")
      return AudioGenerationResult(
        gcs_uri=test_uri,
        metadata=models.SingleGenerationMetadata(),
      )

    if not turns:
      raise AudioGenerationError("At least one dialog turn must be provided")

    label = label or self.label
    start_time = time.perf_counter()
    logger.info(f"{self.model.value} start: {label}")

    initial_delay = 5
    backoff_factor = 2
    max_delay = 60

    last_error: Exception | None = None
    retry_count = 0

    while retry_count <= self.max_retries:
      try:
        internal = self._generate_multi_turn_dialog_internal(
          turns=turns,
          label=label,
        )

        output_gcs_uri = cloud_storage.get_audio_gcs_uri(
          output_filename_base,
          internal.file_extension,
          temp=temp_output,
        )
        cloud_storage.upload_bytes_to_gcs(
          internal.audio_bytes,
          output_gcs_uri,
          content_type=internal.content_type,
        )

        token_counts = dict(internal.token_counts or {})
        token_counts.setdefault("characters", len(internal.input_text))
        token_counts["audio_bytes"] = len(internal.audio_bytes)

        billed_token_counts = self._get_billed_token_counts(token_counts)
        cost = self.calculate_generation_cost(billed_token_counts)

        metadata = models.SingleGenerationMetadata(
          label=label,
          model_name=self.model.value,
          token_counts=token_counts,
          generation_time_sec=time.perf_counter() - start_time,
          cost=cost,
          retry_count=retry_count,
        )

        merged_extra_log_data = {
          "model_name": self.model.value,
          "label": label,
          **(internal.extra_log_data or {}),
          **(extra_log_data or {}),
        }
        _log_audio_response(
          internal.input_text,
          output_gcs_uri,
          metadata,
          merged_extra_log_data,
        )

        return AudioGenerationResult(gcs_uri=output_gcs_uri, metadata=metadata)
      except Exception as e:  # pylint: disable=broad-except
        last_error = e
        retryable_str = "retryable" if self._is_retryable_error(
          e) else "non-retryable"
        logger.error(
          "Audio call failed with %s error:\n%s",
          retryable_str,
          traceback.format_exc(),
        )
        if not self._is_retryable_error(e):
          if isinstance(e, AudioGenerationError):
            raise
          raise AudioGenerationError(
            f"Audio call to {self.model.value} ({label}) failed with non-retryable error"
          ) from e

        retry_count += 1
        if retry_count > self.max_retries:
          raise AudioGenerationError(
            f"Audio call to {self.model.value} ({label}) failed after "
            f"{self.max_retries} retries:\n{e}") from e

        delay = min(max_delay,
                    initial_delay * (backoff_factor**(retry_count - 1)))
        logger.warn(
          "Retrying audio generation for %s in %s seconds... (%s/%s)",
          label,
          delay,
          retry_count,
          self.max_retries,
        )
        time.sleep(delay)

    if last_error is not None:
      raise AudioGenerationError(
        f"Audio call to {self.model.value} ({label}) failed: {last_error}"
      ) from last_error
    raise AudioGenerationError(
      f"Audio call to {self.model.value} ({label}) failed with unknown error")

  @abstractmethod
  def _generate_multi_turn_dialog_internal(
    self,
    *,
    turns: list[DialogTurn],
    label: str,
  ) -> "_AudioInternalResult":
    """Provider-specific audio generation implementation."""

  @abstractmethod
  def _get_generation_costs(self) -> dict[str, float]:
    """Get the generation costs in USD per token by token type."""

  @abstractmethod
  def _is_retryable_error(self, error: Exception) -> bool:
    """Whether the error is retryable."""

  def _get_billed_token_counts(self,
                               token_counts: dict[str, int]) -> dict[str, int]:
    """Return token counts used for billing.

    Subclasses can override this if token_counts includes non-billable keys.
    """

    return token_counts

  def calculate_generation_cost(self, token_counts: dict[str, int]) -> float:
    """Calculate the generation cost in USD."""

    total_cost = 0.0
    costs_by_token_type = self._get_generation_costs()
    for token_type, count in token_counts.items():
      if token_type not in costs_by_token_type:
        raise ValueError(
          f"""Unknown token type ({token_type}) for model {self.model.value}:
{token_counts}""")
      total_cost += costs_by_token_type[token_type] * int(count)
    return total_cost


@dataclass(frozen=True, kw_only=True)
class _AudioInternalResult:
  input_text: str
  audio_bytes: bytes
  file_extension: str
  content_type: str
  token_counts: dict[str, int]
  extra_log_data: dict[str, Any] | None = None


def _format_pause_seconds(seconds: float) -> str:
  return f"{seconds:g}"


def _apply_pause_markers(
  script: str,
  *,
  pause_sec_before: float | None,
  pause_sec_after: float | None,
) -> str:
  rendered = script
  if pause_sec_before is not None:
    rendered = f"[pause for {_format_pause_seconds(pause_sec_before)} seconds] {rendered}"
  if pause_sec_after is not None:
    rendered = f"{rendered} [pause for {_format_pause_seconds(pause_sec_after)} seconds]"
  return rendered


class GeminiAudioClient(AudioClient[genai.Client]):
  """Gemini speech generation client (Google GenAI SDK, API-key auth)."""

  _SPEAKER_NAMES = ("Alex", "Sam")

  _AUDIO_SAMPLE_RATE_HZ = 24000
  _AUDIO_SAMPLE_WIDTH_BYTES = 2
  _AUDIO_CHANNELS = 1

  # https://ai.google.dev/gemini-api/docs/pricing (Speech generation)
  GENERATION_COSTS: dict[AudioModel, dict[str, float]] = {
    AudioModel.GEMINI_2_5_FLASH_TTS: {
      "prompt_tokens": 0.50 / 1_000_000,
      "output_tokens": 10.00 / 1_000_000,
    },
    AudioModel.GEMINI_2_5_PRO_TTS: {
      "prompt_tokens": 1.00 / 1_000_000,
      "output_tokens": 20.00 / 1_000_000,
    },
  }

  def _create_model_client(self) -> genai.Client:
    return genai.Client(api_key=config.get_gemini_api_key())

  def _generate_multi_turn_dialog_internal(
    self,
    *,
    turns: list[DialogTurn],
    label: str,
  ) -> _AudioInternalResult:
    normalized_turns = self._normalize_turns(turns)
    speaker_voices = self._extract_speaker_voices(normalized_turns)
    stitched_script = self._stitch_dialog_script(normalized_turns,
                                                 speaker_voices=speaker_voices)

    speaker_voice_configs = [
      genai_types.SpeakerVoiceConfig(
        speaker=speaker_name,
        voice_config=genai_types.VoiceConfig(
          prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
            voice_name=voice.voice_name)))
      for speaker_name, voice in speaker_voices.items()
    ]

    response: genai_types.GenerateContentResponse = self.model_client.models.generate_content(
      model=self.model.value,
      contents=stitched_script,
      config=genai_types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=genai_types.SpeechConfig(
          multi_speaker_voice_config=genai_types.MultiSpeakerVoiceConfig(
            speaker_voice_configs=speaker_voice_configs)),
      ),
    )

    usage_token_counts = self._extract_token_counts(response)
    pcm_bytes = self._extract_pcm_bytes(response)
    wav_bytes = self._pcm_to_wav_bytes(pcm_bytes)

    extra_log_data = {
      "speaker_voices": {
        speaker: voice.voice_name
        for speaker, voice in speaker_voices.items()
      },
      "sample_rate_hz": self._AUDIO_SAMPLE_RATE_HZ,
      "channels": self._AUDIO_CHANNELS,
    }

    return _AudioInternalResult(
      input_text=stitched_script,
      audio_bytes=wav_bytes,
      file_extension="wav",
      content_type="audio/wav",
      token_counts={
        **usage_token_counts,
        "characters": len(stitched_script),
        "audio_pcm_bytes": len(pcm_bytes),
        "audio_wav_bytes": len(wav_bytes),
      },
      extra_log_data=extra_log_data,
    )

  def _normalize_turns(self, turns: list[DialogTurn]) -> list[DialogTurn]:
    normalized: list[DialogTurn] = []
    for turn in turns:
      if not isinstance(turn, DialogTurn):
        raise AudioGenerationError(f"Invalid dialog turn: {turn}")
      if not isinstance(turn.voice, Voice):
        raise AudioGenerationError(f"Turn voice must be a Voice: {turn.voice}")
      if turn.voice.model is not VoiceModel.GEMINI:
        raise AudioGenerationError(
          f"Gemini multi-turn audio requires GEMINI voices; got {turn.voice.model.name}"
        )

      pause_before = turn.pause_sec_before
      if pause_before is not None:
        if not isinstance(pause_before, (int, float)):
          raise AudioGenerationError("pause_sec_before must be a number")
        if pause_before < 0:
          raise AudioGenerationError("pause_sec_before must be >= 0")

      pause_after = turn.pause_sec_after
      if pause_after is not None:
        if not isinstance(pause_after, (int, float)):
          raise AudioGenerationError("pause_sec_after must be a number")
        if pause_after < 0:
          raise AudioGenerationError("pause_sec_after must be >= 0")

      script = (turn.script or "").strip()
      if not script:
        raise AudioGenerationError("Turn script must be non-empty")
      script = _apply_pause_markers(
        script,
        pause_sec_before=float(pause_before)
        if pause_before is not None else None,
        pause_sec_after=float(pause_after)
        if pause_after is not None else None,
      )
      normalized.append(DialogTurn(voice=turn.voice, script=script))

    if not normalized:
      raise AudioGenerationError("At least one dialog turn must be provided")
    return normalized

  def _extract_speaker_voices(self,
                              turns: list[DialogTurn]) -> dict[str, Voice]:
    unique_voices: list[Voice] = []
    for turn in turns:
      if turn.voice not in unique_voices:
        unique_voices.append(turn.voice)

    if len(unique_voices) > 2:
      raise AudioGenerationError(
        "Gemini multi-speaker audio supports up to 2 speakers")

    speaker_voices: dict[str, Voice] = {}
    for idx, voice in enumerate(unique_voices):
      speaker_voices[self._SPEAKER_NAMES[idx]] = voice
    return speaker_voices

  def _stitch_dialog_script(
    self,
    turns: list[DialogTurn],
    *,
    speaker_voices: dict[str, Voice],
  ) -> str:
    voice_to_speaker = {voice: name for name, voice in speaker_voices.items()}

    stitched_lines: list[str] = []
    for turn in turns:
      speaker_name = voice_to_speaker.get(turn.voice)
      if not speaker_name:
        raise AudioGenerationError(
          "Turn voice does not match configured speakers")

      for raw_line in turn.script.splitlines():
        line = raw_line.strip()
        if not line:
          continue
        stitched_lines.append(f"{speaker_name}: {line}")

    stitched = "\n".join(stitched_lines).strip()
    if not stitched:
      raise AudioGenerationError(
        "Dialog script must be non-empty after stitching")
    return stitched

  def _get_billed_token_counts(self,
                               token_counts: dict[str, int]) -> dict[str, int]:
    return {
      "prompt_tokens": int(token_counts.get("prompt_tokens", 0)),
      "output_tokens": int(token_counts.get("output_tokens", 0)),
    }

  def _get_generation_costs(self) -> dict[str, float]:
    if costs := self.GENERATION_COSTS.get(self.model):
      return costs
    raise ValueError(f"Unknown Gemini TTS model for pricing: {self.model}")

  def _is_retryable_error(self, error: Exception) -> bool:
    if isinstance(error, ResourceExhausted):
      return True
    if isinstance(error, genai_errors.ServerError):
      return True
    if isinstance(error,
                  genai_errors.ClientError) and error.code in (408, 429):
      return True
    return False

  @staticmethod
  def _extract_pcm_bytes(
      response: genai_types.GenerateContentResponse) -> bytes:
    try:
      data = response.candidates[0].content.parts[0].inline_data.data
    except Exception as e:
      raise AudioGenerationError(
        f"Gemini response missing inline audio data: {e}") from e

    if isinstance(data, bytes):
      return data

    if isinstance(data, str):
      try:
        return base64.b64decode(data)
      except Exception as e:
        raise AudioGenerationError(
          f"Gemini returned inline audio data as a non-base64 string: {e}"
        ) from e

    raise AudioGenerationError(
      f"Gemini returned inline audio data with unexpected type: {type(data)}")

  @staticmethod
  def _extract_token_counts(
    response: genai_types.GenerateContentResponse, ) -> dict[str, int]:
    if response.usage_metadata is None:
      raise AudioGenerationError("No usage metadata received from Gemini API")

    cached_prompt_tokens = int(
      response.usage_metadata.cached_content_token_count or 0)
    prompt_token_count = int(response.usage_metadata.prompt_token_count or 0)
    output_tokens = int(response.usage_metadata.candidates_token_count or 0)
    prompt_tokens = max(prompt_token_count - cached_prompt_tokens, 0)

    return {
      "prompt_tokens": prompt_tokens,
      "cached_prompt_tokens": cached_prompt_tokens,
      "output_tokens": output_tokens,
    }

  @classmethod
  def _pcm_to_wav_bytes(cls, pcm_bytes: bytes) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
      # pylint: disable=no-member
      wav_file.setnchannels(cls._AUDIO_CHANNELS)
      wav_file.setsampwidth(cls._AUDIO_SAMPLE_WIDTH_BYTES)
      wav_file.setframerate(cls._AUDIO_SAMPLE_RATE_HZ)
      wav_file.writeframes(pcm_bytes)
      # pylint: enable=no-member

    return buffer.getvalue()


class ElevenlabsAudioClient(AudioClient[ElevenLabs]):
  """ElevenLabs audio client implementation."""

  _DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
  _DEFAULT_TIMEOUT_SEC = 300

  GENERATION_COSTS: dict[AudioModel, dict[str, float]] = {
    AudioModel.ELEVENLABS_ELEVEN_V3: {
      "characters": 0.0,
    },
  }

  def __init__(
    self,
    *,
    label: str,
    model: AudioModel,
    max_retries: int,
    output_format: str = _DEFAULT_OUTPUT_FORMAT,
    language_code: str | None = None,
    settings: dict[str, Any] | None = None,
    timeout_sec: int = _DEFAULT_TIMEOUT_SEC,
  ):
    super().__init__(label=label, model=model, max_retries=max_retries)
    self.output_format = (output_format
                          or "").strip() or self._DEFAULT_OUTPUT_FORMAT
    self.language_code = (language_code or "").strip() or None
    self.settings = settings
    self.timeout_sec = timeout_sec

  def _create_model_client(self) -> ElevenLabs:
    return ElevenLabs(
      api_key=config.get_elevenlabs_api_key(),
      timeout=float(self.timeout_sec),
    )

  def _generate_multi_turn_dialog_internal(
    self,
    *,
    turns: list[DialogTurn],
    label: str,
  ) -> _AudioInternalResult:
    normalized_inputs = self._normalize_inputs(turns)
    unique_voice_ids = sorted({i["voice_id"] for i in normalized_inputs})
    if len(unique_voice_ids) > 10:
      raise AudioGenerationError(
        "ElevenLabs text-to-dialogue supports up to 10 unique voice IDs")

    kwargs: dict[str, Any] = {
      "inputs": normalized_inputs,
      "output_format": self.output_format,
      "model_id": self.model.value,
    }
    if self.language_code:
      kwargs["language_code"] = self.language_code
    if self.settings:
      kwargs["settings"] = self.settings

    response: HttpResponse[
      AudioWithTimestampsAndVoiceSegmentsResponseModel] = (
        self.model_client.text_to_dialogue.with_raw_response.
        convert_with_timestamps(**kwargs))

    request_id = (response.headers.get("request-id")
                  or response.headers.get("x-request-id") or "")
    billed_characters_raw = (response.headers.get("x-character-count") or "")
    billed_characters: int | None = None
    if str(billed_characters_raw).strip():
      try:
        billed_characters = int(str(billed_characters_raw).strip())
      except ValueError:
        billed_characters = None

    data = response.data
    audio_b64 = (getattr(data, "audio_base_64", None) or "").strip()
    if not audio_b64:
      raise AudioGenerationError("ElevenLabs response missing audio_base_64")

    try:
      audio_bytes = base64.b64decode(audio_b64)
    except Exception as e:
      raise AudioGenerationError(
        f"ElevenLabs returned non-base64 audio: {e}") from e

    file_extension, content_type = self._get_output_encoding()

    input_text = "\n".join(i["text"] for i in normalized_inputs).strip()
    input_characters = sum(len(i["text"]) for i in normalized_inputs)
    voice_segments = getattr(data, "voice_segments", None) or []
    voice_segments_count = len(voice_segments)

    return _AudioInternalResult(
      input_text=input_text,
      audio_bytes=audio_bytes,
      file_extension=file_extension,
      content_type=content_type,
      token_counts={
        "characters": billed_characters
        if billed_characters is not None else input_characters,
        "characters_input": input_characters,
        "voice_segments": voice_segments_count,
        "unique_voice_ids": len(unique_voice_ids),
      },
      extra_log_data={
        "output_format": self.output_format,
        "request_id": request_id,
        "unique_voice_ids": unique_voice_ids,
      },
    )

  def _normalize_inputs(self, turns: list[DialogTurn]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for turn in turns:
      voice_id_raw = turn.voice
      if isinstance(voice_id_raw, Voice):
        if voice_id_raw.model is not VoiceModel.ELEVENLABS:
          raise AudioGenerationError(
            f"ElevenLabs voice must be an ELEVENLABS Voice; got {voice_id_raw.model.name}"
          )
        voice_id = voice_id_raw.voice_name
      elif isinstance(voice_id_raw, str):
        voice_id = voice_id_raw
      else:
        raise AudioGenerationError(
          f"ElevenLabs voice must be an ELEVENLABS Voice or voice_id string; got {type(voice_id_raw)}"
        )

      voice_id = voice_id.strip()
      if not voice_id:
        raise AudioGenerationError("ElevenLabs voice_id must be non-empty")

      pause_before = turn.pause_sec_before
      if pause_before is not None:
        if not isinstance(pause_before, (int, float)):
          raise AudioGenerationError("pause_sec_before must be a number")
        if pause_before < 0:
          raise AudioGenerationError("pause_sec_before must be >= 0")

      pause_after = turn.pause_sec_after
      if pause_after is not None:
        if not isinstance(pause_after, (int, float)):
          raise AudioGenerationError("pause_sec_after must be a number")
        if pause_after < 0:
          raise AudioGenerationError("pause_sec_after must be >= 0")

      text = (turn.script or "").strip()
      if not text:
        raise AudioGenerationError("Turn script must be non-empty")
      text = _apply_pause_markers(
        text,
        pause_sec_before=float(pause_before)
        if pause_before is not None else None,
        pause_sec_after=float(pause_after)
        if pause_after is not None else None,
      )

      normalized.append({
        "text": text,
        "voice_id": voice_id,
      })

    if not normalized:
      raise AudioGenerationError("At least one dialog turn must be provided")
    return normalized

  def _get_output_encoding(self) -> tuple[str, str]:
    output_format = (self.output_format or "").strip().lower()
    if output_format.startswith("mp3_"):
      return "mp3", "audio/mpeg"
    if output_format.startswith("opus_"):
      return "opus", "audio/ogg"
    if output_format.startswith("wav_"):
      return "wav", "audio/wav"
    if output_format.startswith("pcm_"):
      return "pcm", "application/octet-stream"
    if output_format.startswith("ulaw_"):
      return "ulaw", "application/octet-stream"
    if output_format.startswith("alaw_"):
      return "alaw", "application/octet-stream"
    return "bin", "application/octet-stream"

  def _get_billed_token_counts(self,
                               token_counts: dict[str, int]) -> dict[str, int]:
    return {"characters": int(token_counts.get("characters", 0))}

  def _get_generation_costs(self) -> dict[str, float]:
    if costs := self.GENERATION_COSTS.get(self.model):
      return costs
    raise ValueError(f"Unknown ElevenLabs model for pricing: {self.model}")

  def _is_retryable_error(self, error: Exception) -> bool:
    if isinstance(error, httpx.TimeoutException):
      return True
    if isinstance(error, httpx.TransportError):
      return True

    if isinstance(error, ApiError):
      status = int(getattr(error, "status_code", 0) or 0)
      if status in (408, 429):
        return True
      if status >= 500:
        return True
    return False


def _log_audio_response(
  text: str,
  gcs_uri: str,
  metadata: models.SingleGenerationMetadata,
  extra_log_data: dict[str, Any] | None = None,
) -> None:
  """Log the audio response and metadata, similar to LLM client."""

  usage_str = "\n".join(f"{k}: {v}" for k, v in metadata.token_counts.items())
  num_chars = metadata.token_counts.get("characters", "?")

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
Model: {metadata.model_name}
Generation time: {metadata.generation_time_sec:.2f} seconds
Retry count: {metadata.retry_count}
Generation cost: ${metadata.cost:.6f}
{usage_str}
""")

  header = f"Audio done: {metadata.label} ({metadata.model_name})"
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
