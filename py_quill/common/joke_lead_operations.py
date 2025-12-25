"""Operations for creating and syncing joke leads."""

from __future__ import annotations

import datetime
from typing import Any

from firebase_functions import logger
from services import firestore, mailerlite

GROUP_SNICKERDOODLE_CLUB = "174697907700631034"


def _extract_subscriber_id(response: dict[str, Any]) -> str | None:
  """Extract subscriber id from MailerLite SDK responses."""
  if not isinstance(response, dict):
    return None
  if isinstance(response.get('id'), str):
    return response.get('id')
  data = response.get('data')
  if isinstance(data, dict) and isinstance(data.get('id'), str):
    return data.get('id')
  return None


def create_lead(
  *,
  email: str,
  country_code: str,
  signup_source: str,
  group_id: str | None = None,
) -> dict[str, Any]:
  """Create a lead in MailerLite, optionally add to a group, then store in Firestore.

  MailerLite failures raise and do not write to Firestore.
  """
  email_norm = (email or '').strip().lower()
  if not email_norm:
    raise ValueError("email is required")
  country_code = (country_code or '').strip()
  signup_source = (signup_source or '').strip()
  if not country_code:
    raise ValueError("country_code is required")
  if not signup_source:
    raise ValueError("signup_source is required")

  now = datetime.datetime.now(datetime.timezone.utc)
  signup_date = now.date().isoformat()

  client = mailerlite.MailerLiteClient()
  subscriber_resp = client.create_subscriber(
    email=email_norm,
    country_code=country_code,
    group_id=group_id,
  )
  subscriber_id = _extract_subscriber_id(subscriber_resp)

  lead_doc: dict[str, Any] = {
    'email': email_norm,
    'timestamp': now,
    'country_code': country_code,
    'signup_source': signup_source,
    'signup_date': signup_date,
    'mailerlite_subscriber_id': subscriber_id,
  }

  firestore.db().collection('joke_leads').document(email_norm).set(lead_doc)

  logger.info(
    'Stored joke lead',
    extra={
      'json_fields': {
        'event': 'joke_lead_stored',
        'email': email_norm,
        'country_code': country_code,
        'signup_source': signup_source,
        'signup_date': signup_date,
        'mailerlite_subscriber_id': subscriber_id,
        'group_id': group_id,
      }
    },
  )

  return lead_doc
