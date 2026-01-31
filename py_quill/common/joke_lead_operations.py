"""Operations for creating and syncing joke leads."""

from __future__ import annotations

import datetime
from typing import Any

from firebase_functions import logger
from services import firestore, mailerlite

GROUP_SNICKERDOODLE_CLUB = "174697907700631034"
SIGNUP_SOURCE_USER_SYNC = "user_sync"


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
  subscriber = client.create_subscriber(
    email=email_norm,
    country_code=country_code,
    group_id=group_id,
  )
  subscriber_id = subscriber.id

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


def ensure_users_subscribed(
  *,
  group_id: str = GROUP_SNICKERDOODLE_CLUB,
  limit: int | None = None,
) -> dict[str, int]:
  """Ensure users are subscribed in MailerLite and mirrored in Firestore."""
  client = mailerlite.MailerLiteClient()

  stats = {
    'users_processed': 0,
    'users_skipped_missing_email': 0,
    'subscribers_found': 0,
    'subscribers_created': 0,
    'users_updated': 0,
    'lead_docs_written': 0,
    'errors': 0,
  }

  for user_doc in firestore.get_users_missing_mailerlite_subscriber_id(
      limit=limit):
    stats['users_processed'] += 1
    if not getattr(user_doc, 'exists', False):
      continue

    user_data = user_doc.to_dict() or {}
    email = (user_data.get('email') or '').strip().lower()
    if not email:
      stats['users_skipped_missing_email'] += 1
      continue

    try:
      subscriber = client.get_subscriber_by_email(email=email)
      if not subscriber:
        subscriber = client.create_subscriber(
          email=email,
          country_code=(user_data.get('country_code') or ''),
          group_id=group_id,
        )
        stats['subscribers_created'] += 1
      else:
        stats['subscribers_found'] += 1
    except Exception as exc:  # pylint: disable=broad-except
      stats['errors'] += 1
      logger.error(
        f"Failed to sync MailerLite subscriber for {email}: {exc}",
        extra={
          'json_fields': {
            'event': 'mailerlite_user_sync_failed',
            'email': email,
          }
        },
      )
      continue

    try:
      firestore.update_user_mailerlite_subscriber_id(user_doc.id,
                                                     subscriber.id)
      stats['users_updated'] += 1
    except Exception as exc:  # pylint: disable=broad-except
      stats['errors'] += 1
      logger.error(
        f"Failed to update Firestore user {user_doc.id}: {exc}",
        extra={
          'json_fields': {
            'event': 'mailerlite_user_sync_firestore_failed',
            'user_id': user_doc.id,
            'email': email,
          }
        },
      )
      continue

    try:
      firestore.ensure_joke_lead_doc(
        email=email,
        subscriber_id=subscriber.id,
        signup_source=SIGNUP_SOURCE_USER_SYNC,
        country_code=(user_data.get('country_code') or None),
      )
      stats['lead_docs_written'] += 1
    except Exception as exc:  # pylint: disable=broad-except
      stats['errors'] += 1
      logger.error(
        f"Failed to ensure joke lead for {email}: {exc}",
        extra={
          'json_fields': {
            'event': 'mailerlite_user_sync_lead_failed',
            'email': email,
          }
        },
      )

  logger.info(
    f"MailerLite user sync completed with stats: {stats}",
    extra={
      'json_fields': {
        'event': 'mailerlite_user_sync_completed',
        **stats,
      }
    },
  )
  return stats
