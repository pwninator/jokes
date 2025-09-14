from services import firestore


async def get_all_jokes() -> list[str]:
  """Returns all jokes from the firestore database."""
  jokes = await firestore.get_all_jokes_async()
  return [f"{joke.setup_text} {joke.punchline_text}" for joke in jokes]
