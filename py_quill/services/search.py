"""Library for embeddings."""

import dataclasses
import time
import traceback
from enum import Enum

from common import config, models
from firebase_functions import logger
from google import genai
from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector
from google.genai.types import EmbedContentConfig
from services import firestore as firestore_service

_genai_client = None  # pylint: disable=invalid-name
_firestore_client = None  # pylint: disable=invalid-name

_TOKEN_COSTS = {
  # https://cloud.google.com/vertex-ai/generative-ai/pricing#embedding-models
  "gemini-embedding-001": {
    "input_tokens": 0.00015 / 1_000,
  },
}


class TaskType(str, Enum):
  """Task types for embedding generation."""
  RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
  RETRIEVAL_QUERY = "RETRIEVAL_QUERY"
  CLUSTERING = "CLUSTERING"


def get_genai_client() -> genai.Client:
  """Get the GenAI client with lazy initialization."""
  global _genai_client  # pylint: disable=global-statement
  if _genai_client is None:
    _genai_client = genai.Client(
      vertexai=True,
      project=config.PROJECT_ID,
      location=config.PROJECT_LOCATION,
    )
  return _genai_client


def get_firestore_client() -> firestore.Client:
  """Get the Firestore client with lazy initialization."""
  global _firestore_client  # pylint: disable=global-statement
  if _firestore_client is None:
    _firestore_client = firestore.Client()
  return _firestore_client


def get_embedding(
  text: str,
  task_type: TaskType,
  model: str = "gemini-embedding-001",
  output_dimensionality: int = 2048,
) -> tuple[Vector, models.GenerationMetadata]:
  """Get an embedding for a text."""
  start_time = time.perf_counter()
  client = get_genai_client()
  response = client.models.embed_content(
    model=model,
    contents=text,
    config=EmbedContentConfig(
      task_type=task_type,
      output_dimensionality=output_dimensionality,
    ),
  )

  if len(response.embeddings) != 1:
    raise ValueError(f"Expected 1 embedding, got {len(response.embeddings)}")

  input_tokens = response.embeddings[0].statistics.token_count

  generation_metadata = models.GenerationMetadata()
  generation_metadata.add_generation(
    models.SingleGenerationMetadata(
      label=f"embedding_{model}_{task_type}",
      model_name=model,
      token_counts={
        "input_tokens": input_tokens,
      },
      generation_time_sec=time.perf_counter() - start_time,
      cost=input_tokens * _TOKEN_COSTS[model]["input_tokens"],
    ))

  float_list = response.embeddings[0].values
  return Vector(float_list), generation_metadata


@dataclasses.dataclass
class JokeSearchResult:
  """A search result for a punny joke."""
  joke_id: str
  vector_distance: float
  setup_text: str | None = None
  punchline_text: str | None = None
  setup_image_url: str | None = None
  punchline_image_url: str | None = None


def search_jokes(
  query: str,
  label: str,
  field_filters: list[tuple[str, str, str]],
  limit: int = 10,
  distance_measure=DistanceMeasure.COSINE,
  distance_threshold: float | None = None,
  return_jokes: bool = False,
) -> list[JokeSearchResult]:
  """Search for jokes in Firestore."""
  try:
    client = get_firestore_client()
    collection = client.collection("joke_search")

    for field, op, value in field_filters:
      collection = collection.where(field, op, value)

    final_query = query
    query_embedding, _ = get_embedding(final_query, TaskType.RETRIEVAL_QUERY)

    vector_query = collection.find_nearest(
      vector_field="text_embedding",
      query_vector=Vector(query_embedding),
      distance_measure=distance_measure,
      limit=limit,
      distance_threshold=distance_threshold,
      distance_result_field="vector_distance",
    )
    docs = vector_query.stream()
    results = []
    for doc in docs:
      data = doc.to_dict()
      distance = data.pop("vector_distance")
      results.append(
        JokeSearchResult(
          joke_id=doc.id,
          vector_distance=distance,
        ))

    if return_jokes and results:
      joke_ids = [r.joke_id for r in results]
      full_jokes = firestore_service.get_punny_jokes(joke_ids)
      jokes_map = {j.key: j for j in full_jokes if j.key}

      for result in results:
        joke = jokes_map.get(result.joke_id)
        if joke:
          result.setup_text = joke.setup_text
          result.punchline_text = joke.punchline_text
          result.setup_image_url = joke.setup_image_url
          result.punchline_image_url = joke.punchline_image_url

    # Sort by vector distance
    results.sort(key=lambda x: x.vector_distance)

    num_results = len(results)
    logger.info(
      f"Joke search succeeded for label: {label}. Query: '{query}', Results: {num_results}",
      extra={
        "json_fields": {
          "label": label,
          "search_query": query,
          "num_results": num_results,
        }
      },
    )
    return results
  except Exception as e:
    tb_str = traceback.format_exc()
    logger.error(
      f"Joke search failed for label: {label}. Query: '{query}'. Error: {e}\nTraceback: {tb_str}",
      extra={
        "json_fields": {
          "label": label,
          "search_query": query,
          "error": str(e),
        }
      },
    )
    raise e
