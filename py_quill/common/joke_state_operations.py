"""Operations for reading and updating daily joke calendar state."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, cast
from zoneinfo import ZoneInfo

from common import models, utils
from firebase_functions import logger
from google.cloud.firestore_v1.field_path import FieldPath
from services import firestore

_BATCHES_COLLECTION = "joke_schedule_batches"
_DAILY_SCHEDULE_ID = "daily_jokes"
_EARLIEST_TIMEZONE = datetime.timezone(datetime.timedelta(hours=14))
_LA_TIMEZONE = ZoneInfo("America/Los_Angeles")
_MONTH_TILE_IMAGE_WIDTH = 50


@dataclass(frozen=True)
class CalendarDayJoke:
  """A single scheduled joke entry for a calendar day."""

  joke_id: str
  setup_text: str
  thumbnail_url: str | None

  def to_dict(self) -> dict[str, object]:
    """Serialize the day entry for JSON responses."""
    return {
      "joke_id": self.joke_id,
      "setup_text": self.setup_text,
      "thumbnail_url": self.thumbnail_url,
    }


@dataclass(frozen=True)
class CalendarMonth:
  """Calendar data for a single month."""

  year: int
  month: int
  entries: dict[str, CalendarDayJoke]
  movable_day_keys: set[str]

  @property
  def month_id(self) -> str:
    """Return the canonical `YYYY-MM` identifier for this month."""
    return _format_month_id(self.year, self.month)

  def to_dict(self) -> dict[str, object]:
    """Serialize the month payload for JSON responses."""
    return {
      "month_id": self.month_id,
      "year": self.year,
      "month": self.month,
      "days_in_month": _days_in_month(self.year, self.month),
      "first_weekday": _first_weekday(self.year, self.month),
      "entries": {
        day: joke.to_dict()
        for day, joke in self.entries.items()
      },
      "movable_day_keys": sorted(self.movable_day_keys),
    }


@dataclass(frozen=True)
class CalendarWindow:
  """Response payload for a calendar month fetch."""

  months: list[CalendarMonth]
  earliest_month_id: str
  latest_month_id: str
  initial_month_id: str
  today_iso_date: str

  def to_dict(self) -> dict[str, object]:
    """Serialize the calendar window payload for JSON responses."""
    return {
      "months": [month.to_dict() for month in self.months],
      "earliest_month_id": self.earliest_month_id,
      "latest_month_id": self.latest_month_id,
      "initial_month_id": self.initial_month_id,
      "today_iso_date": self.today_iso_date,
    }


@dataclass(frozen=True)
class CalendarMoveResult:
  """Result of moving a scheduled joke to a new day."""

  joke_id: str
  source_date: datetime.date
  target_date: datetime.date

  def to_dict(self) -> dict[str, object]:
    """Serialize the move result for JSON responses."""
    return {
      "joke_id": self.joke_id,
      "source_date": self.source_date.isoformat(),
      "target_date": self.target_date.isoformat(),
    }


def get_daily_calendar_window(
  *,
  start_month: datetime.date,
  end_month: datetime.date,
  now_utc: datetime.datetime | None = None,
) -> CalendarWindow:
  """Load daily joke calendar data for an inclusive month range."""
  if start_month.day != 1 or end_month.day != 1:
    raise ValueError("Calendar requests must use first-of-month dates")

  if start_month > end_month:
    raise ValueError("start_month must be on or before end_month")

  month_bounds = _get_daily_calendar_bounds(now_utc=now_utc)
  today = _earliest_timezone_today(now_utc=now_utc)
  clamped_start = max(start_month, month_bounds[0])
  clamped_end = min(end_month, month_bounds[1])

  months: list[CalendarMonth] = []
  if clamped_start <= clamped_end:
    month_span = ((clamped_end.year - clamped_start.year) *
                  12) + (clamped_end.month - clamped_start.month) + 1
    months = [
      _build_calendar_month(_shift_month(clamped_start, offset),
                            now_utc=now_utc) for offset in range(month_span)
    ]

  initial_month = _initial_month(month_bounds[0],
                                 month_bounds[1],
                                 now_utc=now_utc)
  return CalendarWindow(
    months=months,
    earliest_month_id=_format_month_id(month_bounds[0].year,
                                       month_bounds[0].month),
    latest_month_id=_format_month_id(month_bounds[1].year,
                                     month_bounds[1].month),
    initial_month_id=_format_month_id(initial_month.year, initial_month.month),
    today_iso_date=today.isoformat(),
  )


def move_daily_joke(
  *,
  joke_id: str,
  source_date: datetime.date,
  target_date: datetime.date,
  now_utc: datetime.datetime | None = None,
) -> CalendarMoveResult:
  """Move a future daily joke to a different empty day."""
  if not joke_id.strip():
    raise ValueError("joke_id is required")
  if source_date == target_date:
    raise ValueError("source_date and target_date must differ")

  earliest_today = _earliest_timezone_today(now_utc=now_utc)
  if source_date <= earliest_today:
    raise ValueError("Past and current daily jokes cannot be moved")
  if target_date <= earliest_today:
    raise ValueError("Target date must be in the future")

  client = firestore.db()
  joke_ref = client.collection("jokes").document(joke_id)
  joke_snapshot = joke_ref.get()
  if not joke_snapshot.exists:
    raise ValueError(f"Joke not found: {joke_id}")

  joke = models.PunnyJoke.from_firestore_dict(joke_snapshot.to_dict() or {},
                                              key=joke_id)
  if joke.state not in (models.JokeState.DAILY, models.JokeState.PUBLISHED):
    raise ValueError(
      f'Joke "{joke_id}" must be in PUBLISHED or DAILY state to schedule')

  scheduled_batches = _load_daily_schedule_batches()
  batches_to_write: dict[str, dict[str, dict[str, object]]] = {}
  source_found = False

  for batch_id, batch in scheduled_batches.items():
    parsed = _parse_batch_id(batch_id)
    if parsed is None:
      continue
    year, month = parsed
    next_jokes = dict(batch)
    removed_any = False
    for day_key, day_data in list(batch.items()):
      if str(day_data.get("joke_id") or "").strip() != joke_id:
        continue
      scheduled_date = datetime.date(year, month, int(day_key))
      if scheduled_date <= earliest_today:
        raise ValueError("Past and current daily jokes cannot be moved")
      if scheduled_date == source_date:
        source_found = True
      del next_jokes[day_key]
      removed_any = True
    if removed_any:
      batches_to_write[batch_id] = next_jokes

  if not source_found:
    raise ValueError("Source date does not contain the requested joke")

  target_batch_id = _batch_id(target_date.year, target_date.month)
  target_batch = dict(
    batches_to_write.get(target_batch_id)
    or scheduled_batches.get(target_batch_id) or {})
  target_day_key = _day_key(target_date.day)
  existing_target = target_batch.get(target_day_key)
  if existing_target:
    raise ValueError("Target date already has a scheduled joke")

  target_batch[target_day_key] = _serialize_batch_joke(joke)
  batches_to_write[target_batch_id] = target_batch

  write_batch = client.batch()
  for batch_id, jokes in batches_to_write.items():
    write_batch.set(
      client.collection(_BATCHES_COLLECTION).document(batch_id),
      {"jokes": jokes})
  write_batch.update(
    joke_ref,
    {
      "state": models.JokeState.DAILY.value,
      "public_timestamp": _la_midnight(target_date),
      "is_public": False,
    },
  )
  write_batch.commit()  # pyright: ignore[reportUnusedCallResult]

  return CalendarMoveResult(
    joke_id=joke_id,
    source_date=source_date,
    target_date=target_date,
  )


def _build_calendar_month(
  month_start: datetime.date,
  *,
  now_utc: datetime.datetime | None,
) -> CalendarMonth:
  batch = _load_schedule_batch(month_start.year, month_start.month)
  entries: dict[str, CalendarDayJoke] = {}
  for day_key, day_data in batch.items():
    joke_id = str(day_data.get("joke_id") or "").strip()
    if not joke_id:
      continue
    setup_text = str(day_data.get("setup") or "").strip()
    setup_image_url = str(day_data.get("setup_image_url")
                          or "").strip() or None
    entries[day_key] = CalendarDayJoke(
      joke_id=joke_id,
      setup_text=setup_text,
      thumbnail_url=utils.format_image_url(setup_image_url,
                                           width=_MONTH_TILE_IMAGE_WIDTH)
      if setup_image_url else None,
    )

  movable_cutoff = _earliest_timezone_today(now_utc=now_utc)
  movable_day_keys = {
    _day_key(day_number)
    for day_number in range(
      1,
      _days_in_month(month_start.year, month_start.month) + 1)
    if datetime.date(month_start.year, month_start.month, day_number) >
    movable_cutoff
  }
  return CalendarMonth(
    year=month_start.year,
    month=month_start.month,
    entries=entries,
    movable_day_keys=movable_day_keys,
  )


def _get_daily_calendar_bounds(
  *,
  now_utc: datetime.datetime | None,
) -> tuple[datetime.date, datetime.date]:
  today = _earliest_timezone_today(now_utc=now_utc)
  latest_month = _month_start(_shift_month(today.replace(day=1), 12))

  earliest_month = _find_earliest_scheduled_month()
  if earliest_month is None:
    earliest_month = today.replace(day=1)

  earliest_month = min(earliest_month, latest_month)

  return earliest_month, latest_month


def _initial_month(
  earliest_month: datetime.date,
  latest_month: datetime.date,
  *,
  now_utc: datetime.datetime | None,
) -> datetime.date:
  current_month = _earliest_timezone_today(now_utc=now_utc).replace(day=1)
  if current_month < earliest_month:
    return earliest_month
  if current_month > latest_month:
    return latest_month
  return current_month


def _find_earliest_scheduled_month() -> datetime.date | None:
  query = _daily_batches_query()
  for snapshot in query.stream():
    if not snapshot.exists:
      continue
    data_raw: object = snapshot.to_dict() or {}
    if not isinstance(data_raw, dict):
      continue
    data = cast(dict[str, object], data_raw)
    jokes = data.get("jokes")
    if not isinstance(jokes, dict) or not jokes:
      continue
    parsed = _parse_batch_id(snapshot.id)
    if parsed is None:
      logger.warn(f"Skipping malformed schedule batch id: {snapshot.id}")
      continue
    return datetime.date(parsed[0], parsed[1], 1)
  return None


def _load_schedule_batch(year: int,
                         month: int) -> dict[str, dict[str, object]]:
  snapshot = _batch_ref(firestore.db(), datetime.date(year, month, 1)).get()
  return _schedule_batch_data(snapshot)


def _load_daily_schedule_batches() -> dict[str, dict[str, dict[str, object]]]:
  batches: dict[str, dict[str, dict[str, object]]] = {}
  for snapshot in _daily_batches_query().stream():
    batches[snapshot.id] = _schedule_batch_data(snapshot)
  return batches


def _daily_batches_query() -> Any:
  return (firestore.db().collection(_BATCHES_COLLECTION).order_by(
    FieldPath.document_id()).start_at([f"{_DAILY_SCHEDULE_ID}_"]).end_at(
      [f"{_DAILY_SCHEDULE_ID}_\uf8ff"]))


def _schedule_batch_data(snapshot: Any) -> dict[str, dict[str, object]]:
  if not getattr(snapshot, "exists", False):
    return {}
  data_raw: object = snapshot.to_dict() or {}
  if not isinstance(data_raw, dict):
    return {}
  data = cast(dict[str, object], data_raw)
  jokes_raw = data.get("jokes")
  if not isinstance(jokes_raw, dict):
    return {}
  jokes = cast(dict[object, object], jokes_raw)
  parsed: dict[str, dict[str, object]] = {}
  for day, value in jokes.items():
    if not isinstance(value, dict):
      continue
    parsed[str(day)] = cast(dict[str, object], value)
  return parsed


def _serialize_batch_joke(joke: models.PunnyJoke) -> dict[str, object]:
  return {
    "joke_id": joke.key or "",
    "setup": joke.setup_text or "",
    "punchline": joke.punchline_text or "",
    "setup_image_url": joke.setup_image_url,
    "punchline_image_url": joke.punchline_image_url,
  }


def _batch_ref(client: Any, target_date: datetime.date) -> Any:
  return client.collection(_BATCHES_COLLECTION).document(
    _batch_id(target_date.year, target_date.month))


def _batch_id(year: int, month: int) -> str:
  return f"{_DAILY_SCHEDULE_ID}_{year}_{month:02d}"


def _parse_batch_id(batch_id: str) -> tuple[int, int] | None:
  prefix = f"{_DAILY_SCHEDULE_ID}_"
  if not batch_id.startswith(prefix):
    return None
  suffix = batch_id.removeprefix(prefix)
  parts = suffix.split("_")
  if len(parts) != 2:
    return None
  try:
    return int(parts[0]), int(parts[1])
  except ValueError:
    return None


def _shift_month(month_start: datetime.date, delta: int) -> datetime.date:
  total_months = (month_start.year * 12) + (month_start.month - 1) + delta
  year = total_months // 12
  month = (total_months % 12) + 1
  return datetime.date(year, month, 1)


def _month_start(value: datetime.date) -> datetime.date:
  return datetime.date(value.year, value.month, 1)


def _earliest_timezone_today(
  *,
  now_utc: datetime.datetime | None,
) -> datetime.date:
  if now_utc is None:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
  if now_utc.tzinfo is None:
    now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
  return now_utc.astimezone(_EARLIEST_TIMEZONE).date()


def _la_midnight(target_date: datetime.date) -> datetime.datetime:
  # Match the Flutter scheduler behavior: store the target day at LA midnight.
  return datetime.datetime(target_date.year,
                           target_date.month,
                           target_date.day,
                           tzinfo=_LA_TIMEZONE)


def _format_month_id(year: int, month: int) -> str:
  return f"{year:04d}-{month:02d}"


def _days_in_month(year: int, month: int) -> int:
  if month == 12:
    next_month = datetime.date(year + 1, 1, 1)
  else:
    next_month = datetime.date(year, month + 1, 1)
  return (next_month - datetime.timedelta(days=1)).day


def _first_weekday(year: int, month: int) -> int:
  # Match the Flutter calendar: Sunday=0.
  return (datetime.date(year, month, 1).weekday() + 1) % 7


def _day_key(day: int) -> str:
  return f"{day:02d}"
