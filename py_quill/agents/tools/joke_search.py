"""Agent tool for searching for jokes in the Firestore database."""

from __future__ import annotations

import asyncio

from common import config
from services import firestore, search


async def search_for_jokes(joke_description_query: str) -> list[str]:
  """Searches for jokes using a given query.

  This function is optimized for parallel execution. Call multiple times for different queries.

  The joke description query should be a single short natural language query that describes the jokes to search for, such as "jokes about dogs" or "jokes about Halloween".
  
  Search operators like "AND", "OR", "NOT", etc. are not supported.

  Args:
      joke_description_query: String that describes the jokes to search for.

  Returns:
      A list of jokes, where each joke is a string.
  """
  joke_description_query = joke_description_query.strip()
  if not joke_description_query:
    return []

  if "jokes" not in joke_description_query.lower():
    joke_description_query = f"jokes about {joke_description_query}"

  search_results = await asyncio.to_thread(
    search.search_jokes,
    query=joke_description_query,
    limit=15,
    distance_threshold=config.JOKE_SEARCH_TIGHT_THRESHOLD,
    label="joke_search_tool",
    field_filters=[],
  )
  joke_ids = [result.joke.key for result in search_results if result.joke.key]
  jokes = await asyncio.to_thread(firestore.get_punny_jokes, joke_ids)
  return [f"{joke.setup_text} {joke.punchline_text}" for joke in jokes]


async def get_num_search_results(joke_description_query: str) -> int:
  """Gets the number of search results for a given query.

  This function is optimized for parallel execution. Call multiple times for different queries.

  The joke description query should be a single short natural language query that describes the jokes to search for, such as "jokes about dogs" or "jokes about Halloween".
  
  Search operators like "AND", "OR", "NOT", etc. are not supported.
  
  Args:
      joke_description_query: String that describes the jokes to search for.

  Returns:
      The number of jokes that match the given description query.
  """
  search_results = await search_for_jokes(joke_description_query)
  return len(search_results)
