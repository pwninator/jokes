"""MailerLite API client wrapper.

Thin wrapper around the `mailerlite` SDK used by this project.
"""

from __future__ import annotations

from typing import Any

import mailerlite as MailerLite
from common import config
from firebase_functions import logger


class Error(Exception):
  """Base exception for MailerLite client errors."""


class MailerLiteClient:
  """Wrapper client exposing a small surface area for MailerLite operations."""

  def __init__(self, *, client: Any | None = None, api_key: str | None = None):
    api_key = api_key or config.get_mailerlite_api_key()
    self._client = client or MailerLite.Client({'api_key': api_key})

  @property
  def client(self) -> Any:
    """Return the underlying SDK client (useful for tests)."""
    return self._client

  def create_subscriber(
    self,
    *,
    email: str,
    country_code: str,
    group_id: str | None = None,
  ) -> dict[str, Any]:
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
    if not isinstance(resp, dict):
      raise Error(f"Unexpected MailerLite response type: {type(resp)}")
    return resp

  def add_to_group(self, *, subscriber_id: str,
                   group_id: str) -> dict[str, Any]:
    """Add an existing subscriber to a MailerLite group."""
    subscriber_id = (subscriber_id or '').strip()
    group_id = (group_id or '').strip()
    if not subscriber_id:
      raise ValueError("subscriber_id is required")
    if not group_id:
      raise ValueError("group_id is required")

    # The SDK's Groups API doesn't expose an add-subscriber helper; it supports
    # group assignment via subscriber update using the subscriber email.
    try:
      group_id_int = int(group_id)
    except Exception as exc:
      raise ValueError("group_id must be an int-like string") from exc

    resp = self._client.subscribers.update(subscriber_id,
                                           groups=[group_id_int])

    if not isinstance(resp, dict):
      raise Error(f"Unexpected MailerLite response type: {type(resp)}")
    return resp
