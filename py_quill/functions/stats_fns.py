"""Stats calculation functions."""

import datetime
import zoneinfo

from firebase_functions import https_fn, options, scheduler_fn
from google.cloud.firestore import FieldFilter
from firebase_functions import logger
from services import firestore as firestore_service


def _bucket_jokes_viewed(count: int) -> str:
  """Bucket joke view counts into human-friendly ranges."""
  safe_count = max(0, count)
  if safe_count == 0:
    return "0"
  if safe_count < 10:
    return "1-9"
  if safe_count < 100:
    lower = (safe_count // 10) * 10
    upper = lower + 9
    return f"{lower}-{upper}"

  lower = max(100, (safe_count // 50) * 50)
  upper = lower + 49
  return f"{lower}-{upper}"


def _to_int(value: object) -> int:
  """Best-effort conversion to int with fallback to zero."""
  try:
    return int(value)
  except Exception:
    return 0


@https_fn.on_request(
  memory=options.MemoryOption.GB_4,
  timeout_sec=1200,
)
def joke_stats_calculate_http(req: https_fn.Request) -> https_fn.Response:
  """HTTP endpoint to calculate joke stats."""
  del req
  joke_stats_calculate(
    scheduler_fn.ScheduledEvent(
      job_name=None,
      schedule_time=datetime.datetime.now(datetime.timezone.utc),
    ))
  return https_fn.Response(status=200)


@scheduler_fn.on_schedule(
  schedule="5 0 * * *",  # 00:05 (5 minutes past midnight) each day
  timezone="America/Los_Angeles",
  memory=options.MemoryOption.GB_1,
)
def joke_stats_calculate(event: scheduler_fn.ScheduledEvent) -> None:
  """Calculate daily joke stats for the previous day and upsert into Firestore."""
  del event

  # Get current time in Los Angeles
  la_tz = zoneinfo.ZoneInfo("America/Los_Angeles")
  now_la = datetime.datetime.now(la_tz)

  # We want stats for yesterday
  yesterday_la = now_la - datetime.timedelta(days=1)

  # Format document ID as YYYYMMDD (using yesterday's date)
  doc_id = yesterday_la.strftime("%Y%m%d")

  # Create timestamp for 00:00:00 yesterday LA time
  yesterday_start = yesterday_la.replace(hour=0,
                                         minute=0,
                                         second=0,
                                         microsecond=0)

  # Stats calculation logic
  now_utc = datetime.datetime.now(datetime.timezone.utc)
  cutoff_7d = now_utc - datetime.timedelta(hours=168)
  cutoff_1d = now_utc - datetime.timedelta(hours=24)

  # Query users active in the last 7 days (superset of 1 day)
  users_query = firestore_service.db().collection("joke_users").where(
    filter=FieldFilter("last_login_at", ">=", cutoff_7d))

  num_1d_users_by_days_used: dict[str, int] = {}
  num_1d_users_by_jokes_viewed: dict[str, int] = {}
  num_7d_users_by_jokes_viewed: dict[str, int] = {}
  num_7d_users_by_days_used_by_jokes_viewed: dict[str, dict[str, int]] = {}

  for doc in users_query.stream():
    data = doc.to_dict() or {}
    last_login = data.get("last_login_at")

    # Ensure last_login is timezone-aware UTC for comparison
    if isinstance(last_login, datetime.datetime):
      if last_login.tzinfo is None:
        last_login = last_login.replace(tzinfo=datetime.timezone.utc)
      else:
        last_login = last_login.astimezone(datetime.timezone.utc)
    else:
      continue  # Skip invalid dates

    client_days_used = str(_to_int(data.get("client_num_days_used", 0)))
    client_viewed_bucket = _bucket_jokes_viewed(
      _to_int(data.get("client_num_viewed", 0)))

    # 7-day stats (already filtered by query, but double check date)
    if last_login >= cutoff_7d:
      num_7d_users_by_jokes_viewed[client_viewed_bucket] = (
        num_7d_users_by_jokes_viewed.get(client_viewed_bucket, 0) + 1)

      # Matrix: Days Used -> Jokes Viewed
      if client_days_used not in num_7d_users_by_days_used_by_jokes_viewed:
        num_7d_users_by_days_used_by_jokes_viewed[client_days_used] = {}

      days_map = num_7d_users_by_days_used_by_jokes_viewed[client_days_used]
      days_map[client_viewed_bucket] = days_map.get(client_viewed_bucket, 0) + 1

    # 1-day stats
    if last_login >= cutoff_1d:
      num_1d_users_by_days_used[
        client_days_used] = num_1d_users_by_days_used.get(client_days_used,
                                                          0) + 1
      num_1d_users_by_jokes_viewed[client_viewed_bucket] = (
        num_1d_users_by_jokes_viewed.get(client_viewed_bucket, 0) + 1)

  # Prepare data
  stats_data = {
    "stats_date":
    yesterday_start,
    "created_at":
    now_la,
    "num_1d_users_by_days_used":
    num_1d_users_by_days_used,
    "num_1d_users_by_jokes_viewed":
    num_1d_users_by_jokes_viewed,
    "num_7d_users_by_jokes_viewed":
    num_7d_users_by_jokes_viewed,
    "num_7d_users_by_days_used_by_jokes_viewed":
    num_7d_users_by_days_used_by_jokes_viewed,
  }

  # Upsert into Firestore
  firestore_service.db().collection("joke_stats").document(doc_id).set(
    stats_data, merge=True)

  logger.info(f"Stats calculated for {doc_id}: {stats_data}")
