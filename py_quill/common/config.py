"""Global configuration constants."""

from google.cloud import secretmanager

# Google Cloud Project ID
PROJECT_ID = "storyteller-450807"
PROJECT_LOCATION = "us-central1"

# Google Cloud Storage buckets
AUDIO_BUCKET_NAME = "gen_audio"
IMAGE_BUCKET_NAME = "images.quillsstorybook.com"
ADMIN_HOST = "snickerdoodlejokes.com"

# Quill specific configuration
NUM_CHARACTER_PORTRAIT_IMAGE_ATTEMPTS = 8
NUM_COVER_IMAGE_ATTEMPTS = 8
NUM_PAGE_IMAGE_ATTEMPTS = 4

# Joke search constants
JOKE_SEARCH_TIGHT_THRESHOLD = 0.32
JOKE_SEARCH_LOOSE_THRESHOLD = 0.37


def get_openai_api_key() -> str:
  """Gets the OpenAI API key from the secret manager."""
  secret_id = "OPENAI_API_KEY"
  client = secretmanager.SecretManagerServiceClient()
  name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
  response = client.access_secret_version(name=name)
  return response.payload.data.decode("UTF-8")


def get_anthropic_api_key() -> str:
  """Gets the OpenAI API key from the secret manager."""
  secret_id = "ANTHROPIC_API_KEY"
  client = secretmanager.SecretManagerServiceClient()
  name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
  response = client.access_secret_version(name=name)
  return response.payload.data.decode("UTF-8")


def get_gemini_api_key() -> str:
  """Gets the Gemini API key from the secret manager."""
  secret_id = "GEMINI_API_KEY"
  client = secretmanager.SecretManagerServiceClient()
  name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
  response = client.access_secret_version(name=name)
  return response.payload.data.decode("UTF-8")
