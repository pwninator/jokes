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


def format_image_url(
  image_url: str,
  format: str | None = None,
  quality: int | None = None,
  width: int | None = None,
) -> str:
  """Update CDN parameters in an image CDN URL.

  Args:
    image_url: The CDN URL
    format: The new format parameter
    quality: The new quality parameter
    width: The new width parameter

  Returns:
    The updated CDN URL with new parameters

  Raises:
    ValueError: If the URL format is invalid
  """
  # Expected format: https://images.quillsstorybook.com/cdn-cgi/image/width=1024,format=auto,quality=75/object_path

  # Check if it's a valid CDN URL
  if not image_url.startswith(
      "https://images.quillsstorybook.com/cdn-cgi/image/"):
    # Return the original URL if it's not a CDN URL
    return image_url

  # Extract the object path by finding the part after the parameters
  url_prefix = "https://images.quillsstorybook.com/cdn-cgi/image/"
  remainder = image_url.removeprefix(url_prefix)

  # Find where the object path starts (after the first '/')
  slash_index = remainder.find('/')
  if slash_index == -1:
    raise ValueError(f"Invalid CDN URL format: {image_url}")

  object_path = remainder[slash_index + 1:]

  params_str = remainder[:slash_index]
  params = {}
  if params_str:
    for part in params_str.split(','):
      key, value = part.split('=')
      params[key] = value

  if format:
    params['format'] = format
  if quality:
    params['quality'] = quality
  if width:
    params['width'] = width

  new_params_str = ",".join([f"{key}={value}" for key, value in params.items()])

  # Reconstruct the URL with new parameters
  return f"https://images.quillsstorybook.com/cdn-cgi/image/{new_params_str}/{object_path}"
