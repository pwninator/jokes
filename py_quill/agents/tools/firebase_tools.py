"""Agent tool that need access to firebase."""

from __future__ import annotations

import asyncio
import datetime
import zoneinfo

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
    out = []
    for c in cats:
      d = {"display_name": c.display_name}
      if getattr(c, "image_description", None):
        d["image_description"] = c.image_description
      out.append(d)
    callback_context.state[constants.STATE_ALL_STORAGE_JOKE_CATEGORIES] = out
  else:
    callback_context.state[constants.STATE_ALL_STORAGE_JOKE_CATEGORIES] = []


async def save_joke_categories(categories: list[dict[str, str]]) -> None:
  """Saves joke categories to storage by upserting them.

  This function only inserts new categories or updates existing ones. It does not delete categories.

  Args:
      categories: List of dictionaries where each dict contains:
        - display_name: string name of the category that will be displayed in the UI to users.
        - image_description: optional string description of the category that will be used to generate an image for the category. Only needed for new categories.
  """
  if not categories:
    return

  to_upsert: list[models.JokeCategory] = []
  for item in categories:
    if not isinstance(item, dict):
      continue
    display_name = (item.get("display_name") or "").strip()
    # Same as display name
    joke_description_query = display_name
    image_description = item.get("image_description")
    if image_description:
      image_description = image_description.strip()
    if not display_name or not joke_description_query:
      continue
    to_upsert.append(
      models.JokeCategory(
        display_name=display_name,
        joke_description_query=joke_description_query,
        image_description=image_description,
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

  now_la = datetime.datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
  search_results = await asyncio.to_thread(
    search.search_jokes,
    query=joke_description_query,
    limit=15,
    distance_threshold=config.JOKE_SEARCH_TIGHT_THRESHOLD,
    label="joke_search_tool",
    field_filters=[('public_timestamp', '<=', now_la)],
  )
  joke_ids = [result.joke_id for result in search_results if result.joke_id]
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


_EDITABLE_JOKE_FIELDS = [
  "pun_theme",
  "phrase_topic",
  "tags",
  "for_kids",
  "for_adults",
  "seasonal",
  "pun_word",
  "punned_word",
  "setup_image_description",
  "punchline_image_description",
]


async def update_joke(
  joke_id: str,
  update_data: dict[str, any],
) -> None:
  """Updates a joke in Firestore. Only the fields provided in the update_data dictionary will be updated.
  Any fields not included in the dictionary will be left unchanged in Firestore.

  Args:
      joke_id: The ID of the joke to update.
      update_data: A dictionary of fields to update. Any keys that are not in the list of
        editable fields will be ignored. Fields with a value of `None` will also be ignored.
        The possible keys are:
        - pun_theme: The new pun theme for the joke.
        - phrase_topic: The new phrase topic for the joke.
        - tags: The new tags for the joke.
        - for_kids: Whether the joke is for kids.
        - for_adults: Whether the joke is for adults.
        - seasonal: The new seasonal theme for the joke.
        - pun_word: The new pun word for the joke.
        - punned_word: The new punned word for the joke.
        - setup_image_description: The new setup image description.
        - punchline_image_description: The new punchline image description.
  """
  if not joke_id:
    raise ValueError("joke_id is required")

  if not update_data:
    raise ValueError("update_data must not be empty")

  filtered_update_data = {
    k: v
    for k, v in update_data.items()
    if k in _EDITABLE_JOKE_FIELDS and v is not None
  }

  if not filtered_update_data:
    raise ValueError(
      "update_data must contain at least one valid and non-None field")

  await asyncio.to_thread(firestore.update_punny_joke, joke_id,
                          filtered_update_data)


async def get_joke_details(joke_id: str) -> dict[str, any]:
  """Gets the details of a joke from Firestore.

  This function returns a dictionary containing a subset of the joke's fields.
  It includes the joke's ID, its setup and punchline text, and all fields
  that are editable via the `update_joke` function.

  If a field is not set on the joke object in Firestore (e.g., it has no value),
  it will still be included in the returned dictionary with its default value
  (e.g., `None` for strings, `False` for booleans, or an empty list for tags).

  Args:
      joke_id: The ID of the joke to fetch.

  Returns:
      A dictionary containing the joke's details, or an empty dictionary if the joke is not found.
      The dictionary will contain the following keys:
        - joke_id: The ID of the joke.
        - setup_text: The setup text of the joke.
        - punchline_text: The punchline text of the joke.
        - and all of the editable fields.
  """
  if not joke_id:
    return {}

  joke = await asyncio.to_thread(firestore.get_punny_joke, joke_id)

  if not joke:
    return {}

  details = {
    "joke_id": joke.key,
    "setup_text": joke.setup_text,
    "punchline_text": joke.punchline_text,
  }

  for field in _EDITABLE_JOKE_FIELDS:
    if hasattr(joke, field):
      details[field] = getattr(joke, field)

  return details
