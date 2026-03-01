"""Models for the Firestore database."""

from __future__ import annotations

import dataclasses
import datetime
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

from common import utils
from services import cloud_storage


class ReadingLevel(Enum):
  """Reading level enum matching the Flutter app's levels."""
  PRE_K = 0
  KINDERGARTEN = 1
  FIRST = 2
  SECOND = 3
  THIRD = 4
  FOURTH = 5
  FIFTH = 6
  SIXTH = 7
  SEVENTH = 8
  EIGHTH = 9
  NINTH = 10
  TENTH = 11
  ELEVENTH = 12
  TWELFTH = 13

  @staticmethod
  def from_value(value: int) -> 'ReadingLevel':
    """Convert an integer value to a ReadingLevel enum.

    Args:
        value: Integer value (0-7)
    Returns:
        Corresponding ReadingLevel enum value, defaulting to THIRD if invalid
    """
    try:
      return ReadingLevel(max(0, min(value, 7)))
    except ValueError:
      return ReadingLevel.THIRD


class JokeState(Enum):
  """Lifecycle state of a punny joke. Stored as string in Firestore."""
  UNKNOWN = "UNKNOWN"
  DRAFT = "DRAFT"
  UNREVIEWED = "UNREVIEWED"
  APPROVED = "APPROVED"
  REJECTED = "REJECTED"
  DAILY = "DAILY"
  PUBLISHED = "PUBLISHED"


class JokeAdminRating(Enum):
  """Rating given by an admin to a joke."""
  UNREVIEWED = "UNREVIEWED"
  APPROVED = "APPROVED"
  REJECTED = "REJECTED"


class JokeSocialPostType(Enum):
  """Social post layout type."""

  JOKE_GRID = (
    "JOKE_GRID",
    """\
A grid of joke setup and punchline images. The goal purely entertainment to make the viewer laugh in order to drive follows and shares.
""",
  )
  JOKE_GRID_TEASER = (
    "JOKE_GRID_TEASER",
    """\
A grid of joke setup and punchline images with the last punchline covered as a teaser. The goal is to hook the viewer with the first few jokes and tease them with the last one to drive clickthroughs to the website.
""",
  )
  JOKE_CAROUSEL = (
    "JOKE_CAROUSEL",
    """\
A sequence of setup and punchline images to be shown in a swipeable carousel. The goal purely entertainment to make the viewer laugh in order to drive follows and shares.
""",
  )
  JOKE_REEL_VIDEO = (
    "JOKE_REEL_VIDEO",
    """\
A single-joke short-form vertical video reel. The goal is fast entertainment optimized for reel-style consumption and social sharing.
""",
  )

  def __new__(cls, value: str, description: str):
    obj = object.__new__(cls)
    obj._value_ = value
    obj._description = description  # pyright: ignore[reportAttributeAccessIssue]
    return obj

  @property
  def description(self) -> str:
    """Human-friendly description of the post layout."""
    return cast(
      str, self._description)  # pyright: ignore[reportAttributeAccessIssue]


class SocialPlatform(Enum):
  """Supported social platforms for joke posts."""
  PINTEREST = "pinterest"
  INSTAGRAM = "instagram"
  FACEBOOK = "facebook"


@dataclass
class SingleGenerationMetadata:
  """Metadata about a single generation."""

  label: str = ""
  model_name: str = ""
  token_counts: dict[str, int] = field(default_factory=dict)
  generation_time_sec: float = 0
  cost: float = 0
  retry_count: int = 0

  @property
  def is_empty(self) -> bool:
    """Check if the metadata represents an actual generation (has a model name)."""
    return not self.model_name

  @property
  def as_dict(self) -> dict[str, Any]:
    """Convert to dictionary for Firestore storage."""
    return dataclasses.asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> SingleGenerationMetadata:
    """Create SingleGenerationMetadata from Firestore dictionary."""
    return cls(**data)


@dataclass
class GenerationMetadata:
  """Metadata about AI generation costs and timing."""

  generations: list[SingleGenerationMetadata] = field(default_factory=list)

  def add_generation(
    self,
    other: SingleGenerationMetadata | GenerationMetadata | None,
  ) -> None:
    """Add a generation to the metadata, skipping empty ones."""
    if other:
      if isinstance(other, GenerationMetadata):
        # Filter the incoming list to only include non-empty generations
        non_empty_generations = [
          gen for gen in other.generations if not gen.is_empty
        ]
        self.generations.extend(non_empty_generations)
      else:
        # Only add if the single generation is not empty
        if not other.is_empty:
          self.generations.append(other)

  @property
  def total_cost(self) -> float:
    """Total cost of all generations."""
    return sum(generation.cost for generation in self.generations)

  @property
  def counts_and_costs_by_model(self) -> dict[str, tuple[int, float]]:
    """Costs by model."""
    result: dict[str, tuple[int, float]] = {}
    for generation in self.generations:
      _ = result.setdefault(generation.model_name, (0, 0))
      count, cost = result[generation.model_name]
      result[generation.model_name] = (count + 1, cost + generation.cost)
    return result

  @property
  def counts_and_costs_by_label(self) -> dict[str, tuple[int, float]]:
    """Costs by label."""
    result: dict[str, tuple[int, float]] = {}
    for generation in self.generations:
      count, cost = result.setdefault(generation.label, (0, 0))
      result[generation.label] = (count + 1, cost + generation.cost)
    return result

  @property
  def as_dict(self) -> dict[str, object]:
    """Convert to dictionary for Firestore storage."""
    costs_by_model = {}
    total_cost = 0
    generations = []
    for generation in self.generations:
      costs_by_model.setdefault(generation.model_name, 0)
      costs_by_model[generation.model_name] += generation.cost
      total_cost += generation.cost
      generations.append(generation.as_dict)

    return {
      'generations': generations,
      'costs_by_model': costs_by_model,
      'total_cost': total_cost,
    }

  @classmethod
  def from_single_generation_metadata(
      cls, metadata: SingleGenerationMetadata | None) -> GenerationMetadata:
    """Create GenerationMetadata from SingleGenerationMetadata."""
    result = cls()
    if metadata:
      result.add_generation(metadata)
    return result

  @classmethod
  def from_dict(cls, data: dict[str, Any] | None) -> GenerationMetadata:
    """Create GenerationMetadata from Firestore dictionary."""
    if not data:
      return cls()
    return cls(generations=[
      SingleGenerationMetadata.from_dict(generation)
      for generation in data.get('generations', [])
    ])


@dataclass
class Image:
  """Represents a generated image and its associated metadata."""
  key: str | None = None
  url: str | None = None
  alt_text: str | None = None
  gcs_uri: str | None = None
  url_upscaled: str | None = None
  gcs_uri_upscaled: str | None = None
  original_prompt: str | None = None
  final_prompt: str | None = None
  model_thought: str | None = None
  error: str | None = None
  owner_user_id: str | None = None
  generation_metadata: GenerationMetadata = field(
    default_factory=GenerationMetadata)
  gemini_evaluation: dict[str, Any] | None = None
  generation_id: str | None = None

  # Custom temp data not stored in Firestore
  custom_temp_data: dict[str, Any] = field(default_factory=dict)

  @property
  def is_success(self) -> bool:
    """Check if the image generation was successful."""
    return self.url is not None

  @property
  def as_dict(self) -> dict[str, Any]:
    """Convert to dictionary for Firestore storage."""
    return {
      'url': self.url,
      'alt_text': self.alt_text,
      'gcs_uri': self.gcs_uri,
      'url_upscaled': self.url_upscaled,
      'gcs_uri_upscaled': self.gcs_uri_upscaled,
      'original_prompt': self.original_prompt,
      'final_prompt': self.final_prompt,
      'model_thought': self.model_thought,
      'error': self.error,
      'owner_user_id': self.owner_user_id,
      'generation_metadata':
      self.generation_metadata.as_dict if self.generation_metadata else {},
      'gemini_evaluation': self.gemini_evaluation,
      'generation_id': self.generation_id,
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any], key: str | None = None) -> Image:
    """Create Image from Firestore dictionary."""
    generation_metadata = None
    if 'generation_metadata' in data:
      generation_metadata = GenerationMetadata.from_dict(
        data['generation_metadata'])
    return cls(
      key=key if key else data.get("key"),
      url=data.get("url"),
      alt_text=data.get("alt_text"),
      gcs_uri=data.get("gcs_uri"),
      url_upscaled=data.get("url_upscaled"),
      gcs_uri_upscaled=data.get("gcs_uri_upscaled"),
      original_prompt=data.get("original_prompt"),
      final_prompt=data.get("final_prompt"),
      model_thought=data.get("model_thought"),
      error=data.get("error"),
      owner_user_id=data.get("owner_user_id"),
      generation_metadata=generation_metadata or GenerationMetadata(),
      gemini_evaluation=data.get("gemini_evaluation"),
      generation_id=data.get("generation_id"),
    )


@dataclass
class Video:
  """Represents a generated video and its publishing metadata."""
  key: str | None = None
  gcs_uri: str | None = None

  @property
  def url(self) -> str | None:
    """Return the public URL of the video."""
    if not self.gcs_uri:
      return None
    return cloud_storage.get_public_cdn_url(self.gcs_uri)

  @property
  def is_success(self) -> bool:
    """Check if the video generation was successful."""
    return self.gcs_uri is not None

  @property
  def as_dict(self) -> dict[str, Any]:
    """Convert to dictionary for Firestore storage."""
    return {
      'gcs_uri': self.gcs_uri,
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any], key: str | None = None) -> Video:
    """Create Video from Firestore dictionary."""
    return cls(
      key=key if key else data.get("key"),
      gcs_uri=data.get("gcs_uri"),
    )


@dataclass(kw_only=True)
class Character:
  """Represents a character in the story."""
  key: str | None = None
  name: str
  age: int
  gender: str
  user_description: str
  tagline: str
  sanitized_description: str
  portrait_description: str
  portrait_image_key: str | None
  all_portrait_image_keys: list[str]
  owner_user_id: str
  generation_metadata: GenerationMetadata = field(
    default_factory=GenerationMetadata)

  @property
  def is_public(self) -> bool:
    """Check if the character is public."""
    return self.owner_user_id == "PUBLIC"

  @property
  def description_xml(self) -> str:
    """Convert the description to XML format."""
    parts = [
      "<character>",
      f"<name>{self.name}</name>",
      f"<age>{self.age}</age>",
    ]
    if self.gender:
      parts.append(f"<gender>{self.gender}</gender>")
    parts.extend([
      "<description>",
      self.sanitized_description,
      "</description>",
      "</character>",
    ])
    return "\n".join(parts)

  @classmethod
  def get_full_description(
    cls,
    name: str,
    age: int,
    gender: str,
    portrait_description: str = "",
    sanitized_description: str = "",
  ) -> str:
    """Get the portrait description."""
    match gender.lower():
      case "male":
        gender_str = "Gender: male. "
      case "female":
        gender_str = "Gender: female. "
      case _:
        gender_str = ""
    return (f"Name: {name}. Age: {age} year old. {gender_str}"
            f"Description: {sanitized_description} {portrait_description}")

  def to_dict(self, include_key: bool) -> dict[str, Any]:
    """Convert to dictionary for Firestore storage."""
    data = {
      'name': self.name,
      'age': self.age,
      'gender': self.gender,
      'user_description': self.user_description,
      'tagline': self.tagline,
      'sanitized_description': self.sanitized_description,
      'portrait_description': self.portrait_description,
      'portrait_image_key': self.portrait_image_key,
      'all_portrait_image_keys': self.all_portrait_image_keys,
      'owner_user_id': self.owner_user_id,
      'generation_metadata':
      self.generation_metadata.as_dict if self.generation_metadata else {},
    }
    if include_key:
      data['key'] = self.key
    return data

  @classmethod
  def from_dict(cls,
                data: dict[str, Any],
                key: str | None = None) -> Character:
    """Create Character from Firestore dictionary."""

    generation_metadata = None

    if 'generation_metadata' in data:

      generation_metadata = GenerationMetadata.from_dict(
        data['generation_metadata'])

    _parse_int_field(data, 'age', 0)

    _parse_string_list(data, 'all_portrait_image_keys', dedupe=True)

    return cls(
      key=key if key else data.get("key"),
      name=data.get('name', ''),
      age=data.get('age', 0),
      gender=data.get('gender', ''),
      user_description=data.get('user_description', ''),
      tagline=data.get('tagline', ""),
      sanitized_description=data.get('sanitized_description', ""),
      portrait_description=data.get('portrait_description', ""),
      portrait_image_key=data.get('portrait_image_key'),
      all_portrait_image_keys=data.get('all_portrait_image_keys', []),
      owner_user_id=data.get('owner_user_id', ''),
      generation_metadata=generation_metadata or GenerationMetadata(),
    )

  def update(self, other: Character) -> None:
    """Update this character's fields from another character object."""
    self.name = other.name
    self.age = other.age
    self.gender = other.gender
    self.user_description = other.user_description
    self.tagline = other.tagline
    self.sanitized_description = other.sanitized_description
    self.portrait_description = other.portrait_description
    self.portrait_image_key = other.portrait_image_key

    if not self.generation_metadata:
      self.generation_metadata = GenerationMetadata()
    self.generation_metadata.add_generation(other.generation_metadata)

    if (self.portrait_image_key is not None
        and self.portrait_image_key not in self.all_portrait_image_keys):
      self.all_portrait_image_keys = [self.portrait_image_key
                                      ] + self.all_portrait_image_keys


@dataclass
class StoryCharacterData:
  """Represents a character's description in a story."""

  name: str = ""
  """The name of the character."""

  visual: str = ""
  """Visual description of the character."""

  humor: str = ""
  """Description of what makes the character funny."""

  @property
  def as_dict(self) -> dict[str, Any]:
    """Convert to dictionary for Firestore storage."""
    return {
      'name': self.name,
      'visual': self.visual,
      'humor': self.humor,
    }

  @property
  def xml(self) -> str:
    """Convert to XML format."""
    return f"""
<character>
  <name>{self.name}</name>
  <visual_description>{self.visual}</visual_description>
  <humor>{self.humor}</humor>
</character>
""".strip()

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> StoryCharacterData:
    """Create a StoryCharacterData instance from a dictionary.

    Args:
        data: Dictionary containing 'name', 'visual', and 'humor' fields

    Returns:
        StoryCharacterData instance
    """
    return cls(name=data.get('name', ''),
               visual=data.get('visual', ''),
               humor=data.get('humor', ''))


@dataclass
class StoryIllustrationData:
  """Represents an illustration with its description and characters."""

  description: str = ""
  """Description of the illustration."""

  characters: list[str] = field(default_factory=list)
  """List of character names that appear in the illustration."""

  @property
  def as_dict(self) -> dict[str, Any]:
    """Convert to dictionary for Firestore storage."""
    return {
      'description': self.description,
      'characters': self.characters,
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> StoryIllustrationData:
    """Create a StoryIllustrationData instance from a dictionary.

    Args:
        data: Dictionary containing 'description' and 'characters' fields

    Returns:
        StoryIllustrationData instance
    """
    return cls(description=data.get('description', ''),
               characters=data.get('characters', []))


@dataclass
class StoryPageData:
  """Represents a page in the story."""
  illustration: StoryIllustrationData = field(
    default_factory=StoryIllustrationData)
  """The illustration for this page."""

  text: str = ""
  """The text content of this page."""

  humor: str = ""
  """Description of the humor in this page."""

  page_number: int = 0
  """The page number, as provided by the LLM."""

  raw_page_content: str = ""
  """Raw content of the page for debugging."""

  @property
  def is_complete(self) -> bool:
    """Check if the page is complete."""
    return bool(self.page_number > 0 and self.text
                and self.illustration.description)

  @property
  def as_dict(self) -> dict[str, Any]:
    """Convert to dictionary for Firestore storage."""
    return {
      'illustration': self.illustration.as_dict,
      'text': self.text,
      'humor': self.humor,
      'page_number': self.page_number,
      'raw_page_content': self.raw_page_content,
    }


@dataclass
class StoryLearningConceptData:
  """Represents an educational concept in the story."""
  explanation: str = ""
  """Child-friendly explanation of the concept."""

  plot: str = ""
  """How the concept drives the plot forward."""

  demonstration: str = ""
  """How the concept is actively demonstrated in the story."""

  @property
  def as_dict(self) -> dict[str, Any]:
    """Convert to dictionary for Firestore storage."""
    return {
      'explanation': self.explanation,
      'plot': self.plot,
      'demonstration': self.demonstration,
    }


@dataclass
class StoryData:
  """Data returned from story generation."""

  title: str = ""
  """The story's title."""

  tagline: str = ""
  """Single-line tagline that hooks reader interest."""

  summary: str = ""
  """One sentence summary of the story."""

  tone: str = ""
  """Tone of the story."""

  plot_brainstorm: str = ""
  """Brainstorming ideas for the plot."""

  plot_summary: str = ""
  """Detailed summary of the plot (about 20 sentences)."""

  outline: str = ""
  """Outline of the story generated during the planning phase."""

  pages: list[StoryPageData] = field(default_factory=list)
  """List of pages containing text and illustration descriptions."""

  characters: dict[str, StoryCharacterData] = field(default_factory=dict)
  """Map of character names to their descriptions for illustration generation."""

  cover_illustration: StoryIllustrationData = field(
    default_factory=StoryIllustrationData)
  """The cover illustration data."""

  learning_concepts: dict[str, StoryLearningConceptData] = field(
    default_factory=dict)
  """Map of educational concepts/topics/keywords to their details."""

  @property
  def is_empty(self) -> bool:
    """Check if the story data is empty."""
    return not self.pages

  @property
  def as_dict(self) -> dict[str, Any]:
    """Convert to dictionary for Firestore storage."""
    return {
      'title': self.title,
      'tagline': self.tagline,
      'summary': self.summary,
      'tone': self.tone,
      'plot_brainstorm': self.plot_brainstorm,
      'plot_summary': self.plot_summary,
      'outline': self.outline,
      'pages': [page.as_dict for page in self.pages],
      'characters': {
        name: char.as_dict
        for name, char in self.characters.items()
      },
      'cover_illustration': self.cover_illustration.as_dict,
      'learning_concepts': {
        name: concept.as_dict
        for name, concept in self.learning_concepts.items()
      },
    }

  @property
  def outline_xml(self) -> str:
    """Convert the outline to XML format."""
    if not (self.title and self.tone and self.outline and self.characters
            and self.learning_concepts):
      raise ValueError(f"StoryData is not complete:\n{self}")

    parts: list[str] = []

    for name, concept in self.learning_concepts.items():
      parts.append(f"""
<reference_material_concept>
  <concept>{name}</concept>
  <explanation>{concept.explanation}</explanation>
  <plot_usage>{concept.plot}</plot_usage>
  <demonstration>{concept.demonstration}</demonstration>
</reference_material_concept>
""".strip())

    parts.append(f"<title>{self.title}</title>")
    parts.append(f"<tone>{self.tone}</tone>")
    parts.append("\n\n".join(c.xml for c in self.characters.values()))
    parts.append(f"""
<outline>
{self.outline}
</outline>""".strip())

    return "\n\n".join(parts)

  def update(self, other: StoryData) -> set[str]:
    """Update this StoryData's fields from another StoryData object.

    Args:
        other: Another StoryData object to merge values from

    Returns:
        Set of keys that were updated
    """
    updated_keys: set[str] = set()
    if other.title:
      self.title = other.title
      updated_keys.add('title')
    if other.tagline:
      self.tagline = other.tagline
      updated_keys.add('tagline')
    if other.summary:
      self.summary = other.summary
      updated_keys.add('summary')
    if other.tone:
      self.tone = other.tone
      updated_keys.add('tone')
    if other.plot_brainstorm:
      self.plot_brainstorm = other.plot_brainstorm
      updated_keys.add('plot_brainstorm')
    if other.plot_summary:
      self.plot_summary = other.plot_summary
      updated_keys.add('plot_summary')
    if other.outline:
      self.outline = other.outline
      updated_keys.add('outline')
    if other.pages:
      self.pages.extend(other.pages)
      self.pages.sort(key=lambda x: x.page_number)
      updated_keys.add('pages')
    if other.cover_illustration.description or other.cover_illustration.characters:
      self.cover_illustration = other.cover_illustration
      updated_keys.add('cover_illustration')
    if other.characters:
      self.characters.update(other.characters)
      updated_keys.add('characters')
    if other.learning_concepts:
      self.learning_concepts.update(other.learning_concepts)
      updated_keys.add('learning_concepts')

    return updated_keys


@dataclass
class JokeSheet:
  """Represents a joke sheet document in Firestore (`joke_sheets`)."""

  key: str | None = None
  joke_str_hash: str = ""
  joke_ids: list[str] = field(default_factory=list)
  category_id: str | None = None
  index: int | None = None
  sheet_slug: str | None = None
  image_gcs_uri: str | None = None
  image_gcs_uris: list[str] = field(default_factory=list)
  pdf_gcs_uri: str | None = None
  avg_saved_users_fraction: float = 0.0

  def __post_init__(self):
    """Normalize preview and page image fields for backward compatibility."""
    normalized_image_uris = [uri for uri in self.image_gcs_uris if uri.strip()]
    self.image_gcs_uris = normalized_image_uris

    if self.image_gcs_uri and self.image_gcs_uri not in self.image_gcs_uris:
      self.image_gcs_uris.insert(0, self.image_gcs_uri)

    if not self.image_gcs_uri and self.image_gcs_uris:
      self.image_gcs_uri = self.image_gcs_uris[0]

  @property
  def display_index(self) -> int | None:
    """Return the 1-based index for display/URLs."""
    if self.index is None:
      return None
    if self.index < 0:
      return None
    return self.index + 1

  @property
  def slug(self) -> str | None:
    """Return the URL slug for the joke sheet details page."""
    if self.sheet_slug:
      return self.sheet_slug
    category_id = (self.category_id or "").strip()
    display_index = self.display_index
    if not category_id or display_index is None:
      return None
    category_slug = category_id.replace("_", "-")
    return f"free-{category_slug}-jokes-{display_index}"

  @staticmethod
  def parse_slug(slug: str) -> tuple[str | None, int | None]:
    """Parse a joke sheet slug into (category_id, index)."""
    slug = (slug or "").strip()
    if not slug:
      return None, None
    match = re.match(r"^free-(?P<category>.+)-jokes-(?P<index>\d+)$", slug)
    if not match:
      return None, None
    category_slug = match.group("category")
    if not category_slug:
      return None, None
    try:
      display_index = int(match.group("index"))
    except (TypeError, ValueError):
      return None, None
    if display_index <= 0:
      return None, None
    category_id = category_slug.replace("-", "_")
    return category_id, display_index - 1

  def to_dict(self) -> dict[str, Any]:
    """Serialize sheet fields for Firestore writes."""
    data = dataclasses.asdict(self)
    # `key` is the Firestore document id, not stored as a field.
    data.pop("key", None)

    return data

  @classmethod
  def from_firestore_dict(cls, data: dict[str, Any], key: str) -> JokeSheet:
    """Create a JokeSheet from a Firestore dictionary."""
    if not data:
      data = {}
    else:
      data = dict(data)

    # Populate document id.
    data["key"] = key

    # Filter to dataclass fields to avoid unexpected keys.
    allowed = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in data.items() if k in allowed}
    return cls(**filtered)


@dataclass(kw_only=True)
class JokeBook:
  """Represents a joke book document in Firestore (`joke_books`)."""

  id: str | None = None
  """Firestore document ID for this joke book."""

  book_name: str = ""
  jokes: list[str] = field(default_factory=list)
  associated_book_key: str | None = None
  belongs_to_page_gcs_uri: str | None = None
  zip_url: str | None = None
  paperback_pdf_url: str | None = None
  ebook_pdf_url: str | None = None

  @property
  def joke_count(self) -> int:
    """Return the number of jokes in the book."""
    return len(self.jokes)

  def to_dict(self) -> dict[str, Any]:
    """Serialize joke book fields for Firestore writes."""
    data = dataclasses.asdict(self)
    data.pop('id', None)
    return data

  @classmethod
  def from_firestore_dict(cls, data: dict[str, Any], key: str) -> JokeBook:
    """Create a JokeBook from a Firestore dictionary."""
    if not data:
      data = {}
    else:
      data = dict(data)

    data['id'] = key
    if 'book_name' not in data or data.get('book_name') is None:
      data['book_name'] = ''
    _parse_string_list(data, 'jokes', dedupe=False)

    allowed = {field.name for field in dataclasses.fields(cls)}
    filtered = {name: value for name, value in data.items() if name in allowed}
    return cls(**filtered)


@dataclass(kw_only=True)
class JokeSocialPost:
  """Represents a social post derived from jokes."""

  type: JokeSocialPostType
  jokes: list[PunnyJoke] = field(default_factory=list)
  key: str | None = None
  link_url: str | None = None
  creation_time: datetime.datetime | None = None

  pinterest_image_urls: list[str] = field(default_factory=list)
  pinterest_video_gcs_uri: str | None = None
  pinterest_post_id: str | None = None
  pinterest_post_time: datetime.datetime | None = None
  pinterest_title: str | None = None
  pinterest_description: str | None = None
  pinterest_alt_text: str | None = None

  instagram_image_urls: list[str] = field(default_factory=list)
  instagram_video_gcs_uri: str | None = None
  instagram_post_id: str | None = None
  instagram_post_time: datetime.datetime | None = None
  instagram_caption: str | None = None
  instagram_alt_text: str | None = None

  facebook_image_urls: list[str] = field(default_factory=list)
  facebook_video_gcs_uri: str | None = None
  facebook_post_id: str | None = None
  facebook_post_time: datetime.datetime | None = None
  facebook_message: str | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.link_url, str) or not self.link_url:
      raise ValueError("JokeSocialPost requires a link_url")

  def is_platform_posted(self, platform: SocialPlatform) -> bool:
    """Return True if the platform has already been posted."""
    prefix = platform.value
    post_time = getattr(self, f"{prefix}_post_time", None)
    post_id = getattr(self, f"{prefix}_post_id", None)
    return bool(post_time or post_id)

  def platform_summary(self, platform: SocialPlatform) -> str:
    """Return a summary of the social post for a given platform."""
    lines: list[str] = []
    post_time: datetime.datetime | None = None
    match platform:
      case SocialPlatform.PINTEREST:
        post_time = self.pinterest_post_time or self.creation_time
        lines.append("Pinterest post:")
        lines.append(f"Title: {self.pinterest_title}")
        lines.append(f"Description: {self.pinterest_description}")
        lines.append(f"Alt text: {self.pinterest_alt_text}")

      case SocialPlatform.INSTAGRAM:
        post_time = self.instagram_post_time or self.creation_time
        lines.append("Instagram post:")
        lines.append(f"Caption: {self.instagram_caption}")
        lines.append(f"Alt text: {self.instagram_alt_text}")

      case SocialPlatform.FACEBOOK:
        post_time = self.facebook_post_time or self.creation_time
        lines.append("Facebook post:")
        lines.append(f"Message: {self.facebook_message}")

    if post_time:
      lines.append(f"Posted at {post_time.strftime('%Y-%m-%d %H:%M')}")

    return "\n".join(lines)

  def to_dict(self) -> dict[str, Any]:
    """Serialize social post fields for Firestore writes."""
    data = dataclasses.asdict(self)
    data['type'] = self.type.value
    data['jokes'] = [joke.get_minimal_joke_data() for joke in self.jokes]
    data.pop('key', None)
    data.pop('creation_time', None)
    return data

  @classmethod
  def from_firestore_dict(cls, data: dict[str, Any],
                          key: str) -> JokeSocialPost:
    """Create a JokeSocialPost from a Firestore dictionary."""
    if not data:
      data = {}
    else:
      data = dict(data)

    creation_time = data.get('creation_time')
    if creation_time is not None and not isinstance(creation_time,
                                                    datetime.datetime):
      data.pop('creation_time', None)

    type_value = data.get('type')
    if not isinstance(type_value, str) or not type_value:
      raise ValueError("JokeSocialPost requires a type")
    try:
      data['type'] = JokeSocialPostType[type_value]
    except KeyError as exc:
      raise ValueError(f"Invalid JokeSocialPost type: {type_value}") from exc

    link_url = data.get('link_url')
    if not isinstance(link_url, str) or not link_url:
      raise ValueError("JokeSocialPost requires a link_url")

    raw_jokes = data.get('jokes')
    jokes: list[PunnyJoke] = []
    if isinstance(raw_jokes, list):
      for raw_item in cast(list[Any], raw_jokes):
        if not isinstance(raw_item, dict):
          continue
        item = cast(dict[str, Any], raw_item)
        try:
          item_key = item.get('key')
          if not isinstance(item_key, str):
            continue
          jokes.append(PunnyJoke.from_firestore_dict(item, key=item_key))
        except (TypeError, ValueError):
          continue
    data['jokes'] = jokes

    data['key'] = key

    allowed = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in data.items() if k in allowed}
    return cls(**filtered)


@dataclass(kw_only=True)
class JokeCategory:
  """Represents a joke category used for grouping jokes."""

  id: str | None = None
  """Firestore document ID for this category."""

  display_name: str
  """Display name of the category."""

  joke_description_query: str | None = None
  """If set, this category is a search category and jokes are selected by searching for this query."""

  seasonal_name: str | None = None
  """If set, this category is seasonal and jokes are selected by `seasonal`."""

  book_id: str | None = None
  """If set, this category includes jokes from the joke_books collection with this ID."""

  search_distance: float | None = None
  """Optional search distance threshold override for this category's search query."""

  tags: list[str] = field(default_factory=list)
  """If set, this category also includes jokes that match any of these tags."""

  negative_tags: list[str] = field(default_factory=list)
  """If set, jokes with any of these tags are excluded from the category."""

  state: str = "PROPOSED"
  """Category lifecycle: APPROVED, SEASONAL, PROPOSED, REJECTED, or BOOK."""

  image_url: str | None = None
  """Primary image URL for the category tile."""

  all_image_urls: list[str] = field(default_factory=list)
  """All known image URLs for the category (used by the app image carousel)."""

  joke_sheets_branded_id: str | None = None
  """Optional branded lunchbox notes sheet id for the full category."""

  joke_sheets_unbranded_id: str | None = None
  """Optional unbranded lunchbox notes sheet id for the full category."""

  image_description: str | None = None
  joke_id_order: list[str] = field(default_factory=list)
  jokes: list[PunnyJoke] = field(default_factory=list)

  public_joke_count: int | None = None
  """Cached count of public jokes in this category (only populated from cache docs)."""

  @property
  def key(self) -> str:
    """Computed Firestore-safe key from display name.

    Lowercase and replace any non-alphanumeric characters with underscores,
    collapsing runs and trimming leading/trailing underscores.
    """
    lowered = (self.display_name or "").lower()
    # Replace any run of non [a-z0-9] with a single underscore
    snake = re.sub(r"[^a-z0-9]+", "_", lowered)
    return snake.strip("_")

  def to_dict(self) -> dict[str, Any]:
    """Serialize category fields for Firestore writes."""
    data = dataclasses.asdict(self)
    # `id` is the Firestore document id, not stored as a field.
    data.pop('id', None)
    # `jokes` is the cached joke list loaded from a subcollection.
    data.pop('jokes', None)
    # Derived/cache-only fields should never be written to the category doc.
    data.pop("public_joke_count", None)
    return data

  @classmethod
  def from_firestore_dict(cls, data: dict[str, Any], key: str) -> JokeCategory:
    """Create a JokeCategory from a Firestore dictionary."""
    if not data:
      data = {}
    else:
      data = dict(data)

    # Populate document id.
    data['id'] = key

    # Ensure required fields exist.
    if 'display_name' not in data or data.get('display_name') is None:
      data['display_name'] = ''

    # Ensure list fields have the right types.
    _parse_string_list(data, 'all_image_urls', dedupe=False)
    _parse_string_list(data, 'tags', dedupe=True)
    _parse_string_list(data, 'negative_tags', dedupe=True)
    _parse_string_list(data, 'joke_id_order', dedupe=True)

    _parse_float_field(data, 'search_distance')

    # Optional integer field.
    raw_count = data.get('public_joke_count')
    if isinstance(raw_count, (int, float)):
      data['public_joke_count'] = int(raw_count)
    else:
      data.pop('public_joke_count', None)

    # Default state if missing/empty.
    state_val = data.get('state')
    if not isinstance(state_val, str) or not state_val:
      data['state'] = "PROPOSED"

    # Filter to dataclass fields to avoid unexpected keys.
    allowed = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in data.items() if k in allowed}
    return cls(**filtered)


@dataclass(kw_only=True)
class PunnyJoke:
  """Represents a punny joke."""

  key: str | None = None
  random_id: int | None = None

  setup_text: str
  punchline_text: str
  setup_text_slug: str | None = None

  # Category membership (best-effort).
  # - "_uncategorized" means the joke is public but not in any category cache.
  # - Any other non-empty string is the last processed category that included it.
  category_id: str | None = None

  pun_theme: str | None = None
  phrase_topic: str | None = None
  tags: list[str] = field(default_factory=list)
  for_kids: bool = False
  for_adults: bool = False
  seasonal: str | None = None
  pun_word: str | None = None
  punned_word: str | None = None

  setup_scene_idea: str | None = None
  """Conceptual outline for the setup illustration."""

  punchline_scene_idea: str | None = None
  """Conceptual outline for the punchline illustration."""

  setup_image_description: str | None = None
  punchline_image_description: str | None = None

  setup_image_prompt: str | None = None
  punchline_image_prompt: str | None = None

  setup_image_url: str | None = None
  punchline_image_url: str | None = None

  setup_image_url_upscaled: str | None = None
  punchline_image_url_upscaled: str | None = None

  all_setup_image_urls: list[str] = field(default_factory=list)
  all_punchline_image_urls: list[str] = field(default_factory=list)

  num_thumbs_up: int = 0
  num_thumbs_down: int = 0
  num_saved_users: int = 0
  num_shared_users: int = 0
  num_viewed_users: int = 0
  num_saved_users_fraction: float = 0.0
  num_shared_users_fraction: float = 0.0
  popularity_score: float = 0.0

  state: JokeState = JokeState.UNKNOWN
  admin_rating: JokeAdminRating = JokeAdminRating.UNREVIEWED

  book_id: str | None = None
  owner_user_id: str | None = None
  public_timestamp: datetime.datetime | None = None
  is_public: bool = False
  generation_metadata: GenerationMetadata = field(
    default_factory=GenerationMetadata)

  @property
  def human_readable_setup_text_slug(self) -> str:
    """Get the setup text slug."""
    return utils.get_text_slug(self.setup_text, human_readable=True)

  @classmethod
  def from_firestore_dict(cls, data: dict[str, Any], key: str) -> 'PunnyJoke':
    """Create a PunnyJoke from a Firestore dictionary.

    Mirrors Firestore read logic so new fields are auto-applied while
    stripping Firestore-only fields and converting nested metadata.
    """
    if not data:
      data = {}
    else:
      data = dict(data)

    # Drop Firestore-only fields
    data.pop('creation_time', None)
    data.pop('last_modification_time', None)

    # Convert nested metadata
    if 'generation_metadata' in data:
      data['generation_metadata'] = GenerationMetadata.from_dict(
        data.get('generation_metadata'))

    # Convert string enums
    _parse_enum_field(
      data,
      'state',
      JokeState,
      JokeState.UNKNOWN,
    )
    _parse_enum_field(
      data,
      'admin_rating',
      JokeAdminRating,
      JokeAdminRating.UNREVIEWED,
    )

    _parse_string_list(data, 'tags')
    _parse_string_list(data, 'all_setup_image_urls', dedupe=False)
    _parse_string_list(data, 'all_punchline_image_urls', dedupe=False)

    _parse_int_field(data, 'num_thumbs_up', 0)
    _parse_int_field(data, 'num_thumbs_down', 0)
    _parse_int_field(data, 'num_saved_users', 0)
    _parse_int_field(data, 'num_shared_users', 0)
    _parse_int_field(data, 'num_viewed_users', 0)
    _parse_float_field(data, 'num_saved_users_fraction', 0.0)
    _parse_float_field(data, 'num_shared_users_fraction', 0.0)
    _parse_float_field(data, 'popularity_score', 0.0)

    data['key'] = key

    # Filter to dataclass fields to avoid unexpected keys
    allowed = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in data.items() if k in allowed}

    return cls(**filtered)

  @staticmethod
  def prepare_book_page_metadata_updates(
    existing_metadata: dict[str, Any] | None,
    new_setup_page_url: str,
    new_punchline_page_url: str,
    setup_prompt: str | None = None,
    punchline_prompt: str | None = None,
  ) -> dict[str, Any]:
    """Prepare metadata updates for book page URLs with history tracking."""
    metadata = existing_metadata or {}
    existing_ready = metadata.get('book_page_ready')
    book_page_ready = False
    if isinstance(existing_ready, bool):
      book_page_ready = existing_ready
    elif isinstance(existing_ready, str):
      book_page_ready = existing_ready.lower() == 'true'

    def _normalize_book_page_url(url: str | None) -> str | None:
      """Normalize CDN params to the canonical book page format."""
      if not url:
        return url
      prefix = "https://images.quillsstorybook.com/cdn-cgi/image/"
      if not url.startswith(prefix):
        return url
      remainder = url.removeprefix(prefix)
      slash_index = remainder.find('/')
      if slash_index == -1:
        return url
      object_path = remainder[slash_index + 1:]
      return (f"{prefix}width=1024,format=auto,quality=75/"
              f"{object_path}")

    def _unique_normalized(urls: list[str]) -> list[str]:
      seen: set[str] = set()
      result: list[str] = []
      for url in urls:
        norm = _normalize_book_page_url(url)
        if norm and norm not in seen:
          seen.add(norm)
          result.append(norm)
      return result

    existing_setup_urls = metadata.get('all_book_page_setup_image_urls')
    setup_history_raw = ([
      item for item in cast(list[Any], existing_setup_urls)
      if isinstance(item, str)
    ] if isinstance(existing_setup_urls, list) else [])

    existing_punchline_urls = metadata.get(
      'all_book_page_punchline_image_urls')
    punchline_history_raw = ([
      item for item in cast(list[Any], existing_punchline_urls)
      if isinstance(item, str)
    ] if isinstance(existing_punchline_urls, list) else [])

    previous_setup_url = _normalize_book_page_url(
      metadata.get('book_page_setup_image_url'))
    previous_punchline_url = _normalize_book_page_url(
      metadata.get('book_page_punchline_image_url'))

    normalized_setup_history = _unique_normalized(setup_history_raw)
    normalized_punchline_history = _unique_normalized(punchline_history_raw)

    normalized_new_setup = _normalize_book_page_url(new_setup_page_url)
    normalized_new_punchline = _normalize_book_page_url(new_punchline_page_url)

    for url in (previous_setup_url, normalized_new_setup):
      if url and url not in normalized_setup_history:
        normalized_setup_history.append(url)

    for url in (previous_punchline_url, normalized_new_punchline):
      if url and url not in normalized_punchline_history:
        normalized_punchline_history.append(url)

    updates = {
      'book_page_setup_image_url': normalized_new_setup,
      'book_page_punchline_image_url': normalized_new_punchline,
      'all_book_page_setup_image_urls': normalized_setup_history,
      'all_book_page_punchline_image_urls': normalized_punchline_history,
      'book_page_ready': book_page_ready,
    }
    if setup_prompt:
      updates['book_page_setup_image_prompt'] = setup_prompt
    if punchline_prompt:
      updates['book_page_punchline_image_prompt'] = punchline_prompt
    return updates

  @property
  def unpopulated_fields(self) -> set[str]:
    """Get the fields that are not populated."""
    return {
      field.name
      for field in dataclasses.fields(self) if not getattr(self, field.name)
    }

  def set_setup_image(self, image: Image, update_text: bool = True) -> None:
    """Set the setup image."""
    if not image or not image.url:
      return

    self._set_setup_image_url(image.url)
    if update_text:
      self.setup_image_description = image.original_prompt
      self.setup_image_prompt = image.final_prompt
    self.generation_metadata.add_generation(image.generation_metadata)

  def set_punchline_image(
    self,
    image: Image,
    update_text: bool = True,
  ) -> None:
    """Set the punchline image."""
    if not image or not image.url:
      return

    self._set_punchline_image_url(image.url)
    if update_text:
      self.punchline_image_description = image.original_prompt
      self.punchline_image_prompt = image.final_prompt
    self.generation_metadata.add_generation(image.generation_metadata)

  def _set_setup_image_url(self, url: str) -> None:
    """Set the setup image URL and add it to the all_setup_image_urls list."""
    if not url:
      return

    if url and url not in self.all_setup_image_urls:
      self.all_setup_image_urls.append(url)
    if self.setup_image_url and self.setup_image_url not in self.all_setup_image_urls:
      self.all_setup_image_urls.append(self.setup_image_url)

    self.setup_image_url = url

  def _set_punchline_image_url(self, url: str) -> None:
    """Set the punchline image URL and add it to the all_punchline_image_urls list."""
    if not url:
      return

    if url and url not in self.all_punchline_image_urls:
      self.all_punchline_image_urls.append(url)
    if self.punchline_image_url and self.punchline_image_url not in self.all_punchline_image_urls:
      self.all_punchline_image_urls.append(self.punchline_image_url)

    self.punchline_image_url = url

  def to_dict(self, include_key: bool = False) -> dict[str, object]:
    """Convert to dictionary for Firestore/response serialization.

    - Serializes `state` enum to its string value
    - Serializes `generation_metadata` using its `as_dict`
    - Optionally includes `key`
    """
    data = dataclasses.asdict(self)

    # Ensure enums are serialized to their string values
    data['state'] = self.state.value
    data['admin_rating'] = self.admin_rating.value

    # Ensure generation_metadata is serialized via as_dict
    if self.generation_metadata:
      data['generation_metadata'] = self.generation_metadata.as_dict
    else:
      data['generation_metadata'] = {}
    if not include_key:
      data.pop('key', None)
    return data

  def get_minimal_joke_data(self) -> dict[str, str | None]:
    """Get a minimal dictionary representation of the joke for denormalization."""
    return {
      "key": self.key,
      "setup_text": self.setup_text,
      "punchline_text": self.punchline_text,
      "setup_image_url": self.setup_image_url,
      "punchline_image_url": self.punchline_image_url,
    }

  @property
  def is_public_and_in_public_state(self) -> bool:
    """Check if the joke is public and in a public state."""
    return bool(self.is_public
                and self.state in (JokeState.PUBLISHED, JokeState.DAILY))

  def get_category_cache_joke_data(self) -> dict[str, str | None]:
    """Get the joke payload used by `joke_categories/*/category_jokes/cache`.

    Includes both the legacy category cache keys and the minimal joke keys to
    support schema migration.

    TODO: Remove the legacy category cache keys after schema migration.
    """
    minimal = self.get_minimal_joke_data()
    payload = {
      "joke_id": minimal.get("key"),
      "setup": minimal.get("setup_text"),
      "punchline": minimal.get("punchline_text"),
      "setup_image_url": minimal.get("setup_image_url"),
      "punchline_image_url": minimal.get("punchline_image_url"),
    }
    return {**minimal, **payload}


@dataclass(kw_only=True)
class PosableCharacterDef:
  """Definition for a posable character (assets and dimensions)."""

  key: str | None = None
  name: str | None = None

  width: int = 0
  height: int = 0

  head_gcs_uri: str = ""
  surface_line_gcs_uri: str = ""
  left_hand_gcs_uri: str = ""
  right_hand_gcs_uri: str = ""
  mouth_open_gcs_uri: str = ""
  mouth_closed_gcs_uri: str = ""
  mouth_o_gcs_uri: str = ""
  left_eye_open_gcs_uri: str = ""
  left_eye_closed_gcs_uri: str = ""
  right_eye_open_gcs_uri: str = ""
  right_eye_closed_gcs_uri: str = ""

  def to_dict(self, include_key: bool = False) -> dict[str, object]:
    """Convert to dictionary for Firestore storage."""
    data = dataclasses.asdict(self)
    if not include_key:
      data.pop('key', None)
    return data

  @classmethod
  def from_firestore_dict(cls, data: dict[str, object],
                          key: str) -> PosableCharacterDef:
    """Create a PosableCharacterDef from a Firestore dictionary."""
    if not data:
      data = {}
    else:
      data = dict(data)

    data['key'] = key

    _parse_int_field(data, 'width', 0)
    _parse_int_field(data, 'height', 0)

    # Filter to dataclass fields
    allowed = {f.name for f in dataclasses.fields(cls)}
    filtered: dict[str, Any] = {k: v for k, v in data.items() if k in allowed}

    return cls(**filtered)


@dataclass(kw_only=True)
class AmazonProductStats:
  """Daily product-level metrics for one ASIN within a campaign."""

  asin: str
  units_sold: int = 0
  kenp_pages_read: int = 0
  total_sales_usd: float = 0.0
  unit_prices: set[float] = field(default_factory=set)
  total_profit_usd: float = 0.0
  kenp_royalties_usd: float = 0.0
  total_print_cost_usd: float | None = None
  total_royalty_usd: float | None = None

  def to_dict(self) -> dict[str, object]:
    """Convert to dictionary for Firestore storage."""
    data = dataclasses.asdict(self)
    data["unit_prices"] = sorted(self.unit_prices)
    return data

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> AmazonProductStats:
    """Create a product-stats model from a dictionary."""
    if not data:
      data = {}
    else:
      data = dict(data)
    if "total_sales_usd" not in data and "sales_amount" in data:
      data["total_sales_usd"] = data.get("sales_amount")
    if "total_profit_usd" not in data and "total_profit" in data:
      data["total_profit_usd"] = data.get("total_profit")
    if "kenp_royalties_usd" not in data and "kenp_royalties" in data:
      data["kenp_royalties_usd"] = data.get("kenp_royalties")
    if "total_print_cost_usd" not in data and "total_print_cost" in data:
      data["total_print_cost_usd"] = data.get("total_print_cost")
    if "total_royalty_usd" not in data and "total_royalty" in data:
      data["total_royalty_usd"] = data.get("total_royalty")

    asin = str(data.get("asin", "")).strip()
    _parse_int_field(data, "units_sold", 0)
    _parse_int_field(data, "kenp_pages_read", 0)
    _parse_float_field(data, "total_sales_usd", 0.0)
    _parse_float_field(data, "total_profit_usd", 0.0)
    _parse_float_field(data, "kenp_royalties_usd", 0.0)
    unit_prices: set[float] = set()
    raw_unit_prices = data.get("unit_prices")
    if isinstance(raw_unit_prices, list):
      for raw_price in cast(list[Any], raw_unit_prices):
        if isinstance(raw_price, (int, float)):
          unit_prices.add(float(raw_price))
        elif isinstance(raw_price, str):
          stripped = raw_price.strip()
          if not stripped:
            continue
          try:
            unit_prices.add(float(stripped))
          except ValueError:
            continue
    total_print_cost_usd = _parse_optional_float(data, "total_print_cost_usd")
    total_royalty_usd = _parse_optional_float(data, "total_royalty_usd")

    return cls(
      asin=asin,
      units_sold=data.get("units_sold", 0),
      kenp_pages_read=data.get("kenp_pages_read", 0),
      total_sales_usd=data.get("total_sales_usd", 0.0),
      unit_prices=unit_prices,
      total_profit_usd=data.get("total_profit_usd", 0.0),
      kenp_royalties_usd=data.get("kenp_royalties_usd", 0.0),
      total_print_cost_usd=total_print_cost_usd,
      total_royalty_usd=total_royalty_usd,
    )


@dataclass(kw_only=True)
class AmazonAdsDailyCampaignStats:
  """Daily campaign metrics merged from Amazon Ads reporting outputs."""

  key: str | None = None
  campaign_id: str
  campaign_name: str
  date: datetime.date
  spend: float = 0.0
  impressions: int = 0
  clicks: int = 0
  kenp_pages_read: int = 0
  kenp_royalties_usd: float = 0.0
  total_attributed_sales_usd: float = 0.0
  total_units_sold: int = 0
  gross_profit_before_ads_usd: float = 0.0
  gross_profit_usd: float = 0.0
  sale_items_by_asin_country: dict[str, dict[str, AmazonProductStats]] = field(
    default_factory=dict)

  @property
  def sale_items_by_asin(self) -> dict[str, AmazonProductStats]:
    """Return ASIN-level aggregates collapsed across all countries."""
    return _aggregate_product_stats_by_asin(self.sale_items_by_asin_country)

  @property
  def sale_items(self) -> list[AmazonProductStats]:
    """Compatibility accessor returning ASIN-level sale items."""
    return [
      self.sale_items_by_asin[asin]
      for asin in sorted(self.sale_items_by_asin.keys())
    ]

  def to_dict(self, include_key: bool = False) -> dict[str, object]:
    """Convert to dictionary for Firestore storage."""
    data: dict[str, object] = {
      "campaign_id":
      self.campaign_id,
      "campaign_name":
      self.campaign_name,
      "date":
      self.date.isoformat(),
      "spend":
      self.spend,
      "impressions":
      self.impressions,
      "clicks":
      self.clicks,
      "kenp_pages_read":
      self.kenp_pages_read,
      "kenp_royalties_usd":
      self.kenp_royalties_usd,
      "total_attributed_sales_usd":
      self.total_attributed_sales_usd,
      "total_units_sold":
      self.total_units_sold,
      "gross_profit_before_ads_usd":
      self.gross_profit_before_ads_usd,
      "gross_profit_usd":
      self.gross_profit_usd,
      "sale_items_by_asin_country":
      _serialize_product_stats_by_asin_country(
        self.sale_items_by_asin_country),
    }
    if include_key:
      data["key"] = self.key
    return data

  @classmethod
  def from_dict(
    cls,
    data: dict[str, Any],
    key: str | None = None,
  ) -> AmazonAdsDailyCampaignStats:
    """Create a daily campaign stats model from snake_case dictionary data."""
    if not data:
      data = {}
    else:
      data = dict(data)
    if "kenp_royalties_usd" not in data and "kenp_royalties" in data:
      data["kenp_royalties_usd"] = data.get("kenp_royalties")
    if ("total_attributed_sales_usd" not in data
        and "total_attributed_sales" in data):
      data["total_attributed_sales_usd"] = data.get("total_attributed_sales")
    if ("gross_profit_before_ads_usd" not in data
        and "gross_profit_before_ads" in data):
      data["gross_profit_before_ads_usd"] = data.get("gross_profit_before_ads")
    if "gross_profit_usd" not in data and "gross_profit" in data:
      data["gross_profit_usd"] = data.get("gross_profit")

    parsed_date = _parse_required_date(
      data.get("date"),
      field_name="AmazonAdsDailyCampaignStats.date",
    )

    _parse_float_field(data, "spend", 0.0)
    _parse_int_field(data, "impressions", 0)
    _parse_int_field(data, "clicks", 0)
    _parse_int_field(data, "kenp_pages_read", 0)
    _parse_float_field(data, "kenp_royalties_usd", 0.0)
    _parse_float_field(data, "total_attributed_sales_usd", 0.0)
    _parse_int_field(data, "total_units_sold", 0)
    _parse_float_field(data, "gross_profit_before_ads_usd", 0.0)
    _parse_float_field(data, "gross_profit_usd", 0.0)

    sale_items_by_asin_country = _parse_product_stats_by_asin_country_map(
      data.get("sale_items_by_asin_country"))

    campaign_id = str(data.get("campaign_id", "")).strip()
    campaign_name = str(data.get("campaign_name", "")).strip()
    if not campaign_id:
      raise ValueError("AmazonAdsDailyCampaignStats.campaign_id is required")
    if not campaign_name:
      raise ValueError("AmazonAdsDailyCampaignStats.campaign_name is required")

    return cls(
      key=key,
      campaign_id=campaign_id,
      campaign_name=campaign_name,
      date=parsed_date,
      spend=data.get("spend", 0.0),
      impressions=data.get("impressions", 0),
      clicks=data.get("clicks", 0),
      kenp_pages_read=data.get("kenp_pages_read", 0),
      kenp_royalties_usd=data.get("kenp_royalties_usd", 0.0),
      total_attributed_sales_usd=data.get("total_attributed_sales_usd", 0.0),
      total_units_sold=data.get("total_units_sold", 0),
      gross_profit_before_ads_usd=data.get("gross_profit_before_ads_usd", 0.0),
      gross_profit_usd=data.get("gross_profit_usd", 0.0),
      sale_items_by_asin_country=sale_items_by_asin_country,
    )

  @classmethod
  def from_firestore_dict(
    cls,
    data: dict[str, Any],
    key: str,
  ) -> AmazonAdsDailyCampaignStats:
    """Create a daily campaign stats model from Firestore data."""
    return cls.from_dict(data, key=key)


@dataclass(kw_only=True)
class AmazonAdsDailyStats:
  """Aggregated daily metrics across all Amazon Ads campaigns."""

  key: str | None = None
  date: datetime.date
  spend: float = 0.0
  impressions: int = 0
  clicks: int = 0
  kenp_pages_read: int = 0
  kenp_royalties_usd: float = 0.0
  total_attributed_sales_usd: float = 0.0
  total_units_sold: int = 0
  gross_profit_before_ads_usd: float = 0.0
  gross_profit_usd: float = 0.0
  campaigns_by_id: dict[str, AmazonAdsDailyCampaignStats] = field(
    default_factory=dict)

  def to_dict(self, include_key: bool = False) -> dict[str, object]:
    """Convert to dictionary for Firestore storage."""
    data: dict[str, object] = {
      "date": self.date.isoformat(),
      "spend": self.spend,
      "impressions": self.impressions,
      "clicks": self.clicks,
      "kenp_pages_read": self.kenp_pages_read,
      "kenp_royalties_usd": self.kenp_royalties_usd,
      "total_attributed_sales_usd": self.total_attributed_sales_usd,
      "total_units_sold": self.total_units_sold,
      "gross_profit_before_ads_usd": self.gross_profit_before_ads_usd,
      "gross_profit_usd": self.gross_profit_usd,
      "campaigns_by_id": {
        cid: stats.to_dict()
        for cid, stats in self.campaigns_by_id.items()
      },
    }
    if include_key:
      data["key"] = self.key
    return data

  @classmethod
  def from_dict(
    cls,
    data: dict[str, Any],
    key: str | None = None,
  ) -> AmazonAdsDailyStats:
    """Create a daily stats model from dictionary data."""
    if not data:
      data = {}
    else:
      data = dict(data)
    if "kenp_royalties_usd" not in data and "kenp_royalties" in data:
      data["kenp_royalties_usd"] = data.get("kenp_royalties")
    if ("total_attributed_sales_usd" not in data
        and "total_attributed_sales" in data):
      data["total_attributed_sales_usd"] = data.get("total_attributed_sales")
    if ("gross_profit_before_ads_usd" not in data
        and "gross_profit_before_ads" in data):
      data["gross_profit_before_ads_usd"] = data.get("gross_profit_before_ads")
    if "gross_profit_usd" not in data and "gross_profit" in data:
      data["gross_profit_usd"] = data.get("gross_profit")

    parsed_date = _parse_required_date(
      data.get("date"),
      field_name="AmazonAdsDailyStats.date",
    )

    _parse_float_field(data, "spend", 0.0)
    _parse_int_field(data, "impressions", 0)
    _parse_int_field(data, "clicks", 0)
    _parse_int_field(data, "kenp_pages_read", 0)
    _parse_float_field(data, "kenp_royalties_usd", 0.0)
    _parse_float_field(data, "total_attributed_sales_usd", 0.0)
    _parse_int_field(data, "total_units_sold", 0)
    _parse_float_field(data, "gross_profit_before_ads_usd", 0.0)
    _parse_float_field(data, "gross_profit_usd", 0.0)

    campaigns_raw = data.get("campaigns_by_id")
    campaigns_by_id: dict[str, AmazonAdsDailyCampaignStats] = {}
    if isinstance(campaigns_raw, dict):
      for cid, cdata in cast(dict[str, Any], campaigns_raw).items():
        if isinstance(cdata, dict):
          campaigns_by_id[cid] = AmazonAdsDailyCampaignStats.from_dict(
            cast(dict[str, Any], cdata))

    return cls(
      key=key,
      date=parsed_date,
      spend=data.get("spend", 0.0),
      impressions=data.get("impressions", 0),
      clicks=data.get("clicks", 0),
      kenp_pages_read=data.get("kenp_pages_read", 0),
      kenp_royalties_usd=data.get("kenp_royalties_usd", 0.0),
      total_attributed_sales_usd=data.get("total_attributed_sales_usd", 0.0),
      total_units_sold=data.get("total_units_sold", 0),
      gross_profit_before_ads_usd=data.get("gross_profit_before_ads_usd", 0.0),
      gross_profit_usd=data.get("gross_profit_usd", 0.0),
      campaigns_by_id=campaigns_by_id,
    )

  @classmethod
  def from_firestore_dict(
    cls,
    data: dict[str, Any],
    key: str,
  ) -> AmazonAdsDailyStats:
    """Create a daily stats model from Firestore data."""
    return cls.from_dict(data, key=key)


@dataclass(kw_only=True)
class AmazonKdpDailyStats:
  """Aggregated daily metrics from uploaded KDP xlsx data."""

  key: str | None = None
  date: datetime.date
  total_units_sold: int = 0
  kenp_pages_read: int = 0
  ebook_units_sold: int = 0
  paperback_units_sold: int = 0
  hardcover_units_sold: int = 0
  total_royalties_usd: float = 0.0
  ebook_royalties_usd: float = 0.0
  paperback_royalties_usd: float = 0.0
  hardcover_royalties_usd: float = 0.0
  total_print_cost_usd: float = 0.0
  sale_items_by_asin_country: dict[str, dict[str, AmazonProductStats]] = field(
    default_factory=dict)

  @property
  def sale_items_by_asin(self) -> dict[str, AmazonProductStats]:
    """Return ASIN-level aggregates collapsed across all countries."""
    return _aggregate_product_stats_by_asin(self.sale_items_by_asin_country)

  def to_dict(self, include_key: bool = False) -> dict[str, object]:
    """Convert to dictionary for Firestore storage."""
    data: dict[str, object] = {
      "date":
      self.date.isoformat(),
      "total_units_sold":
      self.total_units_sold,
      "kenp_pages_read":
      self.kenp_pages_read,
      "ebook_units_sold":
      self.ebook_units_sold,
      "paperback_units_sold":
      self.paperback_units_sold,
      "hardcover_units_sold":
      self.hardcover_units_sold,
      "total_royalties_usd":
      self.total_royalties_usd,
      "ebook_royalties_usd":
      self.ebook_royalties_usd,
      "paperback_royalties_usd":
      self.paperback_royalties_usd,
      "hardcover_royalties_usd":
      self.hardcover_royalties_usd,
      "total_print_cost_usd":
      self.total_print_cost_usd,
      "sale_items_by_asin_country":
      _serialize_product_stats_by_asin_country(
        self.sale_items_by_asin_country),
    }
    if include_key:
      data["key"] = self.key
    return data

  @classmethod
  def from_dict(
    cls,
    data: dict[str, Any],
    key: str | None = None,
  ) -> AmazonKdpDailyStats:
    """Create a KDP daily stats model from dictionary data."""
    if not data:
      data = {}
    else:
      data = dict(data)

    parsed_date = _parse_required_date(
      data.get("date"),
      field_name="AmazonKdpDailyStats.date",
    )

    _parse_int_field(data, "total_units_sold", 0)
    _parse_int_field(data, "kenp_pages_read", 0)
    _parse_int_field(data, "ebook_units_sold", 0)
    _parse_int_field(data, "paperback_units_sold", 0)
    _parse_int_field(data, "hardcover_units_sold", 0)
    _parse_float_field(data, "total_royalties_usd", 0.0)
    _parse_float_field(data, "ebook_royalties_usd", 0.0)
    _parse_float_field(data, "paperback_royalties_usd", 0.0)
    _parse_float_field(data, "hardcover_royalties_usd", 0.0)
    _parse_float_field(data, "total_print_cost_usd", 0.0)

    sale_items_by_asin_country = _parse_product_stats_by_asin_country_map(
      data.get("sale_items_by_asin_country"))

    return cls(
      key=key,
      date=parsed_date,
      total_units_sold=data.get("total_units_sold", 0),
      kenp_pages_read=data.get("kenp_pages_read", 0),
      ebook_units_sold=data.get("ebook_units_sold", 0),
      paperback_units_sold=data.get("paperback_units_sold", 0),
      hardcover_units_sold=data.get("hardcover_units_sold", 0),
      total_royalties_usd=data.get("total_royalties_usd", 0.0),
      ebook_royalties_usd=data.get("ebook_royalties_usd", 0.0),
      paperback_royalties_usd=data.get("paperback_royalties_usd", 0.0),
      hardcover_royalties_usd=data.get("hardcover_royalties_usd", 0.0),
      total_print_cost_usd=data.get("total_print_cost_usd", 0.0),
      sale_items_by_asin_country=sale_items_by_asin_country,
    )

  @classmethod
  def from_firestore_dict(
    cls,
    data: dict[str, Any],
    key: str,
  ) -> AmazonKdpDailyStats:
    """Create a KDP daily stats model from Firestore data."""
    return cls.from_dict(data, key=key)


@dataclass(kw_only=True)
class AmazonSalesReconciledAdsLot:
  """Unmatched ads-attributed units carried forward for one ASIN/date."""

  purchase_date: datetime.date
  units_remaining: int = 0
  kenp_pages_remaining: int = 0

  def to_dict(self) -> dict[str, object]:
    """Convert to dictionary for Firestore storage."""
    return {
      "purchase_date": self.purchase_date.isoformat(),
      "units_remaining": self.units_remaining,
      "kenp_pages_remaining": self.kenp_pages_remaining,
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> AmazonSalesReconciledAdsLot:
    """Create an unmatched ads lot model from dictionary data."""
    if not data:
      data = {}
    else:
      data = dict(data)

    parsed_date = _parse_required_date(
      data.get("purchase_date"),
      field_name="AmazonSalesReconciledAdsLot.purchase_date",
    )
    _parse_int_field(data, "units_remaining", 0)
    _parse_int_field(data, "kenp_pages_remaining", 0)

    return cls(
      purchase_date=parsed_date,
      units_remaining=data.get("units_remaining", 0),
      kenp_pages_remaining=data.get("kenp_pages_remaining", 0),
    )


@dataclass(kw_only=True)
class AmazonSalesReconciledAsinStats:
  """Reconciled KDP vs ads unit and revenue estimates for one ASIN+country/day."""

  asin: str
  country_code: str | None = None
  kdp_units: int = 0
  ads_click_date_units: int = 0
  ads_ship_date_units: int = 0
  unmatched_ads_click_date_units: int = 0
  organic_units: int = 0
  kdp_kenp_pages_read: int = 0
  ads_click_date_kenp_pages_read: int = 0
  ads_ship_date_kenp_pages_read: int = 0
  unmatched_ads_click_date_kenp_pages_read: int = 0
  organic_kenp_pages_read: int = 0
  kdp_sales_usd: float = 0.0
  ads_click_date_sales_usd_est: float = 0.0
  ads_ship_date_sales_usd_est: float = 0.0
  organic_sales_usd_est: float = 0.0
  kdp_royalty_usd: float = 0.0
  ads_click_date_royalty_usd_est: float = 0.0
  ads_ship_date_royalty_usd_est: float = 0.0
  organic_royalty_usd_est: float = 0.0
  kdp_print_cost_usd: float = 0.0
  ads_click_date_print_cost_usd_est: float = 0.0
  ads_ship_date_print_cost_usd_est: float = 0.0
  organic_print_cost_usd_est: float = 0.0

  def to_dict(self) -> dict[str, object]:
    """Convert to dictionary for Firestore storage."""
    data: dict[str, object] = {
      "asin": self.asin,
      "kdp_units": self.kdp_units,
      "ads_click_date_units": self.ads_click_date_units,
      "ads_ship_date_units": self.ads_ship_date_units,
      "unmatched_ads_click_date_units": self.unmatched_ads_click_date_units,
      "organic_units": self.organic_units,
      "kdp_kenp_pages_read": self.kdp_kenp_pages_read,
      "ads_click_date_kenp_pages_read": self.ads_click_date_kenp_pages_read,
      "ads_ship_date_kenp_pages_read": self.ads_ship_date_kenp_pages_read,
      "unmatched_ads_click_date_kenp_pages_read":
      self.unmatched_ads_click_date_kenp_pages_read,
      "organic_kenp_pages_read": self.organic_kenp_pages_read,
      "kdp_sales_usd": self.kdp_sales_usd,
      "ads_click_date_sales_usd_est": self.ads_click_date_sales_usd_est,
      "ads_ship_date_sales_usd_est": self.ads_ship_date_sales_usd_est,
      "organic_sales_usd_est": self.organic_sales_usd_est,
      "kdp_royalty_usd": self.kdp_royalty_usd,
      "ads_click_date_royalty_usd_est": self.ads_click_date_royalty_usd_est,
      "ads_ship_date_royalty_usd_est": self.ads_ship_date_royalty_usd_est,
      "organic_royalty_usd_est": self.organic_royalty_usd_est,
      "kdp_print_cost_usd": self.kdp_print_cost_usd,
      "ads_click_date_print_cost_usd_est":
      self.ads_click_date_print_cost_usd_est,
      "ads_ship_date_print_cost_usd_est":
      self.ads_ship_date_print_cost_usd_est,
      "organic_print_cost_usd_est": self.organic_print_cost_usd_est,
    }
    if self.country_code is not None:
      data["country_code"] = self.country_code
    return data

  @classmethod
  def from_dict(
    cls,
    data: dict[str, Any],
    *,
    asin: str | None = None,
    country_code: str | None = None,
  ) -> AmazonSalesReconciledAsinStats:
    """Create reconciled ASIN+country stats from dictionary data."""
    if not data:
      data = {}
    else:
      data = dict(data)

    resolved_asin = (asin or str(data.get("asin", "")).strip()).strip()
    resolved_country_code = (country_code
                             or str(data.get("country_code", "")).strip())
    if not resolved_asin:
      raise ValueError("AmazonSalesReconciledAsinStats.asin is required")
    if not resolved_country_code:
      raise ValueError(
        "AmazonSalesReconciledAsinStats.country_code is required")

    for field_name in (
        "kdp_units",
        "ads_click_date_units",
        "ads_ship_date_units",
        "unmatched_ads_click_date_units",
        "organic_units",
        "kdp_kenp_pages_read",
        "ads_click_date_kenp_pages_read",
        "ads_ship_date_kenp_pages_read",
        "unmatched_ads_click_date_kenp_pages_read",
        "organic_kenp_pages_read",
    ):
      _parse_int_field(data, field_name, 0)
    for field_name in (
        "kdp_sales_usd",
        "ads_click_date_sales_usd_est",
        "ads_ship_date_sales_usd_est",
        "organic_sales_usd_est",
        "kdp_royalty_usd",
        "ads_click_date_royalty_usd_est",
        "ads_ship_date_royalty_usd_est",
        "organic_royalty_usd_est",
        "kdp_print_cost_usd",
        "ads_click_date_print_cost_usd_est",
        "ads_ship_date_print_cost_usd_est",
        "organic_print_cost_usd_est",
    ):
      _parse_float_field(data, field_name, 0.0)

    return cls(
      asin=resolved_asin,
      country_code=resolved_country_code,
      kdp_units=data.get("kdp_units", 0),
      ads_click_date_units=data.get("ads_click_date_units", 0),
      ads_ship_date_units=data.get("ads_ship_date_units", 0),
      unmatched_ads_click_date_units=data.get("unmatched_ads_click_date_units",
                                              0),
      organic_units=data.get("organic_units", 0),
      kdp_kenp_pages_read=data.get("kdp_kenp_pages_read", 0),
      ads_click_date_kenp_pages_read=data.get("ads_click_date_kenp_pages_read",
                                              0),
      ads_ship_date_kenp_pages_read=data.get("ads_ship_date_kenp_pages_read",
                                             0),
      unmatched_ads_click_date_kenp_pages_read=data.get(
        "unmatched_ads_click_date_kenp_pages_read", 0),
      organic_kenp_pages_read=data.get("organic_kenp_pages_read", 0),
      kdp_sales_usd=data.get("kdp_sales_usd", 0.0),
      ads_click_date_sales_usd_est=data.get("ads_click_date_sales_usd_est",
                                            0.0),
      ads_ship_date_sales_usd_est=data.get("ads_ship_date_sales_usd_est", 0.0),
      organic_sales_usd_est=data.get("organic_sales_usd_est", 0.0),
      kdp_royalty_usd=data.get("kdp_royalty_usd", 0.0),
      ads_click_date_royalty_usd_est=data.get("ads_click_date_royalty_usd_est",
                                              0.0),
      ads_ship_date_royalty_usd_est=data.get("ads_ship_date_royalty_usd_est",
                                             0.0),
      organic_royalty_usd_est=data.get("organic_royalty_usd_est", 0.0),
      kdp_print_cost_usd=data.get("kdp_print_cost_usd", 0.0),
      ads_click_date_print_cost_usd_est=data.get(
        "ads_click_date_print_cost_usd_est", 0.0),
      ads_ship_date_print_cost_usd_est=data.get(
        "ads_ship_date_print_cost_usd_est", 0.0),
      organic_print_cost_usd_est=data.get("organic_print_cost_usd_est", 0.0),
    )


@dataclass(kw_only=True)
class AmazonSalesReconciledDailyStats:
  """Daily reconciled KDP ship-date sales split into ads and organic estimates."""

  key: str | None = None
  date: datetime.date
  is_settled: bool = False
  reconciled_at: datetime.datetime | None = None
  kdp_units_total: int = 0
  ads_click_date_units_total: int = 0
  ads_ship_date_units_total: int = 0
  unmatched_ads_click_date_units_total: int = 0
  organic_units_total: int = 0
  kdp_kenp_pages_read_total: int = 0
  ads_click_date_kenp_pages_read_total: int = 0
  ads_ship_date_kenp_pages_read_total: int = 0
  unmatched_ads_click_date_kenp_pages_read_total: int = 0
  organic_kenp_pages_read_total: int = 0
  kdp_sales_usd_total: float = 0.0
  ads_click_date_sales_usd_est: float = 0.0
  ads_ship_date_sales_usd_est: float = 0.0
  organic_sales_usd_est: float = 0.0
  kdp_royalty_usd_total: float = 0.0
  ads_click_date_royalty_usd_est: float = 0.0
  ads_ship_date_royalty_usd_est: float = 0.0
  organic_royalty_usd_est: float = 0.0
  kdp_print_cost_usd_total: float = 0.0
  ads_click_date_print_cost_usd_est: float = 0.0
  ads_ship_date_print_cost_usd_est: float = 0.0
  organic_print_cost_usd_est: float = 0.0
  by_asin_country: dict[str, dict[str,
                                  AmazonSalesReconciledAsinStats]] = (field(
                                    default_factory=dict))
  zzz_ending_unmatched_ads_lots_by_asin_country: dict[str, dict[
    str, list[AmazonSalesReconciledAdsLot]]] = field(default_factory=dict)

  @property
  def by_asin(self) -> dict[str, AmazonSalesReconciledAsinStats]:
    """Return ASIN-level aggregates collapsed across all countries."""
    return _aggregate_reconciled_stats_by_asin(self.by_asin_country)

  @property
  def zzz_ending_unmatched_ads_lots_by_asin(
      self) -> dict[str, list[AmazonSalesReconciledAdsLot]]:
    """Return ASIN-level unmatched lots collapsed across all countries."""
    return _aggregate_reconciled_lots_by_asin(
      self.zzz_ending_unmatched_ads_lots_by_asin_country)

  def to_dict(self, include_key: bool = False) -> dict[str, object]:
    """Convert to dictionary for Firestore storage."""
    data: dict[str, object] = {
      "date": self.date.isoformat(),
      "is_settled": self.is_settled,
      "reconciled_at": self.reconciled_at,
      "kdp_units_total": self.kdp_units_total,
      "ads_click_date_units_total": self.ads_click_date_units_total,
      "ads_ship_date_units_total": self.ads_ship_date_units_total,
      "unmatched_ads_click_date_units_total":
      self.unmatched_ads_click_date_units_total,
      "organic_units_total": self.organic_units_total,
      "kdp_kenp_pages_read_total": self.kdp_kenp_pages_read_total,
      "ads_click_date_kenp_pages_read_total":
      self.ads_click_date_kenp_pages_read_total,
      "ads_ship_date_kenp_pages_read_total":
      self.ads_ship_date_kenp_pages_read_total,
      "unmatched_ads_click_date_kenp_pages_read_total":
      self.unmatched_ads_click_date_kenp_pages_read_total,
      "organic_kenp_pages_read_total": self.organic_kenp_pages_read_total,
      "kdp_sales_usd_total": self.kdp_sales_usd_total,
      "ads_click_date_sales_usd_est": self.ads_click_date_sales_usd_est,
      "ads_ship_date_sales_usd_est": self.ads_ship_date_sales_usd_est,
      "organic_sales_usd_est": self.organic_sales_usd_est,
      "kdp_royalty_usd_total": self.kdp_royalty_usd_total,
      "ads_click_date_royalty_usd_est": self.ads_click_date_royalty_usd_est,
      "ads_ship_date_royalty_usd_est": self.ads_ship_date_royalty_usd_est,
      "organic_royalty_usd_est": self.organic_royalty_usd_est,
      "kdp_print_cost_usd_total": self.kdp_print_cost_usd_total,
      "ads_click_date_print_cost_usd_est":
      self.ads_click_date_print_cost_usd_est,
      "ads_ship_date_print_cost_usd_est":
      self.ads_ship_date_print_cost_usd_est,
      "organic_print_cost_usd_est": self.organic_print_cost_usd_est,
      "by_asin_country": {
        asin: {
          country_code: stats.to_dict()
          for country_code, stats in country_map.items()
        }
        for asin, country_map in self.by_asin_country.items()
      },
      "zzz_ending_unmatched_ads_lots_by_asin_country": {
        asin: {
          country_code: [lot.to_dict() for lot in lots]
          for country_code, lots in country_map.items()
        }
        for asin, country_map in
        self.zzz_ending_unmatched_ads_lots_by_asin_country.items()
      },
    }
    if include_key:
      data["key"] = self.key
    return data

  @classmethod
  def from_dict(
    cls,
    data: dict[str, Any],
    key: str | None = None,
  ) -> AmazonSalesReconciledDailyStats:
    """Create reconciled daily stats from dictionary data."""
    if not data:
      data = {}
    else:
      data = dict(data)

    parsed_date = _parse_required_date(
      data.get("date"),
      field_name="AmazonSalesReconciledDailyStats.date",
    )

    for field_name in (
        "kdp_units_total",
        "ads_click_date_units_total",
        "ads_ship_date_units_total",
        "unmatched_ads_click_date_units_total",
        "organic_units_total",
        "kdp_kenp_pages_read_total",
        "ads_click_date_kenp_pages_read_total",
        "ads_ship_date_kenp_pages_read_total",
        "unmatched_ads_click_date_kenp_pages_read_total",
        "organic_kenp_pages_read_total",
    ):
      _parse_int_field(data, field_name, 0)
    for field_name in (
        "kdp_sales_usd_total",
        "ads_click_date_sales_usd_est",
        "ads_ship_date_sales_usd_est",
        "organic_sales_usd_est",
        "kdp_royalty_usd_total",
        "ads_click_date_royalty_usd_est",
        "ads_ship_date_royalty_usd_est",
        "organic_royalty_usd_est",
        "kdp_print_cost_usd_total",
        "ads_click_date_print_cost_usd_est",
        "ads_ship_date_print_cost_usd_est",
        "organic_print_cost_usd_est",
    ):
      _parse_float_field(data, field_name, 0.0)

    by_asin_country = _parse_amazon_sales_reconciled_asin_country_stats_map(
      data.get("by_asin_country"))
    zzz_lots_by_asin_country = (
      _parse_amazon_sales_reconciled_lots_by_asin_country_map(
        data.get("zzz_ending_unmatched_ads_lots_by_asin_country")))

    return cls(
      key=key,
      date=parsed_date,
      is_settled=bool(data.get("is_settled", False)),
      reconciled_at=_parse_optional_datetime(data.get("reconciled_at")),
      kdp_units_total=data.get("kdp_units_total", 0),
      ads_click_date_units_total=data.get("ads_click_date_units_total", 0),
      ads_ship_date_units_total=data.get("ads_ship_date_units_total", 0),
      unmatched_ads_click_date_units_total=data.get(
        "unmatched_ads_click_date_units_total", 0),
      organic_units_total=data.get("organic_units_total", 0),
      kdp_kenp_pages_read_total=data.get("kdp_kenp_pages_read_total", 0),
      ads_click_date_kenp_pages_read_total=data.get(
        "ads_click_date_kenp_pages_read_total", 0),
      ads_ship_date_kenp_pages_read_total=data.get(
        "ads_ship_date_kenp_pages_read_total", 0),
      unmatched_ads_click_date_kenp_pages_read_total=data.get(
        "unmatched_ads_click_date_kenp_pages_read_total", 0),
      organic_kenp_pages_read_total=data.get("organic_kenp_pages_read_total",
                                             0),
      kdp_sales_usd_total=data.get("kdp_sales_usd_total", 0.0),
      ads_click_date_sales_usd_est=data.get("ads_click_date_sales_usd_est",
                                            0.0),
      ads_ship_date_sales_usd_est=data.get("ads_ship_date_sales_usd_est", 0.0),
      organic_sales_usd_est=data.get("organic_sales_usd_est", 0.0),
      kdp_royalty_usd_total=data.get("kdp_royalty_usd_total", 0.0),
      ads_click_date_royalty_usd_est=data.get("ads_click_date_royalty_usd_est",
                                              0.0),
      ads_ship_date_royalty_usd_est=data.get("ads_ship_date_royalty_usd_est",
                                             0.0),
      organic_royalty_usd_est=data.get("organic_royalty_usd_est", 0.0),
      kdp_print_cost_usd_total=data.get("kdp_print_cost_usd_total", 0.0),
      ads_click_date_print_cost_usd_est=data.get(
        "ads_click_date_print_cost_usd_est", 0.0),
      ads_ship_date_print_cost_usd_est=data.get(
        "ads_ship_date_print_cost_usd_est", 0.0),
      organic_print_cost_usd_est=data.get("organic_print_cost_usd_est", 0.0),
      by_asin_country=by_asin_country,
      zzz_ending_unmatched_ads_lots_by_asin_country=zzz_lots_by_asin_country,
    )

  @classmethod
  def from_firestore_dict(
    cls,
    data: dict[str, Any],
    key: str,
  ) -> AmazonSalesReconciledDailyStats:
    """Create reconciled daily stats from Firestore data."""
    return cls.from_dict(data, key=key)


@dataclass(kw_only=True)
class AmazonAdsReport:
  """Amazon Ads report metadata persisted in Firestore."""

  key: str | None = None
  report_id: str
  report_name: str
  status: str
  report_type_id: str
  start_date: datetime.date
  end_date: datetime.date
  created_at: datetime.datetime
  updated_at: datetime.datetime
  profile_id: str | None = None
  profile_country: str | None = None
  region: str | None = None
  api_base: str | None = None
  generated_at: datetime.datetime | None = None
  file_size: int | None = None
  url: str | None = None
  url_expires_at: datetime.datetime | None = None
  raw_report_text: str | None = None
  failure_reason: str | None = None
  processed: bool = False

  @property
  def name(self) -> str:
    """Compatibility alias for existing call sites using `name`."""
    return self.report_name

  def to_dict(self, include_key: bool = False) -> dict[str, object]:
    """Convert to dictionary for Firestore storage."""
    data: dict[str, object] = {
      "report_id": self.report_id,
      "report_name": self.report_name,
      "status": self.status,
      "report_type_id": self.report_type_id,
      "start_date": self.start_date.isoformat(),
      "end_date": self.end_date.isoformat(),
      "created_at": self.created_at,
      "updated_at": self.updated_at,
      "profile_id": self.profile_id,
      "profile_country": self.profile_country,
      "region": self.region,
      "api_base": self.api_base,
      "generated_at": self.generated_at,
      "file_size": self.file_size,
      "url": self.url,
      "url_expires_at": self.url_expires_at,
      "failure_reason": self.failure_reason,
      "processed": self.processed,
    }
    if self.raw_report_text is not None:
      data["raw_report_text"] = self.raw_report_text
    if include_key:
      data["key"] = self.key
    return data

  @classmethod
  def from_dict(
    cls,
    data: dict[str, Any],
    key: str | None = None,
  ) -> AmazonAdsReport:
    """Create an Amazon Ads report model from snake_case dictionary data."""
    if not data:
      data = {}
    else:
      data = dict(data)

    def _parse_date(value: Any, field_name: str) -> datetime.date:
      if isinstance(value, datetime.datetime):
        return value.date()
      if isinstance(value, datetime.date):
        return value
      if isinstance(value, str):
        stripped = value.strip()
        if stripped:
          return datetime.date.fromisoformat(stripped)
      raise ValueError(f"AmazonAdsReport.{field_name} is required")

    def _parse_datetime(value: Any,
                        field_name: str) -> datetime.datetime | None:
      if value is None:
        return None
      if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
          return value.replace(tzinfo=datetime.timezone.utc)
        return value.astimezone(datetime.timezone.utc)
      if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
          return None
        normalized = stripped[:-1] + "+00:00" if stripped.endswith(
          "Z") else stripped
        parsed = datetime.datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
          return parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed.astimezone(datetime.timezone.utc)
      raise ValueError(f"Invalid datetime for AmazonAdsReport.{field_name}")

    report_id = str(data.get("report_id", "")).strip()
    report_name = str(data.get("report_name", "")).strip()
    status = str(data.get("status", "")).strip()
    report_type_id = str(data.get("report_type_id", "")).strip()
    if not report_id:
      raise ValueError("AmazonAdsReport.report_id is required")
    if not report_name:
      raise ValueError("AmazonAdsReport.report_name is required")
    if not status:
      raise ValueError("AmazonAdsReport.status is required")
    if not report_type_id:
      raise ValueError("AmazonAdsReport.report_type_id is required")

    created_at = _parse_datetime(data.get("created_at"), "created_at")
    updated_at = _parse_datetime(data.get("updated_at"), "updated_at")
    if created_at is None:
      raise ValueError("AmazonAdsReport.created_at is required")
    if updated_at is None:
      raise ValueError("AmazonAdsReport.updated_at is required")

    file_size_value = data.get("file_size")
    file_size_wrapper: dict[str, Any] = {"file_size": file_size_value}
    _parse_int_field(file_size_wrapper, "file_size")

    return cls(
      key=key,
      report_id=report_id,
      report_name=report_name,
      status=status,
      report_type_id=report_type_id,
      start_date=_parse_date(
        data.get("start_date"),
        "start_date",
      ),
      end_date=_parse_date(
        data.get("end_date"),
        "end_date",
      ),
      created_at=created_at,
      updated_at=updated_at,
      profile_id=str(data.get("profile_id", "")).strip() or None,
      profile_country=str(data.get("profile_country", "")).strip() or None,
      region=str(data.get("region", "")).strip() or None,
      api_base=str(data.get("api_base", "")).strip() or None,
      generated_at=_parse_datetime(
        data.get("generated_at"),
        "generated_at",
      ),
      file_size=cast(int | None, file_size_wrapper["file_size"]),
      url=str(data.get("url", "")).strip() or None,
      url_expires_at=_parse_datetime(
        data.get("url_expires_at"),
        "url_expires_at",
      ),
      raw_report_text=(str(data.get("raw_report_text"))
                       if data.get("raw_report_text") is not None else None),
      failure_reason=str(data.get("failure_reason", "")).strip() or None,
      processed=bool(data.get("processed", False)),
    )

  @classmethod
  def from_amazon_payload(
    cls,
    data: dict[str, Any],
    *,
    key: str | None = None,
  ) -> AmazonAdsReport:
    """Create an Amazon Ads report model from API response payload."""
    if not data:
      data = {}
    else:
      data = dict(data)

    configuration_raw = data.get("configuration")
    if not isinstance(configuration_raw, dict):
      raise ValueError("AmazonAdsReport.configuration is required")

    configuration = cast(dict[str, Any], configuration_raw)
    report_type_id = str(configuration.get("reportTypeId", "")).strip()
    if not report_type_id:
      raise ValueError(
        "AmazonAdsReport.configuration.reportTypeId is required")

    translated = {
      "report_id": data.get("reportId"),
      "report_name": data.get("name"),
      "status": data.get("status"),
      "report_type_id": report_type_id,
      "start_date": data.get("startDate"),
      "end_date": data.get("endDate"),
      "created_at": data.get("createdAt"),
      "updated_at": data.get("updatedAt"),
      "generated_at": data.get("generatedAt"),
      "file_size": data.get("fileSize"),
      "url": data.get("url"),
      "url_expires_at": data.get("urlExpiresAt"),
      "failure_reason": data.get("failureReason"),
    }
    return cls.from_dict(translated, key=key)

  @classmethod
  def from_firestore_dict(
    cls,
    data: dict[str, Any],
    key: str,
  ) -> AmazonAdsReport:
    """Create an Amazon Ads report model from Firestore data."""
    return cls.from_dict(data, key=key)


@dataclass(kw_only=True)
class AmazonAdsEvent:
  """Dated event marker displayed on admin ads stats timeline charts."""

  key: str | None = None
  date: datetime.date
  title: str
  created_at: datetime.datetime | None = None
  updated_at: datetime.datetime | None = None

  def to_dict(self, include_key: bool = False) -> dict[str, object]:
    """Convert to dictionary for Firestore storage."""
    data: dict[str, object] = {
      "date": self.date.isoformat(),
      "title": self.title,
      "created_at": self.created_at,
      "updated_at": self.updated_at,
    }
    if include_key:
      data["key"] = self.key
    return data

  @classmethod
  def from_dict(
    cls,
    data: dict[str, Any],
    key: str | None = None,
  ) -> AmazonAdsEvent:
    """Create an ads event model from dictionary data."""
    if not data:
      data = {}
    else:
      data = dict(data)

    parsed_date = _parse_required_date(
      data.get("date"),
      field_name="AmazonAdsEvent.date",
    )
    title = str(data.get("title", "")).strip()
    if not title:
      raise ValueError("AmazonAdsEvent.title is required")

    return cls(
      key=key,
      date=parsed_date,
      title=title,
      created_at=_parse_optional_datetime(data.get("created_at")),
      updated_at=_parse_optional_datetime(data.get("updated_at")),
    )

  @classmethod
  def from_firestore_dict(
    cls,
    data: dict[str, Any],
    key: str,
  ) -> AmazonAdsEvent:
    """Create an ads event model from Firestore data."""
    return cls.from_dict(data, key=key)


def _parse_enum_field(
  data: dict[str, Any],
  field_name: str,
  enum_cls: type[Enum],
  default_value: Enum,
) -> None:
  """Coerce a string value in `data[field_name]` to the given Enum.

  If the field is missing, empty, or invalid, sets it to `default_value`.
  """
  value = data.get(field_name)
  try:
    data[field_name] = enum_cls(value) if value else default_value
  except Exception:
    data[field_name] = default_value


def _parse_required_date(value: Any, *, field_name: str) -> datetime.date:
  """Parse a required date from datetime/date/ISO string input."""
  if isinstance(value, datetime.datetime):
    return value.date()
  if isinstance(value, datetime.date):
    return value
  if isinstance(value, str):
    stripped = value.strip()
    if stripped:
      return datetime.date.fromisoformat(stripped)
  raise ValueError(f"{field_name} is required")


def _parse_optional_datetime(value: Any) -> datetime.datetime | None:
  """Parse an optional datetime from datetime or ISO string input."""
  if value is None:
    return None
  if isinstance(value, datetime.datetime):
    if value.tzinfo is None:
      return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)
  if isinstance(value, str):
    stripped = value.strip()
    if not stripped:
      return None
    normalized = stripped[:-1] + "+00:00" if stripped.endswith(
      "Z") else stripped
    parsed = datetime.datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
      return parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)
  raise ValueError(f"Invalid datetime value: {value}")


def _serialize_product_stats_by_asin_country(
  value: dict[str, dict[str, AmazonProductStats]],
) -> dict[str, dict[str, dict[str, object]]]:
  """Serialize nested `(asin -> country -> product stats)` mapping."""
  serialized: dict[str, dict[str, dict[str, object]]] = {}
  for asin in sorted(value.keys()):
    country_map = value[asin]
    serialized_country_map: dict[str, dict[str, object]] = {}
    for country_code in sorted(country_map.keys()):
      serialized_country_map[country_code] = country_map[country_code].to_dict(
      )
    serialized[asin] = serialized_country_map
  return serialized


def _parse_product_stats_by_asin_country_map(
  value: Any, ) -> dict[str, dict[str, AmazonProductStats]]:
  """Parse nested `(asin -> country -> product stats)` mapping."""
  if not isinstance(value, dict):
    return {}

  parsed: dict[str, dict[str, AmazonProductStats]] = {}
  for asin, raw_country_map in cast(dict[str, Any], value).items():
    asin_key = str(asin).strip()
    if not asin_key or not isinstance(raw_country_map, dict):
      continue
    parsed_country_map: dict[str, AmazonProductStats] = {}
    for country_code, raw_item in cast(dict[str, Any],
                                       raw_country_map).items():
      country_code_key = str(country_code).strip().upper()
      if not country_code_key or not isinstance(raw_item, dict):
        continue
      item_dict = dict(cast(dict[str, Any], raw_item))
      if not str(item_dict.get("asin", "")).strip():
        item_dict["asin"] = asin_key
      parsed_country_map[country_code_key] = AmazonProductStats.from_dict(
        item_dict)
    if parsed_country_map:
      parsed[asin_key] = parsed_country_map
  return parsed


def _aggregate_product_stats_by_asin(
  value: dict[str, dict[str, AmazonProductStats]],
) -> dict[str, AmazonProductStats]:
  """Aggregate nested `(asin -> country -> stats)` into ASIN totals."""
  aggregated: dict[str, AmazonProductStats] = {}
  for asin in sorted(value.keys()):
    country_map = value[asin]
    merged = AmazonProductStats(asin=asin)
    merged_total_print_cost_usd: float | None = None
    merged_total_royalty_usd: float | None = None
    unit_prices: set[float] = set()
    for country_item in country_map.values():
      merged.units_sold += country_item.units_sold
      merged.kenp_pages_read += country_item.kenp_pages_read
      merged.total_sales_usd += country_item.total_sales_usd
      merged.total_profit_usd += country_item.total_profit_usd
      merged.kenp_royalties_usd += country_item.kenp_royalties_usd
      unit_prices.update(country_item.unit_prices)
      if country_item.total_print_cost_usd is not None:
        merged_total_print_cost_usd = ((merged_total_print_cost_usd or 0.0) +
                                       country_item.total_print_cost_usd)
      if country_item.total_royalty_usd is not None:
        merged_total_royalty_usd = ((merged_total_royalty_usd or 0.0) +
                                    country_item.total_royalty_usd)
    merged.total_print_cost_usd = merged_total_print_cost_usd
    merged.total_royalty_usd = merged_total_royalty_usd
    merged.unit_prices = unit_prices
    aggregated[asin] = merged
  return aggregated


def _parse_amazon_sales_reconciled_asin_country_stats_map(
  value: Any, ) -> dict[str, dict[str, AmazonSalesReconciledAsinStats]]:
  """Parse nested `(asin -> country -> reconciled stats)` map."""
  if not isinstance(value, dict):
    return {}

  parsed: dict[str, dict[str, AmazonSalesReconciledAsinStats]] = {}
  for asin, raw_country_map in cast(dict[str, Any], value).items():
    asin_key = str(asin).strip()
    if not asin_key or not isinstance(raw_country_map, dict):
      continue
    country_map: dict[str, AmazonSalesReconciledAsinStats] = {}
    for country_code, raw_item in cast(dict[str, Any],
                                       raw_country_map).items():
      country_code_key = str(country_code).strip().upper()
      if not country_code_key or not isinstance(raw_item, dict):
        continue
      country_map[country_code_key] = AmazonSalesReconciledAsinStats.from_dict(
        cast(dict[str, Any], raw_item),
        asin=asin_key,
        country_code=country_code_key,
      )
    if country_map:
      parsed[asin_key] = country_map
  return parsed


def _parse_amazon_sales_reconciled_lots_by_asin_country_map(
  value: Any, ) -> dict[str, dict[str, list[AmazonSalesReconciledAdsLot]]]:
  """Parse nested `(asin -> country -> unmatched ads lots)` map."""
  if not isinstance(value, dict):
    return {}

  parsed: dict[str, dict[str, list[AmazonSalesReconciledAdsLot]]] = {}
  for asin, raw_country_map in cast(dict[str, Any], value).items():
    asin_key = str(asin).strip()
    if not asin_key or not isinstance(raw_country_map, dict):
      continue
    country_map: dict[str, list[AmazonSalesReconciledAdsLot]] = {}
    for country_code, raw_lots in cast(dict[str, Any],
                                       raw_country_map).items():
      country_code_key = str(country_code).strip().upper()
      if not country_code_key or not isinstance(raw_lots, list):
        continue
      lots: list[AmazonSalesReconciledAdsLot] = []
      for raw_lot in cast(list[Any], raw_lots):
        if not isinstance(raw_lot, dict):
          continue
        lots.append(
          AmazonSalesReconciledAdsLot.from_dict(cast(dict[str, Any], raw_lot)))
      if lots:
        country_map[country_code_key] = lots
    if country_map:
      parsed[asin_key] = country_map
  return parsed


def _aggregate_reconciled_stats_by_asin(
  value: dict[str, dict[str, AmazonSalesReconciledAsinStats]],
) -> dict[str, AmazonSalesReconciledAsinStats]:
  """Aggregate nested `(asin -> country -> stats)` into ASIN totals."""
  aggregated: dict[str, AmazonSalesReconciledAsinStats] = {}
  for asin in sorted(value.keys()):
    country_map = value[asin]
    merged = AmazonSalesReconciledAsinStats(asin=asin)
    for country_item in country_map.values():
      merged.kdp_units += country_item.kdp_units
      merged.ads_click_date_units += country_item.ads_click_date_units
      merged.ads_ship_date_units += country_item.ads_ship_date_units
      merged.unmatched_ads_click_date_units += (
        country_item.unmatched_ads_click_date_units)
      merged.organic_units += country_item.organic_units
      merged.kdp_kenp_pages_read += country_item.kdp_kenp_pages_read
      merged.ads_click_date_kenp_pages_read += (
        country_item.ads_click_date_kenp_pages_read)
      merged.ads_ship_date_kenp_pages_read += (
        country_item.ads_ship_date_kenp_pages_read)
      merged.unmatched_ads_click_date_kenp_pages_read += (
        country_item.unmatched_ads_click_date_kenp_pages_read)
      merged.organic_kenp_pages_read += country_item.organic_kenp_pages_read
      merged.kdp_sales_usd += country_item.kdp_sales_usd
      merged.ads_click_date_sales_usd_est += country_item.ads_click_date_sales_usd_est
      merged.ads_ship_date_sales_usd_est += country_item.ads_ship_date_sales_usd_est
      merged.organic_sales_usd_est += country_item.organic_sales_usd_est
      merged.kdp_royalty_usd += country_item.kdp_royalty_usd
      merged.ads_click_date_royalty_usd_est += country_item.ads_click_date_royalty_usd_est
      merged.ads_ship_date_royalty_usd_est += country_item.ads_ship_date_royalty_usd_est
      merged.organic_royalty_usd_est += country_item.organic_royalty_usd_est
      merged.kdp_print_cost_usd += country_item.kdp_print_cost_usd
      merged.ads_click_date_print_cost_usd_est += country_item.ads_click_date_print_cost_usd_est
      merged.ads_ship_date_print_cost_usd_est += country_item.ads_ship_date_print_cost_usd_est
      merged.organic_print_cost_usd_est += country_item.organic_print_cost_usd_est
    aggregated[asin] = merged
  return aggregated


def _aggregate_reconciled_lots_by_asin(
  value: dict[str, dict[str, list[AmazonSalesReconciledAdsLot]]],
) -> dict[str, list[AmazonSalesReconciledAdsLot]]:
  """Aggregate nested `(asin -> country -> lots)` into ASIN-only lots."""
  aggregated: dict[str, list[AmazonSalesReconciledAdsLot]] = {}
  for asin in sorted(value.keys()):
    country_map = value[asin]
    merged: list[AmazonSalesReconciledAdsLot] = []
    for lots in country_map.values():
      merged.extend(lots)
    if merged:
      aggregated[asin] = merged
  return aggregated


def _parse_string_list(
  data: dict[str, Any],
  field_name: str,
  *,
  trim: bool = True,
  dedupe: bool = True,
) -> None:
  """Coerce a value in `data[field_name]` to a list of strings.

  Trims strings and removes duplicates/empties by default.
  """
  raw = data.get(field_name)
  if not isinstance(raw, list):
    data[field_name] = []
    return

  result: list[str] = []
  seen: set[str] = set()
  for item in cast(list[Any], raw):
    if not isinstance(item, str):
      continue
    val = item.strip() if trim else item
    if not val or (dedupe and val in seen):
      continue
    if dedupe:
      seen.add(val)
    result.append(val)
  data[field_name] = result


def _parse_optional_float(data: dict[str, Any],
                          field_name: str) -> float | None:
  """Return a float from data[field_name] or None if missing/invalid."""
  val = data.get(field_name)
  if val is None:
    return None
  if isinstance(val, (int, float)):
    return float(val)
  if isinstance(val, str) and (stripped := val.strip()):
    try:
      return float(stripped)
    except ValueError:
      pass
  return None


def _parse_float_field(data: dict[str, Any],
                       field_name: str,
                       default: float | None = None) -> None:
  """Coerce a value in `data[field_name]` to a float or default."""
  val = data.get(field_name)
  if isinstance(val, (int, float)):
    data[field_name] = float(val)
    return
  if isinstance(val, str):
    if stripped := val.strip():
      try:
        data[field_name] = float(stripped)
        return
      except ValueError:
        pass
  data[field_name] = default


def _parse_int_field(data: dict[str, object],
                     field_name: str,
                     default: int | None = None) -> None:
  """Coerce a value in `data[field_name]` to an int or default."""
  val = data.get(field_name)
  if isinstance(val, bool):
    val = int(val)
  elif isinstance(val, int):
    pass
  elif isinstance(val, float):
    val = int(val)
  elif isinstance(val, str):
    if stripped := val.strip():
      try:
        val = int(stripped)
      except ValueError:
        pass
  else:
    val = default

  data[field_name] = val
