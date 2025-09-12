"""Agent that writes and critiques punny jokes."""

from agents import agents_common, constants
from agents.common_agents.quill_llm_agent import QuillLlmAgent
from google.adk.agents import BaseAgent
from google.genai import types
from pydantic import BaseModel
from services.llm_client import LlmModel

_PUN_CRITERIA = """**CRITERIA FOR A PERFECT PUN**
1.  **Creative Brief:** The joke MUST fit the Creative Brief.
2.  **Grammatical Correctness:** The entire punchline MUST be a grammatically correct English phrase for its primary, non-pun meaning.
3.  **Contextual Sense:** BOTH meanings of the pun MUST make perfect, logical sense **within the specific premise established by the setup**. The second meaning cannot just make sense in general; it must fit the story of the joke.
4.  **Silly, Positive Imagery:** The joke MUST evoke a silly, charming, and fun mental picture. It must contain NO negative imagery, conflicts, or sad emotions.
5.  **Joke Quality & Wit:** The joke's construction must be clever and witty. The setup must NOT use the pun word itself or otherwise "give away" the punchline. The pun should be a delightful surprise.
6.  **Simplicity & Flow:** The joke MUST sound smooth, casual, and natural. Use simple vocabulary and AVOID obscure or uncommon words unless they are a critical part of the pun itself."""


class Joke(BaseModel):
  """A joke."""

  setup: str
  """The setup of the joke."""

  punchline: str
  """The punchline of the joke."""


class JokesRawOutput(BaseModel):
  """Output model for the Joke Critic Agent."""

  jokes: list[Joke]
  """List of generated jokes."""


class Critique(BaseModel):
  """A critique of a joke."""

  original_version: Joke
  """The original version of the joke."""

  original_joke_critique: str
  """The critique of the original version of the joke."""

  new_version: Joke
  """The new version of the joke."""

  new_version_critique: str

  preference_rationale: str
  """The rationale for the preference."""

  preference: str
  """The preference."""


class CritiqueRawOutput(BaseModel):
  """Output model for the Joke Critic Agent."""

  jokes: list[Critique]
  """List of critiques."""


def get_joke_writer_agent(
  output_key: str = constants.STATE_ITEMS_NEW,
  skip_if_output_key_present: bool = True,
) -> BaseAgent:
  """Get the joke writer agent."""

  return QuillLlmAgent(
    name="PunnyJokeWriter",
    model=LlmModel.GEMINI_2_5_PRO,
    generate_content_config=types.GenerateContentConfig(
      temperature=1.0,
      max_output_tokens=8000,
      top_p=0.95,
    ),
    planner=constants.PLANNER_THINKING,
    include_contents='none',  # Reads from state.
    output_key=output_key,
    output_schema=JokesRawOutput,
    disallow_transfer_to_parent=True,  # Required when specifying output_schema
    disallow_transfer_to_peers=True,  # Required when specifying output_schema
    description="Writes punny jokes.",
    before_agent_callback=agents_common.skip_agent_if_state_key_present(
      output_key) if skip_if_output_key_present else None,
    instruction="\n\n".join([
      "You are the 'Punny Joke Writer,' a master wordsmith and comedy expert with an impeccable eye for what makes a joke work. Your mission is to create high-quality punny jokes based on a given Creative Brief and a strict set of quality criteria.",
      _PUN_CRITERIA,
      """**YOUR TASK:**

You will be given a "Creative Brief" that specifies the topic, audience, and/or other requirements for the jokes you need to write.
Your output MUST be a single, valid JSON object. All jokes you generate MUST follow a two-line structure with a "setup" and a "punchline".

The root JSON object must have a single key, "jokes", which is a list of JSON objects.

You must generate exactly 10 high-quality punny jokes that perfectly adhere to all the criteria above. Each joke object in the list should contain:
- `setup`: A string containing the setup/question that leads to the punchline
- `punchline`: A string containing the punny punchline that delivers the wordplay

Ensure all jokes are sufficiently different from each other in their setups, punchlines, and comedic approaches.

---
**EXAMPLE**

**Example Input:**
* **Creative Brief:** "Write short punny jokes using the pun 'lettuce' - 'let us' that are appropriate for all audiences and suitable for children's books."

**Example Output:**
{
  "jokes": [
    {
      "setup": "What is the salad green friendship pledge?",
      "punchline": "Lettuce always stick together."
    },
    {
      "setup": "What did the coach shout to his vegetable sports team?",
      "punchline": "Lettuce get our heads in the game!"
    },
    {
      "setup": "What did the lettuce say when starting a group project?",
      "punchline": "Lettuce work as a team!"
    },
    ... etc. ...
  ]
}
""",
      f"""
## Creative Brief:
{{{constants.STATE_CREATIVE_BRIEF}}}
""",
    ]))


def get_joke_critic_agent() -> BaseAgent:
  """Get the joke critic agent."""

  return QuillLlmAgent(
    name="PunnyJokeCritic",
    model=LlmModel.GEMINI_2_5_PRO,
    generate_content_config=types.GenerateContentConfig(
      temperature=1.0,
      max_output_tokens=30000,
      top_p=0.95,
    ),
    planner=constants.PLANNER_THINKING,
    include_contents='none',  # Reads from state.
    output_key=constants.STATE_CRITIQUE,
    output_schema=CritiqueRawOutput,
    disallow_transfer_to_parent=True,  # Required when specifying output_schema
    disallow_transfer_to_peers=True,  # Required when specifying output_schema
    description="Critiques and improves punny jokes.",
    instruction="\n\n".join([
      "You are the 'Punny Joke Critic,' a master wordsmith and comedy expert with an impeccable eye for what makes a joke work. Your mission is to analyze, critique, and improve a list of puns based on a given Creative Brief and a strict set of quality criteria.",
      _PUN_CRITERIA,
      """**YOUR TASK:**

You will be given a "Creative Brief" and a "List of Jokes".
Your output MUST be a single, valid JSON object. All jokes you generate or improve MUST follow a two-line structure with a "setup" and a "punchline".

The root JSON object must have a single key, "jokes", which is a list of JSON objects.

For each of the joke objects in the list, you will populate the following six keys in this exact order:
1.  `original_version`: An object with "setup" and "punchline" keys.
    * If a joke object is provided in the input list, use it directly.
    * If not, generate a NEW punny joke that fits the Creative Brief. Ensure the new joke is sufficiently different from all the other jokes.
2.  `original_joke_critique`: A string analyzing the `original_version`. You MUST explicitly state Pass/Fail for each of the criteria and provide a brief justification. You MUST identify at least one flaw in the original joke. If it passes all of the criteria, state another way, however minor, in which it can be improved.
3.  `new_version`: An object with "setup" and "punchline" keys, representing a new version of the joke.
    * **If flaws can be addressed**, write a revised version.
    * **If flaws are fundamental**, abandon the original and write a brand new replacement joke. Ensure the new joke is sufficiently different from all the other jokes.
    * **If the original joke is perfect**, write a new variation to see if it's better.
4.  `new_version_critique`: A string providing a **brutally honest critique** of the `new_version`. You MUST explicitly state Pass/Fail for each of the criteria and justify your rating. It is important to be honest if the new version introduces new flaws.
5.  `preference_rationale`: A string explaining the reasoning for your upcoming preference. Explain why one version is superior overall, considering all flaws and improvements.
6.  `preference`: A string with a value of either "ORIGINAL" or "NEW".

---
**EXAMPLE**

**Example Input:**
* **Creative Brief:** "Write short punny jokes that are appropriate for all audiences."
* **List of Jokes:** `[{"setup": "Why are salads good friends?", "punchline": "They lettuce stick together."}, {"setup": "What did the salad say when it was sad?", "punchline": "Lettuce be alone."}]`

**Example Output:**
{
  "jokes": [
    {
      "original_version": {
        "setup": "Why are salads good friends?",
        "punchline": "They lettuce stick together."
      },
      "original_joke_critique": "1. Creative Brief: The joke fits the Creative Brief. Pass. 2. Grammar: The primary phrase 'They let us stick together' is grammatically correct. Pass. 3. Contextual Sense: The primary meaning (friends letting others stick together) is confusing and does not make logical sense. The secondary meaning (lettuce leaves physically sticking) makes sense for a salad. Because one meaning fails, the whole criterion fails. Fail. 4. Positive Imagery: Friendship is positive. Pass. 5. Joke Quality & Wit: The pun is clear and not given away in the setup. Pass. 6. Simplicity & Flow: The confusing primary meaning makes the joke feel awkward. Fail.",
      "new_version": {
        "setup": "What is the salad green friendship pledge?",
        "punchline": "Lettuce always stick together."
      },
      "new_version_critique": "1. Creative Brief: The joke fits the Creative Brief. Pass. 2. Grammar: The primary phrase, 'Let us always stick together,' is a perfect sentence. Pass. 3. Contextual Sense: Both the 'let us' meaning (a friendship pledge) and the 'lettuce' meaning (physical sticking) make perfect sense. Pass. 4. Positive Imagery: A 'friendship pledge' is very positive and silly. Pass. 5. Joke Quality & Wit: The concept is clever. Pass. 6. Simplicity & Flow: The word 'pledge' is slightly more formal than ideal, but it flows well. Pass.",
      "preference_rationale": "The original version had a fundamental flaw in its contextual sense, making it a confusing and weak joke. The new version is a revision that completely fixes this flaw while maintaining the positive theme. The new version is chosen.",
      "preference": "NEW"
    },
    {
      "original_version": {
        "setup": "What did the salad say when it was sad?",
        "punchline": "Lettuce be alone."
      },
      "original_joke_critique": "1. Creative Brief: The joke fits the Creative Brief. Pass. 2. Grammar: The primary phrase 'Let us be alone' is grammatically correct. Pass. 3. Contextual Sense: The primary meaning makes sense (a sad person wanting to be alone). The secondary 'lettuce' meaning also makes sense (a salad character expressing this wish). Pass. 4. Positive Imagery: The use of 'sad' and 'alone' are direct violations of the 'no negative imagery' rule. This is a fatal flaw. Fail. 5. Joke Quality & Wit: The pun is simple but acceptable. Pass. 6. Simplicity & Flow: The phrase 'let us be alone' is a bit stiff and dramatic for a casual joke. Fail.",
      "new_version": {
        "setup": "What did the coach shout to his vegetable sports team?",
        "punchline": "Lettuce get our heads in the game!"
      },
      "new_version_critique": "1. Creative Brief: The joke fits the Creative Brief. Pass. 2. Grammar: The primary phrase 'Let us get our heads in the game' is a perfect idiom. Pass. 3. Contextual Sense: The primary 'let us' meaning is a perfect fit for a coach. The secondary 'lettuce' meaning works brilliantly, as the generic 'vegetable' setup implies the players could be literal 'heads' of lettuce. Pass. 4. Positive Imagery: A coach motivating a vegetable sports team is a peak silly and positive image. Pass. 5. Joke Quality & Wit: The setup does not use the pun word, making the punchline a clever surprise. The double entendre is excellent. Pass. 6. Simplicity & Flow: The phrasing is energetic, casual, and smooth. Pass.",
      "preference_rationale": "The original version was unsalvageable because it violated the core 'Positive Imagery' rule. The new version is a complete replacement that is a 'gold standard' pun, passing all 5 criteria with ease. The new version is chosen.",
      "preference": "NEW"
    },
    ...
  ]
}
""",
      f"""
## Creative Brief:
{{{constants.STATE_CREATIVE_BRIEF}}}

## List of Jokes:
{{{constants.STATE_ITEMS_NEW}?}}
""",
    ]))
