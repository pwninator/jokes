"""Book cloud functions."""

import enum
import json
import random
import time
import traceback
from datetime import datetime
from typing import Any, Callable, Collection, Iterator, List

from common import config, models, utils
from firebase_functions import firestore_fn, https_fn, logger, options
from functions.prompts import (illustration_descriptions, joke_prompts,
                               reference_material, story)
from google.cloud.firestore import (DELETE_FIELD, SERVER_TIMESTAMP,
                                    CollectionReference, DocumentSnapshot)
from services import audio_voices, firestore, gen_audio, leonardo, wikipedia
from services.llm_client import LlmModel

_NONE = ()

_BASIC_TEXT_MODELS = (
  LlmModel.GEMINI_2_5_FLASH,
  # LlmModel.CLAUDE_3_5_HAIKU,
)
_ADVANCED_TEXT_MODELS = (
  # LlmModel.GEMINI_2_5_PRO,
  LlmModel.CLAUDE_3_7_SONNET, )

_BASIC_VOICE_MODELS = (audio_voices.Voice.EN_US_STANDARD_FEMALE_1, )
# Enhanced voices are now the same as basic, so no point in using them
# _ENHANCED_VOICE_MODELS = (
#     audio_voices.Voice.EN_US_NEURAL2_FEMALE_1,
# )
_ADVANCED_VOICE_MODELS = (audio_voices.Voice.EN_US_CHIRP3_HD_FEMALE_LEDA, )

_NUM_RECENT_STORIES = 50


class StoryMode(enum.Enum):
  """Available story modes with their corresponding model sets."""

  def __init__(
    self,
    text_models: list[LlmModel],
    voice_models: list[audio_voices.Voice],
  ):
    self._text_models = text_models
    self._voice_models = voice_models

  @property
  def text_models(self) -> list[LlmModel]:
    """Get the text models for this story mode."""
    return self._text_models

  @property
  def voice_models(self) -> list[audio_voices.Voice]:
    """Get the voice models for this story mode."""
    return self._voice_models

  DAILY_TALE = (
    _BASIC_TEXT_MODELS,
    _NONE,
  )
  STANDARD = (
    _BASIC_TEXT_MODELS,
    _BASIC_VOICE_MODELS,
  )
  PREMIUM = (
    _ADVANCED_TEXT_MODELS,
    _ADVANCED_VOICE_MODELS,
  )


class Error(Exception):
  """Base class for all exceptions in this module."""


class BookGenerationError(Error):
  """Exception raised for book generation errors.

  Attributes:
      message -- explanation of the error
      is_critical -- whether this is a critical error
  """

  def __init__(self, message: str, is_critical: bool = True):
    self.message = message
    self.is_critical = is_critical
    super().__init__(self.message)


def _critical_error(book_ref: firestore_fn.DocumentReference,
                    error_msg: str) -> BookGenerationError:
  """Add a critical error to the book document and update status.

  Args:
      book_ref: Reference to the book document
      error_msg: Error message to add
  """
  # Get the current book data to retrieve existing critical errors
  book_doc = book_ref.get()
  book_data = book_doc.to_dict() or {}

  # Get the existing critical errors or initialize an empty list
  critical_errors = book_data.get('critical_errors', [])
  critical_errors.append(error_msg)

  book_ref.update({
    'critical_errors': critical_errors,
    'status': 'error',
    'last_modification_time': SERVER_TIMESTAMP,
  })
  _record_timing_event(book_data, book_ref, 'Critical Error',
                       {'error': error_msg})
  return BookGenerationError(error_msg)


def _add_minor_error(book_ref: firestore_fn.DocumentReference,
                     error_msg: str) -> None:
  """Add a minor error to the book document but continue processing.

  Args:
      book_ref: Reference to the book document
      error_msg: Error message to add
  """
  # Get the current book data to retrieve existing minor errors
  book_doc = book_ref.get()
  book_data = book_doc.to_dict() or {}

  # Get the existing minor errors or initialize an empty list
  minor_errors = book_data.get('minor_errors', [])
  minor_errors.append(error_msg)

  book_ref.update({'minor_errors': minor_errors})
  _record_timing_event(book_data, book_ref, 'Minor Error',
                       {'error': error_msg})


@firestore_fn.on_document_created(
  document="books/{bookId}",
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def on_book_created(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None]) -> None:
  """Triggers when a new book document is created."""

  book_snapshot = event.data
  if not book_snapshot:
    logger.warn("No data in event")
    return

  user_id = book_snapshot.get('owner_user_id')
  book_id = book_snapshot.id

  try:
    # Check if book is already populated
    book_data = book_snapshot.to_dict()
    if book_data and book_data.get('title'):
      # Check if chapters exist
      chapters = list(
        book_snapshot.reference.collection('chapters').limit(1).stream())
      if chapters:
        log_info(
          f"Book {book_snapshot.id} already populated with title and chapters. "
          "Skipping generation.",
          book_id=book_id,
          user_id=user_id)
        return models.GenerationMetadata()

    # Try up to 3 times to generate the book
    max_attempts = 3
    attempt = 1

    while attempt <= max_attempts:
      log_info(
        f"Attempt {attempt}/{max_attempts} to generate book {book_snapshot.id}",
        book_id=book_id,
        user_id=user_id)
      book_ref = book_snapshot.reference
      try:
        return _populate_book(book_snapshot, delete_existing_pages=True)

      except BookGenerationError as e:
        log_warning(
          f"Book generation attempt {attempt} failed with error: {e.message}",
          book_id=book_snapshot.id,
          user_id=book_snapshot.get('owner_user_id'))
        attempt += 1

        # If we've exhausted all attempts, rethrow the error
        if attempt > max_attempts:
          log_error(
            f"All {max_attempts} attempts to generate book {book_snapshot.id} failed",
            book_id=book_id,
            user_id=user_id)
          book_ref.update({
            'status': 'error',
            'final_error':
            f"Failed after {max_attempts} attempts: {e.message}",
            'last_modification_time': SERVER_TIMESTAMP,
          })
          raise

  except Exception as e:
    log_error(f"Error generating book: {e}", book_id=book_id, user_id=user_id)

    if book_snapshot:
      book_snapshot.reference.update({
        "error":
        str(e),
        "status":
        "error",
        "last_modification_time":
        SERVER_TIMESTAMP,
      })

    raise


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=600,
)
def populate_book(req: https_fn.Request) -> https_fn.Response:
  """HTTP function to manually populate a book with generated content.

  Args:
      req: The HTTP request. Must contain 'book_id' parameter.

  Returns:
      HTTP response with generation metadata
  """
  # Skip processing for health check requests
  if req.path == "/__/health":
    return https_fn.Response("OK", status=200)

  book_id = req.args.get('book_id')
  if not book_id:
    return https_fn.Response(json.dumps({"error":
                                         "Missing book_id parameter"}),
                             status=400,
                             mimetype='application/json')

  # Get the book document
  book_ref = firestore.db().collection('books').document(book_id)
  book_doc = book_ref.get()
  if not book_doc.exists:
    return https_fn.Response(json.dumps({"error":
                                         f"Book {book_id} not found"}),
                             status=404,
                             mimetype='application/json')

  # Populate the book
  generation_metadata = _populate_book(book_doc, delete_existing_pages=True)

  return https_fn.Response(json.dumps({
    "success":
    True,
    "generation_metadata":
    generation_metadata.as_dict
  }),
                           mimetype='application/json')


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=120,
)
def populate_page(req: https_fn.Request) -> https_fn.Response:
  """HTTP function to manually populate a page with a generated illustration.

  Args:
      req: The HTTP request. Must contain 'book_id', 'chapter_id', and 'page_id' parameters.

  Returns:
      HTTP response with generation metadata
  """
  # Skip processing for health check requests
  if req.path == "/__/health":
    return https_fn.Response("OK", status=200)

  book_id = req.args.get('book_id')
  chapter_id = req.args.get('chapter_id')
  page_id = req.args.get('page_id')

  if not all([book_id, chapter_id, page_id]):
    return https_fn.Response(json.dumps({
      "error":
      "Missing required parameters. Need book_id, chapter_id, and page_id"
    }),
                             status=400,
                             mimetype='application/json')

  # Get the page document
  page_ref = firestore.db().collection('books').document(book_id).collection(
    'chapters').document(chapter_id).collection('pages').document(page_id)
  page_doc = page_ref.get()
  if not page_doc.exists:
    return https_fn.Response(json.dumps({"error":
                                         f"Page {page_id} not found"}),
                             status=404,
                             mimetype='application/json')

  # Populate the page with illustration
  try:
    generation_metadata = _populate_page(page_doc)
    return https_fn.Response(json.dumps({
      "success":
      True,
      "generation_metadata":
      generation_metadata.as_dict
    }),
                             mimetype='application/json')
  except Exception as e:  # pylint: disable=broad-exception-caught
    return https_fn.Response(json.dumps({"error": str(e)}),
                             status=500,
                             mimetype='application/json')


@firestore_fn.on_document_created(
  document="books/{bookId}/chapters/{chapterId}/pages/{pageId}",
  memory=options.MemoryOption.GB_1,
  timeout_sec=120,
)
def on_page_created(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None]) -> None:
  """Triggers when a new page document is created.

  This function generates an illustration for the page using the pre-generated description.
  """
  page_snapshot = event.data
  if not page_snapshot:
    log_warning("No snapshot in on_page_created event",
                book_id=None,
                user_id=None)
    return

  page_key = page_snapshot.id
  # Get the book ID from the page reference path
  page_ref = page_snapshot.reference
  path_parts = page_ref.path.split('/')
  book_id = path_parts[1] if len(path_parts) > 1 else None

  page_data = page_snapshot.to_dict()
  if not page_data:
    log_warning(
      f"No page data in on_page_created event for page {page_key}",
      book_id=book_id,
      user_id=None,
    )
    return

  try:
    # Skip if image already generated
    if image_key := page_data.get('image_key'):
      log_info(f"Page {page_key} already has image key: {image_key}",
               book_id=book_id,
               user_id=None)
      return models.GenerationMetadata()

    _populate_page(page_snapshot)

  except Exception as e:
    log_error(f"Error populating page: {e}", book_id=book_id, user_id=None)
    if event.data:
      event.data.reference.update({
        "error": str(e),
        "status": "error",
      })
    raise


def _start_page_image_generation(
  book_data: dict[str, Any],
  book_ref: firestore_fn.DocumentReference,
  page_number: int | str,
  illustration_data: models.StoryIllustrationData,
  character_descriptions: dict[str, models.StoryCharacterData],
) -> tuple[str | None, Callable[[dict[str, bytes] | None], models.Image]
           | None]:
  """Kicks off asynchronous image generation for a page.

  Returns:
      Tuple of (image_key, image_callback)
  """
  page_image_key = None
  page_image_callback = None

  if not illustration_data.description:
    log_error(
      f"Skipping image generation for page {page_number} due to missing description.",
      book_id=book_ref.id,
      user_id=book_data.get('owner_user_id'))
    return None, None

  owner_user_id = book_data.get('owner_user_id')
  if not owner_user_id:
    raise ValueError(
      f"No owner user ID for page {page_number} in book {book_ref.id}")

  try:
    image_prompt, image_backup_prompt = _get_illustration_prompt(
      illustration_data, character_descriptions, book_ref.id, owner_user_id)

    page_image, page_image_callback = leonardo.generate_image(
      "Page illustration",
      user_uid=owner_user_id,
      prompt_chunks=image_prompt,
      fallback_prompt_chunks=image_backup_prompt,
      refine_prompt=False,
      num_images=config.NUM_PAGE_IMAGE_ATTEMPTS,
      extra_log_data=_get_extra_log_data(book_ref.id, owner_user_id),
    )
    page_image_key = page_image.key

    _record_timing_event(book_data, book_ref,
                         f"Page {page_number} - Image Kickoff")

  except Exception as e:
    _add_minor_error(
      book_ref,
      f"Failed to start image gen for page {page_number}: {e}\n{traceback.format_exc()}"
    )
    page_image_callback = None
    page_image_key = None

  return page_image_key, page_image_callback


def _generate_page_audio(
  book_data: dict[str, Any],
  book_ref: firestore_fn.DocumentReference,
  page_doc_snapshot: DocumentSnapshot,
) -> tuple[str | None, models.GenerationMetadata]:
  """Generates audio for the page text.

  Args:
      book_data: The book data
      book_ref: The book document reference
      page_doc_snapshot: The page document snapshot

  Returns:
      Tuple of (audio_gcs_uri, audio_metadata)
  """
  audio_metadata = models.GenerationMetadata()
  audio_gcs_uri = None

  page_data = page_doc_snapshot.to_dict()
  if not page_data:
    _add_minor_error(
      book_ref,
      f"Cannot generate audio for page {page_doc_snapshot.id}: No page data found."
    )
    return None, audio_metadata

  if not book_data:
    _add_minor_error(
      book_ref, f"Cannot generate audio for page {page_doc_snapshot.id}: "
      f"No book data found for book {book_ref.id}.")
    return None, audio_metadata

  audio_voice = None
  audio_voice_str = book_data.get('audio_voice')
  if audio_voice_str:
    try:
      audio_voice = audio_voices.Voice[audio_voice_str]
    except KeyError:
      _add_minor_error(book_ref,
                       f"Invalid audio_voice value: {audio_voice_str}.")

  if not audio_voice:
    return None, audio_metadata

  page_key = page_doc_snapshot.id
  chapter_id = page_doc_snapshot.reference.parent.id
  book_id = book_ref.id
  page_number = page_data.get("page_number", "?")

  page_text = page_data.get('text')
  if not page_text:
    _add_minor_error(
      book_ref,
      f"Cannot generate audio for page {page_number}: No text found.")
    return None, audio_metadata

  try:
    audio_label = "Page Audio"
    audio_filename_base = f"{book_id}/{chapter_id}/{page_key}"

    generated_uri, single_audio_meta = gen_audio.text_to_speech(
      text=page_text,
      output_filename_base=audio_filename_base,
      label=audio_label,
      voice=audio_voice,
      extra_log_data=_get_extra_log_data(book_ref.id, book_data=book_data),
    )

    audio_gcs_uri = generated_uri
    audio_metadata.add_generation(single_audio_meta)
    _record_timing_event(book_data, book_ref,
                         f"Page {page_number} - Audio Generated")

  except gen_audio.GenAudioError as e:
    _add_minor_error(book_ref,
                     f"Failed to generate audio for page {page_number}: {e}")
  except Exception as e:  # Catch any other unexpected audio errors
    _add_minor_error(
      book_ref,
      f"Unexpected error generating audio for page {page_number}: {e}\n{traceback.format_exc()}"
    )

  return audio_gcs_uri, audio_metadata


def _finish_page_image_generation(
  book_data: dict[str, Any],
  book_ref: firestore_fn.DocumentReference,
  page_number: int | str,
  page_image_callback: Callable[[dict[str, bytes] | None], models.Image],
  page_doc_snapshot: DocumentSnapshot,
) -> models.GenerationMetadata:
  """Waits for image generation to complete and processes the result.

  Returns:
      Image processing metadata.
  """
  processing_metadata = models.GenerationMetadata()
  try:
    reference_images = _get_reference_images(book_ref)
    _record_timing_event(book_data, book_ref,
                         f"Page {page_number} - Image Processing Start")
    final_page_image = page_image_callback(reference_images)
    processing_metadata.add_generation(final_page_image.generation_metadata)
    _record_timing_event(book_data, book_ref,
                         f"Page {page_number} - Image Processed")

  except Exception as e:
    _add_minor_error(
      book_ref,
      f"Failed to process image for page {page_number}: {e}\n{traceback.format_exc()}"
    )
    page_doc_snapshot.reference.update({'image_key': DELETE_FIELD})

  return processing_metadata


def _populate_page(
    page_doc_snapshot: DocumentSnapshot) -> models.GenerationMetadata:
  """Populates a page with generated illustration and optionally audio.
  Refactored version using helper functions.
  """
  page_data = page_doc_snapshot.to_dict()
  if not page_data:
    raise ValueError("No page data")

  page_key = page_data.get("key") or page_doc_snapshot.id

  # Navigation: page -> pages collection -> chapter document -> chapters collection -> book document
  # Get the pages collection
  pages_collection = page_doc_snapshot.reference.parent
  # Get the chapter document
  chapter_ref = pages_collection.parent
  # Get the chapters collection
  chapters_collection = chapter_ref.parent
  # Get the book document
  book_ref = chapters_collection.parent

  book_doc = book_ref.get()
  if not book_doc.exists:
    # Debug info to help diagnose
    path_parts = page_doc_snapshot.reference.path.split('/')
    error_details = {
      'page_path': page_doc_snapshot.reference.path,
      'book_ref_path': book_ref.path,
      'path_parts': path_parts
    }
    logger.error(f"Book document lookup failed. Details: {error_details}")
    raise ValueError(
      f"Book not found for page {page_key}. Path: {page_doc_snapshot.reference.path}"
    )

  book_id = book_ref.id

  book_data = book_doc.to_dict()
  if not book_data:
    raise ValueError(f"No book data for page {page_key} in book {book_id}")

  page_number = page_data.get("page_number", "?")
  _record_timing_event(book_data, book_ref,
                       f"Page {page_number} - Populate Start")

  illustration_dict = page_data.get('illustration', {})
  illustration_data = models.StoryIllustrationData.from_dict(illustration_dict)

  character_descriptions = {}
  if book_data.get('characters'):
    for name, char_dict in book_data.get('characters', {}).items():
      character_descriptions[name] = models.StoryCharacterData.from_dict(
        char_dict)

  total_generation_metadata = models.GenerationMetadata()

  # 1. Start Image Generation (Async)
  page_image_key, page_image_callback = _start_page_image_generation(
    book_data, book_ref, page_number, illustration_data,
    character_descriptions)

  # Update Firestore immediately if image generation started
  if page_image_key:
    page_doc_snapshot.reference.update({
      'image_key':
      page_image_key,
      'status':
      'generating_image',
      'last_modification_time':
      SERVER_TIMESTAMP,
    })

  # 2. Generate Audio (Blocking)
  audio_gcs_uri, audio_meta = _generate_page_audio(book_data, book_ref,
                                                   page_doc_snapshot)
  total_generation_metadata.add_generation(audio_meta)

  # Update Firestore immediately if audio was generated
  if audio_gcs_uri:
    page_doc_snapshot.reference.update({
      'audio_gcs_uri':
      audio_gcs_uri,
      'generation_metadata':
      total_generation_metadata.as_dict,
      'last_modification_time':
      SERVER_TIMESTAMP,
    })

  # 3. Finish Image Generation (Blocking)
  if page_image_callback:
    image_finish_meta = _finish_page_image_generation(book_data, book_ref,
                                                      page_number,
                                                      page_image_callback,
                                                      page_doc_snapshot)
    total_generation_metadata.add_generation(image_finish_meta)

  # Final Update for accumulated metadata
  page_doc_snapshot.reference.update({
    'generation_metadata':
    total_generation_metadata.as_dict,
    'status':
    'complete',
    'last_modification_time':
    SERVER_TIMESTAMP,
  })

  _record_timing_event(book_data, book_ref, f"Page {page_number} - Done")
  return total_generation_metadata


# pylint: disable=fixme
def _populate_book(doc_snapshot: DocumentSnapshot,
                   delete_existing_pages: bool) -> models.GenerationMetadata:
  """Populates a book with generated content.

  Args:
      doc_snapshot: The book document snapshot
      delete_existing_pages: Whether to delete existing pages before generating new ones

  Returns:
      GenerationMetadata containing token usage and timing information for book-level operations

  Raises:
      BookGenerationError: If critical errors are encountered during generation
  """

  # Record book creation event
  book_ref = doc_snapshot.reference
  book_ref.update({
    'status': 'generating',
    'last_modification_time': SERVER_TIMESTAMP,
  })
  book_data = doc_snapshot.to_dict()
  _record_timing_event(book_data, book_ref, 'Populate Book - Start')

  try:
    (
      owner_user_id,
      user_prompt,
      user_guidelines,
      main_character_keys,
      side_character_keys,
      llm_model,
      reading_level,
    ) = _get_and_validate_book_params(book_data, doc_snapshot)

    # Validate required fields
    if not all([main_character_keys, user_prompt, owner_user_id]):
      raise _critical_error(book_ref, "Missing required fields")

    # Check existing pages
    chapters = book_ref.collection('chapters').stream()
    for chapter in chapters:
      # Delete all pages in the chapter
      pages_collection = chapter.reference.collection('pages')

      # Clear existing pages
      if delete_existing_pages:
        for page in pages_collection.stream():
          page.reference.delete()
        # Delete the chapter itself
        chapter.reference.delete()
      else:
        # If the book already has pages, just return
        if list(pages_collection.limit(1).stream()):
          logger.info(
            f"Book {book_ref.id} already has pages. Skipping generation.")
          return models.GenerationMetadata()

    # Get characters
    main_characters, side_characters = _get_characters(main_character_keys,
                                                       side_character_keys)

    if not main_characters:
      raise _critical_error(book_ref, "No main characters found")

    # Track book-level generation costs
    generation_metadata = models.GenerationMetadata()

    # Get user's recent stories
    try:
      recent_stories = firestore.get_recent_stories(owner_user_id,
                                                    limit=_NUM_RECENT_STORIES)
      recent_story_titles = [
        f"{story['title']}: {story.get('summary')}" for story in recent_stories
      ]
    except Exception as e:  # pylint: disable=broad-exception-caught
      _add_minor_error(book_ref, f"Failed to get recent stories: {str(e)}")
      recent_stories = []
      recent_story_titles = []

    # Get jokes to entertain the user while they wait for the book to generate
    _record_timing_event(book_data, book_ref, 'Jokes - Start')
    try:
      # Join together the user prompt and all character descriptions for the joke prompt
      joke_prompt = user_prompt
      for character in main_characters + side_characters:
        joke_prompt += f"\n{character.sanitized_description}"
      joke_generator = joke_prompts.generate_jokes(
        joke_prompt,
        extra_log_data=_get_extra_log_data(book_ref.id, owner_user_id))
      jokes_metadata = get_and_store_jokes(book_data,
                                           book_ref,
                                           joke_generator,
                                           num_jokes=1)
      generation_metadata.add_generation(jokes_metadata)
    except Exception as e:  # pylint: disable=broad-exception-caught
      _add_minor_error(book_ref, f"Failed to generate initial jokes: {str(e)}")

    # Get educational reference material
    try:
      plot = book_data.get('plot')
      learning_topic = book_data.get('learning_topic')
      wiki_url = book_data.get('learning_source_url')
      learning_concepts = book_data.get('learning_concepts')
      if not (plot and learning_topic and learning_concepts and wiki_url):
        (
          plot,
          learning_topic,
          wiki_url,
          reference_material_full_text,
          plot_response_dict,
          ref_metadata,
        ) = _get_reference_material(
          book_data,
          book_ref,
          user_prompt,
          main_characters + side_characters,
          reading_level,
          recent_stories,
        )
        generation_metadata.add_generation(ref_metadata)
        _add_debug_data(book_ref, 'plot_response_dict', plot_response_dict)
        _record_timing_event(book_data, book_ref,
                             'Choose/Fetch Reference Material')
      else:
        reference_material_full_text = wikipedia.get_text(learning_topic)
        _record_timing_event(book_data, book_ref, 'Fetch Wikipedia')
    except Exception as e:  # pylint: disable=broad-exception-caught
      raise _critical_error(
        book_ref, f"Failed to get reference material: {str(e)}") from e

    # Start story generation
    try:
      story_generator = story.generate_story(
        plot=plot,
        user_prompt=user_prompt,
        user_guidelines=user_guidelines,
        main_characters=main_characters,
        side_characters=side_characters,
        past_story_titles=recent_story_titles,
        learning_topic=learning_topic,
        reference_material_full_text=reference_material_full_text,
        llm_model=llm_model,
        reading_level=reading_level,
        extra_log_data=_get_extra_log_data(book_ref.id, owner_user_id),
      )
    except Exception as e:  # pylint: disable=broad-exception-caught
      raise _critical_error(
        book_ref, f"Failed to initialize story generation: {str(e)}") from e

    # Get the rest of the jokes
    try:
      jokes_metadata = get_and_store_jokes(book_data, book_ref, joke_generator)
      generation_metadata.add_generation(jokes_metadata)
    except Exception as e:  # pylint: disable=broad-exception-caught
      _add_minor_error(book_ref,
                       f"Failed to generate remaining jokes: {str(e)}")

    # Process the story
    cover_image_callback = None
    max_page_number_seen = 0
    story_data = models.StoryData()
    try:
      for incremental_story_data, incremental_metadata in story_generator:
        generation_metadata.add_generation(incremental_metadata)
        updated_keys = story_data.update(incremental_story_data)

        update_dict = {}

        # Finish processing cover image before continuing
        if cover_image_callback is not None:
          try:
            # Process cover image with character portraits as reference
            portrait_bytes_by_char_name = _get_reference_images(book_ref)
            cover_image = cover_image_callback(portrait_bytes_by_char_name)
            generation_metadata.add_generation(cover_image.generation_metadata)
            _record_timing_event(book_data, book_ref, 'Cover Image - Done')
          except Exception as e:
            # TODO: Add a retry mechanism for cover image generation
            _add_minor_error(book_ref,
                             f"Failed to process cover image: {str(e)}")
            update_dict['cover_image_key'] = DELETE_FIELD
          finally:
            cover_image_callback = None

        for k in updated_keys:
          match k:
            case "tone":
              _add_debug_data(book_ref, 'tone', story_data.tone)
            case 'title':
              update_dict['title'] = story_data.title
              _record_timing_event(book_data, book_ref, 'Title')
            case 'tagline':
              update_dict['tagline'] = story_data.tagline
            case 'summary':
              update_dict['summary'] = story_data.summary
            case 'plot_brainstorm':
              _add_debug_data(book_ref, 'plot_brainstorm',
                              story_data.plot_brainstorm)
            case 'outline':
              _add_debug_data(book_ref, 'outline', story_data.outline)
              _record_timing_event(book_data, book_ref, 'Outline')
            case 'pages':
              for page in incremental_story_data.pages:
                if not page.is_complete:
                  raise _critical_error(
                    book_ref,
                    f"Page {page.page_number} is not complete: {page.as_dict}")

                if page.page_number != max_page_number_seen + 1:
                  raise _critical_error(
                    book_ref, f"Expected page {max_page_number_seen + 1}, "
                    f"got page {page.page_number}: {page.as_dict}")

                try:
                  firestore.add_book_page(book_ref, page)
                except Exception as e:
                  raise _critical_error(
                    book_ref,
                    f"Failed to add page {page.page_number}: {str(e)}") from e

                max_page_number_seen = page.page_number
                _record_timing_event(book_data, book_ref,
                                     f'Page {page.page_number} - Start')

            case 'characters':
              update_dict['characters'] = {
                name: char.as_dict
                for name, char in story_data.characters.items()
              }
              _record_timing_event(book_data, book_ref, 'Characters')
            case 'learning_concepts':
              update_dict.update({
                'plot': plot,
                'learning_topic': learning_topic,
                'learning_source_url': wiki_url,
                'learning_concepts': {
                  name: concept.as_dict
                  for name, concept in story_data.learning_concepts.items()
                },
              })
              _record_timing_event(book_data, book_ref, 'Learning Concepts')
            case 'cover_illustration':
              if not (story_characters := story_data.characters):
                _add_minor_error(
                  book_ref,
                  "No character descriptions found for cover illustration")
                story_characters = {}

              try:
                # Generate detailed cover illustration description
                cover_image_prompt, cover_image_backup_prompt = _get_illustration_prompt(
                  story_data.cover_illustration, story_characters, book_ref.id,
                  owner_user_id)

                # Kick off generation for the cover image
                _record_timing_event(book_data, book_ref,
                                     'Cover Image - Start')
                cover_image, cover_image_callback = leonardo.generate_image(
                  "Cover illustration",
                  user_uid=owner_user_id,
                  prompt_chunks=cover_image_prompt,
                  fallback_prompt_chunks=cover_image_backup_prompt,
                  refine_prompt=False,
                  num_images=config.NUM_COVER_IMAGE_ATTEMPTS,
                )
                # Update book with cover image key
                update_dict['cover_image_key'] = cover_image.key
              except Exception as e:
                # TODO: Add a retry mechanism for cover image generation
                _add_minor_error(book_ref,
                                 f"Failed to generate cover image: {str(e)}")
            case _:
              _add_minor_error(book_ref, f"Unknown key in story data: {k}")

        if update_dict or incremental_metadata:
          update_dict.update({
            'generation_metadata': generation_metadata.as_dict,
            'last_modification_time': SERVER_TIMESTAMP,
          })
          book_ref.update(update_dict)
    except Exception as e:
      raise _critical_error(book_ref,
                            f"Error during story generation: {str(e)}") from e

    if story_data.is_empty:
      raise _critical_error(book_ref, "No story data generated")

    # Update the book with the final page count
    book_ref.update({
      'num_pages': max_page_number_seen,
      'generation_metadata': generation_metadata.as_dict,
      'status': 'complete',
      'last_modification_time': SERVER_TIMESTAMP,
    })

    _record_timing_event(book_data, book_ref, 'Populate Book - Done')
    return generation_metadata

  except BookGenerationError:
    # The error has already been recorded in the document by _add_critical_error
    raise
  except Exception as e:
    # Catch any unhandled exceptions and mark as critical
    error_msg = f"Unhandled exception in _populate_book: {str(e)}"
    raise _critical_error(book_ref, error_msg) from e


def _get_and_validate_book_params(
  book_data: dict[str, Any],
  doc_snapshot: DocumentSnapshot,
) -> tuple[str, str, str, list[str], list[str], LlmModel, models.ReadingLevel]:
  """Get the book parameters from the book data."""
  if not book_data:
    raise ValueError("No book data found")

  owner_user_id = book_data.get('owner_user_id')
  user_prompt = book_data.get('user_prompt')
  user_guidelines = book_data.get('user_guidelines')
  main_character_keys = book_data.get('main_character_keys', [])
  side_character_keys = book_data.get('side_character_keys', [])

  # Process story mode and models
  story_mode = book_data.get('story_mode')
  llm_model_override = book_data.get('llm_model_name')
  audio_voice_override = book_data.get('audio_voice')
  llm_model, audio_voice = _get_models_for_story_mode(story_mode,
                                                      llm_model_override,
                                                      audio_voice_override)

  # Update the book with the selected models
  voice_name = audio_voice.name if audio_voice else None
  doc_snapshot.reference.update({
    'llm_model_name': llm_model.name,
    'audio_voice': voice_name,
  })

  reading_level_value = book_data.get('reading_level',
                                      models.ReadingLevel.THIRD.value)
  reading_level = models.ReadingLevel.from_value(reading_level_value)

  return (
    owner_user_id,
    user_prompt,
    user_guidelines,
    main_character_keys,
    side_character_keys,
    llm_model,
    reading_level,
  )


def _get_characters(
  main_character_keys: list[str], side_character_keys: list[str]
) -> tuple[Collection[models.Character], Collection[models.Character]]:
  """Get the characters from the character keys."""
  all_character_keys = set(main_character_keys + side_character_keys)
  all_characters = firestore.get_characters(all_character_keys)
  characters_by_key = {char.key: char for char in all_characters}
  main_characters = [
    characters_by_key[key] for key in main_character_keys
    if key in characters_by_key
  ]
  side_characters = [
    characters_by_key[key] for key in side_character_keys
    if key in characters_by_key
  ]
  return main_characters, side_characters


def _get_reference_material(
  book_data: dict[str, Any],
  book_ref: firestore_fn.DocumentReference,
  story_prompt: str,
  characters: list[models.Character],
  reading_level: models.ReadingLevel,
  recent_stories: list[dict[str, str]],
) -> tuple[str, str, str, dict[str, Any], models.GenerationMetadata]:
  """Get relevant educational reference material for a story prompt.

  Args:
      book_data: The book data
      book_ref: The book reference
      story_prompt: The story prompt to find reference material for
      characters: List of characters to consider for topic selection
      reading_level: The reading level of the book
      recent_stories: List of recent stories with their learning topics

  Returns:
      Tuple of (
        plot,
        wikipedia_title,
        wikipedia_url,
        wikipedia_text,
        plot_response_dict,
        plot_metadata,
      )

  Raises:
      ValueError: If no relevant content could be found
  """
  # Extract past learning topics to avoid repetition
  past_topics = []
  if recent_stories:
    past_topics = [
      story.get('learning_topic', None) for story in recent_stories
    ]
    # Filter out empty topics
    past_topics = [topic for topic in past_topics if topic]

  generation_metadata = models.GenerationMetadata()
  (plot, wikipedia_title, plot_response_dict,
   plot_metadata) = reference_material.generate_plot_and_wiki_title(
     story_prompt,
     characters,
     past_topics,
     reading_level,
     extra_log_data=_get_extra_log_data(book_ref.id, book_data=book_data),
   )
  generation_metadata.add_generation(plot_metadata)

  if not plot or not wikipedia_title:
    raise ValueError("No plot or wikipedia title generated")

  try:
    results = wikipedia.search(wikipedia_title, num_results=10)
    if results:
      chosen_result, choose_metadata = reference_material.choose_best_wikipedia_result(
        results,
        wikipedia_title,
        plot,
        extra_log_data=_get_extra_log_data(book_ref.id, book_data=book_data),
      )
      generation_metadata.add_generation(choose_metadata)

      if chosen_result:
        article_text = wikipedia.get_text(chosen_result.title)
        return (
          plot,
          chosen_result.title,
          chosen_result.url,
          article_text,
          plot_response_dict,
          generation_metadata,
        )
  except Exception as e:  # pylint: disable=broad-exception-caught
    raise _critical_error(
      book_ref,
      f"Error searching Wikipedia for '{wikipedia_title}': {e}") from e

  raise ValueError("Could not find relevant Wikipedia content")


def _get_reference_images(
    book_ref: firestore_fn.DocumentReference) -> dict[str, bytes]:
  """Get reference images for image generation.

  Gets character portrait images to use as reference for consistent style.

  Args:
      book_ref: Reference to the book document

  Returns:
      Dict mapping character names to their portrait image bytes
  """
  # Get book data
  book_doc = book_ref.get()
  if not book_doc.exists:
    return {}

  book_data = book_doc.to_dict()
  if not book_data:
    return {}

  # Get character portrait images
  main_character_keys = book_data.get('main_character_keys', [])
  side_character_keys = book_data.get('side_character_keys', [])
  all_character_keys = set(main_character_keys + side_character_keys)

  all_characters = firestore.get_characters(all_character_keys)
  char_name_by_portrait_key = {
    character.portrait_image_key: character.name
    for character in all_characters if character.portrait_image_key
  }

  portrait_images = firestore.get_images(char_name_by_portrait_key.keys())
  char_name_by_portrait_url = {
    img.url: char_name_by_portrait_key[img.key]
    for img in portrait_images
  }

  # Download portrait images
  portrait_bytes_by_url = utils.download_images(
    char_name_by_portrait_url.keys())
  portrait_bytes_by_char_name = {
    char_name_by_portrait_url[url]: img_bytes
    for url, img_bytes in portrait_bytes_by_url.items()
  }

  return portrait_bytes_by_char_name


def _get_illustration_prompt(
  illustration_data: models.StoryIllustrationData,
  character_descriptions: dict[str, models.StoryCharacterData],
  book_id: str,
  user_id: str,
) -> tuple[list[str], list[str]]:
  """Get the illustration prompt for a page.

  Sometimes the prompt can get blocked by moderation filters, so we provide a simpler
  backup prompt that is less likely to be blocked. The backup prompt is preferred to be a
  character description so that the illustration is consistent with the characters
  on the other pages.

  Args:
      illustration_data: The illustration data to generate a prompt for
      character_descriptions: Map of character names to their StoryCharacterData objects
      book_id: The book ID
      user_id: The user ID

  Returns:
      Tuple of (main prompt parts, backup prompt parts)
  """
  main_prompt = [illustration_data.description]
  backup_prompt = []

  if illustration_data.characters and character_descriptions:
    # Add character descriptions for detected characters
    # for name in illustration_data.characters:
    #   if char := character_descriptions.get(name):
    #     main_prompt.append(f"{name} is: {char.visual}")
    main_prompt = [
      illustration_descriptions.refine_illustration_description(
        illustration_data.description,
        {
          name: char.visual
          for name, char in character_descriptions.items()
        },
        extra_log_data=_get_extra_log_data(book_id, user_id=user_id),
      )
    ]

    # Use the first character's description as backup
    first_char_name = illustration_data.characters[0]
    if first_char := character_descriptions.get(first_char_name):
      backup_prompt = [first_char.visual]

  return main_prompt, backup_prompt


def _add_debug_data(book_ref: firestore_fn.DocumentReference, label: str,
                    data: Any) -> None:
  """Add debug data to a document in the book's debug_data subcollection."""
  debug_doc_ref = book_ref.collection('debug_data').document("debug_data")
  debug_doc_ref.set({
    label: data,
  }, merge=True)


def _record_timing_event(
  book_data: dict[str, Any],
  book_ref: firestore_fn.DocumentReference,
  event_type: str,
  metadata: dict | None = None,
) -> None:
  """Record a timing event in the book's timing_events subcollection.

  Args:
    book_data: The book data
    book_ref: Reference to the book document
    event_type: Type of timing event (e.g. 'title_generation', 'cover_image_generation')
    metadata: Optional additional context about the event
  """
  if not book_data:
    raise ValueError(f"Book document {book_ref.id} is empty")

  creation_time = book_data.get('creation_time')
  if not creation_time:
    raise ValueError(
      f"Book document {book_ref.id} does not have a creation time")

  # Calculate duration from creation time
  duration_seconds = time.time() - creation_time.timestamp()

  # Get current timestamp and format as YYYYMMDD_HHMMSS_NNNN
  timing_event_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')

  timing_event = {
    'event_type': event_type,
    'timestamp': SERVER_TIMESTAMP,
    'duration_seconds': duration_seconds,
    'metadata': metadata or {},
  }

  if progress := _get_timing_event_progress(event_type):
    timing_event['progress'] = progress

  book_ref.collection('timing_events').document(timing_event_id).set(
    timing_event)

  extra_log_data = _get_extra_log_data(book_ref.id, book_data=book_data)
  json_fields = {
    'event_type': event_type,
    'duration_seconds': duration_seconds,
    'story_mode': book_data.get('story_mode', "UNKNOWN"),
    'llm_model_name': book_data.get('llm_model_name', "UNKNOWN"),
    'audio_voice': book_data.get('audio_voice', "UNKNOWN"),
    'reading_level': book_data.get('reading_level', "UNKNOWN"),
    **(extra_log_data or {}),
  }

  logger.info(f"Timing event: {event_type}",
              extra={"json_fields": json_fields})


_TIMING_EVENTS_WITH_PROGRESS = (
  "Populate Book - Start",
  "Jokes - Start",
  "Jokes",
  "Choose/Fetch Reference Material",
  "Learning Concepts",
  "Title",
  "Characters",
  "Cover Image - Done",
  "Outline",
  "Page 1 - Start",
  "Page 1 - Audio Generated",
  "Page 1 - Image Processing Start",
  "Page 1 - Image Processed",
  "Page 1 - Done",
  "Page 2 - Done",
  "Page 3 - Done",
  "Page 4 - Done",
  "Page 5 - Done",
  "Page 6 - Done",
  "Page 7 - Done",
  "Page 8 - Done",
  "Page 9 - Done",
  "Page 10 - Done",
)
_PROGRESS_PER_TIMING_EVENT = 1 / len(_TIMING_EVENTS_WITH_PROGRESS)
_PROGRESS_BY_TIMING_EVENT = {
  event: i * _PROGRESS_PER_TIMING_EVENT
  for i, event in enumerate(_TIMING_EVENTS_WITH_PROGRESS)
}


def _get_timing_event_progress(event_type: str) -> float | None:
  """Get the progress of a timing event.

  Args:
    event_type: The type of timing event

  Returns:
    The progress of the timing event, or None if the event is not in the list
  """
  return _PROGRESS_BY_TIMING_EVENT.get(event_type)


def get_and_store_jokes(
  book_data: dict[str, Any],
  book_ref: firestore_fn.DocumentReference,
  joke_batch_iterator: Iterator[tuple[list[str], models.GenerationMetadata]],
  num_jokes: int = 0,
) -> models.GenerationMetadata:
  """Gets jokes from the joke generator and stores them in Firestore.

  Jokes are stored in a subcollection called 'jokes' under the book document.
  Each joke is stored as a separate document with an auto-generated ID.

  Args:
    book_data: The book data
    book_ref: Reference to the book document to store jokes under
    joke_batch_iterator: Iterator yielding lists of jokes
    num_jokes: Process at least this many jokes. If zero, process all jokes.

  Returns:
    Generation metadata for the jokes
  """
  jokes_collection = book_ref.collection('jokes')
  total_jokes_stored = 0
  generation_metadata = models.GenerationMetadata()

  try:
    for jokes_batch, batch_metadata in joke_batch_iterator:
      # Store the jokes batch
      _store_jokes_batch(jokes_collection, jokes_batch)
      total_jokes_stored += len(jokes_batch)
      generation_metadata.add_generation(batch_metadata)

      # If we've stored at least num_jokes jokes, we can stop
      if num_jokes > 0 and total_jokes_stored >= num_jokes:
        break

    _record_timing_event(book_data, book_ref, 'Jokes',
                         {'count': total_jokes_stored})

  except Exception as e:  # pylint: disable=broad-exception-caught
    # If joke generation fails, log the error but don't stop the book generation
    _add_minor_error(book_ref, f'Jokes - Error storing jokes: {str(e)}')

  return generation_metadata


def _store_jokes_batch(jokes_collection: CollectionReference,
                       jokes_batch: List[str]) -> None:
  """Stores a batch of jokes in the jokes collection.

  Args:
    jokes_collection: Reference to the jokes collection
    jokes_batch: List of jokes to store
  """
  if not jokes_batch:
    return

  # Create a batch to perform multiple writes atomically
  batch = firestore.db().batch()

  # Add each joke to the batch
  for joke in jokes_batch:
    # Generate a unique document ID
    joke_doc_ref = jokes_collection.document()

    # Add the joke to the batch
    batch.set(joke_doc_ref, {
      'text': joke,
      'timestamp': SERVER_TIMESTAMP,
    })

  # Commit the batch
  batch.commit()


def _get_models_for_story_mode(
  story_mode: StoryMode | str,
  text_model_override: LlmModel | str | None = None,
  voice_model_override: audio_voices.Voice | str | None = None,
) -> tuple[LlmModel, audio_voices.Voice | None]:
  """Get the models for a given story mode.

  Args:
    story_mode: The story mode to get models for
    text_model_override: Optional override for the text model
    voice_model_override: Optional override for the voice model

  Returns:
    Tuple of (text model, voice model)
  """
  if isinstance(story_mode, str):
    match story_mode:
      case 'basic':
        # Legacy value
        story_mode = StoryMode.DAILY_TALE
      case 'advanced':
        # Legacy value
        story_mode = StoryMode.PREMIUM
      case _:
        story_mode = StoryMode[story_mode]

  if text_model_override:
    if isinstance(text_model_override, str):
      text_model_override = LlmModel[text_model_override]
    text_model = text_model_override
  else:
    text_model = random.choice(story_mode.text_models)

  if voice_model_override:
    if isinstance(voice_model_override, str):
      voice_model_override = audio_voices.Voice[voice_model_override]
    voice_model = voice_model_override
  elif story_mode.voice_models:
    voice_model = random.choice(story_mode.voice_models)
  else:
    voice_model = None

  return text_model, voice_model


def log_info(
  message: str,
  book_id: str | None = None,
  user_id: str | None = None,
  book_data: dict[str, Any] | None = None,
) -> None:
  """Log an info message with extra context data.

  Args:
      message: The message to log
      book_id: The book ID
      user_id: The user ID (optional)
      book_data: The book data (optional)
  """
  extra_data = _get_extra_log_data(book_id, user_id, book_data)
  logger.info(message, extra=extra_data)


def log_warning(
  message: str,
  book_id: str | None = None,
  user_id: str | None = None,
  book_data: dict[str, Any] | None = None,
  exc_info: bool = True,
) -> None:
  """Log a warning message with extra context data.

  Args:
      message: The message to log
      book_id: The book ID
      user_id: The user ID (optional)
      book_data: The book data (optional)
  """
  extra_data = _get_extra_log_data(book_id, user_id, book_data)
  logger.warn(message, extra=extra_data, exc_info=exc_info)


def log_error(
  message: str,
  book_id: str | None = None,
  user_id: str | None = None,
  book_data: dict[str, Any] | None = None,
  exc_info: bool = True,
) -> None:
  """Log an error message with extra context data.

  Args:
      message: The message to log
      book_id: The book ID
      user_id: The user ID (optional)
      book_data: The book data (optional)
      exc_info: Whether to include exception stack trace (default True)
  """
  extra_data = _get_extra_log_data(book_id, user_id, book_data)
  logger.error(message, extra=extra_data, exc_info=exc_info)


def _get_extra_log_data(
  book_id: str | None = None,
  user_id: str | None = None,
  book_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
  """Get the extra log data for a book."""
  if not user_id and book_data:
    user_id = book_data.get('owner_user_id')
  if not user_id:
    user_id = "UNKNOWN"

  if not book_id:
    book_id = "UNKNOWN"

  return {
    "book_id": book_id,
    "user_id": user_id,
  }
