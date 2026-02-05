"""Audio voice enums and helpers.

These are shared between audio generation implementations (e.g. Gemini speech
generation, Google Cloud Text-to-Speech).
"""

from __future__ import annotations

import enum


class LanguageCode(enum.Enum):
  """Supported language codes for audio generation."""

  EN_US = "en-US"
  EN_GB = "en-GB"


class VoiceModel(enum.Enum):
  """Voice model types."""

  CHIRP3 = "chirp3"
  ELEVENLABS = "elevenlabs"
  GEMINI = "gemini"
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

  @classmethod
  def voices_for_model(cls, model: VoiceModel) -> list["Voice"]:
    """Return all voices for a given model."""

    voices = [voice for voice in cls if voice.model is model]
    return sorted(voices, key=lambda v: (v.voice_name, v.name))

  @classmethod
  def from_voice_name(
    cls,
    voice_name: str,
    *,
    model: VoiceModel | None = None,
  ) -> "Voice":
    """Resolve a Voice enum member from its API voice name.

    Args:
      voice_name: The API voice name (e.g. "Leda" for Gemini, or
        "en-US-Standard-F" for Cloud TTS).
      model: Optional model filter (e.g. VoiceModel.GEMINI).
    """

    normalized = (voice_name or "").strip()
    if not normalized:
      raise ValueError("voice_name must be non-empty")

    for voice in cls:
      if model is not None and voice.model is not model:
        continue
      if voice.voice_name == normalized:
        return voice

    allowed = sorted(v.voice_name for v in cls
                     if model is None or v.model is model)
    model_msg = f" for model {model.name}" if model is not None else ""
    raise ValueError(
      f"Unknown voice_name{model_msg}: {normalized}. Allowed: {allowed}")

  @classmethod
  def from_identifier(
    cls,
    identifier: str,
    *,
    model: VoiceModel | None = None,
  ) -> "Voice":
    """Resolve a voice from either enum name or API voice name.

    This is useful for request inputs where the UI may submit either the enum
    member name (e.g. "GEMINI_KORE") or the API voice name (e.g. "Kore").
    """

    normalized = (identifier or "").strip()
    if not normalized:
      raise ValueError("identifier must be non-empty")

    try:
      voice = cls[normalized]
      if model is not None and voice.model is not model:
        raise ValueError(
          f"Voice {normalized} is model {voice.model.name}, expected {model.name}"
        )
      return voice
    except KeyError:
      return cls.from_voice_name(normalized, model=model)

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
  EN_US_NEURAL2_FEMALE_1 = ("en-US-Neural2-F", LanguageCode.EN_US,
                            VoiceModel.NEURAL2, VoiceGender.FEMALE)
  EN_US_NEURAL2_MALE_1 = ("en-US-Neural2-A", LanguageCode.EN_US,
                          VoiceModel.NEURAL2, VoiceGender.MALE)
  EN_US_CHIRP3_HD_FEMALE_LEDA = ("en-US-Chirp3-HD-Leda", LanguageCode.EN_US,
                                 VoiceModel.CHIRP3, VoiceGender.FEMALE)
  EN_US_CHIRP3_HD_MALE_CHARON = ("en-US-Chirp3-HD-Charon", LanguageCode.EN_US,
                                 VoiceModel.CHIRP3, VoiceGender.MALE)

  # Gemini (Speech generation) prebuilt voices
  # Source: https://ai.google.dev/gemini-api/docs/speech-generation
  GEMINI_ZEPHYR = ("Zephyr", LanguageCode.EN_US, VoiceModel.GEMINI,
                   VoiceGender.MALE)  # Bright
  GEMINI_PUCK = ("Puck", LanguageCode.EN_US, VoiceModel.GEMINI,
                 VoiceGender.MALE)  # Upbeat
  GEMINI_CHARON = ("Charon", LanguageCode.EN_US, VoiceModel.GEMINI,
                   VoiceGender.MALE)  # Informative
  GEMINI_KORE = ("Kore", LanguageCode.EN_US, VoiceModel.GEMINI,
                 VoiceGender.FEMALE)  # Firm
  GEMINI_FENRIR = ("Fenrir", LanguageCode.EN_US, VoiceModel.GEMINI,
                   VoiceGender.MALE)  # Excitable
  GEMINI_LEDA = ("Leda", LanguageCode.EN_US, VoiceModel.GEMINI,
                 VoiceGender.FEMALE)  # Youthful
  GEMINI_ORUS = ("Orus", LanguageCode.EN_US, VoiceModel.GEMINI,
                 VoiceGender.MALE)  # Firm
  GEMINI_AOEDE = ("Aoede", LanguageCode.EN_US, VoiceModel.GEMINI,
                  VoiceGender.FEMALE)  # Breezy
  GEMINI_CALLIRRHOE = ("Callirrhoe", LanguageCode.EN_US, VoiceModel.GEMINI,
                       VoiceGender.FEMALE)  # Easy-going
  GEMINI_AUTONOE = ("Autonoe", LanguageCode.EN_US, VoiceModel.GEMINI,
                    VoiceGender.FEMALE)  # Bright
  GEMINI_ENCELADUS = ("Enceladus", LanguageCode.EN_US, VoiceModel.GEMINI,
                      VoiceGender.FEMALE)  # Breathy
  GEMINI_IAPETUS = ("Iapetus", LanguageCode.EN_US, VoiceModel.GEMINI,
                    VoiceGender.MALE)  # Clear
  GEMINI_UMBRIEL = ("Umbriel", LanguageCode.EN_US, VoiceModel.GEMINI,
                    VoiceGender.FEMALE)  # Easy-going
  GEMINI_ALGIEBA = ("Algieba", LanguageCode.EN_US, VoiceModel.GEMINI,
                    VoiceGender.MALE)  # Smooth
  GEMINI_DESPINA = ("Despina", LanguageCode.EN_US, VoiceModel.GEMINI,
                    VoiceGender.FEMALE)  # Smooth
  GEMINI_ERINOME = ("Erinome", LanguageCode.EN_US, VoiceModel.GEMINI,
                    VoiceGender.MALE)  # Clear
  GEMINI_ALGENIB = ("Algenib", LanguageCode.EN_US, VoiceModel.GEMINI,
                    VoiceGender.MALE)  # Gravelly
  GEMINI_RASALGETHI = ("Rasalgethi", LanguageCode.EN_US, VoiceModel.GEMINI,
                       VoiceGender.MALE)  # Informative
  GEMINI_LAOMEDEIA = ("Laomedeia", LanguageCode.EN_US, VoiceModel.GEMINI,
                      VoiceGender.FEMALE)  # Upbeat
  GEMINI_ACHERNAR = ("Achernar", LanguageCode.EN_US, VoiceModel.GEMINI,
                     VoiceGender.FEMALE)  # Soft
  GEMINI_ALNILAM = ("Alnilam", LanguageCode.EN_US, VoiceModel.GEMINI,
                    VoiceGender.MALE)  # Firm
  GEMINI_SCHEDAR = ("Schedar", LanguageCode.EN_US, VoiceModel.GEMINI,
                    VoiceGender.MALE)  # Even
  GEMINI_GACRUX = ("Gacrux", LanguageCode.EN_US, VoiceModel.GEMINI,
                   VoiceGender.MALE)  # Mature
  GEMINI_PULCHERRIMA = ("Pulcherrima", LanguageCode.EN_US, VoiceModel.GEMINI,
                        VoiceGender.MALE)  # Forward
  GEMINI_ACHIRD = ("Achird", LanguageCode.EN_US, VoiceModel.GEMINI,
                   VoiceGender.MALE)  # Friendly
  GEMINI_ZUBENELGENUBI = ("Zubenelgenubi", LanguageCode.EN_US,
                          VoiceModel.GEMINI, VoiceGender.MALE)  # Casual
  GEMINI_VINDEMIATRIX = ("Vindemiatrix", LanguageCode.EN_US, VoiceModel.GEMINI,
                         VoiceGender.FEMALE)  # Gentle
  GEMINI_SADACHBIA = ("Sadachbia", LanguageCode.EN_US, VoiceModel.GEMINI,
                      VoiceGender.MALE)  # Lively
  GEMINI_SADALTAGER = ("Sadaltager", LanguageCode.EN_US, VoiceModel.GEMINI,
                       VoiceGender.MALE)  # Knowledgeable
  GEMINI_SULAFAT = ("Sulafat", LanguageCode.EN_US, VoiceModel.GEMINI,
                    VoiceGender.FEMALE)  # Warm
