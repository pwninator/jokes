"""Agent tool for getting all jokes from the firestore database."""

from agents import constants
from google.adk.agents.callback_context import CallbackContext
from services import firestore


async def get_all_jokes() -> list[str]:
  """Gets all available jokes from storage.

  This function is optimized for parallel execution. It can be called in parallel with other operations.
  
  Returns:
      A list of jokes, where each joke is a string.
  """
  jokes = await firestore.get_all_jokes_async()
  return [f"{joke.setup_text} {joke.punchline_text}" for joke in jokes]


def populate_state_with_all_storage_jokes(
    callback_context: CallbackContext) -> None:
  """Populates the state with all storage jokes."""
  jokes = firestore.get_all_jokes()
  joke_strs = [f"{joke.setup_text} {joke.punchline_text}" for joke in jokes]
  callback_context.state[constants.STATE_ALL_STORAGE_JOKES] = joke_strs
