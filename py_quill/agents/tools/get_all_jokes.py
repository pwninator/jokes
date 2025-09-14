"""Agent tool for getting all jokes from the firestore database."""

from services import firestore


async def get_all_jokes() -> list[str]:
  """Gets all available jokes from storage.

  This function is optimized for parallel execution. It can be called in parallel with other operations.
  
  Returns:
      A list of jokes, where each joke is a string.
  """
  jokes = await firestore.get_all_jokes_async()
  return [f"{joke.setup_text} {joke.punchline_text}" for joke in jokes]
