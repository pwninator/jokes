"""Agent tools for working with joke categories."""

from agents import constants
from common import models
from google.adk.agents.callback_context import CallbackContext
from services import firestore


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
