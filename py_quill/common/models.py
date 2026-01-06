"""Models for the Firestore database."""

from __future__ import annotations

import dataclasses
import datetime
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
  def as_dict(self) -> dict:
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
    result = {}
    for generation in self.generations:
      result.setdefault(generation.model_name, (0, 0))
      count, cost = result[generation.model_name]
      result[generation.model_name] = (count + 1, cost + generation.cost)
    return result

  @property
  def counts_and_costs_by_label(self) -> dict[str, tuple[int, float]]:
    """Costs by label."""
    result = {}
    for generation in self.generations:
      result.setdefault(generation.label, (0, 0))
      count, cost = result[generation.label]
      result[generation.label] = (count + 1, cost + generation.cost)
    return result

  @property
  def as_dict(self) -> dict:
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
  def from_dict(cls, data: list[dict[str, Any]] | None) -> GenerationMetadata:
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
  gcs_uri: str | None = None
  url_upscaled: str | None = None
  gcs_uri_upscaled: str | None = None
  original_prompt: str | None = None
  final_prompt: str | None = None
  model_thought: str | None = None
  error: str | None = None
  owner_user_id: str | None = None
  generation_metadata: GenerationMetadata | None = None
  gemini_evaluation: dict | None = None
  generation_id: str | None = None

  # Custom temp data not stored in Firestore
  custom_temp_data: dict[str, Any] = field(default_factory=dict)

  @property
  def is_success(self) -> bool:
    """Check if the image generation was successful."""
    return self.url is not None

  @property
  def as_dict(self) -> dict:
    """Convert to dictionary for Firestore storage."""
    return {
      'url': self.url,
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
  def from_dict(cls, data: dict, key: str | None = None) -> Image:
    """Create Image from Firestore dictionary."""
    generation_metadata = None
    if 'generation_metadata' in data:
      generation_metadata = GenerationMetadata.from_dict(
        data['generation_metadata'])
    return cls(
      key=key if key else data.get("key"),
      url=data.get("url"),
      gcs_uri=data.get("gcs_uri"),
      url_upscaled=data.get("url_upscaled"),
      gcs_uri_upscaled=data.get("gcs_uri_upscaled"),
      original_prompt=data.get("original_prompt"),
      final_prompt=data.get("final_prompt"),
      model_thought=data.get("model_thought"),
      error=data.get("error"),
      owner_user_id=data.get("owner_user_id"),
      generation_metadata=generation_metadata,
      gemini_evaluation=data.get("gemini_evaluation"),
      generation_id=data.get("generation_id"),
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
  generation_metadata: GenerationMetadata | None = None

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

  def to_dict(self, include_key: bool) -> dict:
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
  def from_dict(cls, data: dict, key: str | None = None) -> Character:
    """Create Character from Firestore dictionary."""
    generation_metadata = None
    if 'generation_metadata' in data:
      generation_metadata = GenerationMetadata.from_dict(
        data['generation_metadata'])
    return cls(
      key=key if key else data.get("key"),
      name=data['name'],
      age=data['age'],
      gender=data['gender'],
      user_description=data['user_description'],
      tagline=data.get('tagline', ""),
      sanitized_description=data.get('sanitized_description', ""),
      portrait_description=data.get('portrait_description', ""),
      portrait_image_key=data['portrait_image_key'],
      all_portrait_image_keys=data['all_portrait_image_keys'],
      owner_user_id=data['owner_user_id'],
      generation_metadata=generation_metadata,
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

    if self.portrait_image_key not in self.all_portrait_image_keys:
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
  def as_dict(self) -> dict:
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
  def from_dict(cls, data: dict) -> 'StoryCharacterData':
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
  def as_dict(self) -> dict:
    """Convert to dictionary for Firestore storage."""
    return {
      'description': self.description,
      'characters': self.characters,
    }

  @classmethod
  def from_dict(cls, data: dict) -> 'StoryIllustrationData':
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
    return self.page_number > 0 and self.text and self.illustration.description

  @property
  def as_dict(self) -> dict:
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
  def as_dict(self) -> dict:
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
  def as_dict(self) -> dict:
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

    parts = []

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
    updated_keys = set()
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
  joke_str: str = ""
  joke_ids: list[str] = field(default_factory=list)
  category_id: str | None = None
  index: int | None = None
  image_gcs_uri: str | None = None
  pdf_gcs_uri: str | None = None
  avg_saved_users_fraction: float = 0.0

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

  def to_dict(self) -> dict:
    """Serialize sheet fields for Firestore writes."""
    data = dataclasses.asdict(self)
    # `key` is the Firestore document id, not stored as a field.
    data.pop("key", None)

    return data

  @classmethod
  def from_firestore_dict(cls, data: dict, key: str) -> "JokeSheet":
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

  search_distance: float | None = None
  """Optional search distance threshold override for this category's search query."""

  tags: list[str] = field(default_factory=list)
  """If set, this category also includes jokes that match any of these tags."""

  state: str = "PROPOSED"
  """Category lifecycle: APPROVED, SEASONAL, PROPOSED, or REJECTED."""

  image_url: str | None = None
  """Primary image URL for the category tile."""

  all_image_urls: list[str] = field(default_factory=list)
  """All known image URLs for the category (used by the app image carousel)."""

  image_description: str | None = None
  jokes: list[PunnyJoke] = field(default_factory=list)

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

  def to_dict(self) -> dict:
    """Serialize category fields for Firestore writes."""
    data = dataclasses.asdict(self)
    # `id` is the Firestore document id, not stored as a field.
    data.pop('id', None)
    # `jokes` is the cached joke list loaded from a subcollection.
    data.pop('jokes', None)
    return data

  @classmethod
  def from_firestore_dict(cls, data: dict, key: str) -> 'JokeCategory':
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
    all_image_urls = data.get('all_image_urls')
    if isinstance(all_image_urls, list):
      data['all_image_urls'] = [
        u for u in all_image_urls if isinstance(u, str)
      ]
    else:
      data['all_image_urls'] = []

    tags = data.get('tags')
    if isinstance(tags, list):
      normalized_tags: list[str] = []
      seen = set()
      for t in tags:
        if not isinstance(t, str):
          continue
        tag = t.strip()
        if not tag or tag in seen:
          continue
        seen.add(tag)
        normalized_tags.append(tag)
      data['tags'] = normalized_tags
    else:
      data['tags'] = []

    search_distance = data.get('search_distance')
    if isinstance(search_distance, (int, float)):
      data['search_distance'] = float(search_distance)
    elif isinstance(search_distance, str):
      if value := search_distance.strip():
        try:
          data['search_distance'] = float(value)
        except ValueError:
          data['search_distance'] = None
      else:
        data['search_distance'] = None
    else:
      data['search_distance'] = None

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

  @classmethod
  def from_firestore_dict(cls, data: dict, key: str) -> 'PunnyJoke':
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

    def _normalize_book_page_url(url: str | None) -> str | None:
      """Normalize CDN params to the canonical book page format."""
      if not url or not isinstance(url, str):
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
      seen = set()
      result: list[str] = []
      for url in urls:
        norm = _normalize_book_page_url(url)
        if norm and norm not in seen:
          seen.add(norm)
          result.append(norm)
      return result

    existing_setup_urls = metadata.get('all_book_page_setup_image_urls')
    setup_history_raw = (list(existing_setup_urls) if isinstance(
      existing_setup_urls, list) else [])

    existing_punchline_urls = metadata.get(
      'all_book_page_punchline_image_urls')
    punchline_history_raw = (list(existing_punchline_urls) if isinstance(
      existing_punchline_urls, list) else [])

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

  def to_dict(self, include_key: bool = False) -> dict:
    """Convert to dictionary for Firestore/response serialization.

    - Serializes `state` enum to its string value
    - Serializes `generation_metadata` using its `as_dict`
    - Optionally includes `key`
    """
    data = dataclasses.asdict(self)

    # Ensure enums are serialized to their string values
    if isinstance(self.state, JokeState):
      data['state'] = self.state.value
    if isinstance(self.admin_rating, JokeAdminRating):
      data['admin_rating'] = self.admin_rating.value

    # Ensure generation_metadata is serialized via as_dict
    if self.generation_metadata is not None:
      data['generation_metadata'] = self.generation_metadata.as_dict
    else:
      data['generation_metadata'] = {}
    if not include_key:
      data.pop('key', None)
    return data

  def get_minimal_joke_data(self) -> dict[str, str | None]:
    """Get a minimal dictionary representation of the joke for feed generation."""
    return {
      "key": self.key,
      "setup_text": self.setup_text,
      "punchline_text": self.punchline_text,
      "setup_image_url": self.setup_image_url,
      "punchline_image_url": self.punchline_image_url,
    }


def _parse_enum_field(
  data: dict,
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
