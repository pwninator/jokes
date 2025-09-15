"""Agent that categorizes jokes."""
from agents import constants
from agents.common_agents.quill_llm_agent import QuillLlmAgent
from agents.tools import get_all_jokes, joke_search
from google.adk.agents import BaseAgent
from google.genai import types
from pydantic import BaseModel


class JokeCategories(BaseModel):
  """Data structure for a list of joke categories."""

  categories: list[str]


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
    output_key=constants.STATE_JOKE_CATEGORIES,
    output_schema=JokeCategories,
    disallow_transfer_to_parent=True,  # Required when specifying output_schema
    disallow_transfer_to_peers=True,  # Required when specifying output_schema
    description="Groups jokes into categories.",
    before_agent_callback=get_all_jokes.populate_state_with_all_storage_jokes,
    tools=[joke_search.get_num_search_results],
    instruction=
    f"""You are a joke categorizer. Your task is to group jokes into categories. The categories will be shown to users in an app to help them discover new jokes. The categories should be creative, fun, and useful.

Some examples of categories:
- Animals, e.g. "Dogs", "Cats", "Dinosaurs", etc.
- Themes, e.g. "Love", "Work", "Science", etc.
- Topics, e.g. "Cooking", "History", "Celebrities", etc.
- Events, e.g. "Christmas", "Halloween", etc.
- Anything else that is creative, fun, and useful for users

The categories will be passed to an embedding vector search tool to identify jokes in that category. Note that the embedding does NOT consider joke type (e.g. dad jokes, puns, etc.), so joke type should NOT be use as categories.

After you have created the categories, use the get_num_search_results tool to search for jokes in each category (call the tool multiple times,  once for each category). A category is only good if it contains at least 10 jokes. If the search for a category returns less than 10 jokes, you should revise the category and try again.

Each category should be a single word or phrase without any punctuation or descriptor of jokes (e.g. "jokes about", "puns about", etc.). If it's a noun, it should be in the plural form.

Examples of good categories:
- Dogs
- Sea creatures
- Love
- Halloween

Examples of bad categories:
- Dog jokes (should be "Dogs")
- Sea Creature (should be "Sea creatures")
- Love puns (should be "Love")

After you have finalized the categories, output the categories formatted as a JSON object with a single field "categories" that is a list of strings.

## All jokes:
{{{constants.STATE_ALL_STORAGE_JOKES}}}
""")
