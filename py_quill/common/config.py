"""Global configuration constants."""

from google.cloud import secretmanager

# Google Cloud Project ID
PROJECT_ID = "storyteller-450807"
PROJECT_LOCATION = "us-central1"

# Google Cloud Storage buckets
AUDIO_BUCKET_NAME = "gen_audio"
IMAGE_BUCKET_NAME = "images.quillsstorybook.com"
ADMIN_HOST = "snickerdoodlejokes.com"

# Admin session
SESSION_COOKIE_NAME = '__session'
SESSION_MAX_AGE_SECONDS = 14 * 24 * 60 * 60  # 14 days

# Quill specific configuration
NUM_CHARACTER_PORTRAIT_IMAGE_ATTEMPTS = 8
NUM_COVER_IMAGE_ATTEMPTS = 8
NUM_PAGE_IMAGE_ATTEMPTS = 4

# Joke search constants
JOKE_SEARCH_TIGHT_THRESHOLD = 0.32
JOKE_SEARCH_LOOSE_THRESHOLD = 0.37

# Firebase Web Configuration (Public)
FIREBASE_WEB_CONFIG = {
  'apiKey': 'AIzaSyDvr_hRrKkHVw7x0AkRaRMNOuFd8e5P3Vo',
  'appId': '1:416102166155:web:7030e554efae8e3e3dee8e',
  'messagingSenderId': '416102166155',
  'projectId': 'storyteller-450807',
  'authDomain': 'snickerdoodlejokes.com',
  'storageBucket': 'storyteller-450807.firebasestorage.app',
  'measurementId': 'G-4KQFXXRSJY',
}


def _get_secret(secret_id: str) -> str:
  """Return the latest version of a Secret Manager secret as a UTF-8 string."""
  client = secretmanager.SecretManagerServiceClient()
  name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
  response = client.access_secret_version(name=name)
  return response.payload.data.decode("UTF-8")


def get_openai_api_key() -> str:
  """Gets the OpenAI API key from the secret manager."""
  return _get_secret("OPENAI_API_KEY")


def get_anthropic_api_key() -> str:
  """Gets the Anthropic API key from the secret manager."""
  return _get_secret("ANTHROPIC_API_KEY")


def get_gemini_api_key() -> str:
  """Gets the Gemini API key from the secret manager."""
  return _get_secret("GEMINI_API_KEY")


def get_google_analytics_api_key() -> str:
  """Gets the GA4 Measurement Protocol API secret from the secret manager."""
  return _get_secret("GOOGLE_ANALYTICS_API_KEY")
