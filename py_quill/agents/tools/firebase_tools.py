"""Agent tool that need access to firebase."""

from __future__ import annotations

import asyncio

from agents import constants
from common import config, firebase_init, models
from google.adk.agents.callback_context import CallbackContext
from services import firestore, search

app = firebase_init.app


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


def populate_state_with_all_joke_categories(
    callback_context: CallbackContext) -> None:
  """Populates the state with all joke categories."""
  cats = firestore.get_all_joke_categories()
  if cats:
    callback_context.state[constants.STATE_ALL_STORAGE_JOKE_CATEGORIES] = [{
      "key":
      c.key,
      "display_name":
      c.display_name,
      "joke_description_query":
      c.joke_description_query,
    } for c in cats]
  else:
    callback_context.state[constants.STATE_ALL_STORAGE_JOKE_CATEGORIES] = []


async def save_joke_categories(categories: list[dict]) -> None:
  """Saves joke categories to storage by upserting them.

  Expects a list of dictionaries where each dict contains:
  - display_name: str
  - joke_description_query: str
  """
  if not categories:
    return

  to_upsert: list[models.JokeCategory] = []
  for item in categories:
    if not isinstance(item, dict):
      continue
    display_name = (item.get("display_name") or "").strip()
    joke_description_query = (item.get("joke_description_query") or "").strip()
    if not display_name or not joke_description_query:
      continue
    to_upsert.append(
      models.JokeCategory(
        display_name=display_name,
        joke_description_query=joke_description_query,
      ))

  if not to_upsert:
    return
  await firestore.upsert_joke_categories(to_upsert)


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
