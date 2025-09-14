"""Agent that categorizes jokes."""
from google.adk.agents import (
    LlmAgent,
    SequentialAgent,
    BaseAgent,
)
from py_quill.services import firestore, search
from pydantic import BaseModel
from google.adk.agents.invocation_context import InvocationContext

# State keys
STATE_ALL_JOKES = "all_jokes"
STATE_CATEGORIES_TO_PROCESS = "categories_to_process"
STATE_GOOD_CATEGORIES = "good_categories"
STATE_BAD_CATEGORIES = "bad_categories"
STATE_PROCESSED_CATEGORIES = "processed_categories"
STATE_FINAL_CATEGORIES = "final_categories"

class CategorizerAgentOutput(BaseModel):
    categories: list[str]

class GetJokesAgent(BaseAgent):
    """An agent that gets all jokes from firestore."""

    async def run(self, context: InvocationContext) -> str:
        jokes = firestore.get_all_punny_jokes()
        jokes_str = "\n".join([f"- {joke.setup_text} {joke.punchline_text}" for joke in jokes])
        context.session.state[STATE_ALL_JOKES] = jokes_str
        return "Got all jokes."

class CategoryBatchProcessorAgent(BaseAgent):
    """An agent that processes a batch of categories."""

    async def run(self, context: InvocationContext) -> str:
        categories_to_process = context.session.state.get(STATE_CATEGORIES_TO_PROCESS, [])

        good_categories = context.session.state.get(STATE_GOOD_CATEGORIES, [])
        bad_categories = [] # Reset bad categories for this batch

        processed_categories = context.session.state.get(STATE_PROCESSED_CATEGORIES, [])

        for category in categories_to_process:
            if category in processed_categories:
                continue

            search_results = search.search_jokes(query=category, limit=10)
            joke_count = len(search_results)

            if joke_count >= 10:
                good_categories.append(category)
            else:
                bad_categories.append(category)

            processed_categories.append(category)

        context.session.state[STATE_GOOD_CATEGORIES] = good_categories
        context.session.state[STATE_BAD_CATEGORIES] = bad_categories
        context.session.state[STATE_PROCESSED_CATEGORIES] = processed_categories
        context.session.state[STATE_CATEGORIES_TO_PROCESS] = []

        return f"Processed {len(categories_to_process)} categories."

class CategorizationLoopAgent(BaseAgent):
    """An agent that manages the categorization loop."""
    def __init__(self, batch_processor: BaseAgent, refiner: LlmAgent, max_iterations: int = 5, **kwargs):
        super().__init__(**kwargs)
        self.batch_processor = batch_processor
        self.refiner = refiner
        self.max_iterations = max_iterations

    async def run(self, context: InvocationContext) -> str:
        for i in range(self.max_iterations):
            await self.batch_processor.run(context)

            bad_categories = context.session.state.get(STATE_BAD_CATEGORIES, [])
            if not bad_categories:
                break

            await self.refiner.run(context)

        return "Categorization loop finished."

class FinalOutputAgent(BaseAgent):
    """An agent that prepares the final output."""

    async def run(self, context: InvocationContext) -> str:
        good_categories = context.session.state.get(STATE_GOOD_CATEGORIES, [])
        context.session.state[STATE_FINAL_CATEGORIES] = good_categories
        return "Final categories are ready."

def get_categorizer_agent() -> SequentialAgent:
    """Gets the categorizer agent."""

    category_generation_agent = LlmAgent(
        name="CategoryGenerationAgent",
        instruction="""
        You are a joke categorizer. You will be given a list of jokes and you need to
        generate a list of categories for them. The categories should be fun,
        useful, and likely to contain at least 10 jokes.
        Here are the jokes:
        {{all_jokes}}
        """,
        output_schema=CategorizerAgentOutput,
        output_key="categories_output",
        after_agent_callback=lambda context: context.session.state.update({
            STATE_CATEGORIES_TO_PROCESS: context.session.state.get("categories_output").categories
        })
    )

    refinement_agent = LlmAgent(
        name="RefinementAgent",
        instruction="""
        You have a list of good categories and bad categories.
        Good categories: {{good_categories}}
        Bad categories: {{bad_categories}}
        Your task is to generate a new list of categories to try based on the bad categories.
        The new categories should not be in the list of processed categories: {{processed_categories}}
        """,
        output_schema=CategorizerAgentOutput,
        output_key="categories_output",
        after_agent_callback=lambda context: context.session.state.update({
            STATE_CATEGORIES_TO_PROCESS: context.session.state.get("categories_output").categories,
            STATE_BAD_CATEGORIES: []
        })
    )

    batch_processor = CategoryBatchProcessorAgent(name="CategoryBatchProcessor")
    loop_agent = CategorizationLoopAgent(
        name="CategorizationRefinementLoop",
        batch_processor=batch_processor,
        refiner=refinement_agent,
        max_iterations=5
    )

    return SequentialAgent(
        name="JokeCategorizerAgent",
        sub_agents=[
            GetJokesAgent(name="GetJokes"),
            category_generation_agent,
            loop_agent,
            FinalOutputAgent(name="FinalOutput")
        ]
    )
