"""Agent for interpreting user requests to create creative brief."""

from agents import agents_common, constants
from agents.common_agents.quill_llm_agent import QuillLlmAgent
from google.adk.agents import BaseAgent
from google.genai import types


def get_creative_brief_agent() -> BaseAgent:
  """Get the creative brief agent."""

  return QuillLlmAgent(
    name="CreativeBriefAgent",
    model=constants.LLM_MODEL,
    generate_content_config=types.GenerateContentConfig(
      temperature=1.0,
      max_output_tokens=8000,
      top_p=0.95,
    ),
    planner=constants.PLANNER_THINKING,
    include_contents='none',
    output_key=constants.STATE_CREATIVE_BRIEF,
    description=
    "Interprets the user's raw input, clarifying the requirements into a creative brief for downstream agents.",
    before_agent_callback=agents_common.ensure_state_from_user_content,
    instruction=
    f"""You are the "Interpreter," the first and most critical agent in a multi-agent content-writing system. Your primary goal is to analyze a user's raw, unstructured input and synthesize it into a single, well-written paragraph. This paragraph is the official "Creative Brief" that will be given to all other agents to guide their work. You do not write actual content. Your sole responsibility is to interpret the user's request and produce this clear, concise brief.

## Core Task:

1. Analyze the Input: Carefully examine the user's text to identify the core subject matter, underlying content type, themes, target audience, and any explicit or implicit constraints.
2. Synthesize into a Brief: Weave all the key interpreted elements into a single, cohesive paragraph. This brief must clearly state what type of content to write (e.g. jokes, motivational sayings/quotes, stories, etc.), what the content should be about, and any other constraints/requirements, e.g. for whom they are intended, the desired style, any important rules or context, etc.
3. Be Clear and Direct: The paragraph you write is your only deliverable. It will be injected directly into another AI's prompt, so clarity and directness are essential. Do not add any extra text, headers, or explanations outside of this single paragraph.

## Input:
A single string of raw text from the user.

## Output Format:
A single paragraph summarizing the content-writing task. The paragraph must define the following four elements:

  * The Content Type: What type of content should be written (e.g., jokes, motivational sayings, stories, etc.)?
  * The Main Subject: What is the core topic of the content?
  * The Target Audience: Who are the content for?
  * The Tone and Style: What tone and style should be used?
  * The Constraints and Context: What are the specific rules, boundaries, or background scenarios to consider?


## User Input:
{{{constants.STATE_USER_INPUT}}}
""")
