"""Daily joke notification functions."""

from __future__ import annotations

import datetime
import zoneinfo

from firebase_functions import https_fn, logger, options, scheduler_fn
from functions.function_utils import error_response, success_response
from services import firebase_cloud_messaging, firestore


@scheduler_fn.on_schedule(
  schedule="0 * * * *",
  timezone="Etc/GMT+12",
  memory=options.MemoryOption.GB_1,
  timeout_sec=300,
)
def send_daily_joke_scheduler(event: scheduler_fn.ScheduledEvent) -> None:
  """Scheduled function that sends daily joke notifications."""

  scheduled_time_utc = event.schedule_time
  if scheduled_time_utc is None:
    scheduled_time_utc = datetime.datetime.now(datetime.timezone.utc)
  _notify_all_joke_schedules(scheduled_time_utc)


@https_fn.on_request(
  memory=options.MemoryOption.GB_1,
  timeout_sec=300,
)
def send_daily_joke_http(req: https_fn.Request) -> https_fn.Response:
  """Send a daily joke notification to subscribers."""

  del req

  try:
    # Get current UTC time
    utc_now = datetime.datetime.now(datetime.timezone.utc)

    _notify_all_joke_schedules(utc_now)
  except Exception as e:
    return error_response(f'Failed to send daily joke notification: {str(e)}')

  return success_response({"message": "Daily joke notification sent"})


def _notify_all_joke_schedules(scheduled_time_utc: datetime.datetime) -> None:
  """Iterate all schedules and send notifications for each.

  Args:
      scheduled_time_utc: The scheduled time from the scheduler event.
  """
  schedule_ids = firestore.list_joke_schedules()
  logger.info(f"Found {len(schedule_ids)} joke schedules to process")
  for schedule_id in schedule_ids:
    try:
      logger.info(
        f"Sending daily joke notification for schedule: {schedule_id}")
      _send_daily_joke_notification(
        scheduled_time_utc,
        schedule_name=schedule_id,
      )
    except Exception as schedule_error:  # pylint: disable=broad-except
      logger.error(
        f"Failed sending jokes for schedule {schedule_id}: {schedule_error}")


def _send_daily_joke_notification(
  now: datetime.datetime,
  schedule_name: str = "daily_jokes",
) -> None:
  """Send a daily joke notification to subscribers.

  At each hour of the day, we send two notifications: one for the current date,
  and one for the next date. The dates are at UTC-12. Clients subscribe to the
  topic for the hour they want to receive notifications, using either the "c" or
  "n" variety depending on whether their local timezone is one day ahead of
  UTC-12 or not.

  Args:
      now: The current datetime when this was executed (any timezone)
      schedule_name: The name of the joke schedule to use
  """
  logger.info(
    f"Sending daily joke notification for {schedule_name} at {now.isoformat()}"
  )

  if now.tzinfo is None:
    raise ValueError(
      f"now must have timezone information, got naive datetime: {now}")

  now_utc = now.astimezone(datetime.timezone.utc)
  utc_minus_12 = now_utc - datetime.timedelta(hours=12)
  hour_utc_minus_12 = utc_minus_12.hour
  date_utc_minus_12 = utc_minus_12.date()

  _send_single_joke_notification(
    schedule_name=schedule_name,
    joke_date=date_utc_minus_12,
    notification_hour=hour_utc_minus_12,
    topic_suffix="c",
  )

  _send_single_joke_notification(
    schedule_name=schedule_name,
    joke_date=date_utc_minus_12 + datetime.timedelta(days=1),
    notification_hour=hour_utc_minus_12,
    topic_suffix="n",
  )

  pst_timezone = zoneinfo.ZoneInfo("America/Los_Angeles")
  now_pst = now.astimezone(pst_timezone)

  if now_pst.hour == 9:
    logger.info(
      f"It's 9am PST, sending additional notification for {schedule_name}")
    _send_single_joke_notification(
      schedule_name=schedule_name,
      joke_date=now_pst.date(),
    )


def _send_single_joke_notification(
  schedule_name: str,
  joke_date: datetime.date,
  notification_hour: int | None = None,
  topic_suffix: str | None = None,
) -> None:
  """Send a joke notification for a given date."""
  logger.info(f"Getting joke for {schedule_name} on {joke_date}")
  jokes = firestore.get_daily_jokes(schedule_name, joke_date, 1)
  joke = jokes[0] if jokes else None
  if not joke:
    logger.error(f"No joke found for {joke_date}")
    return
  logger.info(f"Joke found for {joke_date}: {joke.key}")

  if notification_hour is not None and topic_suffix is not None:
    topic_name = f"{schedule_name}_{notification_hour:02d}{topic_suffix}"
  else:
    topic_name = schedule_name
  logger.info(f"Sending joke notification to topic: {topic_name}")
  firebase_cloud_messaging.send_punny_joke_notification(topic_name, joke)
