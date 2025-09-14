"""Agent tool for searching for jokes in the Firestore database."""

from __future__ import annotations

import asyncio

from services import firestore, search


async def search_for_jokes(query: str) -> list[str]:
  """Searches for jokes using a given query.

  This function is optimized for parallel execution. Call multiple times for different queries.

  Args:
      query: String of the query to search for.

  Returns:
      A list of jokes, where each joke is a string.
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
