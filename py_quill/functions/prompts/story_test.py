"""Unit tests for story.py module."""

from common import models
from functions.prompts.story import _parse_story_response, _repair_xml


class TestParseStoryResponse:
  """Test the _parse_story_response function."""

  def test_complete_story(self):
    """Test parsing a complete story with all components."""
    input_text = """
<tone>A blend of Inside Out's emotional depth and humor with Wall-E's environmental message, featuring Toy Story's friendship dynamics.</tone>

<title>The Great Adventure</title>
<tagline>A journey through science!</tagline>
<summary>A curious child discovers the wonders of science in their own backyard.</summary>

<character>
<name>Alex</name>
<visual>A bright-eyed 8-year-old with curly red hair and round glasses</visual>
<humor>Alex's enthusiasm for science leads to hilarious experiments</humor>
</character>
<character>
<name>Professor Whiz</name>
<visual>A friendly robot with blinking LED eyes and a lab coat</visual>
<humor>The professor's attempts at human expressions always go wrong</humor>
</character>

<outline>
<phase>
<name>The Discovery</name>
<key_plot_points>
* Alex discovers a mysterious plant in the backyard
* Professor Whiz arrives with scientific equipment
* CLUE DROP: Strange light patterns around the plant
</key_plot_points>
<humor>
Professor Whiz's equipment malfunctions in increasingly ridiculous ways, while Alex narrates everything in an overly dramatic documentary style.
</humor>
<reference>
* Introduction to basic plant biology
* Demonstration of scientific observation methods
</reference>
</phase>
</outline>

<cover_illustration>
<cover_illustration_description>Alex and Professor Whiz stand in a vibrant garden, surrounded by labeled diagrams of plants and water droplets floating in the air</cover_illustration_description>
<cover_illustration_character>Alex</cover_illustration_character>
<cover_illustration_character>Professor Whiz</cover_illustration_character>
</cover_illustration>

<page>
<num>1</num>
<humor>
* Visual gag: Alex's magnifying glass makes their eye comically huge
* Situational comedy: Alex dramatically narrates their "groundbreaking discovery" of an ordinary dandelion
* Character-driven humor: Professor Whiz's overly precise measurements of everything
</humor>
<illustration_description>Alex peers through a magnifying glass at a sunflower, with rays of sunlight streaming down dramatically.</illustration_description>
<illustration_character>Alex</illustration_character>
<text>Once upon a time, there was a curious child.</text>
</page>
<page>
<num>2</num>
<humor>
* Visual gag: Professor Whiz's hologram glitches and shows dancing vegetables instead of scientific diagrams
* Dialogue humor: Professor Whiz mixing up human idioms
* Character-driven humor: Alex taking extremely detailed notes about everything, including the professor's mistakes
</humor>
<illustration_description>Professor Whiz demonstrates photosynthesis with a glowing hologram display showing the process.</illustration_description>
<illustration_character>Professor Whiz</illustration_character>
<text>They loved to explore the world around them.</text>
</page>

<reference>
<concept>Photosynthesis</concept>
<explanation>Photosynthesis is how plants make food using sunlight.</explanation>
<plot>Plants in the story use photosynthesis to help save the day.</plot>
<demonstration>A magical plant grows stronger in sunlight, demonstrating photosynthesis in action.</demonstration>
</reference>
<reference>
<concept>Water Cycle</concept>
<explanation>The water cycle is the journey water takes around Earth.</explanation>
<plot>Characters must follow the water cycle to find a lost friend.</plot>
<demonstration>Water evaporates and forms clouds that help guide the way.</demonstration>
</reference>
"""
    story_data, remaining_text = _parse_story_response(input_text)
    self.assert_story_data(
      story_data,
      expected_title="The Great Adventure",
      expected_tagline="A journey through science!",
      expected_summary=
      "A curious child discovers the wonders of science in their own backyard.",
      expected_tone=
      "A blend of Inside Out's emotional depth and humor with Wall-E's environmental message, featuring Toy Story's friendship dynamics.",
      expected_outline="""<phase>
<name>The Discovery</name>
<key_plot_points>
* Alex discovers a mysterious plant in the backyard
* Professor Whiz arrives with scientific equipment
* CLUE DROP: Strange light patterns around the plant
</key_plot_points>
<humor>
Professor Whiz's equipment malfunctions in increasingly ridiculous ways, while Alex narrates everything in an overly dramatic documentary style.
</humor>
<reference>
* Introduction to basic plant biology
* Demonstration of scientific observation methods
</reference>
</phase>""",
      expected_pages=[
        models.StoryPageData(
          illustration=models.StoryIllustrationData(
            description=
            "Alex peers through a magnifying glass at a sunflower, with rays of sunlight streaming down dramatically.",
            characters=["Alex"]),
          text="Once upon a time, there was a curious child.",
          humor=
          """* Visual gag: Alex's magnifying glass makes their eye comically huge
* Situational comedy: Alex dramatically narrates their "groundbreaking discovery" of an ordinary dandelion
* Character-driven humor: Professor Whiz's overly precise measurements of everything""",
          page_number=1),
        models.StoryPageData(
          illustration=models.StoryIllustrationData(
            description=
            "Professor Whiz demonstrates photosynthesis with a glowing hologram display showing the process.",
            characters=["Professor Whiz"]),
          text="They loved to explore the world around them.",
          humor=
          """* Visual gag: Professor Whiz's hologram glitches and shows dancing vegetables instead of scientific diagrams
* Dialogue humor: Professor Whiz mixing up human idioms
* Character-driven humor: Alex taking extremely detailed notes about everything, including the professor's mistakes""",
          page_number=2)
      ],
      expected_concepts={
        "Photosynthesis":
        models.StoryLearningConceptData(
          explanation="Photosynthesis is how plants make food using sunlight.",
          plot="Plants in the story use photosynthesis to help save the day.",
          demonstration=
          "A magical plant grows stronger in sunlight, demonstrating photosynthesis in action."
        ),
        "Water Cycle":
        models.StoryLearningConceptData(
          explanation=
          "The water cycle is the journey water takes around Earth.",
          plot="Characters must follow the water cycle to find a lost friend.",
          demonstration=
          "Water evaporates and forms clouds that help guide the way.")
      },
      expected_character_descriptions={
        "Alex":
        models.StoryCharacterData(
          name="Alex",
          visual=
          "A bright-eyed 8-year-old with curly red hair and round glasses",
          humor="Alex's enthusiasm for science leads to hilarious experiments"
        ),
        "Professor Whiz":
        models.StoryCharacterData(
          name="Professor Whiz",
          visual="A friendly robot with blinking LED eyes and a lab coat",
          humor="The professor's attempts at human expressions always go wrong"
        )
      },
      expected_cover_illustration=models.StoryIllustrationData(
        description=
        "Alex and Professor Whiz stand in a vibrant garden, surrounded by labeled diagrams of plants and water droplets floating in the air",
        characters=["Alex", "Professor Whiz"]))
    self.assert_remaining_text(remaining_text, "")

  def test_partial_story(self):
    """Test parsing a partial story with some missing components."""
    input_text = """
<tone>A blend of Toy Story's humor with Finding Nemo's adventure.</tone>

<title>The Great Adventure</title>

<character>
<name>Alex</name>
<visual>A bright-eyed 8-year-old with curly red hair</visual>
<humor>Alex's enthusiasm for science leads to hilarious experiments</humor>
</character>

<outline>
<phase>
<name>The Beginning</name>
<key_plot_points>
* Alex finds a mysterious magnifying glass
* Strange things start happening
</key_plot_points>
<humor>
Alex's attempts to be a serious scientist lead to increasingly funny situations.
</humor>
<reference>
* Introduction to basic scientific observation
</reference>
</phase>
</outline>

<cover_illustration>
<cover_illustration_description>Alex stands in a garden, holding a magnifying glass</cover_illustration_description>
<cover_illustration_character>Alex</cover_illustration_character>
</cover_illustration>

<page>
<num>1</num>
<humor>
* Visual gag: Alex's hair gets progressively more static-y as they conduct experiments
* Character-driven humor: Alex's overly serious "scientist voice" narration
</humor>
<illustration_description>Alex excitedly examines a leaf with a magnifying glass.</illustration_description>
<illustration_character>Alex</illustration_character>
<text>Once upon a time, there was a curious child.</text>
</page>

<reference>
<concept>Photosynthesis</concept>
<explanation>Photosynthesis is how plants make food using sunlight.</explanation>
<plot>Plants in the story use photosynthesis to help save the day.</plot>
<demonstration>A magical plant grows stronger in sunlight, demonstrating photosynthesis in action.</demonstration>
</reference>
"""

    story_data, remaining_text = _parse_story_response(input_text)

    self.assert_story_data(
      story_data,
      expected_title="The Great Adventure",
      expected_tone=
      "A blend of Toy Story's humor with Finding Nemo's adventure.",
      expected_outline="""<phase>
<name>The Beginning</name>
<key_plot_points>
* Alex finds a mysterious magnifying glass
* Strange things start happening
</key_plot_points>
<humor>
Alex's attempts to be a serious scientist lead to increasingly funny situations.
</humor>
<reference>
* Introduction to basic scientific observation
</reference>
</phase>""",
      expected_pages=[
        models.StoryPageData(
          illustration=models.StoryIllustrationData(
            description=
            "Alex excitedly examines a leaf with a magnifying glass.",
            characters=["Alex"]),
          text="Once upon a time, there was a curious child.",
          humor=
          """* Visual gag: Alex's hair gets progressively more static-y as they conduct experiments
* Character-driven humor: Alex's overly serious "scientist voice" narration""",
          page_number=1)
      ],
      expected_concepts={
        "Photosynthesis":
        models.StoryLearningConceptData(
          explanation="Photosynthesis is how plants make food using sunlight.",
          plot="Plants in the story use photosynthesis to help save the day.",
          demonstration=
          "A magical plant grows stronger in sunlight, demonstrating photosynthesis in action."
        )
      },
      expected_character_descriptions={
        "Alex":
        models.StoryCharacterData(
          name="Alex",
          visual="A bright-eyed 8-year-old with curly red hair",
          humor="Alex's enthusiasm for science leads to hilarious experiments")
      },
      expected_cover_illustration=models.StoryIllustrationData(
        description="Alex stands in a garden, holding a magnifying glass",
        characters=["Alex"]))
    self.assert_remaining_text(remaining_text, "")

  def test_page_fallback_behavior(self):
    """Test the fallback behavior for pages with missing illustration or text."""
    input_text = """
<page>
<num>1</num>
<humor>
* Visual gag: The text stands alone, looking lonely
* Situational comedy: The missing illustration creates a comedic void
</humor>
<text>Only text. No illustration.</text>
</page>
<page>
<num>2</num>
<humor>
* Visual gag: The illustration speaks a thousand words
* Character-driven humor: Alex's expressions tell the whole story
</humor>
<illustration_description>Only illustration, no text.</illustration_description>
<illustration_character>Alex</illustration_character>
</page>
<page>
<num>3</num>
<humor>
* Visual gag: Perfect harmony of text and image
* Character-driven humor: Alex and Professor Whiz's contrasting reactions
* Situational comedy: The scene unfolds perfectly
</humor>
<text>This is the text.</text>
<illustration_description>Complete page with both.</illustration_description>
<illustration_character>Alex</illustration_character>
<illustration_character>Professor Whiz</illustration_character>
</page>
"""
    story_data, remaining_text = _parse_story_response(input_text)

    # The page with only illustration (without text) should be skipped
    self.assert_story_data(
      story_data,
      expected_pages=[
        models.StoryPageData(
          illustration=models.StoryIllustrationData(description="",
                                                    characters=[]),
          text="Only text. No illustration.",
          humor="""* Visual gag: The text stands alone, looking lonely
* Situational comedy: The missing illustration creates a comedic void""",
          page_number=1),
        models.StoryPageData(
          illustration=models.StoryIllustrationData(
            description="Complete page with both.",
            characters=["Alex", "Professor Whiz"]),
          text="This is the text.",
          humor="""* Visual gag: Perfect harmony of text and image
* Character-driven humor: Alex and Professor Whiz's contrasting reactions
* Situational comedy: The scene unfolds perfectly""",
          page_number=3)
      ])
    self.assert_remaining_text(remaining_text, "")

  def test_nested_tags_in_page(self):
    """Test handling of nested tags within page content."""
    input_text = """
<page>
<num>1</num>
<humor>
* Visual gag: Nested tags create a <funny>hilarious</funny> effect
* Character-driven humor: Alex's <dramatic>over-the-top</dramatic> reactions
</humor>
<illustration_description>A scene with <character>nested tags</character></illustration_description>
<illustration_character>Alex</illustration_character>
<text>Text with <emphasis>nested</emphasis> tags.</text>
</page>
"""
    story_data, remaining_text = _parse_story_response(input_text)

    self.assert_story_data(
      story_data,
      expected_pages=[
        models.StoryPageData(
          illustration=models.StoryIllustrationData(
            description="A scene with <character>nested tags</character>",
            characters=["Alex"]),
          text="Text with <emphasis>nested</emphasis> tags.",
          humor=
          """* Visual gag: Nested tags create a <funny>hilarious</funny> effect
* Character-driven humor: Alex's <dramatic>over-the-top</dramatic> reactions""",
          page_number=1)
      ])
    self.assert_remaining_text(remaining_text, "")

  def test_whitespace_handling(self):
    """Test handling of various whitespace in tags."""
    input_text = """
<page>
<num>1</num>
  <illustration_description>
    Illustration with leading/trailing whitespace  
  </illustration_description>
  <illustration_character>Alex</illustration_character>
  <text>
    Text with leading/trailing whitespace  
  </text>
</page>
<page><num>2</num><illustration_description>No whitespace</illustration_description><illustration_character>Professor Whiz</illustration_character><text>No whitespace</text></page>
"""
    story_data, remaining_text = _parse_story_response(input_text)

    self.assert_story_data(
      story_data,
      expected_pages=[
        models.StoryPageData(illustration=models.StoryIllustrationData(
          description="Illustration with leading/trailing whitespace",
          characters=["Alex"]),
                             text="Text with leading/trailing whitespace",
                             page_number=1),
        models.StoryPageData(illustration=models.StoryIllustrationData(
          description="No whitespace", characters=["Professor Whiz"]),
                             text="No whitespace",
                             page_number=2)
      ])
    self.assert_remaining_text(remaining_text, "")

  def test_duplicate_page_numbers(self):
    """Test handling of duplicate page numbers."""
    input_text = """
<page>
<num>1</num>
<illustration_description>First page 1</illustration_description>
<illustration_character>Alex</illustration_character>
<text>First text 1</text>
</page>
<page>
<num>1</num>
<illustration_description>Second page 1</illustration_description>
<illustration_character>Alex</illustration_character>
<illustration_character>Professor Whiz</illustration_character>
<text>Second text 1</text>
</page>
"""
    story_data, remaining_text = _parse_story_response(input_text)

    # Both pages should be included in order
    self.assert_story_data(
      story_data,
      expected_pages=[
        models.StoryPageData(illustration=models.StoryIllustrationData(
          description="First page 1", characters=["Alex"]),
                             text="First text 1",
                             page_number=1),
        models.StoryPageData(illustration=models.StoryIllustrationData(
          description="Second page 1", characters=["Alex", "Professor Whiz"]),
                             text="Second text 1",
                             page_number=1)
      ])
    self.assert_remaining_text(remaining_text, "")

  def test_incomplete_tags_final(self):
    """Test parsing incomplete tags at the end when is_final=True."""
    input_text = """
<page>
<num>1</num>
<humor Humor text.</humor>
<illustration_character>Character name</illustration_character>
<illustration_description>Illustration description.</illustration_description>
<text>First page.</text>
</page>"""
    story_data, remaining_text = _parse_story_response(input_text,
                                                       is_final=True)

    self.assert_story_data(
      story_data,
      expected_pages=[
        models.StoryPageData(page_number=1,
                             text="First page.",
                             illustration=models.StoryIllustrationData(
                               description="Illustration description.",
                               characters=["Character name"]),
                             humor="Humor text.")
      ],
    )
    # Because is_final=True, the repairs should happen, leaving no remaining text
    self.assert_remaining_text(remaining_text, "")

  def test_incomplete_tags_not_final(self):
    """Test parsing incomplete tags when is_final=False."""
    input_text = """
<page>
<num>1</num>
<humor Humor text.</humor>
<illustration_character>Character name</illustration_character>
<illustration_description>Illustration description.</illustration_description>
<text>First page.</text>
</page>"""
    story_data, remaining_text = _parse_story_response(input_text,
                                                       is_final=False)

    # The last </page should NOT be fixed because is_final=False
    self.assert_story_data(story_data)
    # Other tags should be fixed
    self.assert_remaining_text(remaining_text, "")

  def test_incomplete_tags_with_whitespace(self):
    """Test repairing incomplete tags followed by whitespace."""
    input_text = """
      <title>The Incomplete Saga</title>
      <tagline>Science is fun! </tagline>
      <character>
      <name>Bolt</name>
      <visual>A speedy robot </visual>
      </character>
      <page> 
      <num>1</num>
      <text>First page. </text>
      </page>
      """
    # is_final doesn't matter here as repairs happen regardless for whitespace
    story_data, remaining_text = _parse_story_response(input_text,
                                                       is_final=False)

    self.assert_story_data(story_data,
                           expected_title="The Incomplete Saga",
                           expected_tagline="Science is fun!",
                           expected_character_descriptions={
                             "Bolt":
                             models.StoryCharacterData(name="Bolt",
                                                       visual="A speedy robot",
                                                       humor="")
                           },
                           expected_pages=[
                             models.StoryPageData(
                               page_number=1,
                               text="First page.",
                               illustration=models.StoryIllustrationData(),
                               humor="")
                           ])
    assert remaining_text.strip() == ""  # All tags should be repaired

  def test_incremental_parsing_with_repairs(self):
    """Test incremental parsing with intermediate and final repairs."""
    chunk1 = "<title>Incremental Story</title> <tagline>Part 1</tagline> <page"
    chunk2 = "<num>1</num> <text>Content 1</text> </page><page "
    chunk3 = "<num>2</num> <text>Content 2</text> </page>"

    story_data = models.StoryData()
    remaining = ""

    # Process chunk 1 (is_final=False)
    incremental_data, remaining = _parse_story_response(remaining + chunk1,
                                                        is_final=False)
    story_data.update(incremental_data)
    self.assert_story_data(
      story_data,
      expected_title="Incremental Story",
      expected_tagline="Part 1",
    )
    # Tags followed by whitespace are repaired, but <page at end with no whitespace remains
    assert remaining == "  <page"

    # Process chunk 2 (is_final=False)
    combined2 = remaining + chunk2  # "  <page<num>1</num <text>Content </text> </page> <character "
    incremental_data, remaining = _parse_story_response(combined2,
                                                        is_final=False)
    story_data.update(incremental_data)
    # <page> tag from previous chunk plus <num>, <text> tags from this chunk get parsed
    # Parser should consume page 1
    self.assert_story_data(
      story_data,
      expected_title="Incremental Story",
      expected_tagline="Part 1",
      expected_pages=[models.StoryPageData(
        page_number=1,
        text="Content 1",
      )],
    )
    assert remaining == "  <page> "

    # Process chunk 3 (is_final=True - final call)
    combined3 = remaining + chunk3  # "  <character> <name>Chip</name> </character>"
    incremental_data, remaining = _parse_story_response(combined3,
                                                        is_final=True)
    story_data.update(incremental_data)
    # Now is_final=True, the <page at the end of the text should get repaired
    self.assert_story_data(
      story_data,
      expected_title="Incremental Story",
      expected_tagline="Part 1",
      expected_pages=[
        models.StoryPageData(
          page_number=1,
          text="Content 1",
        ),
        models.StoryPageData(
          page_number=2,
          text="Content 2",
        )
      ],
    )

    # Final repair should leave no remaining text
    assert remaining.strip() == ""

  def assert_story_data(
      self,
      actual_data: models.StoryData,
      expected_title: str = "",
      expected_tagline: str = "",
      expected_summary: str = "",
      expected_tone: str = "",
      expected_outline: str = "",
      expected_pages: list[models.StoryPageData] | None = None,
      expected_concepts: dict[str, models.StoryLearningConceptData]
    | None = None,
      expected_character_descriptions: dict[str, models.StoryCharacterData]
    | None = None,
      expected_cover_illustration: models.StoryIllustrationData | None = None):
    """Assert that the actual story data matches the expected values.

    Args:
        actual_data: The actual StoryData object
        expected_title: Expected story title
        expected_tagline: Expected story tagline
        expected_summary: Expected story summary
        expected_tone: Expected story tone
        expected_outline: Expected story outline
        expected_pages: Expected list of page data
        expected_concepts: Expected dict of concept data
        expected_character_descriptions: Expected dict of character descriptions
        expected_cover_illustration: Expected cover illustration data
    """
    assert actual_data.title == expected_title
    assert actual_data.tagline == expected_tagline
    assert actual_data.summary == expected_summary
    assert actual_data.tone == expected_tone
    assert actual_data.outline == expected_outline

    if expected_pages is not None:
      assert len(actual_data.pages) == len(expected_pages)
      for actual_page, expected_page in zip(actual_data.pages, expected_pages):
        assert actual_page.text == expected_page.text
        assert actual_page.humor == expected_page.humor
        assert actual_page.page_number == expected_page.page_number
        assert actual_page.illustration.description == expected_page.illustration.description
        assert actual_page.illustration.characters == expected_page.illustration.characters

    if expected_concepts is not None:
      assert len(actual_data.learning_concepts) == len(expected_concepts)
      for concept, expected_concept_data in expected_concepts.items():
        actual_concept_data = actual_data.learning_concepts[concept]
        assert actual_concept_data.explanation == expected_concept_data.explanation
        assert actual_concept_data.plot == expected_concept_data.plot
        assert actual_concept_data.demonstration == expected_concept_data.demonstration

    if expected_character_descriptions is not None:
      assert len(
        actual_data.characters) == len(expected_character_descriptions)
      for char_name, expected_char_data in expected_character_descriptions.items(
      ):
        actual_char_data = actual_data.characters[char_name]
        assert actual_char_data.name == expected_char_data.name
        assert actual_char_data.visual == expected_char_data.visual
        assert actual_char_data.humor == expected_char_data.humor

    if expected_cover_illustration is not None:
      assert actual_data.cover_illustration.description == expected_cover_illustration.description
      assert actual_data.cover_illustration.characters == expected_cover_illustration.characters

  def assert_remaining_text(self, actual_text, expected_text):
    """Assert that the remaining text matches expected text after stripping whitespace.

    Args:
        actual_text: The actual remaining text
        expected_text: The expected remaining text
    """
    assert actual_text.strip() == expected_text.strip()


class TestRepairXml:
  """Test the _repair_xml function directly."""

  def test_repair_whitespace_incomplete(self):
    """Test repairing tags followed by whitespace."""
    xml = "<tag1>Data</tag1> <tag2 <tag3>More</tag3> </tag4 "
    repaired = _repair_xml(xml, is_final=False)
    # _repair_xml only repairs known tags, tag1-tag4 are not known tags
    # so xml shouldn't change
    assert repaired == "<tag1>Data</tag1> <tag2 <tag3>More</tag3> </tag4 "

  def test_repair_end_incomplete_not_final(self):
    """Test incomplete tags at the end when not final."""
    xml = "<tag1>Data</tag1> <tag2"
    repaired = _repair_xml(xml, is_final=False)
    assert repaired == "<tag1>Data</tag1> <tag2"  # Should not repair end tag

  def test_repair_end_incomplete_final(self):
    """Test incomplete tags at the end when final."""
    xml = "<tag1>Data</tag1> <tag2"
    repaired = _repair_xml(xml, is_final=True)
    # Since tag1 and tag2 are not in the known_tags list,
    # they shouldn't be repaired even when is_final=True
    assert repaired == "<tag1>Data</tag1> <tag2"

  def test_repair_closing_tag_whitespace(self):
    """Test repairing closing tags followed by whitespace."""
    xml = "<tag1><tag2>Data</tag2> </tag1 "
    repaired = _repair_xml(xml, is_final=False)
    # 'tag1' and 'tag2' are not in known_tags, so they should not be repaired
    assert repaired == "<tag1><tag2>Data</tag2> </tag1 "

  def test_repair_closing_tag_end_final(self):
    """Test repairing incomplete closing tag at the end when final."""
    xml = "<tag1><tag2>Data</tag2> </tag1"
    repaired = _repair_xml(xml, is_final=True)
    # 'tag1' and 'tag2' are not in known_tags, so they should not be repaired
    assert repaired == "<tag1><tag2>Data</tag2> </tag1"

  def test_repair_mixed_incomplete_not_final(self):
    """Test mixed incomplete tags with is_final=False."""
    xml = "<story <title My Story </title> <content> <page 1 </page> </content> </page>"
    repaired = _repair_xml(xml, is_final=False)
    # Only tags followed by whitespace are repaired
    expected = "<story <title> My Story </title> <content> <page> 1 </page> </content> </page>"
    assert repaired == expected

  def test_repair_mixed_incomplete_final(self):
    """Test mixed incomplete tags."""
    xml = "<story <title>My Story </title> <content <page 1 </page> </content> </page>"
    repaired = _repair_xml(xml, is_final=True)
    # Only known tags are repaired:
    # - 'title' is fixed to </title>
    # - 'page' is fixed to <page> and </page>
    expected = "<story <title>My Story </title> <content <page> 1 </page> </content> </page>"
    assert repaired == expected

  def test_no_repairs_needed(self):
    """Test input that requires no repairs."""
    xml = "<title>Complete</title><page><num>1</num><text>Text</text></page>"
    repaired = _repair_xml(xml, is_final=True)
    assert repaired == xml  # Should be unchanged

  def test_add_closing_tags_final(self):
    """Test adding missing closing tags when is_final=True."""
    xml = "<outline><phase><name>Start</name>"  # Missing </phase></outline>
    repaired = _repair_xml(xml, is_final=True)
    assert repaired == "<outline><phase><name>Start</name></phase></outline>"
