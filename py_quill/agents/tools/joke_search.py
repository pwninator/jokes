from __future__ import annotations
import asyncio
from typing import List
from common import models
from services import firestore, search


async def search_for_jokes(query: str) -> List[str]:
  """
    Searches for jokes in the Firestore database.

    Args:
        query (str): The query to search for.

    Returns:
        A list of jokes, where each joke is a string in the format "setup punchline".
    """
  search_results = await asyncio.to_thread(
    search.search_jokes,
    query=query,
    label="joke_search_tool",
    field_filters=[],
  )
  joke_ids = [result.joke.key for result in search_results if result.joke.key]
  jokes = await asyncio.to_thread(firestore.get_punny_jokes, joke_ids)
  return [f"{joke.setup_text} {joke.punchline_text}" for joke in jokes]
