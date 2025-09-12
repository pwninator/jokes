"""Initialize the environment."""

import vertexai
from common import config


def init() -> None:
  """Initialize the Vertex AI environment."""
  vertexai.init(project=config.PROJECT_ID,
                location=config.PROJECT_LOCATION,
                staging_bucket="gs://vertex_ai_agent_engine_staging")
