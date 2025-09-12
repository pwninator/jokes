"""Services for the functions."""

# Re-export commonly used service functions for easier monkeypatching in tests
from .firestore import get_punny_joke, get_punny_jokes  # noqa: F401
