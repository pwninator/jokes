"""LLM prompt for generating reference material search queries."""

import json
import re
from typing import Any

from . import story
from common import models
from common.models import ReadingLevel
from services import llm_client, wikipedia
from services.llm_client import LlmModel

# pylint: disable=line-too-long
_READING_LEVEL_GUIDELINES = {
  # Examples: Goodnight Moon, The Very Hungry Caterpillar (Adjusted for AI generation)
  ReadingLevel.PRE_K:
  """
Choose the plot at a Pre-K reading level (ages 3-4):
* Describe familiar, everyday situations (playing, eating, sleeping).
* Feature basic emotions like happy, sad, maybe a little scared; avoid complex emotions.
""",
  # Examples: Brown Bear Brown Bear, Clifford, Dr. Seuss (early) (Adjusted for AI generation)
  ReadingLevel.KINDERGARTEN:
  """
Choose the plot at a Kindergarten reading level (ages 5-6):
* Describe familiar settings (home, school, park) and common experiences.
* Show clear, direct cause-and-effect relationships.
* Include basic emotions (happy, sad, angry, surprised) and simple social interactions (sharing, playing together).
* Follow a predictable, linear story structure (beginning, middle, end).
""",
  # Examples: Frog and Toad, Henry and Mudge (Adjusted for AI generation)
  ReadingLevel.FIRST:
  """
Choose the plot at a 1st Grade reading level (ages 6-7):
* Develop a simple plot with a clear beginning, middle, and end, often in short chapters.
* Describe relatable situations, possibly with some light fantasy elements.
* Include simple problem-solving scenarios (a character faces a simple challenge and finds a solution).
* Focus on clear character actions and dialogue.
""",
  # Examples: Magic Tree House (early), Junie B. Jones
  ReadingLevel.SECOND:
  """
Choose the plot at a 2nd Grade reading level (ages 7-8):
* Develop plots with a clear sequence of events across chapters.
* Show character motivations (why characters do what they do) and distinct character voices.
* Include multiple events leading to a resolution.
""",
  # Examples: Charlotte's Web, Ramona Quimby Age 8
  ReadingLevel.THIRD:
  """
Choose the plot at a 3rd Grade reading level (ages 8-9):
* Develop plots containing subplots or twists; may include world-building elements.
* Depict character development and motivations.
* Explore themes like friendship, responsibility, dealing with challenges.
""",
  # Examples: Because of Winn-Dixie, Harry Potter and the Sorcerer's Stone
  ReadingLevel.FOURTH:
  """
Choose the plot at a 4th Grade reading level (ages 9-10):
* Develop plots containing subplots or twists; may include world-building elements.
* Explore character relationships and internal thoughts.
* Address abstract concepts and themes (e.g., friendship, courage, fairness, belonging) appropriately for the age group.
""",
  # Examples: Wonder, Bridge to Terabithia
  ReadingLevel.FIFTH:
  """
Choose the plot at a 5th Grade reading level (ages 10-11):
* Develop complex plots with multiple threads and potential symbolism.
* Depict deep character development, internal conflicts, motivations, and realistic flaws.
* Explore abstract themes (loss, identity, empathy) with nuance; handle significant emotional events.
""",
  # Examples: Percy Jackson, Roll of Thunder Hear My Cry
  ReadingLevel.SIXTH:
  """
Choose the plot at a 6th Grade reading level (ages 11-12):
* Develop intricate plots (subplots, flashbacks, foreshadowing); may handle historical or mythological contexts.
* Explore complex character relationships, internal conflicts, and character growth arcs.
* Address sophisticated themes (e.g., identity, justice, prejudice, societal issues, morality) with nuance.
""",
  # Examples: The Giver, The Outsiders
  ReadingLevel.SEVENTH:
  """
Choose the plot at a 7th Grade reading level (ages 12-13):
* Develop complex narratives (multiple plotlines, internal/external conflicts, resolutions); may use dystopian or specific social settings.
* Explore sophisticated character development (motivations, flaws, changes over time, peer dynamics).
* Address abstract themes (conformity, societal structures, belonging, consequences) with depth.
""",
  # Examples: The Book Thief, To Kill a Mockingbird
  ReadingLevel.EIGHTH:
  """
Choose the plot at an 8th Grade reading level (ages 13-14):
* Construct intricate plots (subplots, parallel narratives, complex resolutions); may consider historical context.
* Explore nuanced character development (internal conflicts, moral dilemmas, evolving relationships).
* Address abstract themes (justice, prejudice, morality, loss, historical impact) with subtlety and complexity.
""",
  # Examples: Romeo and Juliet, Animal Farm
  ReadingLevel.NINTH:
  """
Choose the plot at a 9th Grade reading level (ages 14-15):
* Develop complex, multi-layered plots with thematic depth; may use allegory or satire.
* Explore highly developed characters (complex motivations, internal conflicts, significant growth, tragic flaws).
* Address challenging abstract themes (social critique, fate, power, manipulation, philosophical questions).
""",
  # Examples: Lord of the Flies, Fahrenheit 451
  ReadingLevel.TENTH:
  """
Choose the plot at a 10th Grade reading level (ages 15-16):
* Construct complex plots (subplots, symbolism, thematic resonance); may explore societal critique.
* Develop psychologically nuanced characters (profound motivations, group dynamics, impact of environment).
* Address challenging themes (human nature, censorship, technology's impact, loss of innocence) with ambiguity or complexity.
""",
  # Examples: The Great Gatsby, 1984
  ReadingLevel.ELEVENTH:
  """
Choose the plot at an 11th Grade reading level (ages 16-17):
* Construct complex narratives (multiple perspectives, interwoven plotlines, thematic complexity); use symbolism effectively.
* Develop highly nuanced, psychologically complex characters (disillusionment, societal roles).
* Address challenging themes (social class, the American Dream, totalitarianism, existential questions) with ambiguity, irony, or multiple interpretations.
""",
  # Examples: Hamlet, Brave New World, Beloved
  ReadingLevel.TWELFTH:
  """
Choose the plot at a 12th Grade reading level (ages 17-18):
* Construct highly complex narratives (multiple perspectives, ambiguous endings, philosophical depth).
* Develop exceptionally nuanced characters (profound motivations, moral dilemmas, transformation, exploring the human condition).
* Address challenging abstract themes (existence, memory, trauma, freedom, societal control) with depth, subtlety, irony, prompting deep reflection.
"""
}

_search_query_llm = llm_client.get_client(
  label="Reference Material Search Queries",
  model=LlmModel.GEMINI_2_5_FLASH,
  temperature=0.9,
  thinking_tokens=0,
  output_tokens=4000,
  system_instructions=[
    f"""You are a creative assistant for a children's story generator application. Your goal is to devise an engaging plot concept based on the user prompt, and in order to ground the factual content of the story, identify the title of a single, Wikipedia article whose content is highly relevant to a core element of the story.

The application will provide you with:

1.  A story prompt: A short description or idea for a children's story.
2.  A list of characters: The names and descriptions of the characters in the story.
3.  A list of previously used Wikipedia article titles (this list may be empty).
4.  A target reading level of the story. Use this to guide the complexity of the story plot.

**Guidelines for Story Plot:**

{story.STORY_INSTRUCTIONS_BASE}

**Guidelines for Wikipedia Article Selection:**

* **Relevant to the Story Prompt:** Ensure the chosen Wikipedia article is directly related to the story prompt.
* **Age-appropriate:** Ensure the likely content of the chosen Wikipedia article is appropriate for young children (avoiding violence, complex historical/political details, or mature themes) and that the topic's complexity can be simplified effectively.
* **Substantial & Specific Title:** Use specific, recognizable titles that correspond to articles with **substantial explanatory content**. Avoid disambiguation pages, list articles, or overly obscure topics unless essential for the plot.
* **Prefer Foundational Topics:** When multiple relevant topics exist, ALWAYS prefer a broader, foundational topic that still provides concrete details applicable to the plot (e.g. "Joe visits a rainforest" -> "Rainforest"), unless they have already been used in previous stories, in which case choose a more specific topic (e.g. "Tropical rainforest", "Temperate rainforest") or related topic (e.g. specific species of animals that live in rainforests).
* **New Topics Only:** Do not suggest a title from the provided list of previously used topics. However, if a broad topic has been used previously (e.g., 'Robotics'), suggesting a related but more specific sub-topic (e.g., 'Hydraulics', 'Electric battery') for a new story is acceptable and encouraged for variety.
* **Aligned with Science, Technology, or Nature:** The article MUST be about one of these topics. Consider character-specific biology/science (e.g., animal senses) if relevant and integrable.
* **Real-World Topics Only:** Use only real-world Wikipedia titles. For fictional prompts, identify relevant real-world analogues (e.g., `Combustion` for fire-breathing dragons) instead of the fictional element itself.

Output the following fields in a JSON dictionary:

*  `potential_article_titles`: Based on the user's story prompt, generate a list of up to 10 potential Wikipedia article titles that are relevant to the story prompt. If there are any foundational topics that fit the prompt and have not been used in previous stories, ONLY include those in the list. Otherwise, include more specific and/or related topics.
*  `user_expectation`: Read the user's story prompt carefully. Summarize the core theme, expected tone (e.g., funny, adventurous), and focus in 1-2 sentences. Then, briefly discuss which of the potential articles best fit the prompt and user expectations. 
  * Interpret potentially child-inappropriate themes (like 'fight', 'battle', 'destroy', 'poison') through the lens of child-friendly media (e.g., cartoons like Paw Patrol).
    * Example: Action sequences should be depicted as adventurous, perhaps comical or slapstick, focusing on challenges, problem-solving, and cleverness rather than realistic harm or threat.
    * Example: "Defeat" should mean being outsmarted, temporarily stopped (e.g., tangled up, tricked), or having plans foiled, always ensuring a child-appropriate resolution.
    * Example: "Poison" might mean a substance causing temporary, funny effects (like hiccups or turning purple) rather than actual harm.
  * Avoid overly sanitizing the user's core request for action, but ensure the *portrayal* and *consequences* are suitable for young children. This reinterpreted understanding guides the plot generation.
*  `plot1`, `plot2`, `plot3`: Based on the reinterpreted user prompt understanding from Step 1 and character descriptions, devise three different brief plot ideas for chosen article(s) from the `user_expectation` section.
  * Aim for concepts that are potentially **epic, adventurous, and genuinely funny, with humor and themes that could appeal to both children and adults** (think Pixar-style broad appeal).
  * Ensure all plot concepts are suitable for young children, avoiding scary, or mature themes.
  * If `user_expectation` chose fewer than 3 articles, repeat the chosen article(s) in all three plots.
  * Each plot should be a JSON object with the following fields:
    * `plot`: A 5-10 sentence description of the plot.
    * `article_title`: The title of a single, real-world Wikipedia article that meets the criteria listed in the given guidelines.
      * This field should ONLY be the article title. DO NOT include any other text (e.g. fragment, URL, article body or snippet, etc.). It should only be a few words.
    * `eval`: A brief evaluation of how well the plot fits the above criteria.
*  `choice_rationale`: Analyze the three plot-title pairs. Choose the single best option based on:
    * **Topic Interest:** Is the Wikipedia article topic inherently interesting and suitable for children?
*  `chosen_plot`: The string identifier of the chosen plot (e.g., "plot1", "plot2", or "plot3").
"""
  ],
  response_schema={
    "type":
    "OBJECT",
    "properties": {
      "potential_article_titles": {
        "type": "ARRAY",
        "items": {
          "type": "STRING",
        },
        "minItems": 1,
        "maxItems": 10,
      },
      "user_expectation": {
        "type": "STRING"
      },
      "plot1": {
        "type": "OBJECT",
        "properties": {
          "plot": {
            "type": "STRING"
          },
          "article_title": {
            "type": "STRING"
          },
          "eval": {
            "type": "STRING"
          }
        },
        "required": ["plot", "article_title", "eval"],
        "property_ordering": ["plot", "article_title", "eval"]
      },
      "plot2": {
        "type": "OBJECT",
        "properties": {
          "plot": {
            "type": "STRING"
          },
          "article_title": {
            "type": "STRING"
          },
          "eval": {
            "type": "STRING"
          }
        },
        "required": ["plot", "article_title", "eval"],
        "property_ordering": ["plot", "article_title", "eval"]
      },
      "plot3": {
        "type": "OBJECT",
        "properties": {
          "plot": {
            "type": "STRING"
          },
          "article_title": {
            "type": "STRING"
          },
          "eval": {
            "type": "STRING"
          }
        },
        "required": ["plot", "article_title", "eval"],
        "property_ordering": ["plot", "article_title", "eval"]
      },
      "choice_rationale": {
        "type": "STRING"
      },
      "chosen_plot": {
        "type": "STRING",
        "enum": ["plot1", "plot2", "plot3"],
      }
    },
    "required": [
      "potential_article_titles", "user_expectation", "plot1", "plot2",
      "plot3", "choice_rationale", "chosen_plot"
    ],
    "property_ordering": [
      "potential_article_titles", "user_expectation", "plot1", "plot2",
      "plot3", "choice_rationale", "chosen_plot"
    ],
  })

_choose_article_llm = llm_client.get_client(
  label="Choose Wikipedia Article",
  model=LlmModel.GEMINI_2_5_FLASH,
  thinking_tokens=0,
  output_tokens=1000,
  temperature=0.1,
  system_instructions=[
    """You are a **Wikipedia Article Selector** assistant. Your goal is to choose the single best Wikipedia page from a list of search results, based on a specific story concept and target article title, ensuring the chosen page's content is appropriate and useful for an educational story.

**You will be provided with:**

1.  **Plot Concept:** The specific plot outline for the story.
2.  **Target Wikipedia Article Title:** The title of the Wikipedia article intended to provide factual content for the story outlined in the Plot Concept.
3.  **Wikipedia Search Results:** A list containing the index, page title, and snippet for each search result.

**Your Task:**

Analyze the provided search results list and select the **single best Wikipedia page title** from that list that best meets **all** the following criteria:

* **Title Match & Relevance:** Accurately covers Target Title. Highly relevant to Plot Concept (use Plot Concept primarily for disambiguation if needed). Avoid disambiguation pages or unrelated topics.
* **Substantial Content:** Corresponds to a well-developed article with explanatory text/facts. Avoid lists, stubs, category/disambiguation pages. Needs extractable content for story.
* **Canonical Source:** Prefer main article over narrow sub-pages, unless plot requires sub-page details.

**Output:**

Provide **only a single JSON object** containing the `index` and the `title` of the single best-fitting Wikipedia page from the provided search results list. The format must be exactly: `{"index": i, "title": "Chosen Page Title"}`. Do not include any other text, explanation, or formatting outside this JSON object.

**Example:**

If provided with results where the first article is the best match:

```
Article 0:
Title: Bird nest
Snippet: A bird nest is the spot in which a bird lays...
Article 1:
Title: List of birds by nesting behaviour
Snippet: This is a list of birds grouped by nesting behavior...
Article 2:
Title: Edible bird's nest
Snippet: Edible bird's nests are bird nests created by edible-nest swiftlets...
```

And the target title was `Bird nest` for a plot about building a fort, you should output:

{"index": 0, "title": "Bird nest"}
"""
  ],
  response_schema={
    "type": "OBJECT",
    "properties": {
      "index": {
        "type": "INTEGER"
      },
      "title": {
        "type": "STRING"
      },
    },
    "required": ["index", "title"],
    "property_ordering": ["index", "title"],
  },
)
# pylint: enable=line-too-long


def generate_plot_and_wiki_title(
  story_prompt: str,
  characters: list[models.Character],
  past_topics: list[str],
  reading_level: ReadingLevel,
  extra_log_data: dict[str, Any],
) -> tuple[str, str, dict[str, str], models.SingleGenerationMetadata]:
  """Generate plot and wikipedia title for a children's book.

  Args:
      story_prompt: The story prompt to find reference material for
      characters: Optional list of characters to consider for topic selection
      past_topics: Optional list of topics the reader has already learned about
      reading_level: The reading level of the story
      extra_log_data: Extra log data to include in the log

  Returns:
      Tuple of (plot, wikipedia title, search queries, generation metadata)

  Raises:
      ValueError: If no queries could be generated
  """

  prompt = [_get_story_context(story_prompt, characters)]

  prompt.append(_READING_LEVEL_GUIDELINES[reading_level])

  if past_topics:
    past_topics_str = "\n".join(f"- {topic}" for topic in past_topics)
    prompt.append(f"""
Previously used Wikipedia article titles:
{past_topics_str}
""")

  response = _search_query_llm.generate(prompt, extra_log_data=extra_log_data)

  # Extract content between square brackets using regex
  match = re.search(r'\{(.*?)\}', response.text, re.DOTALL)
  if not match:
    raise ValueError(f"No valid JSON array found in response: {response.text}")

  response_dict = json.loads(response.text)
  chosen_plot_key = response_dict.get("chosen_plot")
  if not chosen_plot_key:
    raise ValueError(f"No chosen plot key found in response: {response.text}")

  chosen_plot_dict = response_dict.get(chosen_plot_key)
  if not chosen_plot_dict:
    raise ValueError(f"No chosen plot found in response: {response.text}")

  plot = chosen_plot_dict.get("plot")
  article_title = chosen_plot_dict.get("article_title")
  if not plot or not article_title:
    raise ValueError(
      f"No plot or wikipedia title found in response: {response.text}")

  return plot, article_title, response_dict, response.metadata


def choose_best_wikipedia_result(
  search_results: list[wikipedia.WikipediaSearchResult],
  article_title: str,
  story_prompt: str,
  extra_log_data: dict[str, Any],
) -> tuple[wikipedia.WikipediaSearchResult | None,
           models.SingleGenerationMetadata | None]:
  """Choose the most appropriate Wikipedia article for a children's book.

  Args:
      search_results: List of Wikipedia search results to choose from
      article_title: The title of the target Wikipedia article
      story_prompt: The story prompt to choose an article for
      extra_log_data: Extra log data to include in the log

  Returns:
      Tuple of (chosen result or None if none are appropriate, generation metadata)
  """
  if not search_results:
    return None, None

  # Format results for the LLM
  results_text = "\n\n".join(f"""Article {i}:
Title: {result.title}
Snippet: {result.snippet}
""" for i, result in enumerate(search_results))

  prompt = [
    f"""
Plot Concept:
{story_prompt}

Target Wikipedia Article Title:
{article_title}

Search results:
{results_text}
"""
  ]

  response = _choose_article_llm.generate(prompt,
                                          extra_log_data=extra_log_data)

  # Extract the JSON response
  if match := re.search(r'\{.*\}', response.text, re.DOTALL):
    try:
      choice = json.loads(match.group())
      chosen_title = choice.get('title', '').strip()
      chosen_index = choice.get('index', -1)

      # First try to match by exact title
      if chosen_title:
        for result in search_results:
          if result.title.lower() == chosen_title.lower():
            return result, response.metadata

      # Fall back to index if title match fails
      if 0 <= chosen_index < len(search_results):
        return search_results[chosen_index], response.metadata

      return None, response.metadata

    except json.JSONDecodeError:
      print(f"Failed to parse JSON from response: {response.text}")

  return None, None


def _get_story_context(
  story_prompt: str,
  characters: list[models.Character],
) -> str:
  """Get the context for the story."""
  characters_str = "\n".join(char.description_xml for char in characters)
  return f"""
Story prompt:
{story_prompt}

Story characters:
{characters_str}
"""
