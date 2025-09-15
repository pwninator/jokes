"""Agent tools for working with joke categories."""

from agents import constants
from common import models
from google.adk.agents.callback_context import CallbackContext
from services import firestore


def populate_state_with_all_joke_categories(
    callback_context: CallbackContext) -> None:
  """Populates the state with all joke categories (sync wrapper)."""
  cats = firestore.get_all_joke_categories()
  callback_context.state[constants.STATE_JOKE_CATEGORIES] = [
    c.to_dict() for c in cats
  ]


async def save_joke_categories(categories: list[dict[str, str]]) -> None:
  """Saves joke categories to storage by upserting them."""
  to_upsert = [
    models.JokeCategory(
      display_name=c.get('display_name', ''),
      joke_description_query=c.get('joke_description_query', ''),
    ) for c in (categories or [])
  ]
  await firestore.upsert_joke_categories(to_upsert)
