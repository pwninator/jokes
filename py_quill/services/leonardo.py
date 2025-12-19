"""Leonardo AI API service."""

import random
import re
import time
import traceback
from typing import Any, Callable, List, Tuple

import requests
from common import models, utils
from firebase_functions import logger
from services import firestore, llm_client
from services.llm_client import LlmModel

_USE_FAKE_IMAGES_IN_EMULATOR = False

# API Configuration
_BASE_URL = 'https://cloud.leonardo.ai/api/rest/v1'
_API_KEY = '4712fb6d-0249-491e-b557-4823698677b1'

# https://app.leonardo.ai/api-access
_LEONARDO_COST_PER_CREDIT = 9.0 / 3500

# Good quality, sometimes mixes up characters, very cheap
LEONARDO_FLEX_SCHNELL = '1dd50843-d653-4516-a8e3-f0238ee453ff'
# Decent quality, occasionaly mixes up characters, cheap
LEONARDO_FLEX_DEV = 'b2614463-296c-462a-9586-aafdb8f00e36'
# Less good than 1.0, and still pricy
LEONARDO_PHOENIX_0_9 = "6b645e3a-d64f-4341-a6d8-7a3690fbf042"
# Very good quality, but pricy
LEONARDO_PHOENIX_1_0 = "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3"
# Not good at following the prompt
LEONARDO_3D_ANIMATION = "d69c8273-6b17-4a30-a13e-d6637ae1c644"
# Has trouble with non-humans
LEONARDO_ANIME_XL = "e71a1c2f-4f80-4800-934f-2c68979d8cc8"

LEONARDO_MODEL_NAMES_BY_ID = {
  LEONARDO_FLEX_SCHNELL: 'Leonardo Flex Schnell',
  LEONARDO_FLEX_DEV: 'Leonardo Flex Dev',
  LEONARDO_PHOENIX_0_9: 'Leonardo Phoenix 0.9',
  LEONARDO_PHOENIX_1_0: 'Leonardo Phoenix 1.0',
  LEONARDO_3D_ANIMATION: 'Leonardo 3D Animation',
  LEONARDO_ANIME_XL: 'Leonardo Anime XL',
}

# pylint: disable=line-too-long
_TEST_IMAGES = [
  "https://cdn.leonardo.ai/users/91b2db7b-ed6d-49a9-8a18-e9e8518bf644/generations/b7ae1eb2-d65e-492c-a78e-ab91dcd46888/segments/1:1:1/Flux_Dev_The_image_features_a_cinematic_depth_of_field_with_vi_0.jpeg",
  "https://cdn.leonardo.ai/users/91b2db7b-ed6d-49a9-8a18-e9e8518bf644/generations/9a628ccf-8da8-4504-a75f-3b44f02075d5/segments/1:1:1/Flux_Dev_The_image_features_a_cinematic_depth_of_field_with_vi_0.jpeg",
  "https://cdn.leonardo.ai/users/91b2db7b-ed6d-49a9-8a18-e9e8518bf644/generations/2ea0aab7-7e5a-46f6-b4fd-5392f301c038/segments/1:1:1/Flux_Dev_The_image_features_a_cinematic_depth_of_field_with_vi_0.jpeg",
  "https://cdn.leonardo.ai/users/91b2db7b-ed6d-49a9-8a18-e9e8518bf644/generations/9041b71f-d1f5-47a7-b200-0c280fbdce4f/segments/1:1:1/Flux_Dev_The_image_features_a_cinematic_depth_of_field_with_vi_0.jpeg",
  "https://cdn.leonardo.ai/users/91b2db7b-ed6d-49a9-8a18-e9e8518bf644/generations/9a2030f0-d569-433d-98c3-1fcd62ab4eb2/segments/1:1:1/Flux_Dev_The_image_features_a_cinematic_depth_of_field_with_vi_0.jpeg",
  "https://cdn.leonardo.ai/users/91b2db7b-ed6d-49a9-8a18-e9e8518bf644/generations/c5b7879c-3ed8-4cfe-8e72-b230ac2fb84d/segments/1:1:1/Flux_Dev_The_image_features_a_cinematic_depth_of_field_with_vi_0.jpeg",
  "https://cdn.leonardo.ai/users/91b2db7b-ed6d-49a9-8a18-e9e8518bf644/generations/52cc3486-20e6-400c-a155-3bab1f1bf18a/segments/1:1:1/Flux_Dev_The_image_features_a_cinematic_depth_of_field_with_vi_0.jpeg",
  "https://cdn.leonardo.ai/users/91b2db7b-ed6d-49a9-8a18-e9e8518bf644/generations/a82074bf-d7c7-4137-877e-503f14420f0a/segments/1:1:1/Flux_Dev_The_image_features_a_cinematic_depth_of_field_with_vi_0.jpeg",
  "https://cdn.leonardo.ai/users/91b2db7b-ed6d-49a9-8a18-e9e8518bf644/generations/07512f16-9efe-4de7-b989-0f01d24bbee8/segments/1:1:1/Flux_Dev_The_image_features_a_cinematic_depth_of_field_with_vi_0.jpeg",
  "https://cdn.leonardo.ai/users/91b2db7b-ed6d-49a9-8a18-e9e8518bf644/generations/593be52c-c036-4c8e-8be1-d5f0d46ae8f5/segments/1:1:1/Flux_Dev_The_image_features_a_cinematic_depth_of_field_with_vi_0.jpeg",
  "https://cdn.leonardo.ai/users/91b2db7b-ed6d-49a9-8a18-e9e8518bf644/generations/edbd5eed-5b09-441c-9f92-6c1af5959837/segments/1:1:1/Flux_Dev_Blaze_smiles_down_at_the_children_reassuring_them_He__0.jpeg",
]

CUSTOM_STYLE_PROMPT = '''The image is a scene from a Pixar film, featuring a cinematic depth of field, with vibrant, stylized characters in exaggerated proportions and expressive poses.'''
# pylint: enable=line-too-long

_MAX_PROMPT_CHARACTERS = 1500

_PROMPT_MODERATION_REPLACEMENTS = {
  re.compile(r'mushroom', re.IGNORECASE): 'shiitake',
  re.compile(r'exposed', re.IGNORECASE): 'open',
  re.compile(r'low-angle', re.IGNORECASE): 'low',
  re.compile(r'nudge', re.IGNORECASE): 'gently push',
  re.compile(r'shoot', re.IGNORECASE): 'launch',
  re.compile(r'lick', re.IGNORECASE): 'taste',
  re.compile(r'pot', re.IGNORECASE): 'container',
  # re.compile(r'trip', re.IGNORECASE): 'journey' or 'stumble',
}


class ImageGenerationError(Exception):
  """Raised when there is an error generating an image with Leonardo AI."""


def generate_image(
  label: str,
  prompt_chunks: List[str],
  fallback_prompt_chunks: List[str] | None = None,
  refine_prompt: bool = False,
  model_id: str = LEONARDO_FLEX_SCHNELL,
  num_images: int = 4,
  user_uid: str | None = None,
  extra_log_data: dict[str, Any] | None = None,
) -> tuple[models.Image, Callable[[list[bytes] | None], models.Image]]:
  """Generates multiple images using the Leonardo.ai API and uses Gemini to pick the best one.

  Args:
    label: A label for the image generation request.
    prompt_chunks: List of prompt text chunks to combine
    fallback_prompt_chunks: Optional fallback prompts if primary fails
    refine_prompt: Whether to use Leonardo's prompt enhancement
    model_id: The Leonardo AI model ID to use.
    num_images: Number of images to generate (default 4)
    user_uid: The UID of the user requesting the image. Can be None.
    extra_log_data: Extra log data to include in the log
  Returns:
    A tuple containing:
    - The initial Image object with generation_id set
    - A callable that returns the final generated image
  """

  # Try with primary prompt
  try:
    image, image_callback = _send_generation_request(
      model_id,
      prompt_chunks,
      refine_prompt,
      num_images,
      label,
      user_uid=user_uid,
      extra_log_data=extra_log_data)
  except ImageGenerationError as e:
    # This can fail if the prompt is blocked by moderation filters.
    # Try with a backup prompt if provided.
    if fallback_prompt_chunks:
      logger.warn(
        "Primary image generation failed, attempting with backup prompt: %s",
        str(e))
      image, image_callback = _send_generation_request(
        model_id,
        fallback_prompt_chunks,
        refine_prompt,
        num_images,
        f"{label} (backup)",
        user_uid=user_uid,
        extra_log_data=extra_log_data)
      image.error = str(e)
    else:
      raise

  image.owner_user_id = user_uid
  return image, image_callback


def _combine_prompt_chunks(chunks: List[str]) -> str:
  """Combines prompt chunks up to the max character limit."""
  if not chunks:
    return ''

  combined = [chunks[0]]
  for chunk in chunks[1:]:
    if len('\n'.join(combined + [chunk] +
                     [CUSTOM_STYLE_PROMPT])) <= _MAX_PROMPT_CHARACTERS:
      combined.append(chunk)
    else:
      break

  combined.append(CUSTOM_STYLE_PROMPT)
  return '\n'.join(combined)


def _sanitize_prompt(prompt: str) -> str:
  """Sanitizes the prompt to avoid moderation filters."""
  for pattern, replacement in _PROMPT_MODERATION_REPLACEMENTS.items():
    prompt = pattern.sub(replacement, prompt)

  return prompt


def _select_best_image(
  image_prompt: str,
  image_urls: List[str],
  reference_images: dict[str, bytes] | None = None,
  extra_log_data: dict[str, Any] | None = None,
) -> Tuple[str, models.SingleGenerationMetadata | None, dict]:
  """Uses Gemini to select the best image based on the prompt."""
  llm = llm_client.get_client(
    label="Best Image Selection",
    model=LlmModel.GEMINI_2_5_FLASH,
    temperature=0.1,
  )

  # Download images and create Parts from bytes
  image_bytes_by_url = utils.download_images(image_urls)
  if not image_bytes_by_url:
    logger.error("No images could be downloaded")
    return image_urls[0], None, None

  prompt_chunks = [
    f"""You are an expert art critic evaluating images generated for a children's book.
The prompt for these images was:

{image_prompt}

1. CRITICAL ERRORS (Any failures in these result in a score no higher than 2):
- Characters must have the correct number of body parts (no extra/missing limbs)
- Body parts must be in anatomically correct positions, allowing for cartoon-style exaggeration
- Characters must not blend or mix attributes between different characters
- No major anatomical deformities or distortions (beyond standard cartoon stylization)
- No extra characters in the foreground that are not mentioned in the description
- Images must be appropriate for young children (no scary elements, violence, or inappropriate content)
- Images must not contain any known company logos or trademarks

2. Secondary checks for character accuracy:
- Specifically mentioned colors, clothing items, body shapes, sizes, and other visual attributes must match the description
  * Obvious mismatches (e.g. hair color/style, shirt color, etc.) should be penalized more heavily than minor details (e.g. logo on shirt, presence of a necklace, number of freckles, etc.)
- Additional character details not specified in the description are acceptable, as long as they:
  * Fit the overall animated film aesthetic
  * Create a cohesive, appealing character design
  * Don't contradict any specified details

3. Third, check for other aesthetic elements:
- Character expressions and poses should be friendly and appealing to children
- Overall style should match family-friendly animated film aesthetics

Provide a detailed explanation highlighting any concerns about child-appropriateness, anatomical issues, character matches/mismatches, and other elements.

Score from 0-10, where:
- 0: Inappropriate content and should never be shown to children
- 1-2: Major anatomical issues or deformities, or contains extra foreground characters not mentioned in the description
- 3-5: Correct anatomy, but significant mismatches with specified character details (e.g. wrong hair/shirt color)
- 6-7: Minor mismatches with specified details (e.g. a few extra freckles, a different pose, etc.)
- 8-10: Perfect match with the description, with higher scores for better execution and composition

The description is: """,
    image_prompt,
  ]

  if reference_images:
    prompt_chunks.append(
      "Below are reference images of characters that should appear in the generated images."
    )
    for label, image_bytes in reference_images.items():
      prompt_chunks.append(f"\n{label}:")
      prompt_chunks.append(("image/jpeg", image_bytes))
    prompt_chunks.append("""
If the images below contain any of these characters, evaluate how closely the images match
the reference images above on anatomical details. For example, do they have the same
body shape and proportions? Are they the same size? Do they have matching body parts (e.g.
horns, tails, etc.)? Are their arms/legs/appendages the same length and thickness? Deviations
in the anatomy are considered critical errors.
""")

  prompt_chunks.append("\nAnalyze each image: ")

  # Create a mapping between image numbers and URLs for later lookup
  url_by_index = list(image_bytes_by_url.keys())

  for i, (url, image_bytes) in enumerate(image_bytes_by_url.items()):
    prompt_chunks.append(f"\nImage {i} (url: {url}):")
    prompt_chunks.append(("image/jpeg", image_bytes))

  prompt_chunks.append("""
Make sure the image scores are relative to each other, so that the best image scores higher than the worst image.
No two images should have the same score. If multiple images are similar in quality, use decimal points to differentiate and establish a clear ranking.
Format your final answer as a JSON object with keys as "Image 0", "Image 1", etc., and the value being an object with keys "explanation" and "score".
""")

  # Ask Gemini to evaluate the images
  try:
    response = llm.generate(prompt_chunks, extra_log_data=extra_log_data)
  except llm_client.LlmError as e:
    logger.error(f"Error evaluating images: {e}")
    return image_urls[0], None, None

  # Extract JSON dict using regex
  results = utils.extract_json_dict(response.text) or {}

  # Find the best score and corresponding URL
  best_url = None
  best_score = -1
  for image_key, evaluation in results.items():
    score = float(evaluation['score'])
    if score > best_score:
      best_score = score
      index = int(image_key.split()[-1])
      best_url = url_by_index[index]

  if best_url is None:
    logger.warn("No valid scores found in response: %s", response.text)
    best_url = image_urls[0]
    best_score = -1

  return best_url, response.metadata, results


def _build_metadata(
  label: str,
  model_name: str,
  api_credits: float,
  generation_time_sec: float,
) -> models.SingleGenerationMetadata:
  """Creates a SingleGenerationMetadata object without logging.

  Args:
      label: The label for the generation
      model_name: The name of the model used
      api_credits: The number of API credits used
      generation_time_sec: The time taken in seconds

  Returns:
      SingleGenerationMetadata object for storing in the database
  """
  # Calculate cost once to ensure it's consistent
  cost = _calculate_generation_cost(api_credits)

  # Create SingleGenerationMetadata for database storage
  metadata = models.SingleGenerationMetadata(
    label=label,
    model_name=model_name,
    token_counts={"leonardo_credits": api_credits},
    generation_time_sec=generation_time_sec,
    cost=cost,
  )

  return metadata


def _log_generation_results(
  label: str,
  model_name: str,
  api_credits: float,
  generation_time_sec: float,
  prompt: str,
  generation_id: str,
  all_urls: List[str],
  best_url: str | None,
  evaluation_results: dict | None = None,
  extra_log_data: dict[str, Any] | None = None,
) -> None:
  """Logs the generation results with all URLs and scores.

  Args:
      label: The label for the generation
      model_name: The name of the model used
      api_credits: The number of API credits used
      generation_time_sec: The time taken in seconds
      prompt: The prompt used for generation
      generation_id: Generation ID from Leonardo
      all_urls: List of all generated image URLs
      best_url: The selected best URL (may be None if selection failed)
      evaluation_results: Optional evaluation results with scores
      extra_log_data: Extra log data to include in the log
  """
  # Calculate cost once
  cost = _calculate_generation_cost(api_credits)

  # Create structured data for logging
  log_data = {
    "generation_cost_usd": cost,
    "generation_time_sec": generation_time_sec,
    "model_name": model_name,
    "label": label,
    "leonardo_credits": api_credits,
    "generation_id": generation_id,
    "urls_count": len(all_urls),
    **(extra_log_data or {}),
  }

  # Build log message parts
  log_parts = []
  log_parts.append(f"""
============================== Prompt ==============================
{prompt}
""")

  # Add response section with all URLs and scores
  log_parts.append("""
============================== Response ==============================""")

  # Format the URLs with scores
  for i, url in enumerate(all_urls):
    score = "-"
    is_best = url == best_url

    # Try to get score from evaluation results
    if evaluation_results and f"Image {i}" in evaluation_results:
      score = evaluation_results[f"Image {i}"].get("score", "-")

    # Format with asterisks if it's the best one
    if is_best:
      log_parts.append(f"*** Image {i} (Score: {score}) ***\n{url}")
    else:
      log_parts.append(f"Image {i} (Score: {score})\n{url}")

  log_parts.append(f"""
============================== Metadata ==============================
Model: {model_name}
Generation time: {generation_time_sec:.2f} seconds
Generation cost: ${cost:.6f}
Leonardo credits: {api_credits}
Generation ID: {generation_id}""")

  # Log combined message with structured data
  header = f"{model_name} done: {label}"
  combined_log = header + "\n" + "\n".join(log_parts)

  # Log combined if under limit, otherwise log parts separately
  if len(combined_log) <= 65_000:
    logger.info(combined_log, extra={"json_fields": log_data})
  else:
    # Log each part separately
    num_parts = len(log_parts)
    for i, part in enumerate(log_parts):
      is_last_part = i == (num_parts - 1)
      if is_last_part:
        logger.info(f"{header}\n{part}", extra={"json_fields": log_data})
      else:
        logger.info(f"{header}\n{part}")


def _send_generation_request(
  model_id: str,
  chunks: List[str],
  refine_prompt: bool,
  num_images: int,
  label: str,
  user_uid: str | None = None,
  extra_log_data: dict[str, Any] | None = None,
) -> tuple[models.Image, Callable[[list[bytes] | None], models.Image]]:
  """Initiates image generation and returns a tuple of (initial Image object, callback).

  Args:
      model_id: The Leonardo AI model ID to use
      chunks: List of prompt text chunks to combine
      refine_prompt: Whether to use Leonardo's prompt enhancement
      num_images: Number of images to generate
      label: The label for the generation
      user_uid: The user ID of the user who is requesting the image. Can be None.
      extra_log_data: Extra log data to include in the log

  Returns:
      Tuple of (initial Image object, callable that when invoked will check generation
      status and return the Image)

  Raises:
      ImageGenerationError: If the initial generation request fails
  """
  prompt = _combine_prompt_chunks(chunks)
  prompt = _sanitize_prompt(prompt)

  if utils.is_emulator() and _USE_FAKE_IMAGES_IN_EMULATOR:
    logger.info('Running in emulator mode. Returning a test image.')

    # Create a test image URL
    test_url = _TEST_IMAGES[random.randint(0, len(_TEST_IMAGES) - 1)]

    # Build metadata for emulator mode (0 credits/cost)
    image_gen_metadata = _build_metadata(
      label=label,
      model_name=LEONARDO_MODEL_NAMES_BY_ID[model_id],
      api_credits=0,
      generation_time_sec=0,
    )

    test_image = models.Image(
      url=test_url,
      gcs_uri=None,
      original_prompt=prompt,
      final_prompt=prompt,
      generation_metadata=models.GenerationMetadata(),
      owner_user_id=user_uid,
    )

    # Add generation metadata
    test_image.generation_metadata.add_generation(image_gen_metadata)

    # Store the image in Firestore like we do in the production path
    test_image = firestore.create_image(test_image)

    # Log the results
    _log_generation_results(
      label=label,
      model_name=LEONARDO_MODEL_NAMES_BY_ID[model_id],
      api_credits=0,
      generation_time_sec=0,
      prompt=prompt,
      generation_id="emulator",
      all_urls=[test_url],
      best_url=test_url,
      extra_log_data=extra_log_data,
    )

    return test_image, lambda _: test_image

  try:
    response = requests.post(
      f'{_BASE_URL}/generations',
      headers={
        'accept': 'application/json',
        'authorization': f'Bearer {_API_KEY}',
        'content-type': 'application/json',
      },
      json={
        'modelId': model_id,
        'prompt': prompt,
        'num_images': num_images,
        'width': 512,
        'height': 512,
        'contrast': 3.5,
        'enhancePrompt': refine_prompt,
      },
      timeout=60,
    )
  except (requests.RequestException, requests.Timeout) as e:
    error_msg = f'Error generating image: {str(e)}\n{prompt}'
    logger.error(error_msg)
    raise ImageGenerationError(error_msg) from e

  if response.status_code != 200:
    error_msg = f'Failed to create generation: {response.text}\n{prompt}'
    logger.error(error_msg)
    raise ImageGenerationError(error_msg)

  generation_data = response.json()
  generation_id = generation_data['sdGenerationJob']['generationId']
  api_credits = generation_data['sdGenerationJob']['apiCreditCost']
  image_start_time = time.perf_counter()

  # Build metadata for the initial generation request
  image_gen_metadata = _build_metadata(
    label=label,
    model_name=LEONARDO_MODEL_NAMES_BY_ID[model_id],
    api_credits=api_credits,
    generation_time_sec=0,  # Will be updated when complete
  )

  generation_metadata = models.GenerationMetadata()
  generation_metadata.add_generation(image_gen_metadata)

  # Create initial image object
  initial_image = models.Image(
    url=None,  # URL will be set once generation is complete
    gcs_uri=None,
    original_prompt=prompt,
    final_prompt=None,  # Will be set once generation is complete
    generation_metadata=generation_metadata,
    generation_id=generation_id,
    owner_user_id=user_uid,
  )

  # Store initial image in Firestore
  initial_image = firestore.create_image(initial_image)

  def check_generation(
      reference_image_bytes: dict[str, bytes] | None = None) -> models.Image:
    """Checks the status of the generation and returns the final Image."""
    max_attempts = 30
    attempts = 0

    while attempts < max_attempts:
      try:
        status_response = requests.get(
          f'{_BASE_URL}/generations/{generation_id}',
          headers={
            'accept': 'application/json',
            'authorization': f'Bearer {_API_KEY}',
          },
          timeout=60,
        )
      except (requests.RequestException, requests.Timeout) as e:
        error_msg = f'Error checking generation status: {str(e)}'
        logger.error(error_msg)
        raise ImageGenerationError(error_msg) from e

      if status_response.status_code != 200:
        error_msg = f'Failed to check generation status: {status_response.text}'
        logger.error(error_msg)
        raise ImageGenerationError(error_msg)

      status_data = status_response.json()['generations_by_pk']
      status = status_data['status']

      if status == 'FAILED':
        error_msg = f'Generation failed: {status_response.text}'
        logger.error(error_msg)
        raise ImageGenerationError(error_msg)

      if status == 'COMPLETE':
        image_stop_time = time.perf_counter()
        generations = status_data['generated_images']

        if not generations:
          error_msg = 'No images were generated'
          logger.error(error_msg)
          raise ImageGenerationError(error_msg)

        image_urls = [img['url'] for img in generations]
        final_prompt = status_data['prompt']
        generation_time_sec = image_stop_time - image_start_time

        best_url = image_urls[0]
        gemini_evaluation = None
        selection_gen_metadata = None

        if len(image_urls) > 1:
          try:
            (
              best_url,
              selection_gen_metadata,
              evaluation_results,
            ) = _select_best_image(prompt, image_urls, reference_image_bytes,
                                   extra_log_data)
            if selection_gen_metadata:
              generation_metadata.add_generation(selection_gen_metadata)
            gemini_evaluation = evaluation_results
          except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
              f'Error selecting best image: {e}\n{traceback.format_exc()}')
            # Continue with the first image as fallback
            best_url = image_urls[0]
            evaluation_results = None

        # Update the generation_time_sec
        image_gen_metadata.generation_time_sec = generation_time_sec

        # Update the existing image with URL
        initial_image.url = best_url
        initial_image.final_prompt = final_prompt
        initial_image.gemini_evaluation = gemini_evaluation
        firestore.update_image(initial_image)

        # Log all the results now that we have complete information
        _log_generation_results(
          label=label,
          model_name=LEONARDO_MODEL_NAMES_BY_ID[model_id],
          api_credits=api_credits,
          generation_time_sec=generation_time_sec,
          prompt=prompt,
          generation_id=generation_id,
          all_urls=image_urls,
          best_url=best_url,
          evaluation_results=gemini_evaluation,
          extra_log_data=extra_log_data,
        )

        return initial_image

      attempts += 1
      time.sleep(2)

    error_msg = f'Generation timed out after {max_attempts} attempts'
    logger.error(error_msg)
    raise ImageGenerationError(error_msg)

  return initial_image, check_generation


def _calculate_generation_cost(api_credits: float) -> float:
  """Calculates the generation cost in USD."""
  return api_credits * _LEONARDO_COST_PER_CREDIT
