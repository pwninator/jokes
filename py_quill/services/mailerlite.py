"""MailerLite API client wrapper.

Thin wrapper around the `mailerlite` SDK used by this project.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import mailerlite as MailerLite
from common import config
from firebase_functions import logger


class Error(Exception):
  """Base exception for MailerLite client errors."""

@dataclass(frozen=True)
class Subscriber:
  """Minimal subscriber representation used by the app."""
  id: str
  status: str | None = None
  groups: list[int] | None = None

  @classmethod
  def from_response(cls, payload: dict[str, Any]) -> "Subscriber":
    """Parse a subscriber payload from MailerLite API responses."""
    if not isinstance(payload, dict):
      raise Error(f"Unexpected MailerLite response type: {type(payload)}")
    data = payload.get('data') if 'data' in payload else payload
    if not isinstance(data, dict):
      raise Error(f"Unexpected MailerLite response data type: {type(data)}")

    raw_id = data.get('id')
    if not isinstance(raw_id, str) or not raw_id.strip():
      raise Error("MailerLite subscriber id missing from response")

    status = data.get('status')
    if not isinstance(status, str):
      status = None

    groups_raw = data.get('groups')
    groups: list[int] | None = None
    if isinstance(groups_raw, list):
      extracted: list[int] = []
      for item in groups_raw:
        if isinstance(item, int):
          extracted.append(item)
          continue
        if isinstance(item, dict):
          group_id = item.get('id')
          if isinstance(group_id, int):
            extracted.append(group_id)
      groups = extracted or None

    return cls(id=raw_id, status=status, groups=groups)


class MailerLiteClient:
  """Wrapper client exposing a small surface area for MailerLite operations."""

  def __init__(self, *, client: Any | None = None, api_key: str | None = None):
    api_key = api_key or config.get_mailerlite_api_key()
    self._client = client or MailerLite.Client({'api_key': api_key})

  @property
  def client(self) -> Any:
    """Return the underlying SDK client (useful for tests)."""
    return self._client

  def get_subscriber_by_email(self, *, email: str) -> Subscriber | None:
    """Fetch a subscriber by email address.

    Returns:
      Subscriber if found, or None if not found.
    """
    email = (email or '').strip().lower()
    if not email:
      raise ValueError("email is required")

    subscribers_api = self._client.subscribers
    response = subscribers_api.api_client.request(
      "GET",
      f"{subscribers_api.base_api_url}/{email}",
    )
    status_code = getattr(response, "status_code", None)
    if status_code == 404:
      return None
    if status_code is not None and (status_code < 200 or status_code >= 300):
      raise Error(f"MailerLite returned status {status_code} for {email}")

    data = response.json()
    return Subscriber.from_response(data)

  def create_subscriber(
    self,
    *,
    email: str,
    country_code: str,
    group_id: str | None = None,
  ) -> Subscriber:
    """Create a subscriber with project-specific custom fields."""
    email = (email or '').strip().lower()
    if not email:
      raise ValueError("email is required")

    fields = {
      'country': (country_code or '').strip(),
    }

    logger.info(
      'Creating MailerLite subscriber',
      extra={
        'json_fields': {
          'event': 'mailerlite_create_subscriber',
          'email': email,
          'country_code': country_code,
          'group_id': group_id,
        }
      },
    )

    groups = None
    if group_id:
      try:
        groups = [int(group_id)]
      except Exception as exc:
        raise ValueError("group_id must be an int-like string") from exc

    # The SDK expects the email as the first argument and custom fields via
    # keyword args.
    if groups is not None:
      resp = self._client.subscribers.create(email,
                                             fields=fields,
                                             groups=groups)
    else:
      resp = self._client.subscribers.create(email, fields=fields)
    return Subscriber.from_response(resp)
