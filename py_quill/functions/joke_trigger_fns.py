"""Firestore trigger functions for jokes and joke categories."""

from __future__ import annotations

import math

from common import (image_generation, joke_category_operations,
                    joke_operations, models)
from firebase_functions import firestore_fn, logger, options
from google.cloud.firestore_v1.vector import Vector
from services import firestore, search

MIN_VIEWS_FOR_FRACTIONS = 20


@firestore_fn.on_document_written(
  document="joke_categories/{category_id}",
  memory=options.MemoryOption.GB_1,
  timeout_sec=300,
)
def on_joke_category_write(
    event: firestore_fn.Event[firestore_fn.Change]) -> None:
  """Trigger on writes to `joke_categories` collection.

  - If the document is newly created or the `image_description` field value
    changed compared to before, generates and updates the category image.
  - If the `joke_description_query` or `seasonal_name` field changed, refreshes
    the cached joke list for the category.
  """
  # Handle deletes
  if not event.data.after:
    logger.info(f"Joke category deleted: {event.params.get('category_id')}")
    return

  category_id = event.params.get("category_id")
  if not category_id:
    logger.info("Missing category_id param; cannot process category update")
    return

  after_data = event.data.after.to_dict() or {}
  before_data = event.data.before.to_dict() if event.data.before else None

  # Handle image_description changes
  if (before_data is None or (before_data or {}).get("image_description")
      != after_data.get("image_description")):
    image_description = after_data.get("image_description")
    if not image_description:
      logger.info("image_description missing; skipping image generation")
    else:
      # Generate a category image at high quality without pun text or references
      generated_image = image_generation.generate_pun_image(
        pun_text=None,
        image_description=image_description,
        image_quality="high",
        reference_images=None,
      )

      if not generated_image or not generated_image.url:
        logger.info("Image generation returned no URL; skipping update")
      else:
        # Get the current document to check for existing all_image_urls
        doc_ref = firestore.db().collection("joke_categories").document(
          category_id)
        current_doc = doc_ref.get()

        if current_doc.exists:
          current_data = current_doc.to_dict() or {}
          all_image_urls = current_data.get("all_image_urls", [])

          # If all_image_urls doesn't exist, initialize it with the current image_url
          if not all_image_urls and current_data.get("image_url"):
            all_image_urls = [current_data["image_url"]]

          # Append the new image URL to all_image_urls
          all_image_urls.append(generated_image.url)

          # Update both fields
          doc_ref.update({
            "image_url": generated_image.url,
            "all_image_urls": all_image_urls
          })
        else:
          # Document doesn't exist, just set both fields
          doc_ref.set({
            "image_url": generated_image.url,
            "all_image_urls": [generated_image.url]
          })

  # Handle joke_description_query or seasonal_name changes
  # Normalize values by stripping whitespace to match how refresh_single_category_cache processes them
  def _normalize_field(value):
    """Normalize field value by stripping whitespace, treating None and empty string as equivalent."""
    if value is None:
      return ""
    return (value or "").strip()

  before_query = _normalize_field((
    before_data or {}).get("joke_description_query") if before_data else None)
  after_query = _normalize_field(after_data.get("joke_description_query"))

  before_seasonal = _normalize_field((
    before_data or {}).get("seasonal_name") if before_data else None)
  after_seasonal = _normalize_field(after_data.get("seasonal_name"))

  query_changed = (before_data is None or before_query != after_query)
  seasonal_changed = (before_data is None or before_seasonal != after_seasonal)

  if query_changed or seasonal_changed:
    try:
      result = joke_category_operations.refresh_single_category_cache(
        category_id, after_data)
      if result == "updated":
        logger.info(f"Refreshed category cache for {category_id}: updated")
      elif result == "emptied":
        logger.info(f"Refreshed category cache for {category_id}: emptied")
      # If result is None, category was skipped (invalid state or missing query)
    except Exception as exc:  # pylint: disable=broad-except
      logger.error(
        f"Failed refreshing category cache for {category_id}: {exc}")


@firestore_fn.on_document_written(
  document="jokes/{joke_id}",
  memory=options.MemoryOption.GB_1,
  timeout_sec=300,
)
def on_joke_write(event: firestore_fn.Event[firestore_fn.Change]) -> None:
  """A cloud function that triggers on joke document changes."""
  if not event.data.after:
    # Joke document deleted - delete corresponding search document
    joke_id = event.params.get('joke_id')
    _sync_joke_deletion_to_search_collection(joke_id)
    return

  after_data = event.data.after.to_dict() or {}
  after_joke = models.PunnyJoke.from_firestore_dict(after_data,
                                                    event.params["joke_id"])

  before_joke = None
  if event.data.before:
    before_data = event.data.before.to_dict()
    before_joke = models.PunnyJoke.from_firestore_dict(before_data,
                                                       event.params["joke_id"])

  should_update_embedding = False

  # Check if embedding needs updating
  if after_joke.state == models.JokeState.DRAFT:
    should_update_embedding = False
  elif not before_joke:
    should_update_embedding = True
    logger.info(
      f"New joke created, calculating embedding for: {after_joke.key}")
  elif (after_joke.zzz_joke_text_embedding is None
        or isinstance(after_joke.zzz_joke_text_embedding, list)):
    should_update_embedding = True
    logger.info(
      f"Joke missing embedding, calculating embedding for: {after_joke.key}")
  elif (before_joke.setup_text != after_joke.setup_text
        or before_joke.punchline_text != after_joke.punchline_text):
    should_update_embedding = True
    logger.info(
      f"Joke text changed, recalculating embedding for: {after_joke.key}")
  else:
    logger.info(
      f"Joke updated without text change, skipping embedding update for: {after_joke.key}"
    )

  if after_joke.state == models.JokeState.DRAFT:
    return

  update_data: dict[str, object] = {}
  new_embedding = None

  # Ensure recent counters exist to keep analytics in sync with Flutter app
  recent_counter_pairs = [
    ("num_viewed_users", "num_viewed_users_recent"),
    ("num_saved_users", "num_saved_users_recent"),
    ("num_shared_users", "num_shared_users_recent"),
  ]
  recent_values: dict[str, float] = {}
  for total_field, recent_field in recent_counter_pairs:
    recent_value = _coerce_counter_to_float(after_data.get(recent_field))
    needs_write = False
    if recent_value is None:
      base_value = getattr(after_joke, total_field, 0)
      recent_value = float(base_value)
      needs_write = True
    elif not isinstance(after_data.get(recent_field), float):
      needs_write = True
    if needs_write:
      update_data[recent_field] = recent_value
    after_data[recent_field] = recent_value
    recent_values[recent_field] = recent_value

  if should_update_embedding:
    embedding, metadata = _get_joke_embedding(after_joke)
    new_embedding = embedding

    current_metadata = after_joke.generation_metadata
    if isinstance(current_metadata, dict):
      current_metadata = models.GenerationMetadata.from_dict(current_metadata)
    elif not current_metadata:
      current_metadata = models.GenerationMetadata()
    current_metadata.add_generation(metadata)

    update_data.update({
      "zzz_joke_text_embedding": embedding,
      "generation_metadata": current_metadata.as_dict,
    })

  if after_joke.num_viewed_users >= MIN_VIEWS_FOR_FRACTIONS:
    num_saved_users_fraction = (after_joke.num_saved_users /
                                after_joke.num_viewed_users)
    if not math.isclose(after_joke.num_saved_users_fraction,
                        num_saved_users_fraction,
                        rel_tol=1e-9,
                        abs_tol=1e-12):
      logger.info(
        f"Joke num_saved_users_fraction mismatch, updating from {after_joke.num_saved_users_fraction} to {num_saved_users_fraction} for: {after_joke.key}"
      )
      update_data["num_saved_users_fraction"] = num_saved_users_fraction
      after_joke.num_saved_users_fraction = num_saved_users_fraction

    num_shared_users_fraction = (after_joke.num_shared_users /
                                 after_joke.num_viewed_users)
    if not math.isclose(after_joke.num_shared_users_fraction,
                        num_shared_users_fraction,
                        rel_tol=1e-9,
                        abs_tol=1e-12):
      logger.info(
        f"Joke num_shared_users_fraction mismatch, updating from {after_joke.num_shared_users_fraction} to {num_shared_users_fraction} for: {after_joke.key}"
      )
      update_data["num_shared_users_fraction"] = num_shared_users_fraction
      after_joke.num_shared_users_fraction = num_shared_users_fraction

  popularity_score = 0.0
  if after_joke.num_viewed_users > 0:
    num_saves_and_shares = (after_joke.num_saved_users +
                            after_joke.num_shared_users)
    popularity_score = (num_saves_and_shares * num_saves_and_shares /
                        after_joke.num_viewed_users)
  if not math.isclose(
      after_joke.popularity_score, popularity_score, rel_tol=1e-9,
      abs_tol=1e-12):
    logger.info(
      f"Joke popularity_score mismatch, updating from {after_joke.popularity_score} to {popularity_score} for: {after_joke.key}"
    )
    update_data["popularity_score"] = popularity_score
    after_joke.popularity_score = popularity_score

  # Calculate recent popularity score using decayed counters.
  recent_viewed = recent_values["num_viewed_users_recent"]
  recent_saved = recent_values["num_saved_users_recent"]
  recent_shared = recent_values["num_shared_users_recent"]
  popularity_score_recent = 0.0
  if recent_viewed > 0:
    recent_total = recent_saved + recent_shared
    popularity_score_recent = recent_total * recent_total / recent_viewed

  existing_recent_score = _coerce_counter_to_float(
    after_data.get("popularity_score_recent"))
  if (existing_recent_score is None
      or not math.isclose(existing_recent_score,
                          popularity_score_recent,
                          rel_tol=1e-9,
                          abs_tol=1e-12)):
    update_data["popularity_score_recent"] = popularity_score_recent
    after_data["popularity_score_recent"] = popularity_score_recent

  tags_lowered = [t.lower() for t in after_joke.tags]
  if tags_lowered != after_joke.tags:
    update_data["tags"] = tags_lowered
    logger.info(
      f"Joke tags changed, updating from {after_joke.tags} to {tags_lowered} for: {after_joke.key}"
    )

  joke_operations.sync_joke_to_search_collection(
    joke=after_joke,
    new_embedding=new_embedding,
  )

  if update_data and after_joke.key:
    firestore.update_punny_joke(after_joke.key, update_data)

    if should_update_embedding:
      logger.info(f"Successfully updated embedding for joke: {after_joke.key}")


def _coerce_counter_to_float(value: object) -> float | None:
  """Best-effort conversion of Firestore counter values to floats."""
  if value is None:
    return None
  if isinstance(value, bool):
    return float(int(value))
  if isinstance(value, (int, float)):
    return float(value)
  try:
    return float(value)
  except (TypeError, ValueError):
    logger.warn(
      f"Unable to coerce counter value {value} (type {type(value)}) to float")
    return None


def _get_joke_embedding(
    joke: models.PunnyJoke) -> tuple[Vector, models.GenerationMetadata]:
  """Get an embedding for a joke."""
  return search.get_embedding(
    text=f"{joke.setup_text} {joke.punchline_text}",
    task_type=search.TaskType.RETRIEVAL_DOCUMENT,
  )


def _sync_joke_deletion_to_search_collection(joke_id: str) -> None:
  """Deletes the corresponding search document when a joke is deleted."""
  if not joke_id:
    logger.info("Joke document deleted but joke_id not provided")
    return

  search_doc_ref = firestore.db().collection("joke_search").document(joke_id)
  search_doc = search_doc_ref.get()
  if search_doc.exists:
    search_doc_ref.delete()
    logger.info(f"Joke document deleted: {joke_id}, deleted search document")
  else:
    logger.info(f"Joke document deleted: {joke_id}, search document not found")
