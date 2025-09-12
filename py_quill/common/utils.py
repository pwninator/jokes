"""Utility functions"""

import datetime
import json
import os
import re
from typing import Any

import requests

_NON_ALPHANUMERIC_RE = re.compile(r'[^a-zA-Z0-9]')


def download_images(urls: list[str]) -> dict[str, bytes]:
  """Downloads images from the given URLs and returns them as bytes."""
  image_bytes_by_url = {}
  for url in urls:
    try:
      response = requests.get(url, timeout=5)
      response.raise_for_status()
      image_bytes_by_url[url] = response.content
    except Exception as e:  # pylint: disable=broad-exception-caught
      print(f"Error downloading image {url}: {e}")

  return image_bytes_by_url


def extract_json_dict(s: str) -> dict[str, Any] | None:
  """Extract a JSON dictionary from a string."""
  json_match = re.search(r'\{.*\}', s, re.DOTALL)
  if not json_match:
    print(f"No JSON object found in string: {s}")
    return None
  try:
    return json.loads(json_match.group(0))
  except json.JSONDecodeError as e:
    print(f"Error parsing JSON: {e}")
    return None


def timestamp_str() -> str:
  """Returns a timestamp string in the format YYYYMMDD_HHMMSS"""
  return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def create_firestore_key(*args: str, max_length: int = 20) -> str:
  """Creates a Firestore key from the given arguments."""
  parts = [
    _NON_ALPHANUMERIC_RE.sub(
      '_',
      arg.lower()[:max_length],
    ).strip("_") for arg in args
  ]
  return '__'.join(parts)


def create_timestamped_firestore_key(*args: str) -> str:
  """Creates a Firestore key from the given arguments."""
  return create_firestore_key(timestamp_str(), *args)


def is_emulator() -> bool:
  """Returns True if the code is running in an emulator."""
  return os.environ.get('FUNCTIONS_EMULATOR')
