"""Unit tests for models."""

import pytest
from common.models import (Character, GenerationMetadata, Image, ReadingLevel,
                           SingleGenerationMetadata, StoryCharacterData,
                           StoryData, StoryIllustrationData,
                           StoryLearningConceptData, StoryPageData)


class TestReadingLevel:
  """Tests for ReadingLevel enum."""

  def test_from_value_valid(self):
    """Test converting valid integers to ReadingLevel."""
    assert ReadingLevel.from_value(0) == ReadingLevel.PRE_K
    assert ReadingLevel.from_value(4) == ReadingLevel.THIRD
    assert ReadingLevel.from_value(7) == ReadingLevel.SIXTH

  def test_from_value_invalid(self):
    """Test converting invalid integers defaults to appropriate bound."""
    assert ReadingLevel.from_value(-1) == ReadingLevel.PRE_K
    assert ReadingLevel.from_value(8) == ReadingLevel.SIXTH
    assert ReadingLevel.from_value(100) == ReadingLevel.SIXTH


class TestSingleGenerationMetadata:
  """Tests for SingleGenerationMetadata class."""

  def setup_method(self):
    """Set up test data."""
    self.metadata = SingleGenerationMetadata(label="Test Generation",
                                             model_name="gpt-4",
                                             token_counts={
                                               "prompt": 100,
                                               "completion": 50
                                             },
                                             generation_time_sec=1.5,
                                             cost=0.02,
                                             retry_count=1)
    self.empty_metadata = SingleGenerationMetadata()

  def test_is_empty(self):
    """Test is_empty property."""
    assert not self.metadata.is_empty
    assert self.empty_metadata.is_empty

  def test_as_dict(self):
    """Test conversion to dictionary."""
    expected = {
      'label': "Test Generation",
      'model_name': "gpt-4",
      'token_counts': {
        "prompt": 100,
        "completion": 50
      },
      'generation_time_sec': 1.5,
      'cost': 0.02,
      'retry_count': 1
    }
    assert self.metadata.as_dict == expected

  def test_from_dict(self):
    """Test creation from dictionary."""
    data = {
      'label': "Test Generation",
      'model_name': "gpt-4",
      'token_counts': {
        "prompt": 100,
        "completion": 50
      },
      'generation_time_sec': 1.5,
      'cost': 0.02,
      'retry_count': 1
    }
    metadata = SingleGenerationMetadata.from_dict(data)
    assert metadata.label == "Test Generation"
    assert metadata.model_name == "gpt-4"
    assert metadata.token_counts == {"prompt": 100, "completion": 50}
    assert metadata.generation_time_sec == 1.5
    assert metadata.cost == 0.02
    assert metadata.retry_count == 1


class TestGenerationMetadata:
  """Tests for GenerationMetadata class."""

  def setup_method(self):
    """Set up test data."""
    self.single_gen = SingleGenerationMetadata(label="Test",
                                               model_name="gpt-4",
                                               token_counts={"prompt": 100},
                                               generation_time_sec=1.0,
                                               cost=0.01)
    self.metadata = GenerationMetadata()

  def test_add_generation_single(self):
    """Test adding a single generation."""
    self.metadata.add_generation(self.single_gen)
    assert len(self.metadata.generations) == 1
    assert self.metadata.generations[0] == self.single_gen

  def test_add_generation_multiple(self):
    """Test adding multiple generations."""
    other_metadata = GenerationMetadata()
    other_metadata.add_generation(self.single_gen)
    self.metadata.add_generation(other_metadata)
    assert len(self.metadata.generations) == 1
    assert self.metadata.generations[0] == self.single_gen

  def test_add_generation_none(self):
    """Test adding None generation."""
    self.metadata.add_generation(None)
    assert len(self.metadata.generations) == 0

  def test_add_generation_empty(self):
    """Test adding empty generation is skipped."""
    empty_gen = SingleGenerationMetadata()
    self.metadata.add_generation(empty_gen)
    assert len(self.metadata.generations) == 0

  def test_as_dict(self):
    """Test conversion to dictionary."""
    self.metadata.add_generation(self.single_gen)
    result = self.metadata.as_dict
    assert 'generations' in result
    assert 'costs_by_model' in result
    assert 'total_cost' in result
    assert result['total_cost'] == 0.01
    assert result['costs_by_model'] == {'gpt-4': 0.01}

  def test_from_dict(self):
    """Test creation from dictionary."""
    data = {
      'generations': [{
        'label': "Test",
        'model_name': "gpt-4",
        'token_counts': {
          "prompt": 100
        },
        'generation_time_sec': 1.0,
        'cost': 0.01,
        'retry_count': 0
      }]
    }
    metadata = GenerationMetadata.from_dict(data)
    assert len(metadata.generations) == 1
    assert metadata.generations[0].label == "Test"

  def test_from_dict_empty(self):
    """Test creation from empty dictionary."""
    metadata = GenerationMetadata.from_dict(None)
    assert len(metadata.generations) == 0


class TestImage:
  """Tests for Image class."""

  def setup_method(self):
    """Set up test data."""
    self.image = Image(key="test_key",
                       url="http://example.com/image.jpg",
                       original_prompt="A test prompt",
                       final_prompt="A refined prompt",
                       owner_user_id="user123",
                       generation_metadata=GenerationMetadata(),
                       gemini_evaluation={"score": 0.9},
                       generation_id="gen123")

  def test_is_success(self):
    """Test is_success property."""
    assert self.image.is_success
    failed_image = Image(key="test_key", error="Failed")
    assert not failed_image.is_success

  def test_as_dict(self):
    """Test conversion to dictionary."""
    result = self.image.as_dict
    assert result['url'] == "http://example.com/image.jpg"
    assert result['original_prompt'] == "A test prompt"
    assert result['final_prompt'] == "A refined prompt"
    assert result['owner_user_id'] == "user123"
    assert result['gemini_evaluation'] == {"score": 0.9}
    assert result['generation_id'] == "gen123"

  def test_from_dict(self):
    """Test creation from dictionary."""
    data = {
      'url': "http://example.com/image.jpg",
      'original_prompt': "A test prompt",
      'final_prompt': "A refined prompt",
      'owner_user_id': "user123",
      'generation_metadata': {},
      'gemini_evaluation': {
        "score": 0.9
      },
      'generation_id': "gen123"
    }
    image = Image.from_dict(data, key="test_key")
    assert image.key == "test_key"
    assert image.url == "http://example.com/image.jpg"
    assert image.original_prompt == "A test prompt"
    assert image.final_prompt == "A refined prompt"
    assert image.owner_user_id == "user123"
    assert image.gemini_evaluation == {"score": 0.9}
    assert image.generation_id == "gen123"


class TestCharacter:
  """Tests for Character class."""

  def setup_method(self):
    """Set up test data."""
    self.character = Character(
      key="char123",
      name="Alice",
      age=10,
      gender="female",
      user_description="A curious girl",
      tagline="Always ready for adventure",
      sanitized_description="A friendly and curious girl",
      portrait_description="Wearing a blue dress",
      portrait_image_key="portrait123",
      all_portrait_image_keys=["portrait123"],
      owner_user_id="user123",
      generation_metadata=GenerationMetadata())

  def test_description_xml(self):
    """Test description_xml property."""
    expected = """<character>
<name>Alice</name>
<age>10</age>
<gender>female</gender>
<description>
A friendly and curious girl
</description>
</character>"""
    assert self.character.description_xml == expected

  def test_description_xml_no_gender(self):
    """Test description_xml with empty gender."""
    character = Character(key="char123",
                          name="Alex",
                          age=8,
                          gender="",
                          user_description="A creative child",
                          tagline="Creating wonders",
                          sanitized_description="A creative child",
                          portrait_description="Short brown hair",
                          portrait_image_key="portrait456",
                          all_portrait_image_keys=["portrait456"],
                          owner_user_id="user123")
    expected = """<character>
<name>Alex</name>
<age>8</age>
<description>
A creative child
</description>
</character>"""
    assert character.description_xml == expected

  def test_get_full_description_no_gender(self):
    """Test get_full_description with non-binary gender."""
    result = Character.get_full_description("Alex", 8, "non-binary",
                                            "Short brown hair",
                                            "A creative child")
    expected = "Name: Alex. Age: 8 year old. Description: A creative child Short brown hair"
    assert result == expected

  def test_to_dict(self):
    """Test conversion to dictionary."""
    result = self.character.to_dict(include_key=True)
    assert result['key'] == "char123"
    assert result['name'] == "Alice"
    assert result['age'] == 10
    assert result['gender'] == "female"
    assert result['user_description'] == "A curious girl"
    assert result['tagline'] == "Always ready for adventure"
    assert result['portrait_image_key'] == "portrait123"
    assert result['all_portrait_image_keys'] == ["portrait123"]

  def test_to_dict_without_key(self):
    """Test conversion to dictionary without key."""
    result = self.character.to_dict(include_key=False)
    assert 'key' not in result

  def test_from_dict(self):
    """Test creation from dictionary."""
    data = {
      'name': "Alice",
      'age': 10,
      'gender': "female",
      'user_description': "A curious girl",
      'tagline': "Always ready for adventure",
      'sanitized_description': "A friendly and curious girl",
      'portrait_description': "Wearing a blue dress",
      'portrait_image_key': "portrait123",
      'all_portrait_image_keys': ["portrait123"],
      'owner_user_id': "user123",
      'generation_metadata': {}
    }
    character = Character.from_dict(data, key="char123")
    assert character.key == "char123"
    assert character.name == "Alice"
    assert character.age == 10
    assert character.gender == "female"
    assert character.user_description == "A curious girl"
    assert character.tagline == "Always ready for adventure"

  def test_update(self):
    """Test updating character fields."""
    new_character = Character(
      key="char456",
      name="Alice 2.0",
      age=11,
      gender="female",
      user_description="An even more curious girl",
      tagline="Adventure awaits",
      sanitized_description="A very friendly and curious girl",
      portrait_description="Wearing a red dress",
      portrait_image_key="portrait456",
      all_portrait_image_keys=["portrait456"],
      owner_user_id="user123",
      generation_metadata=GenerationMetadata())
    self.character.update(new_character)
    assert self.character.name == "Alice 2.0"
    assert self.character.age == 11
    assert self.character.user_description == "An even more curious girl"
    assert self.character.portrait_image_key == "portrait456"
    assert self.character.all_portrait_image_keys == [
      "portrait456", "portrait123"
    ]

  def test_update_with_generation_metadata(self):
    """Test updating with generation metadata."""
    self.character.generation_metadata = None
    new_character = Character(
      key="char456",
      name="Alice 2.0",
      age=11,
      gender="female",
      user_description="An even more curious girl",
      tagline="Adventure awaits",
      sanitized_description="A very friendly and curious girl",
      portrait_description="Wearing a red dress",
      portrait_image_key="portrait456",
      all_portrait_image_keys=["portrait456"],
      owner_user_id="user123",
      generation_metadata=GenerationMetadata())
    new_character.generation_metadata.add_generation(
      SingleGenerationMetadata(label="Test",
                               model_name="gpt-4",
                               token_counts={"prompt": 100},
                               generation_time_sec=1.0,
                               cost=0.01))
    self.character.update(new_character)
    assert self.character.generation_metadata is not None
    assert len(self.character.generation_metadata.generations) == 1


class TestStoryCharacterData:
  """Tests for StoryCharacterData class."""

  def test_initialization(self):
    """Test initialization with all fields."""
    character = StoryCharacterData(name="Bob",
                                   visual="Tall with curly hair",
                                   humor="Makes silly puns")
    assert character.name == "Bob"
    assert character.visual == "Tall with curly hair"
    assert character.humor == "Makes silly puns"

  def test_default_initialization(self):
    """Test initialization with default values."""
    character = StoryCharacterData()
    assert character.name == ""
    assert character.visual == ""
    assert character.humor == ""

  def test_as_dict(self):
    """Test conversion to dictionary."""
    character = StoryCharacterData(name="Bob",
                                   visual="Tall with curly hair",
                                   humor="Makes silly puns")
    expected_dict = {
      'name': "Bob",
      'visual': "Tall with curly hair",
      'humor': "Makes silly puns"
    }
    assert character.as_dict == expected_dict

  def test_as_xml(self):
    """Test conversion to XML format."""
    character = StoryCharacterData(name="Bob",
                                   visual="Tall with curly hair",
                                   humor="Makes silly puns")
    expected_xml = """<character>
  <name>Bob</name>
  <visual_description>Tall with curly hair</visual_description>
  <humor>Makes silly puns</humor>
</character>"""
    assert character.xml == expected_xml

  def test_from_dict(self):
    """Test creation from dictionary."""
    data = {
      'name': "Bob",
      'visual': "Tall with curly hair",
      'humor': "Makes silly puns"
    }
    character = StoryCharacterData.from_dict(data)
    assert character.name == "Bob"
    assert character.visual == "Tall with curly hair"
    assert character.humor == "Makes silly puns"

  def test_from_dict_with_missing_fields(self):
    """Test creation from dictionary with missing fields."""
    data = {}
    character = StoryCharacterData.from_dict(data)
    assert character.name == ""
    assert character.visual == ""
    assert character.humor == ""

  def test_from_dict_with_partial_fields(self):
    """Test creation from dictionary with only some fields."""
    data = {'name': "Bob", 'visual': "Tall with curly hair"}
    character = StoryCharacterData.from_dict(data)
    assert character.name == "Bob"
    assert character.visual == "Tall with curly hair"
    assert character.humor == ""


class TestStoryIllustrationData:
  """Test StoryIllustrationData class."""

  def test_initialization(self):
    """Test initialization with specific field values."""
    illustration = StoryIllustrationData(
      description="A beautiful sunset over mountains",
      characters=["Alice", "Bob"])
    assert illustration.description == "A beautiful sunset over mountains"
    assert illustration.characters == ["Alice", "Bob"]

  def test_default_initialization(self):
    """Test initialization with default values."""
    illustration = StoryIllustrationData()
    assert illustration.description == ""
    assert illustration.characters == []

  def test_as_dict(self):
    """Test conversion to dictionary."""
    illustration = StoryIllustrationData(
      description="A beautiful sunset over mountains",
      characters=["Alice", "Bob"])
    expected_dict = {
      'description': "A beautiful sunset over mountains",
      'characters': ["Alice", "Bob"]
    }
    assert illustration.as_dict == expected_dict

  def test_from_dict(self):
    """Test creation from dictionary."""
    data = {
      'description': "A beautiful sunset over mountains",
      'characters': ["Alice", "Bob"]
    }
    illustration = StoryIllustrationData.from_dict(data)
    assert illustration.description == "A beautiful sunset over mountains"
    assert illustration.characters == ["Alice", "Bob"]

  def test_from_dict_with_missing_fields(self):
    """Test creation from dictionary with missing fields."""
    data = {}
    illustration = StoryIllustrationData.from_dict(data)
    assert illustration.description == ""
    assert illustration.characters == []

  def test_from_dict_with_partial_fields(self):
    """Test creation from dictionary with only some fields."""
    data = {'description': "A beautiful sunset over mountains"}
    illustration = StoryIllustrationData.from_dict(data)
    assert illustration.description == "A beautiful sunset over mountains"
    assert illustration.characters == []


class TestStoryPageData:
  """Tests for StoryPageData class."""

  maxDiff = None

  def test_initialization(self):
    """Test initialization with all fields."""
    illustration = StoryIllustrationData(description="A classroom scene",
                                         characters=["Teacher", "Students"])
    page = StoryPageData(illustration=illustration,
                         text="It was a bright morning in the classroom.",
                         humor="The teacher's hat kept falling off",
                         page_number=3)
    assert page.illustration == illustration
    assert page.text == "It was a bright morning in the classroom."
    assert page.humor == "The teacher's hat kept falling off"
    assert page.page_number == 3

  def test_default_initialization(self):
    """Test initialization with default values."""
    page = StoryPageData()
    assert page.text == ""
    assert page.humor == ""
    assert page.page_number == 0
    assert isinstance(page.illustration, StoryIllustrationData)
    assert page.illustration.description == ""
    assert page.illustration.characters == []

  def test_as_dict(self):
    """Test conversion to dictionary."""
    illustration = StoryIllustrationData(description="A classroom scene",
                                         characters=["Teacher", "Students"])
    page = StoryPageData(illustration=illustration,
                         text="It was a bright morning in the classroom.",
                         humor="The teacher's hat kept falling off",
                         page_number=3)
    result = page.as_dict
    assert result['text'] == "It was a bright morning in the classroom."
    assert result['humor'] == "The teacher's hat kept falling off"
    assert result['page_number'] == 3
    assert result['illustration']['description'] == "A classroom scene"
    assert result['illustration']['characters'] == ["Teacher", "Students"]


class TestStoryLearningConceptData:
  """Tests for StoryLearningConceptData class."""

  def test_initialization(self):
    """Test initialization with all fields."""
    concept = StoryLearningConceptData(
      explanation="Photosynthesis is how plants make food",
      plot="The characters help a wilting plant",
      demonstration="They observe the plant growing stronger in sunlight")
    assert concept.explanation == "Photosynthesis is how plants make food"
    assert concept.plot == "The characters help a wilting plant"
    assert concept.demonstration == "They observe the plant growing stronger in sunlight"

  def test_default_initialization(self):
    """Test initialization with default values."""
    concept = StoryLearningConceptData()
    assert concept.explanation == ""
    assert concept.plot == ""
    assert concept.demonstration == ""

  def test_as_dict(self):
    """Test conversion to dictionary."""
    concept = StoryLearningConceptData(
      explanation="Photosynthesis is how plants make food",
      plot="The characters help a wilting plant",
      demonstration="They observe the plant growing stronger in sunlight")
    expected_dict = {
      'explanation': "Photosynthesis is how plants make food",
      'plot': "The characters help a wilting plant",
      'demonstration': "They observe the plant growing stronger in sunlight"
    }
    assert concept.as_dict == expected_dict


class TestStoryData:
  """Tests for StoryData class."""

  maxDiff = None

  def setup_method(self):
    """Set up test data."""
    self.story = StoryData(
      title="The Forest Fire Mystery",
      tone="A blend of Inside Out and Wall-E",
      characters={
        "Jenny":
        StoryCharacterData(
          name="Jenny",
          visual=
          "Jenny is a curious 7-year-old Asian girl with a black ponytail",
          humor=
          "Jenny's enthusiasm for science leads her to narrate everything like a nature documentary"
        ),
        "Ignis":
        StoryCharacterData(
          name="Ignis",
          visual="A small crimson dragon with gleaming gold scales",
          humor=
          "Despite being a dragon, Ignis is hilariously overcautious about fire safety"
        )
      },
      learning_concepts={
        "Forest Layers":
        StoryLearningConceptData(
          explanation="A forest has different layers like a giant layer cake",
          plot=
          "Jenny must travel through each forest layer to find magical ingredients",
          demonstration=
          "As Jenny climbs through the understory, she encounters shade-loving ferns"
        ),
        "Fire Triangle":
        StoryLearningConceptData(
          explanation="Fire needs three things to burn: fuel, oxygen, and heat",
          plot=
          "Ignis can't breathe fire because one element of the fire triangle is missing",
          demonstration=
          "Through trial and error with Ignis's fire breathing attempts")
      },
      outline="Once upon a time in a magical forest...")

  def test_is_empty(self):
    """Test is_empty property."""
    assert StoryData().is_empty
    self.story.pages = [StoryPageData()]
    assert not self.story.is_empty

  def test_as_dict(self):
    """Test conversion to dictionary."""
    result = self.story.as_dict
    assert result['title'] == "The Forest Fire Mystery"
    assert result['tone'] == "A blend of Inside Out and Wall-E"
    assert len(result['characters']) == 2
    assert len(result['learning_concepts']) == 2
    assert result['outline'] == "Once upon a time in a magical forest..."

  def test_outline_xml(self):
    """Test outline_xml property with all fields present."""
    xml = self.story.outline_xml
    expected = """<reference_material_concept>
  <concept>Forest Layers</concept>
  <explanation>A forest has different layers like a giant layer cake</explanation>
  <plot_usage>Jenny must travel through each forest layer to find magical ingredients</plot_usage>
  <demonstration>As Jenny climbs through the understory, she encounters shade-loving ferns</demonstration>
</reference_material_concept>

<reference_material_concept>
  <concept>Fire Triangle</concept>
  <explanation>Fire needs three things to burn: fuel, oxygen, and heat</explanation>
  <plot_usage>Ignis can't breathe fire because one element of the fire triangle is missing</plot_usage>
  <demonstration>Through trial and error with Ignis's fire breathing attempts</demonstration>
</reference_material_concept>

<title>The Forest Fire Mystery</title>

<tone>A blend of Inside Out and Wall-E</tone>

<character>
  <name>Jenny</name>
  <visual_description>Jenny is a curious 7-year-old Asian girl with a black ponytail</visual_description>
  <humor>Jenny's enthusiasm for science leads her to narrate everything like a nature documentary</humor>
</character>

<character>
  <name>Ignis</name>
  <visual_description>A small crimson dragon with gleaming gold scales</visual_description>
  <humor>Despite being a dragon, Ignis is hilariously overcautious about fire safety</humor>
</character>

<outline>
Once upon a time in a magical forest...
</outline>"""
    assert xml == expected

  def test_outline_xml_incomplete(self):
    """Test outline_xml property raises ValueError when data is incomplete."""
    incomplete_story = StoryData(title="Incomplete Story")
    with pytest.raises(ValueError):
      _ = incomplete_story.outline_xml


class TestStoryDataUpdate:
  """Tests for StoryData.update method."""

  def setup_method(self):
    """Set up test data."""
    self.base_data = StoryData()
    self.update_data = StoryData()

  def test_update_simple_fields(self):
    """Test updating simple string fields."""
    self.update_data.title = "New Title"
    self.update_data.tagline = "New Tagline"
    self.update_data.summary = "New Summary"
    self.update_data.tone = "New Tone"
    self.update_data.outline = "New Outline"

    updated_keys = self.base_data.update(self.update_data)

    assert self.base_data.title == "New Title"
    assert self.base_data.tagline == "New Tagline"
    assert self.base_data.summary == "New Summary"
    assert self.base_data.tone == "New Tone"
    assert self.base_data.outline == "New Outline"
    assert updated_keys == {"title", "tagline", "summary", "tone", "outline"}

  def test_update_plot_fields(self):
    """Test updating plot-related fields."""
    self.update_data.plot_brainstorm = "New Brainstorm"
    self.update_data.plot_summary = "New Plot Summary"

    updated_keys = self.base_data.update(self.update_data)

    assert self.base_data.plot_brainstorm == "New Brainstorm"
    assert self.base_data.plot_summary == "New Plot Summary"
    assert updated_keys == {"plot_brainstorm", "plot_summary"}

  def test_update_pages(self):
    """Test updating pages list."""
    page1 = StoryPageData(illustration=StoryIllustrationData(
      description="Page 1 Illustration", characters=["Alex"]),
                          text="Page 1 Text",
                          humor="Page 1 Humor")
    page2 = StoryPageData(illustration=StoryIllustrationData(
      description="Page 2 Illustration", characters=["Bob"]),
                          text="Page 2 Text",
                          humor="Page 2 Humor")

    # Add initial page
    self.base_data.pages = [page1]

    # Update with new page
    self.update_data.pages = [page2]
    updated_keys = self.base_data.update(self.update_data)

    assert len(self.base_data.pages) == 2
    assert self.base_data.pages[0].text == "Page 1 Text"
    assert self.base_data.pages[1].text == "Page 2 Text"
    assert updated_keys == {"pages"}

  def test_update_cover_illustration(self):
    """Test updating cover illustration."""
    self.update_data.cover_illustration = StoryIllustrationData(
      description="New Cover", characters=["Alex", "Bob"])

    updated_keys = self.base_data.update(self.update_data)

    assert self.base_data.cover_illustration.description == "New Cover"
    assert self.base_data.cover_illustration.characters == ["Alex", "Bob"]
    assert updated_keys == {"cover_illustration"}

  def test_update_characters(self):
    """Test updating character descriptions."""
    # Initial character
    self.base_data.characters = {
      "Alex": StoryCharacterData(name="Alex",
                                 visual="Young boy",
                                 humor="Clumsy")
    }

    # Update with new character
    self.update_data.characters = {
      "Bob":
      StoryCharacterData(name="Bob", visual="Old wizard", humor="Forgetful")
    }

    updated_keys = self.base_data.update(self.update_data)

    assert len(self.base_data.characters) == 2
    assert self.base_data.characters["Alex"].visual == "Young boy"
    assert self.base_data.characters["Bob"].visual == "Old wizard"
    assert updated_keys == {"characters"}

  def test_update_learning_concepts(self):
    """Test updating learning concepts."""
    # Initial concept
    self.base_data.learning_concepts = {
      "Photosynthesis":
      StoryLearningConceptData(explanation="Plants make food from sunlight",
                               plot="Characters help a plant grow",
                               demonstration="Shows the process step by step")
    }

    # Update with new concept
    self.update_data.learning_concepts = {
      "Water Cycle":
      StoryLearningConceptData(
        explanation="Water moves in a cycle",
        plot="Characters follow a water droplet",
        demonstration="Shows evaporation and condensation")
    }

    updated_keys = self.base_data.update(self.update_data)

    assert len(self.base_data.learning_concepts) == 2
    assert self.base_data.learning_concepts[
      "Photosynthesis"].explanation == "Plants make food from sunlight"
    assert self.base_data.learning_concepts[
      "Water Cycle"].explanation == "Water moves in a cycle"
    assert updated_keys == {"learning_concepts"}

  def test_update_empty_fields(self):
    """Test that empty fields don't trigger updates."""
    self.base_data.title = "Original Title"
    updated_keys = self.base_data.update(StoryData())
    assert self.base_data.title == "Original Title"
    assert updated_keys == set()

  def test_update_multiple_fields(self):
    """Test updating multiple fields at once."""
    # Set up initial data
    self.base_data.title = "Original Title"
    self.base_data.characters = {
      "Alex": StoryCharacterData(name="Alex",
                                 visual="Young boy",
                                 humor="Clumsy")
    }

    # Set up update data
    self.update_data.title = "New Title"
    self.update_data.tagline = "New Tagline"
    self.update_data.characters = {
      "Bob":
      StoryCharacterData(name="Bob", visual="Old wizard", humor="Forgetful")
    }
    self.update_data.cover_illustration = StoryIllustrationData(
      description="New Cover", characters=["Alex", "Bob"])

    updated_keys = self.base_data.update(self.update_data)

    # Check all updates were applied
    assert self.base_data.title == "New Title"
    assert self.base_data.tagline == "New Tagline"
    assert len(self.base_data.characters) == 2
    assert self.base_data.cover_illustration.description == "New Cover"
    assert updated_keys == {
      "title", "tagline", "characters", "cover_illustration"
    }
