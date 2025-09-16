"""Agent that categorizes jokes."""
from agents import constants
from agents.common_agents.quill_llm_agent import QuillLlmAgent
from agents.tools import firebase_tools
from google.adk.agents import BaseAgent
from google.genai import types


def get_joke_categorizer_agent() -> BaseAgent:
  """Get the creative brief agent."""

  return QuillLlmAgent(
    name="JokeCategorizerAgent",
    model=constants.FAST_LLM_MODEL,
    generate_content_config=types.GenerateContentConfig(
      temperature=0.5,
      max_output_tokens=8000,
      top_p=0.95,
    ),
    planner=constants.PLANNER_THINKING,
    include_contents='none',
    description="Groups jokes into categories.",
    before_agent_callback=[
      firebase_tools.populate_state_with_all_storage_jokes,
      firebase_tools.populate_state_with_all_joke_categories,
    ],
    tools=[
      firebase_tools.get_num_search_results,
      firebase_tools.save_joke_categories,
    ],
    instruction=
    f"""You are a joke categorizer. Your task is to group jokes into categories. The categories will be shown to users in an app to help them discover new jokes. The categories should be creative, fun, and useful.

The categories will be passed to an embedding vector search tool to identify jokes in that category. Note that the embedding does NOT consider joke type (e.g. dad jokes, puns, etc.), so joke type should NOT be use as categories.

Some examples of categories:
- Animals, e.g. "Dogs", "Cats", "Dinosaurs", etc.
- Themes, e.g. "Love", "Work", "Science", etc.
- Topics, e.g. "Cooking", "History", "Celebrities", etc.
- Events, e.g. "Christmas", "Halloween", etc.
- Anything else that is creative, fun, and useful for users

Here are the existing categories:
{{{constants.STATE_ALL_STORAGE_JOKE_CATEGORIES}}}

Think deeply about the jokes and existing categories to decide what is the best set of categories that will be useful and fun for users. The final set of categories should be as close to MECE as possible, so that every joke can be assigned to exactly one category.

After you have created the categories, use the get_num_search_results tool to search for jokes in each category (call the tool multiple times, once for each category). A category is only good if it contains at least 10 jokes. If the search for a category returns less than 10 jokes, you should revise the category and try again.

Guidance on creating categories:
- Categories should be as close to MECE as possible, so that every joke can be assigned to exactly one category.
- Each category should be a single word or phrase without any punctuation or descriptor of jokes (e.g. "jokes about", "puns about", etc.). If it's a noun, it should be in the plural form.
    - e.g. "Dogs" instead of "Dog jokes"
    - e.g. "Sea creatures" instead of "Sea Creature"
    - e.g. "Love" instead of "Love puns"
- Every category should be generally approachable and natural for joke categories in a popular joke app.
    - e.g. "Wild Animals" or "Forest Animals" are good, but "Wild Mammals" is too awkwardly specific

Each category should also have a short description of the image that will represent this category in the UI. The scene should be simple, adorable, and comical, featuring two to three different baby creatures from the specified category. Every creature in the scene must be a different species or breed, and all of their expressions should be joyful, happy, content, or otherwise positive and contribute to a cheerful, wholesome mood. The creatures should be engaged in a variety of imaginative activities across different categories to ensure variety. The image will be fairly small, so the scene should be simple.

After you have finalized the categories, use the save_joke_categories tool to save the categories to the database. For each category to save, include the following:
- display_name: The display name of the category that will be shown to users. It should have proper capitalization and spacing.
- image_description: (Optional) A description of the category that will be used to generate an image for the category. Only set this for new categories that did not previously exist.

## All jokes:
{{{constants.STATE_ALL_STORAGE_JOKES}}}
""")
